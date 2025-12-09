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
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account
from tqdm import tqdm
import tempfile
import re
from types import SimpleNamespace

# LangChain imports
from langchain_google_vertexai import ChatVertexAI
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.embeddings import Embeddings

# ChromaDB and FastEmbed imports
import chromadb
from chromadb.config import Settings

# Try to import FastEmbed, fallback if not available
try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

# Load environment variables
load_dotenv(override=True)

# ============================================================================
# RAG Helpers - ChromaDB Connection Functions
# ============================================================================

# Cache for storing ChromaDB clients and default collections
# Key: collection_name or "default", Value: (chroma_client, default_collection)
_cache = {}

# Default values from environment
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "stocks_rag_v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
_embedder_cache = None


def normalize_query(query: str) -> str:
    """
    Normalize query text for embedding.

    Cleans and normalizes the query text by:
    - Stripping whitespace
    - Lowercasing
    - Removing extra spaces

    Args:
        query: Raw query string

    Returns:
        Normalized query string, or empty string if invalid
    """
    if not isinstance(query, str):
        return ""
    return re.sub(r"\s+", " ", query.strip().lower())


def get_embedder():
    """
    Get FastEmbed embedder instance (cached).

    Returns:
        TextEmbedding instance for creating embeddings
    """
    global _embedder_cache

    if _embedder_cache is None:
        if TextEmbedding is None:
            raise ImportError(
                "fastembed is required. Install with: pip install fastembed"
            )
        _embedder_cache = TextEmbedding(model_name=EMBEDDING_MODEL)

    return _embedder_cache


def get_rag_connection(collection_name: Optional[str] = None):
    """
    RAG Connectivity function in GCP Storage - sets up connection.

    This function establishes RAG connectivity by downloading ChromaDB files from
    Google Cloud Storage and initializing a local ChromaDB client. It handles all
    the setup automatically, similar to the get_gcs_csv pattern.

    The function:
    1. Downloads all ChromaDB files from GCS bucket (prefix: "chromadb")
    2. Stores them in a local temporary directory
    3. Creates a ChromaDB PersistentClient connection
    4. Caches the connection for reuse

    Args:
        collection_name: Optional collection name to use as default.
                        If not provided, uses VECTOR_COLLECTION from environment.

    Raises:
        ValueError: If GCS_BUCKET_NAME environment variable is not set.
        RuntimeError: If GCS download fails or credentials are missing.

    Note:
        - This function is automatically called by get_chroma_db() if not already set up
        - Connection is cached, so calling multiple times is safe and efficient
        - Requires GOOGLE_APPLICATION_CREDENTIALS to be set for GCS access
    """
    # Use collection name as cache key, or "default" if not specified
    key = collection_name or "default"

    # If already set up, return early (no need to re-download)
    if key in _cache:
        return

    # Get GCS bucket name from environment variable
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME not set")

    # Create local temporary directory for ChromaDB files
    local_path = os.path.join(tempfile.gettempdir(), "chromadb_rag_helpers")
    os.makedirs(local_path, exist_ok=True)

    # Initialize GCS client and get bucket
    bucket = storage.Client().bucket(bucket_name)

    # List all blobs with "chromadb" prefix (skip directory markers)
    blobs = [
        b for b in bucket.list_blobs(prefix="chromadb") if not b.name.endswith("/")
    ]

    # Download each file from GCS to local directory, preserving structure
    for blob in blobs:
        # Extract relative path (remove "chromadb/" prefix)
        rel_path = blob.name[9:].lstrip("/")
        if rel_path:
            local_file = os.path.join(local_path, rel_path)
            # Create subdirectories as needed
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            # Download file
            blob.download_to_filename(local_file)

    # Print download status if files were found
    if blobs:
        print(f"Downloaded {len(blobs)} files from GCS")

    # Create ChromaDB PersistentClient using downloaded files
    default_collection = collection_name or VECTOR_COLLECTION
    chroma_client = chromadb.PersistentClient(
        path=local_path, settings=Settings(anonymized_telemetry=False)
    )

    # Cache the client and collection for reuse
    _cache[key] = (chroma_client, default_collection)
    print(f"Connected to RAG/ChromaDB (collection: {default_collection})")


