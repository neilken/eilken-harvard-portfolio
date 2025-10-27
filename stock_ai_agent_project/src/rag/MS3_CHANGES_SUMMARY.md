# MS3 Changes Summary

## Overview
This document summarizes the major improvements made to the RAG application for AC215 Milestone 3, focusing on semantic chunking, text cleaning, GCS integration, and comprehensive documentation.

---

## 1. Semantic Chunking Implementation

### What Changed
Implemented sophisticated semantic chunking to replace simple token-based splitting, improving retrieval relevance by preserving semantic boundaries.

### Key Features
- **Semantic Boundary Detection**: Uses sentence embeddings to identify natural semantic boundaries
- **Cosine Similarity Analysis**: Calculates similarity between consecutive sentences
- **Adaptive Chunking**: Splits text at points where semantic similarity drops below threshold
- **Overlap Support**: Maintains sentence-level overlap between chunks for context preservation

### Technical Details
- **Base Class**: `SemanticChunker` inherits from LangChain's `BaseDocumentTransformer`
- **Embedding Model**: Uses FastEmbed with BGE-small-en-v1.5 for sentence embeddings
- **Parameters**:
  - `target_tokens`: Target chunk size (default: 900)
  - `max_tokens`: Maximum chunk size (default: 1400)
  - `sim_percentile`: Similarity threshold (default: 95.0)
  - `overlap_sentences`: Number of sentences to overlap (default: 2)

### Benefits
- Chunks preserve semantic meaning
- Better context retention across boundaries
- Improved retrieval accuracy for queries

---

## 2. Text Normalization and Cleaning Improvements

### What Changed
Enhanced text loading, sanitization, and normalization to improve chunk quality and retrieval relevance.

### Improvements

#### Unicode Normalization
- Fixed problematic Unicode characters (e.g., curly quotes, em dashes)
- Preserved paragraph breaks for document structure
- Normalized whitespace (tabs, multiple spaces) to single spaces

#### Document Structure Preservation
- Maintained paragraph boundaries during text extraction
- Preserved code blocks and list formatting
- Extracted document-level metadata (headers, lists, tables)

#### Metadata Enrichment
- **Key Phrases Extraction**: Identifies important phrases from each chunk
- **Chunk Type Classification**: Categorizes chunks as:
  - `code`: Contains code blocks
  - `list`: List/structured content
  - `definition`: Definitions or explanations
  - `question`: Questions or queries
  - `data`: Numerical data or statistics
  - `paragraph`: Standard prose
- **Document Structure Metadata**: Extracts headers, lists, tables, word counts

#### Context Enrichment
- **Sliding Window Context**: Adds surrounding sentences to each chunk
- **Limited Context Window**: Prevents excessive memory usage with configurable lookback/lookahead limits

### Technical Implementation
```python
def _norm(text: str) -> str:
    """Normalize text: fix Unicode, normalize whitespace, preserve structure"""
    
def _extract_structure(text: str) -> Dict[str, Any]:
    """Extract document structure metadata"""
    
def _extract_metadata(text: str) -> str:
    """Extract document-level metadata"""
    
def _enrich_chunk_with_context(chunks: List[str], window_size: int = 2) -> List[str]:
    """Add sliding window context to chunks"""
    
def _extract_key_phrases(text: str, max_phrases: int = 5) -> List[str]:
    """Extract key phrases from text"""
    
def _classify_chunk_type(text: str) -> str:
    """Classify chunk type based on content"""
```

### Benefits
- Better text quality in ChromaDB
- More relevant search results
- Richer metadata for filtering
- Improved understanding of document content

---

## 3. Google Cloud Storage (GCS) Integration

### What Changed
Implemented persistent storage for ChromaDB vectors in GCS, eliminating the need for Docker volume mounts and enabling cloud-native deployment.

### Key Features

#### Auto-Bucket Creation
- Automatically creates GCS bucket if it doesn't exist
- Configurable bucket name and location via environment variables

#### Bi-Directional Sync
- **Upload** (`_sync_to_gcs`): Syncs local ChromaDB to GCS after ingestion
- **Download** (`_sync_from_gcs`): Syncs GCS to local on startup
- Recursive file transfers for ChromaDB directory structure

#### Service Account Authentication
- Uses service account JSON key for secure access
- Falls back to Application Default Credentials if key not provided
- Full GCS permissions (create, read, write)

#### Duplicate Handling
- **Upsert Behavior**: Updates existing chunks, adds new ones
- **No Duplicates**: Same source always maps to same chunks
- **Incremental Updates**: Can add new documents without re-processing everything

