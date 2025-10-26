# ==========================
# Finance Data Pipeline
# ==========================

FROM python:3.12-slim-bookworm

ARG DEBIAN_PACKAGES="build-essential curl"

# --- Base environment setup ---
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/home/app/.venv

# Path to GCP service account key
#ENV GOOGLE_APPLICATION_CREDENTIALS="secrets/ai-stock-screener-474813-f2e644955fcf.json"
ENV GCP_PROJECT="stock-busters-cs115"
ENV GOOGLE_APPLICATION_CREDENTIALS="/secrets/stock-busters-service-account.json"

# --- System setup ---
RUN set -ex; \
    for i in $(seq 1 8); do mkdir -p "/usr/share/man/man${i}"; done && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends $DEBIAN_PACKAGES && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip && \
    pip install uv && \
    useradd -ms /bin/bash app -d /home/app -u 1000 && \
    mkdir -p /app && \
    chown app:app /app

# --- Switch to non-root user ---
USER app
WORKDIR /app

# --- Copy project files ---
# Use --chown to ensure permissions for app user
COPY --chown=app:app . /app/
#COPY --chown=app:app secrets/ /app/secrets/

# --- Sync Python environment with uv ---
RUN uv sync

# --- Default entrypoint and command ---
# Use uv's virtual environment automatically, then run your Python script
ENTRYPOINT ["/bin/bash", "-c", "source /home/app/.venv/bin/activate && python data_download.py"]
