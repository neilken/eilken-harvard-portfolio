# Data Versioning and Reproducibility

## Overview

This document describes the data versioning strategy for the RAG component, which handles large vector embeddings, document chunks, and persistent ChromaDB state.

## Chosen Method: DVC (Data Version Control)

### Approach

The RAG system uses **DVC** for data versioning, which provides:
1. **Version control for large files**: ChromaDB vectors and embeddings
2. **Git integration**: DVC metadata files tracked in git
3. **Reproducibility**: Link data versions to code commits
4. **Team collaboration**: Shared remote storage (GCS/S3) with DVC tracking
5. **Automatic versioning**: DVC snapshots are created automatically after each ingestion

### Automatic Versioning

**Important:** DVC versioning is **automatically integrated** into the ingestion process. After each successful ingestion (`python rag.py --ingest`), the system:

1. Uploads ChromaDB data to GCS for **operational use** (`gs://<bucket>/chromadb/`)
   - This is the primary storage used by the RAG service (downloaded on startup)
2. Automatically creates a DVC version snapshot (`dvc add --no-commit`)
   - `dvc add --no-commit` creates/updates the `.dvc` metadata file locally with data hash
   - **Important**: `--no-commit` flag keeps original ChromaDB files in place (not moved to `.dvc/cache/`)
   - This ensures ChromaDB server and GCS sync continue to work with original file locations
   - **Note**: `dvc push` is **skipped** - data remains only in operational `chromadb/` storage (no duplication)
3. **Automatically uploads `.dvc` file to GCS** (works in Docker containers)
   - The `.dvc` file is uploaded to `gs://<bucket>/dvc-metadata/chroma_<timestamp>.dvc` (versioned)
   - Also uploaded as `gs://<bucket>/dvc-metadata/chroma_latest.dvc` (for easy access)
   - This works in Docker containers where git commit may not be available
   - You can download later: `gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc`
   - **Note**: Git commit is manual - download from GCS and commit when ready

**Storage Strategy:**
- **Single storage location**: `chromadb/` (operational storage only)
- **No data duplication**: Data is stored once in `chromadb/`, not in `dvc-storage/`
- **Version tracking**: `.dvc` files in git track data hashes for reproducibility
- **Automatic GCS upload**: `.dvc` file is automatically uploaded to GCS after ingestion (works in Docker)

### Justification

#### Why DVC?

**DVC is chosen for the following reasons:**

1. **Data Characteristics**
   - **Large binary files**: ChromaDB stores millions of vector embeddings (384-dim floats)
   - **Versioned datasets**: Source documents and vector databases need versioning
   - **Size**: Vector database can grow to 10GB+ (not suitable for git directly)
   - **DVC handles**: Large files via remote storage (GCS/S3) with git-tracked metadata

2. **Workflow Fit**
   - **Standard tool**: DVC is explicitly mentioned in MS4 requirements
   - **Git integration**: DVC metadata files are small and git-friendly
   - **Remote storage**: Uses GCS as remote storage backend
   - **Pipeline tracking**: Can track data dependencies in ML pipelines

3. **Reproducibility**
   - **Git commits**: DVC links data versions to git commits
   - **Metadata files**: `.dvc` files track data hashes and versions
   - **Clear history**: `dvc diff` and `dvc show` provide version history
   - **Team collaboration**: Shared remote storage with version control

4. **MS4 Alignment**
   - **Explicitly mentioned**: MS4 requirements reference DVC as an example
   - **Standard approach**: Common tool in ML/data science workflows
   - **Documentation**: Well-documented with clear usage patterns

## Version History and Tracking

### DVC Version Tracking

DVC tracks data versions through:

#### 1. DVC Metadata Files (`.dvc`)
- **Location**: Git-tracked `.dvc` files at DVC root (where `dvc init` was run, typically project root)
- **Contains**: File/directory hashes (checksums), remote storage paths, file sizes
- **Purpose**: Links data files to git commits for reproducibility
- **Format**: YAML files with checksums and remote URLs
- **Why in Git?**: The `.dvc` file is **NOT stored in GCS** - only the actual data files are. The `.dvc` file must be in git to:
  - Link data versions to code commits (reproducibility)
  - Enable `git log chroma.dvc` to see data version history
  - Allow `dvc pull` to know which data version to retrieve
  - Track which code version used which data version
