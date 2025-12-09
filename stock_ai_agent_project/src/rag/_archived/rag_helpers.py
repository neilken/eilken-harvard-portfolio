"""
RAG Helpers - Simple functions for querying ChromaDB from GCS

This module provides simple helper functions for connecting to RAG/ChromaDB stored in
Google Cloud Storage and querying document collections.

The functions work independently - they automatically download ChromaDB data from GCS
and connect directly.

Usage:
    from rag_helpers import (
        get_rag_connection,
        get_chroma_db,
        query_rag_texts,
        store_query_in_chromadb,
    )

    # Option A: One-liner to get just the texts
    texts = query_rag_texts("What is ROE?", collection_name="my_collection", k=5)
    for t in texts:
        print(t)

    # Example output:
    # Return on Equity (ROE) measures a company's profitability relative to shareholders' equity...
    # ROE = Net Income / Average Shareholders' Equity. Higher ROE can indicate efficient capital use...

    # Option B: Full context (query returns rich results with metadata/distances)
    get_rag_connection(collection_name="my_collection")
    chroma_db = get_chroma_db(collection_name="my_collection")
    results = chroma_db.query("What is ROE?", k=5)
    for r in results:
        print(r["document"])
        print(r["distance"], r["metadata"])

    # Example output:
    # Return on Equity (ROE) measures a company's profitability relative to shareholders' equity...
    # 0.2341 {'source': 'finance_guide.pdf', 'page': 42}
    # ROE is calculated as Net Income divided by Average Shareholders' Equity...
    # 0.4178 {'source': 'accounting_basics.pdf', 'page': 15}
"""

import os
import tempfile
import re
import sys
from types import SimpleNamespace
from typing import Optional, List, Dict, Any

import chromadb
from chromadb.config import Settings
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables early
load_dotenv(override=True)

# Try to import FastEmbed, fallback if not available
try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

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
            raise ImportError("fastembed is required. Install with: pip install fastembed")
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

    Example:
        # Set up connection explicitly
        get_rag_connection()

        # Or with a specific collection
        get_rag_connection(collection_name="financial_terms")
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
    blobs = [b for b in bucket.list_blobs(prefix="chromadb") if not b.name.endswith("/")]

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
    chroma_client = chromadb.PersistentClient(path=local_path, settings=Settings(anonymized_telemetry=False))

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

    Raises:
        ValueError: If GCS_BUCKET_NAME environment variable is not set.
        RuntimeError: If connection setup fails.

    Example:
        # Get chroma_db_context
        chroma_db = get_chroma_db()

        # Query default collection
        results = chroma_db.query("What is ROE?")

        # Query specific collection
        results = chroma_db.query("What is P/E ratio?", collection="financial_terms")

        # Get more results
        results = chroma_db.query("What is momentum?", k=10)

        # Access results
        for result in results:
            print(f"Document: {result['document']}")
            print(f"Distance: {result['distance']}")
            print(f"Metadata: {result['metadata']}")
    """
    # Use collection name as cache key
    key = collection_name or "default"

    # Ensure connection is set up (will call get_rag_connection() if needed)
    if key not in _cache:
        get_rag_connection(collection_name)

    # Get cached ChromaDB client and default collection
    chroma_client, default_collection = _cache[key]

    def query(query_string: str, collection: Optional[str] = None, k: int = 4) -> List[Dict[str, Any]]:
        """
        Query ChromaDB collection using semantic search.

        This method performs a semantic search query on the specified ChromaDB collection.
        It converts the query text to an embedding vector and finds the most similar
        documents in the collection.

        Args:
            query_string: The natural language query/question to search for.
                         Examples: "What is ROE?", "Explain P/E ratio", "momentum indicators"
            collection: Optional collection name to query.
                       If not provided, uses the default collection from get_chroma_db().
            k: Number of results to return (default: 4, max: 50).
               Lower values return fewer but more relevant results.

        Returns:
            List of dictionaries, each containing:
            - id: Document ID in ChromaDB
            - document: The document text content
            - metadata: Dictionary of document metadata (source, page, etc.)
            - distance: Similarity distance (lower = more similar, typically 0.0-2.0)

        Note:
            - Returns empty list if query_string is empty or invalid
            - Query is normalized (cleaned) before embedding
            - Results are sorted by similarity (most similar first)

        Example:
            # Query and get results
            results = chroma_db.query("What is ROE?", k=3)

            # Access first result
            if results:
                print(f"Top result: {results[0]['document']}")
                print(f"Similarity: {results[0]['distance']:.4f}")
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
        # Handle different embedding formats (numpy array, list, nested list)
        if hasattr(q_vec, "tolist"):
            q_vec = q_vec.tolist()
        # Flatten nested lists if needed
        if isinstance(q_vec, list) and q_vec and isinstance(q_vec[0], list):
            q_vec = q_vec[0] if len(q_vec) == 1 else [item for sublist in q_vec for item in sublist]

        # Perform semantic search query
        # Returns documents, metadata, distances, and IDs for the k most similar documents
        # Note: IDs are always returned, so we don't include them in the include parameter
        res = coll.query(
            query_embeddings=[q_vec],
            n_results=max(1, min(int(k), 50)),  # Ensure k is between 1 and 50
            include=["documents", "metadatas", "distances"],
        )

        # Extract results from ChromaDB response format
        # ChromaDB returns nested lists: [[id1, id2, ...], [doc1, doc2, ...], ...]
        # We need the first (and only) inner list
        # IDs are always returned even if not in include
        def get_first(x):
            """Get first element of list or empty list if empty."""
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
                "distance": float(dist) if dist is not None else 0.0,  # Convert to float, default to 0.0
            }
            for doc_id, text, md, dist in zip(ids, docs, metas, dists)
        ]

    # Return SimpleNamespace object with query method attached
    # This allows chroma_db.query() syntax without defining a class
    return SimpleNamespace(query=query)


