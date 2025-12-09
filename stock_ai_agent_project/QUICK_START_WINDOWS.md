# Quick Start Guide for Windows PowerShell

Complete step-by-step instructions to build and run the RAG application with GCS storage on Windows.

## Prerequisites

1. **Docker Desktop** installed and running
2. **GCS Service Account Key** (`gcs-key.json`) in `src/rag/` directory
3. **Documents** in `src/rag/data/` directory (PDF, TXT, MD files)

## Project Structure

```
CSCI115-AI-Agent/
├── src/rag/
│   ├── rag.py              # Main application
│   ├── pyproject.toml      # Dependencies
│   ├── Dockerfile          # Docker build instructions
│   ├── .env                # Configuration
│   ├── gcs-key.json        # GCS credentials
│   ├── data/               # Your documents go here
│   └── .dockerignore       # Docker ignore file
```

## Step 1: Navigate to Project Directory

Open PowerShell and navigate to the project:

```powershell
cd C:\Users\eilke\CSCI115-AI-Agent\src\rag
```

## Step 2: Verify Files Are Present

Check that all required files exist:

```powershell
Get-ChildItem -Filter "*.py","*.toml","Dockerfile",".env","gcs-key.json"
```

Expected output:
```
Name           Length
----           ------
.env             1453
Dockerfile       1230
gcs-key.json     2366
pyproject.toml    667
rag.py          44058
```

## Step 3: Check Configuration

Verify your GCS settings in `.env`:

```powershell
Get-Content .env | Select-String "GCS"
```

Expected output:
```
USE_GCS_STORAGE=1
GCS_BUCKET_NAME=ac215-chroma-bucket
GCS_SERVICE_ACCOUNT_KEY=gcs-key.json
```

## Step 4: Build Docker Image

Build the application Docker image:

```powershell
docker build -t rag-app .
```

**First build:** Takes 3-5 minutes (downloads dependencies)
**Subsequent builds:** 10-30 seconds (uses cache)

Expected output:
```
[+] Building ... FINISHED
 => importing cache
 => building application
 => Successfully tagged rag-app:latest
```

## Step 5: Add Your Documents

Place your documents (PDF, TXT, MD files) in the `data/` directory:

```powershell
# Copy documents
Copy-Item "C:\path\to\your\documents\*.pdf" -Destination "data\"
Copy-Item "C:\path\to\your\documents\*.txt" -Destination "data\"

# Or manually copy files via Explorer
```

## Step 6: Run Ingestion

Process documents and upload to GCS:

```powershell
docker run --rm rag-app --ingest
```

Expected output:
```
[INFO] Downloading vector store from GCS: gs://ac215-chroma-bucket/chromadb
[INFO] Loaded 21 documents
Processing document 10/21
Processing document 21/21
[INFO] Uploading vector store to GCS: gs://ac215-chroma-bucket/chromadb
[INFO] Successfully uploaded to GCS
Indexed 21 chunks into collection 'stocks_rag_v1'
```

**What happens:**
1. Downloads existing vectors from GCS (if any)
2. Processes documents and creates embeddings
3. Creates GCS bucket if it doesn't exist
4. Uploads ChromaDB to GCS for persistence

## Step 7: Start API Server

Start the FastAPI server:

```powershell
docker run -p 8000:8000 --rm rag-app --serve
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Server runs on:** http://localhost:8000

## Step 8: Test the API

Open a **new PowerShell window** and test the API:

### Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
```

Expected response:
```json
{"status": "healthy"}
```

### Query Documents
```powershell
$body = @{
    query = "What is momentum?"
    k = 3
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/query" -Method POST -Body $body -ContentType "application/json"
```

Expected response:
```json
{
  "query": "What is momentum?",
  "results": [
    {
      "text": "...",
      "source": "data/document.pdf#page=1"
    }
  ]
}
```

## Complete Workflow Commands

### Build and Ingest in One Go
```powershell
# Build
docker build -t rag-app .

# Ingest (processes documents, creates GCS bucket, uploads to GCS)
docker run --rm rag-app --ingest

# Serve API
docker run -p 8000:8000 --rm rag-app --serve
```

### Re-ingest After Adding Documents
```powershell
# Add new documents to data/ directory
# Then re-run ingestion (updates existing, adds new)
docker run --rm rag-app --ingest
```

Output shows:
- `Indexed 42 chunks` (updates existing + adds new)
- Uploads updated vectors to GCS

## Common Tasks

### View GCS Bucket Contents
```powershell
docker run --rm --entrypoint python rag-app -c "from google.cloud import storage; client = storage.Client.from_service_account_json('/workspace/gcs-key.json'); bucket = client.bucket('ac215-chroma-bucket'); print('\nFiles in bucket:'); [print(f'  {blob.name}') for blob in bucket.list_blobs(prefix='chromadb')]"
```