### Configuration
```bash
# Environment variables
USE_GCS_STORAGE=1              # Enable GCS storage
GCS_BUCKET_NAME=ac215-chroma-bucket
GCS_PATH_PREFIX=chromadb
GCS_BUCKET_LOCATION=us-central1
GCS_SERVICE_ACCOUNT_KEY=gcs-key.json
```

### Technical Implementation
```python
def _sync_to_gcs(local_path: str, remote_path: str) -> bool:
    """Sync local directory to GCS bucket.
    
    Uploads ChromaDB files, auto-creates bucket if missing.
    Returns True if successful, False otherwise.
    """
    
def _sync_from_gcs(remote_path: str, local_path: str) -> bool:
    """Sync GCS bucket to local directory.
    
    Downloads ChromaDB files from GCS to local path.
    Creates local directories as needed.
    """
```

### Integration Points
- **Ingestion** (`run_ingest`): Downloads at start, uploads at end
- **Retriever** (`Retriever.__init__`): Downloads on initialization

### Benefits
- Persistent storage survives container restarts
- Shared storage across multiple containers
- Cloud-native deployment ready
- Automatic backup/restore

---

## 4. Documentation and Docstrings

### What Changed
Added comprehensive docstrings to all major functions and classes following Google-style documentation standards.

### Docstrings Added

#### Module-Level Docstring
```python
"""
AC215 MS3 Semantic RAG Application with GCS Persistent Storage

Features:
    - Semantic chunking with context enrichment
    - FastEmbed embeddings (BGE-small)
    - ChromaDB vector store with upsert (no duplicates)
    - GCS persistent storage (optional)
    - FastAPI REST API (/health, /query endpoints)
    ...
"""
```

#### Function Docstrings
- `_load_env_file()`: Loads environment variables from .env
- `_safe_mkdir()`: Safe directory creation
- `_sync_to_gcs()`: GCS upload functionality
- `_sync_from_gcs()`: GCS download functionality
- `run_ingest()`: Main ingestion function with full parameter documentation
- `Retriever` class: Semantic search with caching support
- `make_app()`: FastAPI application setup
- `serve()`: Server startup
- `main()`: CLI entry point

### Docstring Format
Each docstring includes:
- **Purpose**: What the function does
- **Args**: Parameter descriptions and defaults
- **Returns**: Return value description
- **Notes**: Implementation details, usage notes

### Benefits
- Better code maintainability
- Easier onboarding for team members
- Meets assignment documentation requirements
- Clear API documentation for users

---




### Files Added/Modified
```
src/rag/
├── rag.py              # Main application (with docstrings)
├── Dockerfile          # Docker build configuration
├── .env                # Configuration file
├── gcs-key.json        # Service account credentials
├── .dockerignore       # Docker ignore rules
├── screenshot_logs     # Added screenshot of running GCS bucket for ChromaDB
└── pyproject.toml      # Dependencies (added google-cloud-storage)
```

### Docker Commands
```bash
# Build from root
docker build -t ac215-rag -f src\rag\Dockerfile src\rag

# Run ingestion (creates/uploads to GCS)
docker run --rm ac215-rag --ingest

# Run API server
docker run -p 8000:8000 --rm ac215-rag --serve
```


## Summary of Improvements

### Functional Changes
1.  Semantic chunking replaces token-based splitting
2.  Enhanced text cleaning and normalization
3.  Metadata enrichment (key phrases, chunk types, document structure)
4.  GCS persistent storage integration
5.  Duplicate handling with upsert behavior

### Performance Changes
1.  Batch size optimizations (256 instead of 50)
2.  Query result caching (LRU cache)
3.  Memory management improvements
4.  Regex compilation optimizations

### Documentation Changes
1.  Comprehensive module docstring
2.  Function-level docstrings with Google style
3.  Parameter documentation
4.  Usage examples and notes

### Deployment Changes
1.  GCS integration for persistent storage
2.  Service account authentication

---

## Migration Guide

### Running the Updated Code

#### Option 1: Fresh Start
```bash
# Build and run
docker build -t ac215-rag -f src\rag\Dockerfile src\rag
docker run --rm ac215-rag --ingest
docker run -p 8000:8000 --rm ac215-rag --serve
```

#### Option 2: From Existing
The upsert behavior means existing ChromaDB will be automatically updated. No data loss occurs.

### Environment Configuration
Update your `.env` file:
```bash
USE_GCS_STORAGE=1
GCS_BUCKET_NAME=ac215-chroma-bucket
GCS_SERVICE_ACCOUNT_KEY=gcs-key.json
```

---

## Future Enhancements (Not Implemented)

These are potential improvements for future milestones:
- [ ] Parallel processing for document ingestion
- [ ] Vector compression for storage efficiency
- [ ] Advanced filtering based on metadata
- [ ] Multi-turn conversation support
- [ ] Query expansion and refinement

---

**Last Updated**: MS3 Submission