- **Note**: When `dvc add /chroma` is run with an absolute path, it creates `chroma.dvc` at the filesystem root (`/chroma.dvc`). The code checks multiple locations to find the file: `/chroma.dvc`, `/workspace/chroma.dvc`, and project root.

#### 2. Git Integration
- **DVC files in git**: Small `.dvc` metadata files committed to git
- **Data in remote**: Actual large files stored in GCS (configured as DVC remote)
- **Version linking**: Each git commit with `.dvc` changes represents a data version
- **History**: `git log` shows data version changes alongside code changes

#### 3. Remote Storage (GCS) - Single Location

**Operational Storage** (`gs://<bucket>/chromadb/`):
- **Purpose**: Primary storage for RAG service operation
- **Used by**: RAG service downloads from here on startup
- **Managed by**: Custom GCS sync code in `rag.py`
- **Access**: Direct GCS Python client upload/download
- **What's stored**: The actual ChromaDB data files (binary files, vectors, etc.)
- **What's NOT stored**: The `.dvc` metadata files (these go in git, not GCS)

**Note**: ChromaDB data is stored in **one location only** (`chromadb/`):
- No duplication - data stored once in operational storage
- Version tracking via `.dvc` files in git (contains data hashes)
- Reproducibility maintained through git commits linking code to data hashes

### Version History Workflow

**Automatic Versioning (Current Implementation):**

```
1. Developer runs: python rag.py --ingest
   ↓
2. Ingestion creates/updates data files:
   - ChromaDB vector database (stored at CHROMADB_SERVER_DATA_PATH, default /chroma)
   ↓
3. Automatic GCS sync: ChromaDB data uploaded to gs://<bucket>/chromadb/ (operational)
   ↓
4. Automatic DVC versioning (if DVC is initialized): 
   - System checks if `.dvc` directory exists (in current working directory or project root)
   - If initialized: DVC adds ChromaDB data to tracking (`dvc add --no-commit /chroma`)
   - Creates/updates `.dvc` metadata file at DVC root (project root) with data hash
   - **Important**: `--no-commit` flag keeps original files in place (not moved to `.dvc/cache/`)
   - This ensures ChromaDB server and GCS sync continue to work with original file locations
   - **Note**: `dvc push` is skipped - data remains only in operational storage (no duplication)
   - If not initialized: Versioning is skipped with a warning (ingestion still succeeds)
   ↓
5. Automatic GCS upload of `.dvc` file:
   - `.dvc` file uploaded to `gs://<bucket>/dvc-metadata/chroma_<timestamp>.dvc` (versioned)
   - Also uploaded as `gs://<bucket>/dvc-metadata/chroma_latest.dvc` (for easy access)
   - Works in Docker containers where git may not be available
   ↓
6. Manual git commit (when ready):
   - Download `.dvc` file from GCS: `gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc`
   - Commit to git: `git add chroma.dvc .dvc/ && git commit -m "Update ChromaDB data version"`
   ↓
7. Version history available:
   - git log chroma.dvc (see data version changes)
   - dvc diff (compare data versions)
   - dvc show chroma.dvc (view data details)
```

**Note:** DVC versioning is automatic after each ingestion **if DVC is initialized**. If DVC is not initialized, ingestion will succeed but versioning will be skipped (with a warning). 

**Important**: 
- The `.dvc` metadata file is created/updated locally by `dvc add` with data hash
- The `.dvc` file is **automatically uploaded to GCS** after ingestion (works in Docker!)
- The `.dvc` file is **also stored in GCS** at `gs://<bucket>/dvc-metadata/` for easy access
- The `.dvc` file **MUST be in git** to link data versions to code commits (required for reproducibility)
- **Git commit is manual** - download from GCS and commit when ready

**Why `.dvc` files need to be in git:**
- Links data versions to code commits (reproducibility requirement)
- Enables `git log chroma.dvc` to see data version history
- Allows verification that data hash matches the version in git
- Without it in git, you lose the connection between code and data versions

## Setup Instructions

### Initial DVC Setup

