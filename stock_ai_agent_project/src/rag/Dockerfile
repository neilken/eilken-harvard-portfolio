# Single-image: ChromaDB server + RAG app with GCS Python client sync
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROMA_TELEMETRY_DISABLED=1 \
    POSTHOG_DISABLED=true \
    OMP_NUM_THREADS=1

# Install system dependencies (no FUSE needed - using Python client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates wget git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install ChromaDB server (CLI needed for 'chroma run' command)
# Pin version to match pyproject.toml to avoid conflicts
RUN pip install --no-cache-dir "chromadb>=1.0.0"

# (Optional) uv for fast, reproducible installs
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/.venv
ENV PATH="/.venv/bin:${PATH}"

# All app paths will live under /workspace
WORKDIR /workspace

# Project metadata + app code
# Build context is root directory, so paths are relative to root
COPY src/rag/pyproject.toml ./
COPY src/rag/rag.py ./

# Note: .env file is NOT copied into image for security and flexibility
# Use --env-file at runtime: docker run --env-file src/rag/.env ...

# GCS service account key from shared secrets directory
# Build context should be root directory (CSCI115-AI-Agent) to access secrets/
COPY secrets/gcs-key.json* ./gcs-key.json

# Install Python deps declared in pyproject.toml
RUN uv sync

# Bake docs into the image so you don't need -v mounts
# Everything under src/rag/data/ on the host becomes /workspace/data in the image
COPY src/rag/data/ /workspace/data/

# Create ChromaDB data directory (will be synced with GCS using Python client)
RUN mkdir -p /chroma

# Expose FastAPI port and ChromaDB port
EXPOSE 8000

# Use Python directly - rag.py handles ChromaDB server startup
ENTRYPOINT ["/.venv/bin/python", "rag.py"]


  