def get_chroma_db(collection_name: Optional[str] = None):
    """
    Get ChromaDB connection - returns chroma_db_context.

    This function returns a chroma_db_context object that can be used to query
    ChromaDB collections. It automatically ensures the connection is set up by
    calling get_rag_connection() if needed.

    The returned chroma_db_context has a .query() method that allows you to:
    - Query ChromaDB collections using natural language
    - Get semantic search results with documents, metadata, and similarity scores
    - Specify collection name and number of results

    Args:
        collection_name: Optional collection name to use as default.
                        If not provided, uses VECTOR_COLLECTION from environment.

    Returns:
        SimpleNamespace object (chroma_db_context) with a query() method:
        - chroma_db_context.query(query_string, collection=None, k=4)
          Returns: List[Dict[str, Any]] with keys: id, document, metadata, distance
    """
    # Use collection name as cache key
    key = collection_name or "default"

    # Ensure connection is set up (will call get_rag_connection() if needed)
    if key not in _cache:
        get_rag_connection(collection_name)

    # Get cached ChromaDB client and default collection
    chroma_client, default_collection = _cache[key]

    def query(
        query_string: str, collection: Optional[str] = None, k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Query ChromaDB collection using semantic search.

        Args:
            query_string: The natural language query/question to search for.
            collection: Optional collection name to query.
            k: Number of results to return (default: 4, max: 50).

        Returns:
            List of dictionaries, each containing: id, document, metadata, distance
        """
        # Validate query string
        if not query_string or not query_string.strip():
            return []

        # Determine which collection to query and normalize query
        collection_name = collection or default_collection
        q_normalized = normalize_query(query_string)
        if not q_normalized:
            return []

        # Get or create the collection and create embedding
        coll = chroma_client.get_or_create_collection(name=collection_name)
        q_vec = next(get_embedder().query_embed(q_normalized))

        # Convert embedding to flat list format required by ChromaDB
        if hasattr(q_vec, "tolist"):
            q_vec = q_vec.tolist()
        # Flatten nested lists if needed
        if isinstance(q_vec, list) and q_vec and isinstance(q_vec[0], list):
            q_vec = (
                q_vec[0]
                if len(q_vec) == 1
                else [item for sublist in q_vec for item in sublist]
            )

        # Perform semantic search query
        res = coll.query(
            query_embeddings=[q_vec],
            n_results=max(1, min(int(k), 50)),  # Ensure k is between 1 and 50
            include=["documents", "metadatas", "distances"],
        )

        # Extract results from ChromaDB response format
        def get_first(x):
            return x[0] if x else []

        ids = get_first(res.get("ids", []))
        docs = get_first(res.get("documents", []))
        metas = get_first(res.get("metadatas", []))
        dists = get_first(res.get("distances", []))

        # Format results as list of dictionaries for easy access
        return [
            {
                "id": doc_id,
                "document": text,
                "metadata": md or {},  # Use empty dict if metadata is None
                "distance": (
                    float(dist) if dist is not None else 0.0
                ),  # Convert to float, default to 0.0
            }
            for doc_id, text, md, dist in zip(ids, docs, metas, dists)
        ]

    # Return SimpleNamespace object with query method attached
    return SimpleNamespace(query=query)


def query_rag_texts(
    query_string: str, collection_name: Optional[str] = None, k: int = 4
) -> List[str]:
    """
    Convenience function to connect to RAG for a collection_name, run a query,
    and return only the document texts in similarity order.

    Args:
        query_string: Natural language query to search for (e.g., "What is ROE?").
        collection_name: Optional ChromaDB collection to query. If None, uses default
                         collection from VECTOR_COLLECTION environment variable.
        k: Number of top results to return (1-50, default: 4).

    Returns:
        List[str]: List of retrieved document texts (most similar first). Empty list if none.
    """
    # Ensure connection and get context
    get_rag_connection(collection_name)
    chroma_db = get_chroma_db(collection_name)

    # Perform query and return only document texts
    results = chroma_db.query(query_string, collection=collection_name, k=k)
    return [r.get("document", "") for r in results if r.get("document")]


def store_query_in_chromadb(
    query: str,
    collection_name: Optional[str] = None,
    query_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    upload_to_gcs: bool = False,
) -> Dict[str, Any]:
    """
    Store a query in ChromaDB collection with embedding.

    Args:
        query: Query string to store (e.g., "E/F ratio", "What is ROE?").
        collection_name: Optional collection name. If None, uses default from environment.
        query_id: Optional query ID. If None, auto-generates based on normalized query.
        metadata: Optional metadata dictionary.
        upload_to_gcs: If True, uploads updated ChromaDB files back to GCS after storing.

    Returns:
        Dictionary with: stored, query_id, collection, embedding_model
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    # Ensure connection is set up
    get_rag_connection(collection_name)
    key = collection_name or "default"
    chroma_client, default_collection = _cache[key]

    # Use provided collection or default
    target_collection = collection_name or default_collection
    coll = chroma_client.get_or_create_collection(name=target_collection)

    # Generate query ID if not provided (based on normalized query)
    if query_id is None:
        q_normalized = normalize_query(query)
        query_id = f"query_{q_normalized.replace(' ', '_')[:50]}"

    # Default metadata if not provided (ChromaDB requires non-empty dict)
    if metadata is None or not metadata:
        metadata = {"stored_by": "rag_helpers"}

    # Create embedding for the query
    embedder = get_embedder()
    q_normalized = normalize_query(query)

    try:
        q_vec = next(embedder.query_embed(q_normalized))
        if hasattr(q_vec, "tolist"):
            q_vec = q_vec.tolist()
        elif isinstance(q_vec, list):
            q_vec = q_vec
        else:
            q_vec = list(q_vec)
    except Exception as e:
        raise RuntimeError(f"Failed to create embedding for query: {e}")

    # Store query in ChromaDB (upsert: updates if exists, adds if new)
    try:
        coll.upsert(
            ids=[query_id],
            documents=[query],  # Store the original query text
            metadatas=[metadata],
            embeddings=[q_vec],
        )
    except Exception as e:
        raise RuntimeError(f"Failed to store query in ChromaDB: {e}")

    # Upload to GCS if requested
    if upload_to_gcs:
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        if not bucket_name:
            raise ValueError(
                "GCS_BUCKET_NAME not set (required for upload_to_gcs=True)"
            )

        local_path = os.path.join(tempfile.gettempdir(), "chromadb_rag_helpers")
        bucket = storage.Client().bucket(bucket_name)

        # Upload all files from local ChromaDB directory back to GCS
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file = os.path.join(root, file)
                rel_path = os.path.relpath(local_file, local_path)
                gcs_path = f"chromadb/{rel_path}".replace("\\", "/")

                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_file)

        print(f"Uploaded ChromaDB files to GCS (bucket: {bucket_name})")

    return {
        "stored": 1,
        "query_id": query_id,
        "collection": target_collection,
        "embedding_model": EMBEDDING_MODEL,
    }


