#!/bin/bash

# Quantamental Pipeline - Docker Development Shell
# MS4 CI/CD Setup

set -e

# Colors
export GREEN='\033[0;32m'
export RED='\033[0;31m'
export YELLOW='\033[1;33m'
export NC='\033[0m'

# Configuration
IMAGE_NAME="quantamental"
CONTAINER_NAME="quantamental-pipeline"

echo -e "${GREEN}=== Quantamental Development Container ===${NC}"
echo ""

# Check for required environment variables
if [ -z "$WANDB_API_KEY" ]; then
    echo -e "${YELLOW}Warning: WANDB_API_KEY not set. W&B tracking will not work.${NC}"
fi

if [ -z "$GCS_BUCKET_NAME" ]; then
    echo -e "${YELLOW}Warning: GCS_BUCKET_NAME not set. Cloud storage will not work.${NC}"
fi

# Check for GCS service account
if [ -f "secrets/gcs-service-account.json" ]; then
    echo -e "${GREEN}✓ Found GCS service account${NC}"
    GCS_MOUNT="-v $(pwd)/secrets:/app/secrets"
    GCS_ENV="-e GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcs-service-account.json"
else
    echo -e "${RED}✗ No GCS service account found${NC}"
    GCS_MOUNT=""
    GCS_ENV=""
fi

# Build the image
echo -e "${GREEN}Building Docker image...${NC}"
docker build -t $IMAGE_NAME -f Dockerfile .

echo ""
echo -e "${GREEN}Starting development container...${NC}"
echo -e "${YELLOW}Inside the container, you can run:${NC}"
echo "  • pytest tests/ -v              # Run tests"
echo "  • flake8 *.py                   # Lint code"
echo "  • black *.py                    # Format code"
echo "  • python main.py                # Run pipeline"
echo ""

# Run the container
docker run --rm -it \
    --name $CONTAINER_NAME \
    -v "$(pwd)":/app \
    $GCS_MOUNT \
    -e WANDB_API_KEY="${WANDB_API_KEY}" \
    -e GCS_BUCKET_NAME="${GCS_BUCKET_NAME}" \
    -e FMP_API_KEY="${FMP_API_KEY}" \
    $GCS_ENV \
    $IMAGE_NAME \
    /bin/bash

echo -e "${GREEN}Container exited${NC}"
