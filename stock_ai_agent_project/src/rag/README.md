# RAG — Containerized Retrieval-Augmented Generation (FastEmbed + Chroma + FastAPI)

A minimal, reproducible Retrieval-Augmented Generation (RAG) system built with:
- FastEmbed for sentence embeddings (`BAAI/bge-small-en-v1.5`)
- Chroma for persistent vector storage
- FastAPI for serving queries
Everything runs in a single Docker image
---
## RAG Layout
```
RAG/
│
├─ data/                  # source docs (.pdf, .txt, .md)
│
├─ artifacts/             # pipeline outputs
│  ├── sanitized/ # cleaned text chunks
│  ├── ingest_summary.json # ingest summary
│  ├── metadata.json # metadata about ingested docs
│  ├── retrieval_sample.json # retrieval sample
│  └── sample_vector.json # vector embedding sample
│
├─ screenshot_logs/       # log screenshots of building and running container
│  ├─ docker build rag image.png         
│  ├─ docker running container.png   
│  ├─ pulling sample vector from chromadb.png
│  └─ Sample Query in Container.png
│
├─ volumes/
│  └─ chroma/             # persisted Chroma vector store
│
├─ rag.py                 # SINGLE Python file (CLI + pipeline + API)
├─ pyproject.toml         # runtime dependencies
├─ Dockerfile             # single image for ingest + serve
├─ .env                   # local config 
├─ uv.lock                # uv lock file
└─ README.md
```
---
## Prerequisites
- Windows PowerShell (or WSL / Bash)
- Docker Desktop (with WSL2 backend)

## Configuration
Your `.env` should contain:
```
API_PORT=8000
VECTOR_STORE_PATH=/workspace/volumes/chroma
VECTOR_COLLECTION=stocks_rag_v1
DATA_DIR=/workspace/data
ARTIFACTS_DIR=/workspace/artifacts
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
CHROMA_TELEMETRY_DISABLED=1
```
---

## Quick Start
1. Ensure you are in the AC215_StockBusters folder as your working directory

Example:
```
cd AC215_StockBusters
(base) PS C:\Users\user\AC215_StockBusters>
```
2. Optional: Clean up any old container name
```
docker rm -f ac215-rag 2>$null
```
3. Build the image  
```
docker build -t ac215-rag -f src\rag\Dockerfile src\rag
```
4. Run everything (Ingest + Serve in one container)  
```
docker run -it -p 8000:8000 --env-file src\rag\.env --name ac215-rag ac215-rag --ingest --dump-vector --serve
```


This:
- Ingests documents from `data/`
- Cleans and saves text in `artifacts/sanitized/`
- Records chunking info in `artifacts/injest_summary.json`
- Writes ingest metadata to `artifacts/metadata.json`
- Builds a vector store in `volumes/chroma/`
- Prints chunks and vectors for visualization
- Starts the FastAPI server on port 8000
- Outputs sample vector from ChromaDB in `artifacts/`

```
# For only ingestion (no querying)
docker run -it --env-file src\rag\.env ac215-rag
```
# Optional API:
Once running, open:  
http://localhost:8000/docs  
to see the interactive API docs.

## Query Example (PowerShell pretty JSON)
After the container is running, run this from another PowerShell window:
```
irm -Method Post -Uri "http://localhost:8000/query" -ContentType "application/json" -Body (@{ q = "Explain P/E ratio"; k = 5 } | ConvertTo-Json) | ConvertTo-Json -Depth 6
```
Example output:
```
{
  "query": "Explain P/E ratio",
  "results": [
    {
      "doc": "The P/E ratio (price-to-earnings ratio) measures how much investors are willing to pay per dollar of earnings...",
      "score": 0.88,
      "source": "PrinciplesofFinanceSample.pdf"
    }
  ]
}
```