### Check Environment Variables
```powershell
docker run --rm --entrypoint cat rag-app /workspace/.env | Select-String "GCS"
```

### View Local Data Files
```powershell
Get-ChildItem data\
```

### Clean Start (Delete Local Vector Store)
```powershell
Remove-Item -Recurse -Force volumes\chroma\*
```

Then rebuild:
```powershell
docker build -t rag-app .
docker run --rm rag-app --ingest
```

## Troubleshooting

### Error: "The specified bucket does not exist"
- This is normal on first run
- The bucket is auto-created by the code
- Subsequent runs will succeed

### Error: "Failed to upload to GCS"
- Check that `gcs-key.json` exists and is valid
- Verify service account has `Storage Admin` role
- Check GCS bucket location in `.env`

### Error: "No documents found"
- Make sure files are in `src/rag/data/` directory
- Check file extensions: `.txt`, `.md`, `.pdf`
- Rebuild Docker image: `docker build -t rag-app .`

### Build is Slow
- First build downloads ~500MB of dependencies
- Subsequent builds use cache (much faster)
- If still slow, check Docker Desktop resources (Settings → Resources)

### Port 8000 Already in Use
```powershell
# Use different port
docker run -p 8001:8000 --rm rag-app --serve
```

Then access: http://localhost:8001

## Configuration Options

Edit `src/rag/.env` to customize:

```bash
# Enable/disable GCS storage
USE_GCS_STORAGE=1              # 1=enabled, 0=disabled

# Bucket settings
GCS_BUCKET_NAME=ac215-chroma-bucket
GCS_BUCKET_LOCATION=us-central1

# Chunking settings
# (edit target_tokens, max_tokens if needed)

# Performance settings
EMBED_BATCH=256               # Embedding batch size
UPSERT_BATCH=256              # ChromaDB upsert batch size
```

## Production Deployment

### On Google Cloud Run

1. **Build and push to GCR:**
```powershell
# Authenticate
gcloud auth configure-docker

# Build for Cloud Run
docker build -t gcr.io/[PROJECT-ID]/rag-app .

# Push to GCR
docker push gcr.io/[PROJECT-ID]/rag-app
```

2. **Deploy to Cloud Run:**
```powershell
gcloud run deploy rag-app `
  --image gcr.io/[PROJECT-ID]/rag-app `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --set-env-vars USE_GCS_STORAGE=1 `
  --set-env-vars GCS_BUCKET_NAME=ac215-chroma-bucket
```

3. **Access your service:**
```powershell
# Get service URL
gcloud run services describe rag-app --region us-central1 --format "value(status.url)"
```

### On Google Compute Engine

1. **SSH into instance**
2. **Clone repository**
3. **Run commands above** (Docker, build, ingest, serve)

## What Gets Stored in GCS

- **ChromaDB files:** Vector embeddings and metadata
- **SQLite database:** Index and metadata
- **Location:** `gs://ac215-chroma-bucket/chromadb/`
- **Auto-synced:** Every `--ingest` and `--serve` command

## Quick Reference

### From `src/rag/` directory:
| Task | Command |
|------|---------|
| Build | `docker build -t rag-app .` |
| Ingest | `docker run --rm rag-app --ingest` |
| Serve | `docker run -p 8000:8000 --rm rag-app --serve` |

### From root directory (`C:\Users\eilke\CSCI115-AI-Agent`):
| Task | Command |
|------|---------|
| Build | `docker build -t ac215-rag -f src\rag\Dockerfile src\rag` |
| Ingest | `docker run --rm ac215-rag --ingest` |
| Serve | `docker run -p 8000:8000 --rm ac215-rag --serve` |
| Both | `docker run -p 8000:8000 --rm ac215-rag --ingest --serve` |

### API Commands (anywhere):
| Task | Command |
|------|---------|
| Health | `Invoke-RestMethod http://localhost:8000/health` |
| Query | `Invoke-RestMethod -Method Post -Uri "http://localhost:8000/query" -ContentType "application/json" -Body (@{ query = "Explain P/E ratio"; k = 5 } \| ConvertTo-Json) \| ConvertTo-Json -Depth 6` |

## Next Steps

1. ✅ Build Docker image
2. ✅ Add documents to `data/`
3. ✅ Run ingestion (creates GCS bucket)
4. ✅ Start API server
5. ✅ Query via `/query` endpoint
6. 🔄 Add more documents and re-ingest anytime

Your ChromaDB vectors now persist in GCS! 🎉