**Important:** DVC must be initialized and configured before ingestion. The system checks if DVC is initialized (by looking for `.dvc` directory) before running versioning commands. If DVC is not initialized, versioning will be skipped (with a warning) but ingestion will still succeed.

**Required Setup (before first ingestion):**

```bash
# 1. Install DVC (already in pyproject.toml dependencies: dvc[gs]>=3.0.0)
# DVC is installed in the Docker container automatically

# 2. Initialize DVC in project root (run from project root directory)
dvc init

# 3. Configure remote storage
# Uses GCS bucket from GCS_BUCKET_NAME environment variable
# Replace <bucket-name> with your actual GCS bucket name
dvc remote add -d myremote gs://<bucket-name>/dvc-storage

# 4. Verify DVC is configured
dvc remote list  # Should show myremote pointing to gs://<bucket-name>/dvc-storage

# 5. After ingestion, ChromaDB data is automatically added to DVC
# The .dvc file will be created at project root (e.g., chroma.dvc)
# Commit DVC metadata files to git:
git add chroma.dvc .dvc/
git commit -m "Add RAG data to DVC"
```

**Note:** The Dockerfile copies `.dvc/` directory into the container (line 80), so DVC configuration must be set up at the project root before building the Docker image.

### Equivalent to "dvc pull"

To retrieve a specific version of the RAG data:

#### Option 1: Latest Version (Default)
```bash
# Pull latest data from DVC remote
dvc pull

# Or in Docker build/run
docker build -t rag-service:latest -f src/rag/Dockerfile .
docker run --rm --env-file src/rag/.env rag-service:latest
```

#### Option 2: Specific Git Commit Version
```bash
# 1. Checkout specific git commit
git checkout <commit-hash>

# 2. Pull corresponding data version
dvc pull

# 3. Verify data version
dvc show chroma.dvc
```

#### Option 3: Manual DVC Commands
```bash
# List available data versions
git log --oneline chroma.dvc

# Compare data versions
dvc diff HEAD~1 chroma

# Show data details
dvc show chroma.dvc
```

### Version Verification

```bash
# Check current DVC status
dvc status

# View data file info
dvc show chroma.dvc

# Verify data integrity
dvc check

# Compare with remote
dvc diff chroma
```

## Complete Workflow Example

This section provides a complete step-by-step example of the DVC workflow from ingestion to git commit.

### Prerequisites

Before starting, ensure:
1. DVC is initialized in your project root
2. DVC remote is configured to point to your GCS bucket
3. GCS credentials are set up (via `GOOGLE_APPLICATION_CREDENTIALS`)

### Step-by-Step Workflow

#### Step 1: Run Ingestion

Run the ingestion command. This will automatically:
- Process documents and create embeddings
- Store data in ChromaDB
- Upload ChromaDB data to GCS (operational storage)
- Run DVC versioning (if DVC is initialized)
- Upload `.dvc` file to GCS

```bash
# From project root, run ingestion in Docker container
docker run --rm --env-file src/rag/.env rag-service:latest python rag.py --ingest

# Or if running locally (not in Docker)
cd src/rag
python rag.py --ingest
```

**Expected output:**
```
[INFO] ChromaDB data added to DVC tracking
[INFO] .dvc file uploaded to GCS: dvc-metadata/chroma_20241215_143022.dvc and dvc-metadata/chroma_latest.dvc
```

**Note**: If DVC is not initialized, you'll see a warning but ingestion will still succeed.

#### Step 2: Download .dvc File from GCS (MANUAL)

After ingestion, the `.dvc` file is **automatically uploaded to GCS**, but you need to download it to your local filesystem before committing to git.

**Download options:**
```bash
# Option 1: Download from GCS (recommended - works even if container is removed)
gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc

# Option 2: Copy from container (if container still running)
docker cp <container-name>:/chroma.dvc ./chroma.dvc
```

**Note**: The file is at `/chroma.dvc` (root) because we use absolute path `/chroma` with `dvc add`.

#### Step 3: Manual Git Commit (REQUIRED)

Git commit is always manual to give you control over when to create version history commits:

