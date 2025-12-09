"""
Generate investment reasoning for stocks using RAG system.

This script:
1. Downloads Siri's stock CSV from GCS
2. Uses RAG system (from rag_majid/rag_llm.ipynb) to generate investment reasoning
3. Adds reasoning as a new column
4. Uploads enhanced CSV back to GCS in model_output/ directory
"""

import os
import sys
import argparse
from pathlib import Path
from io import BytesIO
import time
import json
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account
from tqdm import tqdm

# LangChain imports
from langchain_google_vertexai import ChatVertexAI
from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.embeddings import Embeddings

# Import from same directory (rag_helpers.py will be in src/rag/)
from rag_helpers import get_rag_connection, get_chroma_db, get_embedder

# Load environment variables
load_dotenv(override=True)

# Configuration
GCS_BUCKET_NAME = "fin-data-bucket-115"
# ChromaDB bucket - use default, override with environment variable if needed
# Note: The bucket containing ChromaDB embeddings from the .md file
# Default to stock-busters-chroma-bucket unless explicitly set
GCS_CHROMADB_BUCKET = os.getenv("GCS_BUCKET_NAME", "stock-busters-chroma-bucket")
INPUT_CSV = "model_output/combined_quantamental_hybrid_with_factors_and_backtest.csv"  # Located in model_output/ folder
OUTPUT_CSV = "model_output/combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"

# Credentials path - try multiple possible locations
# Will be resolved in setup_credentials() function
CREDENTIALS_PATH = None
GCS_CREDENTIALS_PATH = None


def setup_credentials():
    """Set up GCP credentials for Vertex AI and GCS."""
    # Try multiple possible paths for credentials file
    possible_paths = [
        "secrets/stock-busters-service-account.json",
        "../secrets/stock-busters-service-account.json",
        Path(__file__).parent.parent.parent / "secrets" / "stock-busters-service-account.json",
        Path(__file__).parent.parent / "secrets" / "stock-busters-service-account.json",
    ]

    # Also check if GOOGLE_APPLICATION_CREDENTIALS is already set
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        existing_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if os.path.exists(existing_creds):
            creds_file = existing_creds
        else:
            creds_file = None
    else:
        creds_file = None

    # Try to find credentials file
    if not creds_file:
        for path in possible_paths:
            path_obj = Path(path) if isinstance(path, str) else path
            if path_obj.exists():
                creds_file = str(path_obj.resolve())
                break

    if not creds_file or not os.path.exists(creds_file):
        raise FileNotFoundError(
            f"Credentials file not found. Tried: {possible_paths}. "
            f"Also checked GOOGLE_APPLICATION_CREDENTIALS env var."
        )

    # Set as Application Default Credentials for both GCS and Vertex AI
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file

    # Load credentials for explicit use if needed
    # Use the service account file for both GCS and Vertex AI
    credentials = service_account.Credentials.from_service_account_file(creds_file)

    return credentials