if __name__ == "__main__":
    # Example usage
    get_rag_connection()  # Set up connection
    chroma_db = get_chroma_db()  # Get context
    results = chroma_db.query("What is ROE?", k=2)  # Query
    print(f"\nFound {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['document'][:80]}... (distance: {r['distance']:.4f})")


# ----------------------------------------------------------------------------
# Convenience function
# ----------------------------------------------------------------------------
def query_rag_texts(query_string: str, collection_name: Optional[str] = None, k: int = 4) -> List[str]:
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

    Example:
        texts = query_rag_texts("Explain P/E ratio", collection_name="stocks_rag_v1", k=5)
        for t in texts:
            print(t[:120])
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

    This function takes a query string (e.g., "E/F ratio"), creates an embedding for it,
    and stores it in the specified ChromaDB collection. The query can later be retrieved
    or used for similarity matching.

    Args:
        query: Query string to store (e.g., "E/F ratio", "What is ROE?").
        collection_name: Optional collection name. If None, uses default from environment.
        query_id: Optional query ID. If None, auto-generates based on normalized query.
        metadata: Optional metadata dictionary (e.g., {"timestamp": "...", "user": "..."}).
        upload_to_gcs: If True, uploads updated ChromaDB files back to GCS after storing.
                      Default: False (changes are local only).

    Returns:
        Dictionary with:
        - stored: Always 1 (single query stored)
        - query_id: The ID used to store the query
        - collection: Collection name used
        - embedding_model: Embedding model used

    Raises:
        ValueError: If query is empty or GCS_BUCKET_NAME not set (when upload_to_gcs=True).
        RuntimeError: If embedding or storage fails.

    Example:
        # Store a query
        result = store_query_in_chromadb(
            query="E/F ratio",
            collection_name="queries",
            metadata={"timestamp": "2024-01-15", "source": "user_input"}
        )
        print(f"Stored query with ID: {result['query_id']}")

        # Store query with custom ID
        result = store_query_in_chromadb(
            query="What is P/E ratio?",
            query_id="query_pe_ratio",
            collection_name="financial_queries"
        )
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
        # Create a simple ID from normalized query (replace spaces with underscores)
        query_id = f"query_{q_normalized.replace(' ', '_')[:50]}"

    # Default metadata if not provided (ChromaDB requires non-empty dict)
    if metadata is None or not metadata:
        metadata = {"stored_by": "rag_helpers"}

    # Create embedding for the query (use query_embed for queries)
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
    # Store the query text as the document
    try:
        coll.upsert(
            ids=[query_id], documents=[query], metadatas=[metadata], embeddings=[q_vec]  # Store the original query text
        )
    except Exception as e:
        raise RuntimeError(f"Failed to store query in ChromaDB: {e}")

    # Upload to GCS if requested
    if upload_to_gcs:
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME not set (required for upload_to_gcs=True)")

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

    return {"stored": 1, "query_id": query_id, "collection": target_collection, "embedding_model": EMBEDDING_MODEL}
