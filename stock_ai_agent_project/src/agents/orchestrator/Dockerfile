# Orchestrator service - Conversational AI agent with RAG integration
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reproducible installs
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && ln -s /root/.local/bin/uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/.venv
ENV PATH="/.venv/bin:${PATH}"

# Set working directory
WORKDIR /workspace

# Copy project files
# Build context is root directory, so paths are relative to root
COPY src/agents/orchestrator/pyproject.toml ./
COPY src/agents/orchestrator/orchestrator.py ./
COPY src/agents/orchestrator/test_containerized.py ./
COPY src/agents/orchestrator/verify_credentials.py ./
COPY src/agents/orchestrator/Orchasterator_01.ipynb ./

# Copy credentials file from shared secrets directory
# Build context should be root directory (CSCI115-AI-Agent) to access secrets/
COPY secrets/gcs-key.json* ./credentials.json

# Create a placeholder .env file (will be overridden by --env-file at runtime if provided)
# This prevents COPY from failing if .env doesn't exist in build context
RUN echo "# Environment variables - use --env-file .env at runtime" > .env

# Install Python dependencies
RUN uv sync

# Default command: run tests
# Override with: docker run ... orchestrator-test python orchestrator.py
# Or: docker run ... orchestrator-test python test_containerized.py
CMD ["python", "test_containerized.py"]