# ============================================================================
# Configuration
# ============================================================================

GCS_BUCKET_NAME = "fin-data-bucket-115"
# ChromaDB bucket - use default, override with environment variable if needed
# Note: The bucket containing ChromaDB embeddings from the .md file
# Default to stock-busters-chroma-bucket unless explicitly set
GCS_CHROMADB_BUCKET = os.getenv("GCS_BUCKET_NAME", "stock-busters-chroma-bucket")
INPUT_CSV = "model_output/combined_quantamental_hybrid_with_factors_and_backtest.csv"  # Located in model_output/ folder
OUTPUT_CSV = "model_output/combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"

# Credentials path (relative to rag_majid/)
CREDENTIALS_PATH = "../secrets/stock-busters-service-account.json"
GCS_CREDENTIALS_PATH = "../secrets/gcs-key.json"


def setup_credentials():
    """Set up GCP credentials for Vertex AI and GCS.

    Checks credentials in the following order (container-friendly):
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable
    2. secrets/stock-busters-service-account.json (relative to working directory)
    3. ../secrets/stock-busters-service-account.json (fallback for local development)
    """
    # Check environment variable first (container-friendly)
    creds_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_env and os.path.exists(creds_env):
        creds_file = os.path.abspath(creds_env)
        print(f"Using credentials from GOOGLE_APPLICATION_CREDENTIALS: {creds_file}")
    # Check relative path (container-friendly)
    elif os.path.exists("secrets/stock-busters-service-account.json"):
        creds_file = os.path.abspath("secrets/stock-busters-service-account.json")
        print(f"Using credentials from secrets/ directory: {creds_file}")
    # Fallback to parent directory (local development only)
    elif os.path.exists(CREDENTIALS_PATH):
        creds_file = os.path.abspath(CREDENTIALS_PATH)
        print(f"Using credentials from parent directory: {creds_file}")
    else:
        raise FileNotFoundError(
            "Credentials file not found. Options:\n"
            "1. Set GOOGLE_APPLICATION_CREDENTIALS environment variable\n"
            "2. Place credentials at secrets/stock-busters-service-account.json\n"
            "3. Mount credentials as volume in Docker: -v /path/to/secrets:/app/secrets"
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


def download_csv_from_gcs(
    file_name: str, bucket_name: str = GCS_BUCKET_NAME
) -> pd.DataFrame:
    """Download CSV file from GCS bucket."""
    print(f"Downloading {file_name} from GCS bucket {bucket_name}...")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        # Check if file exists, if not search for it
        if not blob.exists():
            print(
                f"File not found at specified path. Searching for '{file_name.split('/')[-1]}' in bucket..."
            )
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
                    print(
                        f"⚠ File not found in model_output folder. Available folders: {sorted(folders)}"
                    )
                    print(f"⚠ Using first match instead: {matching_files[0]}")
                    file_name = matching_files[0]
                blob = bucket.blob(file_name)
                print(f"Using: {file_name}")
            else:
                print("Available files in bucket (first 30):")
                for f in all_files[:30]:
                    print(f"  - {f}")
                raise FileNotFoundError(
                    f"File {filename_only} not found in bucket {bucket_name}"
                )

        csv_bytes = blob.download_as_bytes()
        df = pd.read_csv(BytesIO(csv_bytes))

        print(f"Successfully loaded {file_name}")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")

        return df
    except Exception as e:
        print(f"Error downloading CSV from GCS: {e}")
        raise


def upload_csv_to_gcs(
    df: pd.DataFrame, gcs_path: str, bucket_name: str = GCS_BUCKET_NAME
):
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

    # Set GCS_BUCKET_NAME for ChromaDB connection (override any existing env var)
    # Force use of stock-busters-chroma-bucket for ChromaDB
    os.environ["GCS_BUCKET_NAME"] = "stock-busters-chroma-bucket"
    print("Using ChromaDB bucket: stock-busters-chroma-bucket")

    # Connect to existing ChromaDB in GCS (functions now in this file)
    print(f"Connecting to ChromaDB in GCS bucket: {GCS_CHROMADB_BUCKET}")
    get_rag_connection()

    # Get the ChromaDB client and collection from cache
    key = "default"
    if key not in _cache:
        raise RuntimeError("Failed to get ChromaDB connection")

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
    FastEmbedWrapper(fastembed_embedder)  # Initialize wrapper
    print("✓ FastEmbed embeddings initialized (384 dimensions)")

    # Retrieve the full .md document that was embedded as a single document
    # The original rag.py stores it with "#full_document" marker in the source
    # We use direct retrieval (no semantic search) - optimized with ID caching
    print(
        "Retrieving full .md document from ChromaDB (direct retrieval, no semantic search)..."
    )
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
                    print("✓ Retrieved from cache (no ChromaDB lookup needed)")
                    source = (
                        full_doc_metadata.get("source", "")
                        if isinstance(full_doc_metadata, dict)
                        else ""
                    )
                    print(f"  Source: {source[:100]}...")
                else:
                    print(
                        "  Cache mismatch or incomplete, will retrieve from ChromaDB..."
                    )
        except Exception:
            # Cache file corrupted, will search below
            print("  Cache file error, will retrieve from ChromaDB...")

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
                direct_results = collection.get(
                    ids=[possible_id], include=["documents", "metadatas"]
                )
                if direct_results.get("ids") and len(direct_results["ids"]) > 0:
                    full_doc_id = possible_id
                    full_doc_text = (
                        direct_results["documents"][0]
                        if direct_results.get("documents")
                        else None
                    )
                    full_doc_metadata = (
                        direct_results["metadatas"][0]
                        if direct_results.get("metadatas")
                        else {}
                    )
                    if full_doc_text:
                        print("  ✓ Found by direct ID lookup")
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
                                full_doc_results = collection.get(
                                    ids=[found_id], include=["documents", "metadatas"]
                                )
                                if (
                                    full_doc_results.get("ids")
                                    and len(full_doc_results["ids"]) > 0
                                ):
                                    full_doc_id = found_id
                                    full_doc_text = (
                                        full_doc_results["documents"][0]
                                        if full_doc_results.get("documents")
                                        else None
                                    )
                                    full_doc_metadata = (
                                        full_doc_results["metadatas"][0]
                                        if full_doc_results.get("metadatas")
                                        else {}
                                    )
                                    print("  ✓ Found in sample search")
                                    break
            except Exception:
                pass

        # Fallback: search through all documents if sample didn't find it
        if not full_doc_text:
            print("  Searching through all documents...")
            all_results = collection.get(
                limit=10000, include=["documents", "metadatas"]
            )

            if (
                all_results.get("metadatas")
                and all_results.get("ids")
                and all_results.get("documents")
            ):
                for idx, metadata in enumerate(all_results["metadatas"]):
                    if metadata and "source" in metadata:
                        source = metadata["source"]
                        if "#full_document" in source:
                            full_doc_id = all_results["ids"][idx]
                            full_doc_text = all_results["documents"][idx]
                            full_doc_metadata = metadata
                            print("  ✓ Found in full search")
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
            print("  ✓ Cached document content (will skip ChromaDB lookup next time)")
        except Exception:
            pass  # Cache write failure is not critical

    source = (
        full_doc_metadata.get("source", "")
        if isinstance(full_doc_metadata, dict)
        else ""
    )
    print(
        f"✓ Using full .md document from ChromaDB ({len(full_doc_text):,} characters)"
    )
    print(f"  Source: {source[:100]}...")

    # Create a retriever that returns the single full document
    from langchain_core.documents import Document

    full_doc = Document(
        page_content=full_doc_text,
        metadata=full_doc_metadata
        or {"source": "LLM-Quant_Expanded_RAG_with_context.md (full document)"},
    )

    class FullDocChromaRetriever(BaseRetriever):
        """Retriever that returns the full .md document from ChromaDB (single embedding)."""

        document: Document

        def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
        ):
            # Return the full document regardless of query
            return [self.document]

        def invoke(self, input: str, config=None, **kwargs):
            return self._get_relevant_documents(input)

    retriever = FullDocChromaRetriever(document=full_doc)
    print(
        f"✓ RAG retriever created - using single full .md document from ChromaDB ({len(full_doc_text):,} characters)"
    )

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
    print(
        f"✓ Optimized RAG chain created (context in system message, ~{len(full_doc_text):,} chars)"
    )
    # retriever is created but not used in this function
    print(
        f"  Each stock query will only send ~100-200 chars (vs ~12k+ chars with old method)"
    )

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
    df: pd.DataFrame,
    chain,
    sample_size: Optional[int] = None,
    max_workers: int = 10,
    main_pbar=None,
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
        future_to_idx = {
            executor.submit(process_single_stock, task): task[0] for task in tasks
        }

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
                    main_pbar.set_postfix_str(
                        f"✓ {symbol} ({len(results)}/{total_rows})", refresh=True
                    )

    # Update DataFrame with results
    for idx, (reasoning, _stock_time, _symbol, _error) in results.items():
        df.at[idx, "rag_reasoning"] = reasoning

    total_time = time.time() - start_time

    if errors:
        print(f"\n⚠ Warning: {len(errors)} stocks had errors:")
        for symbol, error in errors[:5]:  # Show first 5 errors
            print(f"   • {symbol}: {error}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more errors")

    return df