def list_gcs_files(bucket_name: str, prefix: str = "") -> list:
    """List files in GCS bucket with optional prefix."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        return [blob.name for blob in blobs]
    except Exception as e:
        print(f"Error listing files in GCS: {e}")
        return []


def download_csv_from_gcs(file_name: str, bucket_name: str = GCS_BUCKET_NAME) -> pd.DataFrame:
    """Download CSV file from GCS bucket."""
    print(f"Downloading {file_name} from GCS bucket {bucket_name}...")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        # Check if file exists, if not search for it
        if not blob.exists():
            print(f"File not found at specified path. Searching for '{file_name.split('/')[-1]}' in bucket...")
            filename_only = file_name.split("/")[-1]
            all_files = list_gcs_files(bucket_name)
            matching_files = [f for f in all_files if filename_only in f]
            if matching_files:
                print(f"Found matching files: {matching_files}")
                # Prefer model_output folder if available
                model_output_files = [f for f in matching_files if "model_output/" in f]
                if model_output_files:
                    file_name = model_output_files[0]
                    print(f"✓ Found in model_output folder: {file_name}")
                else:
                    # List available folders
                    folders = set()
                    for f in all_files[:200]:
                        if "/" in f:
                            folder = f.split("/")[0]
                            folders.add(folder)
                    print(f"⚠ File not found in model_output folder. Available folders: {sorted(folders)}")
                    print(f"⚠ Using first match instead: {matching_files[0]}")
                    file_name = matching_files[0]
                blob = bucket.blob(file_name)
                print(f"Using: {file_name}")
            else:
                print(f"Available files in bucket (first 30):")
                for f in all_files[:30]:
                    print(f"  - {f}")
                raise FileNotFoundError(f"File {filename_only} not found in bucket {bucket_name}")

        csv_bytes = blob.download_as_bytes()
        df = pd.read_csv(BytesIO(csv_bytes))

        print(f"Successfully loaded {file_name}")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")

        return df
    except Exception as e:
        print(f"Error downloading CSV from GCS: {e}")
        raise


def upload_csv_to_gcs(df: pd.DataFrame, gcs_path: str, bucket_name: str = GCS_BUCKET_NAME):
    """Upload DataFrame as CSV to GCS bucket."""
    print(f"Uploading CSV to GCS: {gcs_path}...")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)

        # Convert DataFrame to CSV bytes
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        # Upload to GCS
        blob.upload_from_file(csv_buffer, content_type="text/csv")

        print(f"Successfully uploaded to gs://{bucket_name}/{gcs_path}")
    except Exception as e:
        print(f"Error uploading CSV to GCS: {e}")
        raise


def setup_rag_system(credentials):
    """Set up RAG system with existing ChromaDB from GCS."""
    print("Setting up RAG system...")

    # Set GCS_BUCKET_NAME for rag_helpers (override any existing env var)
    # Force use of stock-busters-chroma-bucket for ChromaDB
    os.environ["GCS_BUCKET_NAME"] = "stock-busters-chroma-bucket"
    print(f"Using ChromaDB bucket: stock-busters-chroma-bucket")

    # Connect to existing ChromaDB in GCS using rag_helpers
    print(f"Connecting to ChromaDB in GCS bucket: {GCS_CHROMADB_BUCKET}")
    get_rag_connection()

    # Get the ChromaDB client and collection from rag_helpers cache
    from rag_helpers import _cache, VECTOR_COLLECTION
    import tempfile

    key = "default"
    if key not in _cache:
        raise RuntimeError("Failed to get ChromaDB connection from rag_helpers")

    chroma_client, collection_name = _cache[key]
    # Use VECTOR_COLLECTION if collection_name is not set
    if not collection_name:
        collection_name = VECTOR_COLLECTION
    print(f"Connected to ChromaDB collection: {collection_name}")

    # Initialize embeddings - must match the model used to create ChromaDB
    # The ChromaDB collection was created with BAAI/bge-small-en-v1.5 (384 dimensions)
    # NOT text-embedding-004 (768 dimensions)
    print("Initializing FastEmbed embeddings (BAAI/bge-small-en-v1.5)...")

    # Create a LangChain-compatible embedding wrapper for FastEmbed
    class FastEmbedWrapper(Embeddings):
        """Wrapper to make FastEmbed compatible with LangChain's Embeddings interface."""

        def __init__(self, embedder):
            self.embedder = embedder

        def embed_documents(self, texts):
            """Embed a list of documents."""
            embeddings = []
            for text in texts:
                # FastEmbed's embed method returns an iterator
                emb = next(self.embedder.embed(text))
                # Convert to list if numpy array
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()
                embeddings.append(emb)
            return embeddings

        def embed_query(self, text):
            """Embed a single query."""
            # FastEmbed's query_embed method returns an iterator
            emb = next(self.embedder.query_embed(text))
            # Convert to list if numpy array
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return emb

    # Get the FastEmbed embedder (uses BAAI/bge-small-en-v1.5 by default)
    fastembed_embedder = get_embedder()
    embeddings = FastEmbedWrapper(fastembed_embedder)
    print("✓ FastEmbed embeddings initialized (384 dimensions)")

    # Retrieve the full .md document that was embedded as a single document
    # The original rag.py stores it with "#full_document" marker in the source
    # We use direct retrieval (no semantic search) - optimized with ID caching
    print("Retrieving full .md document from ChromaDB (direct retrieval, no semantic search)...")
    collection = chroma_client.get_collection(name=collection_name)

    # Cache file to store the document content for fastest retrieval (no ChromaDB lookup needed)
    cache_file = Path(__file__).parent / ".chromadb_full_doc_cache.json"
    full_doc_id = None
    full_doc_text = None
    full_doc_metadata = None
    used_cache = False  # Track if we used cache or searched

    # Try to load cached document content first (fastest path - no ChromaDB lookup)
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
                cached_collection = cache_data.get("collection_name")
                cached_content = cache_data.get("full_doc_text")
                cached_metadata = cache_data.get("full_doc_metadata")
                cached_id = cache_data.get("full_doc_id")

                # Only use cache if it's for the same collection and has content
                if cached_content and cached_collection == collection_name:
                    full_doc_id = cached_id
                    full_doc_text = cached_content
                    full_doc_metadata = cached_metadata or {}
                    used_cache = True
                    print(f"✓ Retrieved from cache (no ChromaDB lookup needed)")
                    source = full_doc_metadata.get("source", "") if isinstance(full_doc_metadata, dict) else ""
                    print(f"  Source: {source[:100]}...")
                else:
                    print(f"  Cache mismatch or incomplete, will retrieve from ChromaDB...")
        except Exception as e:
            # Cache file corrupted, will search below
            print(f"  Cache file error, will retrieve from ChromaDB...")

    # If cache didn't work, retrieve from ChromaDB
    if not full_doc_text:
        print("Retrieving from ChromaDB (first run or cache miss)...")

        # Try to construct ID directly from known pattern first (fastest if pattern is consistent)
        # Pattern from rag.py: {path}#full_document::chunk_0
        # Common paths: /workspace/data/LLM-Quant_Expanded_RAG_with_context.md#full_document::chunk_0
        possible_ids = [
            "/workspace/data/LLM-Quant_Expanded_RAG_with_context.md#full_document::chunk_0",
            "LLM-Quant_Expanded_RAG_with_context.md#full_document::chunk_0",
        ]

        # Try direct ID lookup first (fastest if ID pattern is known)
        for possible_id in possible_ids:
            try:
                direct_results = collection.get(ids=[possible_id], include=["documents", "metadatas"])
                if direct_results.get("ids") and len(direct_results["ids"]) > 0:
                    full_doc_id = possible_id
                    full_doc_text = direct_results["documents"][0] if direct_results.get("documents") else None
                    full_doc_metadata = direct_results["metadatas"][0] if direct_results.get("metadatas") else {}
                    if full_doc_text:
                        print(f"  ✓ Found by direct ID lookup")
                        break
            except Exception:
                continue

        # If direct ID didn't work, try sample search
        if not full_doc_text:
            try:
                # Get a small sample first to find the pattern
                sample_results = collection.get(limit=100, include=["metadatas", "ids"])
                if sample_results.get("metadatas") and sample_results.get("ids"):
                    for idx, metadata in enumerate(sample_results["metadatas"]):
                        if metadata and "source" in metadata:
                            source = metadata["source"]
                            if "#full_document" in source:
                                found_id = sample_results["ids"][idx]
                                # Now retrieve by ID
                                full_doc_results = collection.get(ids=[found_id], include=["documents", "metadatas"])
                                if full_doc_results.get("ids") and len(full_doc_results["ids"]) > 0:
                                    full_doc_id = found_id
                                    full_doc_text = (
                                        full_doc_results["documents"][0] if full_doc_results.get("documents") else None
                                    )
                                    full_doc_metadata = (
                                        full_doc_results["metadatas"][0] if full_doc_results.get("metadatas") else {}
                                    )
                                    print(f"  ✓ Found in sample search")
                                    break
            except Exception:
                pass

        # Fallback: search through all documents if sample didn't find it
        if not full_doc_text:
            print("  Searching through all documents...")
            all_results = collection.get(limit=10000, include=["documents", "metadatas"])

            if all_results.get("metadatas") and all_results.get("ids") and all_results.get("documents"):
                for idx, metadata in enumerate(all_results["metadatas"]):
                    if metadata and "source" in metadata:
                        source = metadata["source"]
                        if "#full_document" in source:
                            full_doc_id = all_results["ids"][idx]
                            full_doc_text = all_results["documents"][idx]
                            full_doc_metadata = metadata
                            print(f"  ✓ Found in full search")
                            break

    if not full_doc_text:
        raise RuntimeError(
            "Could not find full .md document in ChromaDB. "
            "Expected document with '#full_document' marker in source metadata."
        )

    # Save document content to cache for next time (only if we retrieved from ChromaDB)
    # This allows us to skip ChromaDB lookup entirely on subsequent runs
    if full_doc_id and full_doc_text and not used_cache:
        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "full_doc_id": full_doc_id,
                        "full_doc_text": full_doc_text,
                        "full_doc_metadata": full_doc_metadata or {},
                        "collection_name": collection_name,
                    },
                    f,
                )
            print(f"  ✓ Cached document content (will skip ChromaDB lookup next time)")
        except Exception:
            pass  # Cache write failure is not critical

    source = full_doc_metadata.get("source", "") if isinstance(full_doc_metadata, dict) else ""
    print(f"✓ Using full .md document from ChromaDB ({len(full_doc_text):,} characters)")
    print(f"  Source: {source[:100]}...")

    # Create a retriever that returns the single full document
    from langchain_core.documents import Document

    full_doc = Document(
        page_content=full_doc_text,
        metadata=full_doc_metadata or {"source": "LLM-Quant_Expanded_RAG_with_context.md (full document)"},
    )

    class FullDocChromaRetriever(BaseRetriever):
        """Retriever that returns the full .md document from ChromaDB (single embedding)."""

        document: Document

        def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None):
            # Return the full document regardless of query
            return [self.document]

        def invoke(self, input: str, config=None, **kwargs):
            return self._get_relevant_documents(input)

    retriever = FullDocChromaRetriever(document=full_doc)
    print(f"✓ RAG retriever created - using single full .md document from ChromaDB ({len(full_doc_text):,} characters)")

    # Initialize LLM first (needed before creating optimized chain)
    print("Initializing LLM (Gemini 2.5 Flash)...")
    try:
        # First try without explicit credentials (use ADC)
        llm = ChatVertexAI(
            model="gemini-2.5-flash",
            project="stock-busters-cs115",
        )
    except Exception as e:
        print(f"Warning: ADC failed, trying with explicit credentials: {e}")
        # Fallback to explicit credentials
        llm = ChatVertexAI(
            model="gemini-2.5-flash",
            credentials=credentials,
            project="stock-busters-cs115",
        )

    # Optimize: Use system message for static context (more efficient than sending in each prompt)
    # This allows the LLM to better cache/optimize the context across multiple calls
    from langchain_core.messages import SystemMessage

    # Create a custom chain that uses system message for context
    class OptimizedRAGChain:
        """Optimized RAG chain that uses system message for static context."""

        def __init__(self, llm, context_text: str):
            self.llm = llm
            self.context_text = context_text  # The .md file content (static)
            # Pre-format the system message with context (set once, reused for all stocks)
            self.system_message = SystemMessage(
                content=f"""You are a stock analyst. Use this knowledge base to analyze stocks:
{context_text}

Guidelines: Explain why stocks are good investments. Use context metrics. Be concise, no numbers.
Example: Attractive P/E ratio. Strong RSI momentum."""
            )

        def invoke(self, query: str):
            """Invoke with optimized prompt structure."""
            from langchain_core.messages import HumanMessage

            # User message only contains the stock-specific query (much smaller, ~100-200 chars)
            # System message contains the static context (12k chars, but may be cached/optimized by LLM)
            user_message = HumanMessage(content=f"Analyze: {query}")
            messages = [self.system_message, user_message]
            response = self.llm.invoke(messages)
            return response.content if hasattr(response, "content") else str(response)

    # Use optimized chain instead of standard RAG chain
    # This puts the .md context in system message (more efficient) and stock data in user message (smaller)
    optimized_chain = OptimizedRAGChain(llm, full_doc_text)
    print(f"✓ Optimized RAG chain created (context in system message, ~{len(full_doc_text):,} chars)")
    print(f"  Each stock query will only send ~100-200 chars (vs ~12k+ chars with old method)")

    # Create a wrapper to maintain the same interface
    class ChainWrapper:
        def __init__(self, optimized_chain):
            self.optimized_chain = optimized_chain

        def invoke(self, query: str):
            return self.optimized_chain.invoke(query)

    chain = ChainWrapper(optimized_chain)
    print("RAG chain created successfully")
    return chain


