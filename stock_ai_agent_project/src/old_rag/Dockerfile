# Use the official Debian-hosted Python image
FROM python:3.12-slim-bookworm

ARG DEBIAN_PACKAGES="build-essential curl ca-certificates wget git"
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 PYTHONUNBUFFERED=1

# --- Install minimal OS deps ---
RUN set -ex \
 && apt-get update \
 && apt-get install -y --no-install-recommends $DEBIAN_PACKAGES \
 && rm -rf /var/lib/apt/lists/*

# --- Install uv (fast Python package manager) ---
# Installs to /root/.local/bin/uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && ln -s /root/.local/bin/uv /usr/local/bin/uv

# uv config: create a single venv at /.venv and copy wheels for speed
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/.venv

# --- Environment defaults (match your .env) ---
ENV API_PORT=8000 \
    VECTOR_STORE_PATH=./volumes/chroma \
    VECTOR_COLLECTION=stocks_rag_v1 \
    DATA_DIR=./data \
    ARTIFACTS_DIR=./artifacts \
    CHUNK_SIZE=1200 \
    CHUNK_OVERLAP=200 \
    EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \
    CHROMA_TELEMETRY_DISABLED=1

# --- Set workdir and copy project files ---
WORKDIR /workspace

# Copy pyproject first to leverage Docker layer caching for deps
COPY pyproject.toml /workspace/pyproject.toml

# Sync dependencies into the project venv
# Use --frozen if/when you add a uv.lock to pin versions.
RUN uv sync

# Now copy the rest of the app
COPY rag.py /workspace/rag.py
# Keep these as bind mounts at runtime, but create placeholders so paths exist:
RUN mkdir -p /workspace/data /workspace/artifacts /workspace/volumes/chroma

# Document the API port and add a simple healthcheck
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD \
  wget -qO- http://localhost:${API_PORT}/health || exit 1

# Run as root to avoid Windows bind-mount permission issues
USER root

# Entrypoint runs the CLI; default CMD serves the API
ENTRYPOINT ["/.venv/bin/python", "/workspace/rag.py"]
CMD ["--serve"]

  