```bash
# Download from GCS (if not already done)
gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc

# Or copy from container (if container still running)
docker cp <container-name>:/chroma.dvc ./chroma.dvc

# Commit manually
git add chroma.dvc .dvc/
git commit -m "Update ChromaDB data version"
git push  # optional, but recommended
```

### Complete Example Workflow

Here's a complete example from start to finish:

```bash
# 1. Navigate to project root
cd /path/to/CSCI115-AI-Agent

# 2. Ensure DVC is initialized (one-time setup)
dvc init
dvc remote add -d myremote gs://your-bucket-name/dvc-storage

# 3. Run ingestion (triggers automatic DVC versioning)
docker run --name rag-ingest --env-file src/rag/.env rag-service:latest python rag.py --ingest

# Expected output:
# [INFO] Processing documents...
# [INFO] ChromaDB data uploaded to GCS
# [INFO] ChromaDB data added to DVC tracking
# [INFO] .dvc file uploaded to GCS: dvc-metadata/chroma_<timestamp>.dvc and dvc-metadata/chroma_latest.dvc

# 4. Download chroma.dvc file from GCS (recommended)
gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc

# Or copy from container (if container still running)
docker cp rag-ingest:/chroma.dvc ./chroma.dvc
docker rm rag-ingest

# 5. Verify DVC file was copied
ls -la chroma.dvc

# 6. Check git status
git status
# On branch main
# Changes not staged for commit:
#   modified:   chroma.dvc

# 7. Stage and commit DVC metadata
git add chroma.dvc .dvc/
git commit -m "Update ChromaDB data version - 2024-12-XX"

# 8. Push to remote (optional)
git push
```

### Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Ingestion (in Docker container)                     │
│ docker run ... python rag.py --ingest                        │
│                                                              │
│  ├─ Process documents                                        │
│  ├─ Create embeddings                                        │
│  ├─ Store in ChromaDB                                        │
│  ├─ Upload to GCS (operational)                             │
│  └─ [AUTOMATIC] DVC versioning:                              │
│      ├─ dvc add --no-commit /chroma → creates /chroma.dvc  │
│      │  (inside container at root, NOT on local filesystem) │
│      └─ GCS upload → uploads .dvc file to GCS (automatic)  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Download .dvc File from GCS (MANUAL)               │
│ gsutil cp gs://bucket/dvc-metadata/chroma_latest.dvc        │
│   ./chroma.dvc                                               │
│                                                              │
│ Or copy from container: docker cp <container>:/chroma.dvc   │
│   ./chroma.dvc                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Git Commit (MANUAL)                                 │
│ git add chroma.dvc .dvc/                                     │
│ git commit -m "Update ChromaDB data version"                │
│ git push                                                     │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### DVC Not Running Automatically

**Problem**: Ingestion completes but no DVC versioning happens.

**Solution**: Check if DVC is initialized:
```bash
# Check if .dvc directory exists
ls -la .dvc/
# Should show: config, cache/, etc.

# If missing, initialize DVC
dvc init
dvc remote add -d myremote gs://<bucket>/dvc-storage
```

### DVC Add Fails

**Problem**: `dvc add` fails with authentication error.

**Solution**: Ensure GCS credentials are set:
```bash
# Check credentials
echo $GOOGLE_APPLICATION_CREDENTIALS
# Should point to your service account JSON file

# Or set it explicitly
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcs-key.json
```

### Git Commit Shows No Changes

**Problem**: `git status` doesn't show `chroma.dvc` as modified.

**Solution**: The file might not have changed (same data hash):
```bash
# Check if file exists
ls -la chroma.dvc

# Force check DVC status
dvc status

# If data actually changed, re-run ingestion
# If data is the same, no commit needed (data unchanged)
```

### chroma.dvc File Not Found Locally

**Problem**: After ingestion, `chroma.dvc` file doesn't exist on local filesystem.

**Cause**: When running in Docker, `chroma.dvc` is created **inside the container** at `/chroma.dvc` (filesystem root), not on your local filesystem. However, it's automatically uploaded to GCS.