def generate_reasoning_for_stock(chain, stock_data: Dict[str, Any]) -> str:
    """Generate investment reasoning for a single stock using RAG chain."""
    try:
        # Extract key metrics for a more focused query (faster processing)
        symbol = stock_data.get("symbol", "N/A")
        key_metrics = {
            "symbol": symbol,
            "signal": stock_data.get("signal", ""),
            "Hybrid_Score": stock_data.get("Hybrid_Score", ""),
            "Fundamental_Score": stock_data.get("Fundamental_Score", ""),
            "Technical_Score": stock_data.get("Technical_Score", ""),
            "roe": stock_data.get("roe", ""),
            "roic": stock_data.get("roic", ""),
            "peRatio": stock_data.get("peRatio", ""),
            "RSI_14": stock_data.get("RSI_14", ""),
            "sector": stock_data.get("sector", ""),
            "industry": stock_data.get("industry", ""),
        }
        # Ultra-concise query - only essential info (faster processing, less tokens)
        # Format as compact string to minimize token usage
        metrics_str = f"{symbol}|Signal:{key_metrics.get('signal','')}|H:{key_metrics.get('Hybrid_Score','')}|F:{key_metrics.get('Fundamental_Score','')}|T:{key_metrics.get('Technical_Score','')}|ROE:{key_metrics.get('roe','')}|ROIC:{key_metrics.get('roic','')}|PE:{key_metrics.get('peRatio','')}|RSI:{key_metrics.get('RSI_14','')}|{key_metrics.get('sector','')}/{key_metrics.get('industry','')}"
        query = metrics_str
        reasoning = chain.invoke(query)
        return reasoning
    except Exception as e:
        print(f"Error generating reasoning: {e}")
        return f"Error: {str(e)}"


