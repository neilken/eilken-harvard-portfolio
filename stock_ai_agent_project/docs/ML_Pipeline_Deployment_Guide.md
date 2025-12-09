# Quantamental ML Pipeline Deployment on Cloud Run with Cloud Scheduler

## Stock Busters - Quantamental Pipeline
### CSCI-E 115 / AC215 - Milestone 5  - Sirisom Pranivong

---

## Overview

This document describes the deployment of the Quantamental ML Pipeline using **Google Cloud Run Jobs** and **Cloud Scheduler** for automated daily retraining.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ML PIPELINE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Cloud Scheduler                                               │
│   (Daily 6 AM Central)                                          │
│        │                                                        │
│        │ Triggers                                               │
│        ▼                                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Cloud Run Job                              │   │
│   │         (quantamental-pipeline)                         │   │
│   │                                                         │   │
│   │   ┌─────────────────────────────────────────────────┐   │   │
│   │   │            7-Step Pipeline                      │   │   │
│   │   │                                                 │   │   │
│   │   │  1. Data Collection (FMP API)                   │   │   │
│   │   │  2. Feature Engineering (30+ features)          │   │   │
│   │   │  3. Model Training (Random Forest)              │   │   │
│   │   │  4. Model Validation (35% threshold)            │   │   │
│   │   │  5. Prediction & Backtesting                    │   │   │
│   │   │  6. RAG Reasoning (optional)                    │   │   │
│   │   │  7. Data Versioning (W&B Artifacts)             │   │   │
│   │   │                                                 │   │   │
│   │   └─────────────────────────────────────────────────┘   │   │
│   │                                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│        │                                                        │
│        ▼                                                        │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│   │      GCS      │  │     W&B       │  │    Secret     │       │
│   │   (outputs)   │  │  (artifacts)  │  │   Manager     │       │
│   └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Google Cloud SDK (`gcloud`) installed
- Docker installed
- GCP Project with billing enabled
- Weights & Biases account
- FMP API key

---

## Deployment Steps

### Step 1: Install and Configure Google Cloud SDK

```bash
# Install gcloud (Ubuntu/WSL)
sudo snap install google-cloud-cli --classic

# Initialize and login
gcloud init

# Set project
gcloud config set project stock-busters-cs115
```

### Step 2: Enable Required APIs

```bash
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com
```

### Step 3: Set Environment Variables

```bash
export PROJECT_ID="stock-busters-cs115"
export REGION="us-central1"
```

### Step 4: Create Artifact Registry

```bash
gcloud artifacts repositories create stock-busters \
    --repository-format=docker \
    --location=$REGION \
    --description="Stock Busters containers"
```

### Step 5: Configure Docker Authentication

```bash
# Configure Docker for GCP
gcloud auth configure-docker $REGION-docker.pkg.dev

# Login to registry
gcloud auth print-access-token | sudo docker login -u oauth2accesstoken --password-stdin https://$REGION-docker.pkg.dev
```

### Step 6: Build and Push Docker Image

```bash
# Build image
sudo docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/stock-busters/quantamental-pipeline:latest .

# Push to Artifact Registry
sudo docker push $REGION-docker.pkg.dev/$PROJECT_ID/stock-busters/quantamental-pipeline:latest
```

### Step 7: Create Secrets in Secret Manager

```bash
# Create .env file (do not commit to git)
# FMP_API_KEY=your-fmp-api-key
# WANDB_API_KEY=your-wandb-api-key

# Source environment variables
source .env

# Create secrets with regional replication
echo -n "$FMP_API_KEY" | gcloud secrets create fmp-api-key \
    --data-file=- \
    --replication-policy="user-managed" \
    --locations="us-central1"

echo -n "$WANDB_API_KEY" | gcloud secrets create wandb-api-key \
    --data-file=- \
    --replication-policy="user-managed" \
    --locations="us-central1"
```

### Step 8: Grant Secret Access Permissions

```bash
# Grant Cloud Run service account access to secrets
gcloud secrets add-iam-policy-binding fmp-api-key \
    --member="serviceAccount:1037206705113-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding wandb-api-key \
    --member="serviceAccount:1037206705113-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 9: Create Cloud Run Job

```bash
gcloud run jobs create quantamental-pipeline \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/stock-busters/quantamental-pipeline:latest \
    --region=$REGION \
    --cpu=2 \
    --memory=4Gi \
    --max-retries=1 \
    --task-timeout=3600 \
    --set-env-vars="GCS_BUCKET=fin-data-bucket-115" \
    --set-secrets="FMP_API_KEY=fmp-api-key:latest,WANDB_API_KEY=wandb-api-key:latest"
```

### Step 10: Test the Job

```bash
# Execute job manually
gcloud run jobs execute quantamental-pipeline --region=$REGION

# Check execution status
gcloud run jobs executions list --job=quantamental-pipeline --region=$REGION

# View logs
gcloud run jobs executions logs quantamental-pipeline --region=$REGION
```

### Step 11: Create Cloud Scheduler

```bash
# Create service account for scheduler
gcloud iam service-accounts create scheduler-sa \
    --display-name="Cloud Scheduler Service Account"

# Grant permission to invoke Cloud Run Job
gcloud run jobs add-iam-policy-binding quantamental-pipeline \
    --region=$REGION \
    --member="serviceAccount:scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Create scheduler (daily at 6 AM US Central Time)