**Solution**:
```bash
# Option 1: Download from GCS (recommended - works even if container is removed)
gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc

# Option 2: Copy from container (if container still running)
docker cp <container-name>:/chroma.dvc ./chroma.dvc

# Or if container was removed, run ingestion again and copy:
docker run --name rag-ingest --env-file src/rag/.env rag-service:latest python rag.py --ingest
docker cp rag-ingest:/chroma.dvc ./chroma.dvc
docker rm rag-ingest

# Verify file exists locally
ls -la chroma.dvc
```

## Quick Reference Commands

```bash
# Complete workflow (after initial setup)
docker run --rm --env-file src/rag/.env rag-service:latest python rag.py --ingest
gsutil cp gs://<bucket>/dvc-metadata/chroma_latest.dvc ./chroma.dvc
git add chroma.dvc .dvc/
git commit -m "Update ChromaDB data version"
git push

# Check DVC status
dvc status

# View DVC file info
dvc show chroma.dvc

# Compare versions
dvc diff HEAD~1 chroma

# Pull specific version
git checkout <commit-hash>
dvc pull
```

## LLM-Generated Data

### Pre-Trained Embeddings (No LLM Generation)

The RAG system uses **pre-trained embeddings** from BAAI (Beijing Academy of AI):
- **Model**: `BAAI/bge-small-en-v1.5`
- **Type**: Sentence transformer (not LLM-generated)
- **Training**: Pre-trained on diverse English text
- **No fine-tuning**: Model used as-is for reproducibility

### Prompt and Output Tracking

Since RAG does not generate LLM content (only retrieves from documents), there are no LLM prompts or outputs to version. The system:
1. **Ingests** existing financial documents
2. **Embeds** using pre-trained model
3. **Retrieves** relevant chunks for queries

No LLM generation occurs in the RAG pipeline.

## Reproducibility Guarantees

### What is Reproducible?

**Fully Reproducible**:
- Ingestion process (same documents → same chunks)
- Embedding generation (deterministic pre-trained model)
- Chunking parameters (recorded in `chunk_stats.json`)
- Code version (git commit)
- Data version (DVC tracked)

**Partially Reproducible**:
- Exact vector values (may vary slightly with ONNX runtime versions)
- ChromaDB internal structure (HNSW index may differ)
- Query results (semantic similarity is approximate)

### Reproducibility Workflow

To reproduce a specific RAG state:

1. **Checkout code version**: `git checkout <commit-hash>`
2. **Pull corresponding data**: `dvc pull`
3. **Verify data version**: `dvc show chroma.dvc`
4. **Run ingestion** (if needed): `python rag.py --ingest`
5. **Verify**: Check ChromaDB collection count and metadata

## Best Practices

### For Developers

1. **Always commit `.dvc` files**: After `dvc add`, commit the `.dvc` metadata files
2. **Use descriptive commit messages**: Include data version info in commits
3. **Pull before working**: Run `dvc pull` after `git pull` to sync data
4. **Push after updates**: Run `dvc push` after `dvc add` to update remote
5. **Focus on ChromaDB data**: ChromaDB data is the primary versioned asset via DVC. Internal artifacts are not versioned.

### For CI/CD

1. **Install DVC**: `pip install dvc dvc-gcs` in CI environment
2. **Configure credentials**: Set up GCS credentials for DVC remote
3. **Pull data**: Run `dvc pull` before tests/ingestion
4. **Cache data**: Consider caching DVC data between CI runs

### Data Versioning Commands Reference

```bash
# Add data to DVC tracking
dvc add <file-or-dir>

# Push data to remote
dvc push

# Pull data from remote
dvc pull

# Check status
dvc status

# Compare versions
dvc diff <commit1> <commit2> <path>

# Show data info
dvc show <path>.dvc

# Remove from tracking (keep files)
dvc remove <path>.dvc

# List remotes
dvc remote list

# Update remote URL
dvc remote modify myremote url gs://new-bucket/path
```

## Summary

- **Method**: DVC (Data Version Control)
- **Justification**: Standard tool for ML/data versioning, explicitly mentioned in MS4
- **Version tracking**: `.dvc` metadata files in git, large data in GCS remote
- **Retrieval**: `dvc pull` equivalent to "dvc pull" requirement
- **Reproducibility**: Git commits + DVC metadata provide full version history
- **No LLM generation**: Uses pre-trained embeddings, no prompts/outputs to version