def process_single_stock(args_tuple):
    """Process a single stock - designed for parallel execution."""
    idx, row, chain = args_tuple
    try:
        stock_data = row.to_dict()
        symbol = row.get("symbol", "N/A")

        stock_start = time.time()
        reasoning = generate_reasoning_for_stock(chain, stock_data)
        stock_time = time.time() - stock_start

        return (idx, reasoning, stock_time, symbol, None)
    except Exception as e:
        return (idx, f"Error: {str(e)}", 0, row.get("symbol", "N/A"), str(e))


def process_csv_with_rag(
    df: pd.DataFrame, chain, sample_size: Optional[int] = None, max_workers: int = 10, main_pbar=None
):
    """Process CSV rows and generate reasoning for each stock using parallel processing."""
    if sample_size:
        df = df.head(sample_size).copy()  # Use .copy() to avoid SettingWithCopyWarning
    else:
        df = df.copy()  # Use .copy() to avoid SettingWithCopyWarning

    # Add reasoning column
    df["rag_reasoning"] = ""

    total_rows = len(df)
    start_time = time.time()

    # Prepare tasks for parallel processing
    tasks = [(idx, row, chain) for idx, row in df.iterrows()]

    results = {}
    errors = []

    # Calculate progress per stock: 90% of total for processing stocks
    if main_pbar:
        stocks_progress_per_item = 90.0 / total_rows

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_idx = {executor.submit(process_single_stock, task): task[0] for task in tasks}

        # Process completed tasks as they finish
        for future in as_completed(future_to_idx):
            idx, reasoning, stock_time, symbol, error = future.result()
            results[idx] = (reasoning, stock_time, symbol, error)

            if error:
                errors.append((symbol, error))
            else:
                # Update main progress bar if provided
                if main_pbar:
                    main_pbar.update(stocks_progress_per_item)
                    main_pbar.set_postfix_str(f"✓ {symbol} ({len(results)}/{total_rows})", refresh=True)

    # Update DataFrame with results
    for idx, (reasoning, stock_time, symbol, error) in results.items():
        df.at[idx, "rag_reasoning"] = reasoning

    total_time = time.time() - start_time

    if errors:
        print(f"\n⚠ Warning: {len(errors)} stocks had errors:")
        for symbol, error in errors[:5]:  # Show first 5 errors
            print(f"   • {symbol}: {error}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more errors")

    return df