def generate_reasoning_for_dataframe(
    df: pd.DataFrame, chain, sample_size: Optional[int] = None, max_workers: int = 20
) -> pd.DataFrame:
    """
    Generate investment reasoning for stocks in a DataFrame using RAG system.

    This is the core function that processes a DataFrame and adds a 'rag_reasoning' column.
    Used by the pipeline integration to add reasoning to the combined CSV.

    Args:
        df: DataFrame with stock data (must have columns like symbol, signal, scores, metrics, etc.)
        chain: Pre-initialized RAG chain (from setup_rag_system())
        sample_size: Optional number of stocks to process (for testing). If None, processes all.
        max_workers: Number of parallel workers (default: 20)

    Returns:
        DataFrame with added 'rag_reasoning' column
    """
    print(f"Generating reasoning for DataFrame with {len(df)} stocks...")
    df_enhanced = process_csv_with_rag(
        df, chain, sample_size=sample_size, max_workers=max_workers
    )
    print("✓ Reasoning generation complete. Added 'rag_reasoning' column.")
    return df_enhanced


def add_reasoning_to_combined_file(
    combined_file_path: str,
    output_path: Optional[str] = None,
    sample_size: Optional[int] = None,
    max_workers: int = 20,
    upload_to_gcs: bool = True,
    gcs_bucket: Optional[str] = None,
    gcs_path: Optional[str] = None,
) -> str:
    """
    Read CSV from pipeline output, add reasoning, and save enhanced CSV.

    This function is designed to be called after the quantamental pipeline completes.
    It reads the combined CSV file, adds reasoning using RAG, and saves an enhanced version.

    Args:
        combined_file_path: Path to the combined CSV file from pipeline output
        output_path: Optional output path. If None, appends '_with_reasoning' to input filename.
        sample_size: Optional number of stocks to process (for testing). If None, processes all.
        max_workers: Number of parallel workers (default: 20)
        upload_to_gcs: Whether to upload enhanced CSV to GCS (default: True)
        gcs_bucket: GCS bucket name (uses GCS_BUCKET_NAME if not provided)
        gcs_path: GCS path for output file (uses OUTPUT_CSV if not provided)

    Returns:
        Path to the enhanced CSV file (local path)
    """
    print("=" * 60)
    print("Adding RAG Reasoning to Combined CSV")
    print("=" * 60)

    # Setup credentials
    print("\nSetting up credentials...")
    credentials = setup_credentials()
    print("✓ Credentials loaded")

    # Setup RAG system
    print("\nSetting up RAG system...")
    chain = setup_rag_system(credentials)
    print("✓ RAG system ready")

    # Read CSV
    print(f"\nReading CSV from: {combined_file_path}")
    df = pd.read_csv(combined_file_path)
    print(f"✓ Loaded {len(df)} stocks")

    # Check if reasoning column already exists
    if "rag_reasoning" in df.columns:
        print("⚠ Warning: 'rag_reasoning' column already exists. Will be overwritten.")
        df = df.drop(columns=["rag_reasoning"])

    # Generate reasoning
    print("\nGenerating reasoning for stocks...")
    df_enhanced = generate_reasoning_for_dataframe(
        df, chain, sample_size=sample_size, max_workers=max_workers
    )

    # Determine output path
    if output_path is None:
        input_path_obj = Path(combined_file_path)
        output_path = str(
            input_path_obj.parent
            / f"{input_path_obj.stem}_with_reasoning{input_path_obj.suffix}"
        )

    # Save enhanced CSV
    print(f"\nSaving enhanced CSV to: {output_path}")
    df_enhanced.to_csv(output_path, index=False)
    print(f"✓ Enhanced CSV saved: {output_path}")

    # Upload to GCS if requested
    if upload_to_gcs:
        bucket_name = gcs_bucket or GCS_BUCKET_NAME
        gcs_output_path = gcs_path or OUTPUT_CSV

        print(f"\nUploading to GCS: gs://{bucket_name}/{gcs_output_path}")
        upload_csv_to_gcs(df_enhanced, gcs_output_path, bucket_name)
        print(f"✓ Uploaded to GCS: gs://{bucket_name}/{gcs_output_path}")

    print("\n" + "=" * 60)
    print("✓ Reasoning added successfully!")
    print("=" * 60)

    return output_path


