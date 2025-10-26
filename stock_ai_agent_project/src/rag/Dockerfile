# Single-image for ingest + API (no host mounts needed)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates wget git && \
    rm -rf /var/lib/apt/lists/*

# (Optional) uv for fast, reproducible installs
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/.venv
ENV PATH="/.venv/bin:${PATH}"

# All app paths will live under /workspace
WORKDIR /workspace

# Project metadata + app code
COPY pyproject.toml ./
COPY rag.py ./

# Install Python deps declared in pyproject.toml
RUN uv sync

# --- Bake docs into the image so you don't need -v mounts ---
# Everything under src/rag/data/ on the host becomes /workspace/data in the image
COPY data/ /workspace/data/

# Default entrypoint; pass flags at docker run (e.g., --ingest --serve)
ENTRYPOINT ["/.venv/bin/python", "rag.py"]


  