def main():
    """Main execution function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate investment reasoning for stocks using RAG")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Number of stocks to process (for testing). If not specified, processes all stocks.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=20,
        help="Number of parallel workers for concurrent processing (default: 20). Higher = faster but may hit rate limits.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Stock Reasoning Generator using RAG")
    print("=" * 60)

    # Setup credentials (quick, no progress needed)
    print("\nSetting up credentials...")
    credentials = setup_credentials()
    print("✓ Credentials loaded")

    # Download CSV from GCS (quick, no progress needed)
    print("Downloading CSV from GCS...")
    df = download_csv_from_gcs(INPUT_CSV, GCS_BUCKET_NAME)
    print("✓ CSV downloaded")

    # Setup RAG system (quick, no progress needed)
    print("Setting up RAG system...")
    chain = setup_rag_system(credentials)
    print("✓ RAG system ready")

    # Determine number of stocks to process
    if args.sample_size:
        total_stocks = min(args.sample_size, len(df))
        print(f"\n⚠ Processing sample of {total_stocks} stocks for testing")
    else:
        total_stocks = len(df)
        print(f"\n⚠ Processing all {total_stocks} stocks. This may take 5-10 minutes.")

    # Define workflow steps for progress tracking
    total_steps = 3
    workflow_steps = ["Processing Stocks", "Saving Results", "Uploading to GCS"]

    # Create main progress bar (0-100%)
    # Allocate: 90% for processing stocks, 5% for saving, 5% for uploading
    main_pbar = tqdm(
        total=100,
        desc="Overall Progress",
        unit="%",
        bar_format="{l_bar}{bar}| {n}% [{elapsed}<{remaining}] {desc}",
        position=0,
        leave=True,
    )

    # Step 1: Process Stocks
    main_pbar.set_description(f"[1/{total_steps}] {workflow_steps[0]}")
    print(f"Using parallel processing with {args.max_workers} concurrent workers...")

    df_enhanced = process_csv_with_rag(
        df, chain, sample_size=args.sample_size, max_workers=args.max_workers, main_pbar=main_pbar
    )

    # Step 2: Save Results
    main_pbar.set_description(f"[2/{total_steps}] {workflow_steps[1]}")
    main_pbar.set_postfix_str("", refresh=True)
    local_output = "combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"
    df_enhanced.to_csv(local_output, index=False)
    main_pbar.update(5)  # 5% for saving

    # Step 3: Upload to GCS
    main_pbar.set_description(f"[3/{total_steps}] {workflow_steps[2]}")
    main_pbar.set_postfix_str("", refresh=True)
    upload_csv_to_gcs(df_enhanced, OUTPUT_CSV, GCS_BUCKET_NAME)
    main_pbar.update(5)  # 5% for uploading

    # Complete
    main_pbar.set_description("✓ Complete!")
    main_pbar.set_postfix_str("", refresh=True)
    main_pbar.close()

    print("\n" + "=" * 60)
    print("SUCCESS! Enhanced CSV uploaded to GCS")
    print(f"Location: gs://{GCS_BUCKET_NAME}/{OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
