# GCS Storage Integration for ChromaDB

## Quick Start

### 1. Create Bucket
```bash
gsutil mb gs://your-project-rag-storage
```

### 2. Setup Credentials
```bash
# Option A: Service Account Key
gcloud iam service-accounts create rag-storage-sa
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:rag-storage-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
gcloud iam service-accounts keys create key.json \
  --iam-account=rag-storage-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### 3. Configure
Add to `.env`:
```
USE_GCS_STORAGE=1
GCS_BUCKET_NAME=your-project-rag-storage
GCS_PATH_PREFIX=chromadb
```

### 4. Run
```bash
# Ingestion - uploads to GCS automatically
python src/rag/rag.py --ingest

# Serve - downloads from GCS on startup
python src/rag/rag.py --serve
```

## How It Works

- **Ingestion**: Downloads existing data → Processes → Uploads new data
- **Query**: Downloads on startup → Serves queries (no upload)
- **No mounts needed**: Everything stored in GCS bucket

## Cloud Run Deployment

```bash
gcloud run deploy rag-app \
  --image gcr.io/YOUR_PROJECT/rag-app \
  --service-account rag-storage-sa@YOUR_PROJECT.iam.gserviceaccount.com \
  --set-env-vars USE_GCS_STORAGE=1,GCS_BUCKET_NAME=your-bucket
```

See full documentation in the repository for details.
