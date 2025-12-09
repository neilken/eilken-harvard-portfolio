#!/bin/bash

# exit immediately if a command exits with a non-zero status
set -e

# Define some environment variables
export IMAGE_NAME="stockbusters-app-api-service"
export BASE_DIR=$(pwd)
export SECRETS_DIR=$(pwd)/../../../secrets/
export PERSISTENT_DIR=$(pwd)/../../../persistent-folder/
export GCP_PROJECT="stock-busters-cs115" # CHANGE TO YOUR PROJECT ID
export GCS_BUCKET_NAME="fin-data-bucket-115"
export CHROMADB_HOST="stock-busters-chroma-bucket"
export CHROMADB_PORT=8000

# Create the network if we don't have it yet
docker network inspect stockbusters-app-network >/dev/null 2>&1 || docker network create stockbusters-app-network

# Build the image based on the Dockerfile
# docker build --no-cache -t $IMAGE_NAME -f Dockerfile .
docker build -t $IMAGE_NAME -f Dockerfile .

# Run the container
docker run --rm --name $IMAGE_NAME -ti \
-v "$BASE_DIR":/app \
-v "$SECRETS_DIR":/secrets \
-v "$PERSISTENT_DIR":/persistent \
-p 9000:9000 \
-e DEV=1 \
-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/stock-busters-service-account.json \
-e GCP_PROJECT=$GCP_PROJECT \
-e GCS_BUCKET_NAME=$GCS_BUCKET_NAME \
-e CHROMADB_HOST=$CHROMADB_HOST \
-e CHROMADB_PORT=$CHROMADB_PORT \
--network stockbusters-app-network \
$IMAGE_NAME