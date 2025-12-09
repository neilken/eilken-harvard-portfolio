# Quantamental Model - Dockerfile for MS4 CI/CD
# Multi-stage build for efficient image size


FROM python:3.11-slim-bookworm AS builder

# Prevent apt from showing prompts
ENV DEBIAN_FRONTEND=noninteractive

# Python configuration
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Install testing and linting tools (MS4 requirement)
RUN pip install --no-cache-dir --user \
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    pytest-asyncio==0.21.1 \ 
    flake8==6.1.0 \
    black==23.11.0 \
    pre-commit==3.5.0

# Final stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy ALL application code (for MS4 testing)
COPY __init__.py .
COPY config.yaml .
COPY pytest.ini .
COPY coverage.ini .
COPY utils.py .
COPY data_collect.py .
COPY data_process.py .
COPY data_versioning.py .
COPY hybrid_scoring.py .
COPY model_train.py .
COPY model_predict.py .
COPY model_validation.py .
COPY backtest.py .
COPY main.py .
COPY verify_setup.py .
COPY generate_stock_reasoning.py .

# Copy tests directory
COPY tests/ ./tests/

# Create necessary directories
RUN mkdir -p data configs outputs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Default command (can be overridden for testing)
CMD ["python", "main.py"]

# Labels
LABEL maintainer="Stock Busters - Team Stock Buster"
LABEL description="Quantamental Model for Stock Screening - MS4 CI/CD"
LABEL version="2.0-ms4"