def run_pipeline_with_reasoning(
    force_refresh: bool = False,
    skip_training: bool = False,
    rag_enabled: bool = True,
    rag_sample_size: Optional[int] = None,
    rag_max_workers: int = 20,
    step: str = "all",
):
    """
    Run the full quantamental pipeline and add reasoning to the output CSV.

    This is a wrapper around the original pipeline that:
    1. Runs the original quantamental pipeline (unchanged)
    2. After backtest completes, adds reasoning to the combined CSV
    3. Re-uploads enhanced CSV to GCS

    Args:
        force_refresh: Force refresh data from API (ignores cache)
        skip_training: Skip model training (use existing model)
        rag_enabled: Enable/disable reasoning generation (default: True)
        rag_sample_size: Optional number of stocks to process (for testing)
        rag_max_workers: Number of parallel workers for reasoning (default: 20)
        step: Pipeline step to run ('all', 'collect', 'process', 'train', 'predict', 'backtest')

    Returns:
        Dictionary with pipeline results and reasoning status
    """
    # Import original pipeline functions
    from main import (
        run_full_pipeline,
        run_data_collection,
        run_data_processing,
        run_model_training,
        run_prediction,
        run_backtest,
    )
    from utils import load_config

    print("=" * 60)
    print("QUANTAMENTAL PIPELINE WITH RAG REASONING")
    print("=" * 60)

    config = load_config()

    # Check if RAG is enabled in config
    rag_config = config.get("rag", {})
    if rag_enabled and not rag_config.get("enabled", True):
        print("⚠ RAG reasoning disabled in config.yaml. Skipping reasoning step.")
        rag_enabled = False

    if rag_enabled:
        # Use config values if not explicitly provided
        rag_sample_size = (
            rag_sample_size
            if rag_sample_size is not None
            else rag_config.get("sample_size")
        )
        rag_max_workers = (
            rag_max_workers if rag_config.get("max_workers") else rag_max_workers
        )
        print(
            f"RAG Reasoning: Enabled (max_workers={rag_max_workers}, sample_size={rag_sample_size})"
        )
    else:
        print("RAG Reasoning: Disabled")

    results = None

    try:
        # Run original pipeline
        print("\n" + "=" * 60)
        print("RUNNING ORIGINAL QUANTAMENTAL PIPELINE")
        print("=" * 60)

        if step == "all":
            results = run_full_pipeline(
                force_refresh=force_refresh, skip_training=skip_training
            )
        elif step == "backtest":
            # For backtest step, we need to run previous steps first or load from cache
            results = run_backtest(config)
        else:
            # For other individual steps, run them
            if step == "collect":
                run_data_collection(config, force_refresh=force_refresh)
            elif step == "process":
                run_data_processing(config)
            elif step == "train":
                run_model_training(config)
            elif step == "predict":
                run_prediction(config)
            print(f"✓ Step '{step}' completed")
            return {"step": step, "completed": True}

        # After pipeline completes, add reasoning if enabled
        if rag_enabled and results and results.get("agent_files"):
            combined_file = results["agent_files"].get("combined")

            if combined_file and os.path.exists(combined_file):
                print("\n" + "=" * 60)
                print("ADDING RAG REASONING TO CSV")
                print("=" * 60)

                try:
                    # Determine output path (same directory, with _with_reasoning suffix)
                    combined_path_obj = Path(combined_file)
                    output_path = str(
                        combined_path_obj.parent
                        / f"{combined_path_obj.stem}_with_reasoning{combined_path_obj.suffix}"
                    )

                    # Get GCS paths from config
                    gcs_bucket = config.get("gcs", {}).get(
                        "bucket_name", GCS_BUCKET_NAME
                    )
                    gcs_output_folder = config.get("gcs", {}).get(
                        "output_folder", "model_output"
                    )
                    gcs_output_path = (
                        f"{gcs_output_folder}/"
                        f"combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"
                    )

                    # Add reasoning
                    enhanced_file = add_reasoning_to_combined_file(
                        combined_file_path=combined_file,
                        output_path=output_path,
                        sample_size=rag_sample_size,
                        max_workers=rag_max_workers,
                        upload_to_gcs=True,
                        gcs_bucket=gcs_bucket,
                        gcs_path=gcs_output_path,
                    )

                    # Update results
                    if "agent_files" in results:
                        results["agent_files"][
                            "combined_with_reasoning"
                        ] = enhanced_file
                    results["reasoning_added"] = True
                    results["reasoning_output"] = enhanced_file

                    print("\n✓ Pipeline with reasoning complete!")

                except Exception as e:
                    print(f"\n⚠ Error adding reasoning: {e}")
                    print(
                        "Pipeline completed successfully, but reasoning was not added."
                    )
                    import traceback

                    traceback.print_exc()
                    results["reasoning_added"] = False
                    results["reasoning_error"] = str(e)
            else:
                print(f"\n⚠ Combined file not found: {combined_file}")
                print("Skipping reasoning step.")
                results["reasoning_added"] = False
        elif not rag_enabled:
            results["reasoning_added"] = False
            results["reasoning_skipped"] = True

        return results

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback

        traceback.print_exc()
        raise


