# Duplicate Handling in Ingestion

## Overview
Intelligent handling of multiple ingest runs to avoid duplicates and enable efficient re-processing.

## How It Works

### 1. **Upsert Behavior** (Always Active)
- Uses `coll.upsert()` instead of `coll.add()`
- **Updates** existing chunks with same ID
- **Adds** new chunks that don't exist
- **No duplicates created** - same source will update existing chunks

### 2. **Source Tracking** (Optional via `SKIP_EXISTING`)
- Tracks which document sources have been processed
- Can skip already-processed documents on re-run
- Faster re-ingestion when adding new documents

## Behavior Modes

### Mode 1: Update Existing (Default)
```bash
export SKIP_EXISTING=0

# First run
python src/rag/rag.py --ingest
# → Processes: doc1.pdf, doc2.pdf
# → Creates 100 chunks

# Second run (same command)
python src/rag/rag.py --ingest
# → Processes: doc1.pdf, doc2.pdf again
# → Updates existing chunks (no duplicates)
# → Still creates 100 chunks (updated)
```

### Mode 2: Skip Existing (Fast Re-Run)
```bash
export SKIP_EXISTING=1

# First run
python src/rag/rag.py --ingest
# → Processes: doc1.pdf, doc2.pdf
# → Creates 100 chunks

# Second run
python src/rag/rag.py --ingest
# → [SKIP] doc1.pdf already processed
# → [SKIP] doc2.pdf already processed
# → No processing (instant)
```

### Mode 3: Incremental Addition
```bash
export SKIP_EXISTING=0

# First run
python src/rag/rag.py --ingest  # doc1.pdf, doc2.pdf
# → Creates 100 chunks

# Second run (after adding doc3.pdf to data directory)
python src/rag/rag.py --ingest  # doc1.pdf, doc2.pdf, doc3.pdf
# → Updates: doc1.pdf, doc2.pdf chunks
# → Adds: doc3.pdf new chunks
# → Total: ~150 chunks
```

## Use Cases

### Use Mode 1 (Update Existing) When:
- You update documents and want to re-index them
- You changed chunking parameters
- You want to refresh embeddings

### Use Mode 2 (Skip Existing) When:
- You have many documents and only added a few new ones
- You want fast re-runs (testing, development)
- You want to avoid reprocessing unchanged documents

### Use Mode 3 (Incremental) When:
- You add new documents to data directory
- You want to build index progressively
- You process documents over time

## Configuration

In `.env`:
```bash
# Default: Update existing chunks (no skipping)
SKIP_EXISTING=0

# Enable: Skip already processed documents
SKIP_EXISTING=1
```

## Example Output

### Mode 1: Update Existing
```
[INFO] Found 1234 existing chunks in collection
[INFO] Found 15 unique sources already processed
Processing document 1/15 (data/doc1.pdf)
Processing document 2/15 (data/doc2.pdf)
...
Indexed 1234 chunks into collection
```

### Mode 2: Skip Existing
```
[INFO] Found 1234 existing chunks in collection
[INFO] Found 15 unique sources already processed
[SKIP] data/doc1.pdf already processed, skipping...
[SKIP] data/doc2.pdf already processed, skipping...
Indexed 0 chunks into collection
```

### Mode 3: Incremental
```
[INFO] Found 1234 existing chunks in collection
[INFO] Found 13 unique sources already processed
Processing document 1/15 (data/doc1.pdf)  # Updates
Processing document 2/15 (data/doc2.pdf)  # Updates
Processing document 14/15 (data/newdoc.pdf)  # New!
Processing document 15/15 (data/newdoc2.pdf)  # New!
Indexed 234 chunks into collection  # New chunks from newdocs
```

## Technical Details

### Upsert Mechanism
```python
# Uses ChromaDB's upsert method
coll.upsert(ids, documents, metadatas, embeddings)

# Behavior:
# - ID exists → Updates that chunk
# - ID doesn't exist → Adds new chunk
# - Same ID always points to same chunk (no duplicates)
```

### ID Format
```python
# IDs are deterministic based on source + chunk index
cid = f"{src}::chunk_{idx}"

# Example:
"data/doc1.pdf::chunk_0"  # First chunk of doc1.pdf
"data/doc1.pdf::chunk_1"  # Second chunk of doc1.pdf
```

### Benefits
- **No duplicates** - Same document processed multiple times = same chunks
- **Updates work** - Re-processing updates existing chunks
- **Incremental** - Can add new documents progressively
- **Fast re-runs** - Skip mode avoids unnecessary processing

## GCS Integration

With GCS storage:
```bash
export USE_GCS_STORAGE=1
export SKIP_EXISTING=0

# First run
python src/rag/rag.py --ingest
# → Downloads existing from GCS (if any)
# → Processes documents
# → Uploads updated store to GCS

# Second run
python src/rag/rag.py --ingest
# → Downloads existing from GCS
# → Finds existing chunks, updates them
# → Uploads updated store to GCS
```

## Troubleshooting

### I want to completely re-index
```bash
# Option 1: Delete local vector store
rm -rf /workspace/volumes/chroma/*

# Option 2: Delete from ChromaDB
python -c "import chromadb; c = chromadb.PersistentClient(path='/workspace/volumes/chroma'); c.delete_collection('stocks_rag_v1')"
```

### I have duplicates in my collection
```bash
# This shouldn't happen with upsert, but if it does:
# 1. Check that coll.upsert() is being used (not coll.add())
# 2. Verify IDs are unique and deterministic
# 3. Consider re-indexing from scratch
```