## Dump a Sample Vector
```
docker run -it --env-file src\rag\.env ac215-rag --dump-vector
```
This saves:
artifacts/sample_vector.json  
Example contents:
```
{
  "collection": "stocks_rag_v1",
  "id": "chunk_0001",
  "vector_dim": 384,
  "vector": [0.0123, -0.0058, 0.0449, ...]
}
```

## Stop the container
Press Ctrl + C in the terminal window where it’s running.  
If you ran it detached (with -d), stop it with:  
```
docker rm -f ac215-rag
```

## Copy artifacts and vector store to local
```
docker cp ac215-rag:/workspace/artifacts .\artifacts
docker cp ac215-rag:/workspace/volumes .\volumes
```

---
---
## Summary
| Step              | Command                                                                                                                             | Purpose                                  |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------|
| Build image       | `docker build -t ac215-rag -f src\rag\Dockerfile src\rag`                                                                           | Build the image                          |
| Run end-to-end    | `docker run -it -p 8000:8000 --env-file src\rag\.env --name ac215-rag ac215-rag --ingest --serve`                                   | Ingest & serve in one persistent container |
| Run ingest only   | `docker run -it --env-file src\rag\.env ac215-rag`                                                                                  | Run ingestion only (default behavior)    |
| Run API only      | `docker run -it -p 8000:8000 --env-file src\rag\.env --name ac215-rag ac215-rag --serve`                                            | Start the FastAPI server only            |
| Query             | (PowerShell) `irm -Method Post -Uri "http://localhost:8000/query" -ContentType "application/json" -Body (@{ q = "Explain P/E ratio"; k = 5 } | ConvertTo-Json) | ConvertTo-Json -Depth 6` | Query the API                              |
| Dump vector       | `docker run -it --env-file src\rag\.env ac215-rag --dump-vector`                                                                    | Inspect one embedding                     |
| Stop API          | `Ctrl + C` (if foreground) or `docker rm -f ac215-rag` (if detached)                                                                | Stop container                            |
| Copy artifacts    | `docker cp ac215-rag:/workspace/artifacts .\artifacts`<br>`docker cp ac215-rag:/workspace/volumes .\volumes`                         | Copy results & vector DB to host          |


---

## MS2 RAG Deliverables

| **Deliverable**                                                                             | **Repository Location**              | **Description**                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Screenshot of running instances (cloud or local)**                                        | `RAG/screenshot_logs/`               | Screenshots showing Docker container(s) or local PowerShell instances running the RAG pipeline (e.g., build, run, query, and vector retrieval).                                                                                                                    |
| **Documentation and Build Instructions**                                                    | `RAG/Dockerfile` and `RAG/README.md` | Comprehensive documentation of the RAG pipeline design, architecture, configuration, and run instructions. Includes the Dockerfile used to build the containerized environment and the “Quick Start” guide for ingestion and API serving.                          |
| **pyproject.toml (using uv)**                                                               | `RAG/pyproject.toml`                 | Defines Python dependencies and environment configuration for the container (managed with **uv**).                                                                                                                                                                  |
| **Scripts or docker-compose.yml (when applicable)**                                         | `RAG/rag.py` *(main script)*         | `rag.py` acts as the unified CLI and pipeline script handling ingestion, chunking, embedding, vector storage, and API serving. *(No docker-compose.yml is required because the pipeline runs with a single Dockerfile command. docker-composed moved to _archived folder)*                                   |
| **Containerized RAG pipeline with scripts for chunking, vectorization, and DB integration** | `RAG/rag.py`                         | Implements ingestion, sanitization, text splitting, embedding (FastEmbed), and vector store integration (Chroma).                                                                                                            |
| **Pipeline Evidence and Logs**                                                              | `RAG/artifacts/`                     | Contains automatically generated outputs and logs verifying end-to-end pipeline execution — including cleaned text (`sanitized/`), chunking summaries (`metadata.json`), ingestion logs (`ingest_summary.json`), and sample embeddings (`sample_vector.json`). |
