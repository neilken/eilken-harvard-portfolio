#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define environment variables
export IMAGE_NAME="rag-service"

# Build the Docker image
echo "Building Docker image: $IMAGE_NAME"
docker build -t $IMAGE_NAME -f src/rag/Dockerfile .

# Start an interactive bash shell in the container
echo "Starting interactive container shell: $IMAGE_NAME"
docker run --rm -ti \
  --name $IMAGE_NAME \
  -p 9000:9000 \
  -p 8000:8000 \
  -v "$(pwd)/src/rag:/workspace" \
  $IMAGE_NAME /bin/bash