def main():
    """Main execution function - supports both standalone and pipeline modes."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate investment reasoning for stocks using RAG or run pipeline with reasoning"
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "pipeline"],
        default="standalone",
        help=(
            "Execution mode: 'standalone' (process existing CSV) or "
            "'pipeline' (run full pipeline with reasoning). Default: standalone"
        ),
    )

    # Standalone mode arguments
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
    parser.add_argument(
        "--csv-path",
        type=str,
        default=None,
        help="Path to CSV file (standalone mode). If not specified, downloads from GCS.",
    )

    # Pipeline mode arguments
    parser.add_argument(
        "--step",
        choices=["all", "collect", "process", "train", "predict", "backtest"],
        default="all",
        help="Pipeline step to run (pipeline mode). Default: all",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh data from API (pipeline mode)",
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip model training (pipeline mode)",
    )
    parser.add_argument(
        "--disable-rag",
        action="store_true",
        help="Disable RAG reasoning generation (pipeline mode)",
    )

    args = parser.parse_args()

    # Pipeline mode
    if args.mode == "pipeline":
        print("Running in PIPELINE mode...")
        run_pipeline_with_reasoning(
            force_refresh=args.force_refresh,
            skip_training=args.skip_training,
            rag_enabled=not args.disable_rag,
            rag_sample_size=args.sample_size,
            rag_max_workers=args.max_workers,
            step=args.step,
        )
        return

    # Standalone mode (original behavior)
    print("Running in STANDALONE mode...")

    print("=" * 60)
    print("Stock Reasoning Generator using RAG")
    print("=" * 60)

    # Setup credentials (quick, no progress needed)
    print("\nSetting up credentials...")
    credentials = setup_credentials()
    print("✓ Credentials loaded")

    # Load CSV (from file or GCS)
    if args.csv_path:
        print(f"Loading CSV from local file: {args.csv_path}")
        df = pd.read_csv(args.csv_path)
        print("✓ CSV loaded from file")
    else:
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
        df,
        chain,
        sample_size=args.sample_size,
        max_workers=args.max_workers,
        main_pbar=main_pbar,
    )

    # Step 2: Save Results
    main_pbar.set_description(f"[2/{total_steps}] {workflow_steps[1]}")
    main_pbar.set_postfix_str("", refresh=True)
    local_output = (
        "combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv"
    )
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