gcloud scheduler jobs create http trigger-quantamental-pipeline \
    --location=$REGION \
    --schedule="0 6 * * *" \
    --time-zone="America/Chicago" \
    --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/quantamental-pipeline:run" \
    --http-method=POST \
    --oauth-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com"
```

---

## Configuration Details

### Cloud Run Job Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Image** | `us-central1-docker.pkg.dev/stock-busters-cs115/stock-busters/quantamental-pipeline:latest` | Docker image |
| **CPU** | 2 | CPU cores |
| **Memory** | 4 GB | RAM allocation |
| **Timeout** | 3600 seconds (1 hour) | Max execution time |
| **Max Retries** | 1 | Retry on failure |

### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `FMP_API_KEY` | Secret Manager | Financial Modeling Prep API key |
| `WANDB_API_KEY` | Secret Manager | Weights & Biases API key |
| `GCS_BUCKET` | Environment | GCS bucket for outputs (`fin-data-bucket-115`) |

### Schedule Configuration

| Parameter | Value |
|-----------|-------|
| **Schedule** | `0 6 * * *` (Daily at 6 AM) |
| **Timezone** | America/Chicago (US Central) |
| **HTTP Method** | POST |

---

## Cron Schedule Reference

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6, Sunday = 0)
│ │ │ │ │
* * * * *
```

| Schedule | Expression | Description |
|----------|------------|-------------|
| Daily at 6 AM | `0 6 * * *` | Every day |
| Weekly (Sunday) | `0 6 * * 0` | Once a week |
| Weekdays only | `0 6 * * 1-5` | Monday to Friday |
| Monthly | `0 6 1 * *` | First of each month |

---

## Useful Commands

### Job Management

```bash
# Execute job manually
gcloud run jobs execute quantamental-pipeline --region=us-central1

# List all executions
gcloud run jobs executions list --job=quantamental-pipeline --region=us-central1

# View logs
gcloud run jobs executions logs quantamental-pipeline --region=us-central1

# Update job (after pushing new image)
gcloud run jobs update quantamental-pipeline \
    --image=us-central1-docker.pkg.dev/stock-busters-cs115/stock-busters/quantamental-pipeline:latest \
    --region=us-central1

# Delete job
gcloud run jobs delete quantamental-pipeline --region=us-central1
```

### Scheduler Management

```bash
# List schedulers
gcloud scheduler jobs list --location=us-central1

# Trigger scheduler manually
gcloud scheduler jobs run trigger-quantamental-pipeline --location=us-central1

# Pause scheduler
gcloud scheduler jobs pause trigger-quantamental-pipeline --location=us-central1

# Resume scheduler
gcloud scheduler jobs resume trigger-quantamental-pipeline --location=us-central1

# Update schedule
gcloud scheduler jobs update http trigger-quantamental-pipeline \
    --location=us-central1 \
    --schedule="0 6 * * 0"  # Change to weekly

# Delete scheduler
gcloud scheduler jobs delete trigger-quantamental-pipeline --location=us-central1
```

### Secret Management

```bash
# List secrets
gcloud secrets list

# View secret versions
gcloud secrets versions list fmp-api-key

# Update secret value
echo -n "new-api-key" | gcloud secrets versions add fmp-api-key --data-file=-
```

---

## Monitoring

### GCP Console Links

| Resource | URL |
|----------|-----|
| **Cloud Run Jobs** | https://console.cloud.google.com/run/jobs |
| **Cloud Scheduler** | https://console.cloud.google.com/cloudscheduler |
| **Secret Manager** | https://console.cloud.google.com/security/secret-manager |
| **Artifact Registry** | https://console.cloud.google.com/artifacts |
| **Cloud Storage** | https://console.cloud.google.com/storage |

### Weights & Biases

- **Dashboard:** https://wandb.ai
- **Project:** Quantamental-model
- View runs, metrics, and artifacts

---

## Pipeline Output

### Model Metrics (Example Run)

| Metric | Value |
|--------|-------|
| **Accuracy** | 38.71% |
| **Precision** | 61.25% |
| **Recall** | 28.82% |
| **F1 Score** | 39.20% |
| **ROC AUC** | 0.4012 |

### Validation Thresholds

| Status | Threshold | Action |
|--------|-----------|--------|
| 🟢 Production | ≥ 80% | Full deployment |
| 🟡 Degraded | ≥ 35% | Deploy with warnings |
| 🔴 Rejected | < 35% | Block deployment |

---

## Troubleshooting

### Common Issues

**1. Permission Denied on Secrets**
```bash
# Grant secret access to service account
gcloud secrets add-iam-policy-binding SECRET_NAME \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
```

**2. Docker Push Authentication Error**
```bash
# Re-authenticate Docker
gcloud auth print-access-token | sudo docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
```

**3. Job Already Exists**
```bash
# Delete and recreate
gcloud run jobs delete quantamental-pipeline --region=us-central1 --quiet
# Then create again
```

**4. Organization Location Restriction**
```bash
# Use regional replication for secrets
--replication-policy="user-managed" --locations="us-central1"
```

---

## Summary

The Quantamental ML Pipeline is successfully deployed with:

- ✅ **Containerized pipeline** in Artifact Registry
- ✅ **Secrets** managed securely in Secret Manager
- ✅ **Cloud Run Job** for serverless execution
- ✅ **Cloud Scheduler** for automated daily runs at 6 AM Central
- ✅ **W&B integration** for experiment tracking and versioning
- ✅ **GCS integration** for output storage

The pipeline automatically retrains the model daily, validates performance against thresholds, and versions all artifacts for reproducibility.
