# CD Pipeline Documentation

## Overview

The Continuous Deployment (CD) Pipeline automatically deploys the Stock Busters application to Google Kubernetes Engine (GKE) after the CI pipeline completes successfully. It uses Pulumi for Infrastructure as Code (IaC) to manage Kubernetes deployments and leverages Google Cloud Workload Identity Federation (OIDC) for secure authentication without requiring GitHub secrets.

![Successful Automatic CD run after CI run](Successful%20Automatic%20CD%20run%20after%20CI%20run.png)

*Example: CD pipeline automatically triggered after successful CI pipeline completion*

## Table of Contents

1. [Pipeline Architecture](#pipeline-architecture)
2. [Workflow Triggers](#workflow-triggers)
3. [Authentication](#authentication)
4. [Deployment Steps](#deployment-steps)
5. [Infrastructure Components](#infrastructure-components)
6. [Optimization Features](#optimization-features)
7. [Deployment Outputs](#deployment-outputs)
8. [Troubleshooting](#troubleshooting)

---

## Pipeline Architecture

The CD pipeline consists of a single job (`deploy`) that runs sequentially through multiple steps:

```
Checkout → Authenticate → Configure → Build Images → Deploy to K8s → Verify
```

### Job Flow

1. **Checkout**: Retrieves code from repository (shallow clone for speed)
2. **Authenticate**: Authenticates to GCP using Workload Identity Federation (OIDC)
3. **Configure**: Sets up Pulumi, Docker, and Python dependencies
4. **Build Images**: Builds and pushes Docker images to GCP Artifact Registry
5. **Deploy to K8s**: Deploys application to GKE cluster using Pulumi
6. **Verify**: Waits for pods to be ready and checks application health

---

## Workflow Triggers

The CD pipeline runs automatically on:

### Automatic Trigger (Primary)

- **CI Pipeline Completion**: Automatically triggers when the "Unified CI Pipeline" completes successfully on `main`, `develop`, or `Milestone5` branches
  - Uses `workflow_run` event type
  - Only runs if CI pipeline status is `success`
  - Checks out the same commit SHA that triggered the CI pipeline

### Manual Triggers

- **Push events** to `main`, `develop`, or `Milestone5` branches when files in:
  - `.github/workflows/cd.yml`
  - `src/deployment/**`
  - `src/frontend/**`
  are modified

- **Manual dispatch** via GitHub Actions UI (`workflow_dispatch`)
  - Includes `skip_ci_check` option (use with caution)

### Concurrency

The pipeline uses concurrency groups to prevent multiple deployments:
- Only one deployment per branch at a time
- New runs do **NOT** cancel in-progress runs (`cancel-in-progress: false`)
- Ensures stable deployments without interruption

---

## Authentication

### Workload Identity Federation (OIDC)

The CD pipeline uses **Workload Identity Federation** for secure GCP authentication without requiring GitHub secrets. This is more secure than service account keys because:

- **No long-lived secrets**: No service account keys stored in GitHub
- **Short-lived tokens**: OIDC tokens are automatically generated and rotated
- **Fine-grained permissions**: IAM policies control exactly what the pipeline can do
- **Audit trail**: All authentication is logged in GCP Cloud Audit Logs

### Configuration

**Workload Identity Pool Provider**:
```
projects/1037206705113/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

**Service Account**:
```
stockbusters-deployment@stock-busters-cs115.iam.gserviceaccount.com
```

**Required Permissions**:
- GKE cluster access (read/write)
- Artifact Registry (push images)
- Cloud Storage (Pulumi state bucket)
- Compute Engine (for cluster resources)

---

## Deployment Steps

### Step 1: Determine Checkout Ref

- Dynamically determines the correct Git SHA to checkout based on trigger type:
  - `workflow_run`: Uses `github.event.workflow_run.head_sha` from CI pipeline
  - `push` or `workflow_dispatch`: Uses current commit SHA (`github.sha`)
- Sets output `ref` for use in checkout step

### Step 2: Checkout Code

- Uses shallow clone (`fetch-depth: 1`) for faster execution
- Checks out the ref determined in previous step
- Uses `actions/checkout@v4` action

### Step 3: Authenticate to Google Cloud (OIDC)

- Uses `google-github-actions/auth@v2` action
- Authenticates using Workload Identity Federation
- No secrets required

### Step 4: Set up Cloud SDK

- Installs and configures `gcloud` CLI
- Uses `google-github-actions/setup-gcloud@v2` action

### Step 4: Configure Docker for Artifact Registry

- Configures Docker authentication for GCP Artifact Registry
- Uses `gcloud auth configure-docker` with the `--quiet` flag

### Step 5: Install GKE gcloud auth plugin

- Installs `gke-gcloud-auth-plugin` for GKE cluster authentication
- Adds the plugin binary to PATH for `kubectl` and Pulumi access

### Step 6: Create dummy secrets for build (if needed)

- Creates placeholder JSON files for GCS keys and service accounts
- These are typically not used in OIDC but prevent build failures if the build process expects them

### Step 7: Install Dependencies

**Python Setup**:
- **Python**: 3.13
- Uses `actions/setup-python@v5` with pip caching

**Python Dependency Caching**:
- Caches `~/.cache/pip`, `~/.cache/uv`, and `~/.local/lib/python*`
- Cache key based on `pyproject.toml` and `uv.lock` hashes

**Pulumi CLI**:
- Installs latest version via `pulumi/actions@v4`

**Python Packages**:
- Installed via `uv` with caching
- Uses `~/.cache/uv` for faster subsequent installs
- Installs from `src/deployment/pyproject.toml` with `-e .` flag

### Step 8: Configure Pulumi Backend

**Pulumi Backend**:
- **Storage**: GCS bucket (`gs://stock-busters-cs115-pulumi-state-bucket`)
- **Stack**: `dev`
- **Project**: `stock-busters-cs115`

**Configuration Process**:
1. Verifies GCP authentication
2. Verifies GCS bucket access (creates bucket if needed) with retry logic (3 attempts, 3s delay)
3. Logs into Pulumi backend with retry logic (3 attempts, 3s delay)

**Retry Logic**: Includes retry loops with 3-second delays (3 attempts max) for network/authentication issues.

### Step 9: Configure and Select Pulumi Stacks

- **Python**: 3.13
- **Pulumi CLI**: Latest version
- **Python Packages**: Installed via `uv` with caching
  - Uses `~/.cache/uv` for faster subsequent installs
  - Installs from `src/deployment/pyproject.toml`

**Configuration Process**:
1. Configures and selects Pulumi stacks for:
   - `deploy_images`: Builds and pushes Docker images
   - `deploy_k8s`: Deploys to Kubernetes cluster
2. Sets GCP project configuration for each stack
3. Uses exponential backoff retry logic (initial 2s delay, max 3 attempts)

**Retry Logic**: Exponential backoff retries for `pulumi stack select` and `pulumi stack init` commands.

### Step 10: Set up Docker Buildx

- Configures Docker BuildKit for advanced build features
- Enables automatic layer caching
- Supports parallel builds

### Step 11: Deploy Docker Images (Pulumi)

**Location**: `src/deployment/deploy_images/`

**Process**:
1. Builds Docker images for:
   - `frontend`: Next.js application
   - `api-service`: FastAPI backend
2. Pushes images to GCP Artifact Registry:
   - Location: `us-central1-docker.pkg.dev/stock-busters-cs115/stockbusters-app-repository`
   - Tags: Component name + commit SHA
3. Uses Docker BuildKit for faster builds with layer caching

**Docker Images Built**:
- `stockbusters-app-frontend:<tag>`
- `stockbusters-app-api-service:<tag>`

**Command**: `pulumi up --yes --skip-preview`

**Environment Variables**:
- `GCP_REGION`: us-central1
- `PULUMI_CONFIG_PASSPHRASE`: "" (empty)
- `DOCKER_BUILDKIT`: "1" (enabled)

### Step 12: Deploy to Kubernetes (Pulumi)

**Location**: `src/deployment/deploy_k8s/`

**Process**:
1. Deploys infrastructure to GKE:
   - Kubernetes namespace
   - Deployments (frontend and API)
   - Services (LoadBalancer for frontend, ClusterIP for API)
   - Ingress (for external access)
2. Updates existing resources or creates new ones
3. Handles unreachable resources: `PULUMI_K8S_DELETE_UNREACHABLE: "true"`
4. Verifies `gke-gcloud-auth-plugin` is accessible before deployment

**Command**: `pulumi up --yes --skip-preview`

**Environment Variables**:
- `GCP_REGION`: us-central1
- `PULUMI_CONFIG_PASSPHRASE`: "" (empty)
- `PULUMI_K8S_DELETE_UNREACHABLE`: "true"

**Kubernetes Resources**:
- **Namespace**: `stockbusters-app-namespace`
- **Frontend Deployment**: Next.js application
- **API Deployment**: FastAPI backend
- **Services**: LoadBalancer (public) and ClusterIP (internal)
- **Ingress**: Routes external traffic to services

### Step 13: Get Deployment Outputs

Retrieves deployment information from Pulumi stack:
- **Cluster Name**: GKE cluster identifier
- **App URL**: Public application URL
- **IP Address**: LoadBalancer IP address

**Process**:
1. Ensures correct Pulumi stack is selected
2. Retrieves outputs using `pulumi stack output --show-secrets`
3. Extracts: `cluster_name`, `app_url`, `ip_address`
4. Removes quotes and trims whitespace from outputs

**Fallback**: If Pulumi outputs are unavailable, retrieves from Kubernetes directly using `kubectl get ingress`.

**Environment Variable**: `PULUMI_CONFIG_PASSPHRASE: ""`

### Step 14: Get kubeconfig

- Retrieves Kubernetes configuration from Pulumi stack output
- Saves to `/tmp/kubeconfig.yaml`
- Sets output flags: `kubeconfig_path` and `kubeconfig_exists`

### Step 15: Wait for Pods to be Ready

**Parallel Wait Strategy**:
- Waits for frontend and API pods simultaneously (not sequentially)
- Uses background processes (`&`) and `wait` command
- Timeout: 120 seconds per pod type
- Displays pod status after completion

**Optimization**: Parallel waiting saves ~30-60 seconds compared to sequential waits.

**Condition**: Only runs if `kubeconfig_exists == 'true'`

**Process**:
1. Sets `KUBECONFIG` environment variable
2. Runs `kubectl wait` commands in parallel using background processes
3. Captures exit codes for both pod types
4. Displays pod status after completion

### Step 16: Verify Deployment Health

- Checks application health endpoint
- Verifies HTTP response codes (200, 301, 302 considered successful)
- Provides feedback on deployment status

**Condition**: Only runs if `app_url` output is not empty

**Process**:
1. Waits 5 seconds before health check
2. Uses `curl` with 10-second timeout
3. Accepts HTTP 200, 301, or 302 as successful responses

### Step 17: Deployment Summary

Generates a markdown summary in GitHub Actions showing:
- Deployment status
- Cluster name
- Application URL
- IP address
- Commit SHA
- Authentication method (OIDC)

---

## Infrastructure Components

### Google Kubernetes Engine (GKE)

**Cluster Configuration**:
- **Project**: `stock-busters-cs115`
- **Region**: `us-central1`
- **Cluster Name**: `stockbusters-app-cluster`

### GCP Artifact Registry

**Repository**:
- **Location**: `us-central1-docker.pkg.dev/stock-busters-cs115/stockbusters-app-repository`
- **Images Stored**:
  - Frontend application
  - API service

### Pulumi State Storage

**GCS Bucket**: `gs://stock-busters-cs115-pulumi-state-bucket`

**Stacks**:
- `deploy_images`: Manages Docker image builds
- `deploy_k8s`: Manages Kubernetes deployments

### Kubernetes Resources

**Namespace**: `stockbusters-app-namespace`

**Deployments**:
- `frontend`: Next.js application (multiple replicas)
- `api`: FastAPI backend (multiple replicas)

**Services**:
- `frontend`: LoadBalancer (public access)
- `api-service`: ClusterIP (internal access)

**Ingress**:
- Routes external traffic to frontend service
- Provides public IP address via LoadBalancer

---

## Optimization Features

### 1. Shallow Checkout

**Benefit**: Faster code checkout (~5-10 seconds saved)

**Implementation**: Uses `fetch-depth: 1` for minimal history

### 2. Python Dependency Caching

**Benefit**: Faster dependency installation (~30-60 seconds saved)

**Implementation**:
- Caches `~/.cache/pip` and `~/.cache/uv`
- Uses `uv` for faster Python package management
- Cache key based on `pyproject.toml` and `uv.lock` hashes

### 3. Docker Buildx & BuildKit

**Benefit**: Faster image builds with layer caching

**Implementation**:
- Uses Docker BuildKit for automatic layer caching
- Parallel builds when possible
- Caches base image layers

### 4. Parallel Pod Waits

**Benefit**: Saves ~30-60 seconds on pod readiness checks

**Implementation**:
- Frontend and API pod waits run simultaneously
- Uses bash background processes (`&`) and `wait` command

### 5. Retry Logic

**Benefit**: Handles transient network/authentication errors

**Implementation**:
- Exponential backoff for Pulumi commands
- Retries for GCS bucket access
- Retries for Pulumi backend login

### 6. Reduced Timeouts

**Benefit**: Faster failure detection

**Implementation**:
- Pod wait timeout: 120 seconds (reduced from 300s)
- Health check delay: 5 seconds (reduced from 30s)

**Total Execution Time**: 7-8 minutes (optimized from 10+ minutes)

---

## Deployment Outputs

### Available Outputs

The pipeline provides the following outputs from Pulumi:

- **`cluster_name`**: GKE cluster identifier
- **`app_url`**: Public application URL (e.g., `http://<ip>.sslip.io`)
- **`ip_address`**: LoadBalancer IP address
- **`kubeconfig`**: Kubernetes configuration for cluster access

### Accessing Deployment

**Public URL**: Available in deployment summary (format: `http://<ip-address>.sslip.io`)

**Kubernetes Access**:
```bash
# Get cluster credentials
gcloud container clusters get-credentials stockbusters-app-cluster \
  --region us-central1 \
  --project stock-busters-cs115

# Access pods
kubectl get pods -n stockbusters-app-namespace

# Access services
kubectl get services -n stockbusters-app-namespace
```

---

## Troubleshooting

### Deployment Fails After CI Success

**Symptom**: CD pipeline doesn't trigger after CI completes successfully.

**Possible Causes**:
1. CI pipeline ran on wrong branch (not `main`, `develop`, or `Milestone5`)
2. CI pipeline status was not `success`
3. Workflow run event not properly configured

**Solution**:
- Check CI pipeline branch in GitHub Actions
- Verify CI pipeline completed with `success` status
- Check `workflow_run` trigger configuration in `cd.yml`

### Authentication Errors (OIDC)

**Symptom**: `oauth2/google: unable to generate access token` or `401 Unauthorized`.

**Possible Causes**:
1. Workload Identity Federation not properly configured
2. Service account lacks required permissions
3. Network connectivity issues

**Solution**:
- Verify Workload Identity Pool Provider exists in GCP
- Check service account IAM bindings
- Verify network connectivity (may require retries)

### Pulumi State Errors

**Symptom**: `error: failed to load state` or `bucket not found`.

**Possible Causes**:
1. GCS bucket doesn't exist
2. Service account lacks bucket permissions
3. Network timeout

**Solution**:
- Verify bucket exists: `gsutil ls gs://stock-busters-cs115-pulumi-state-bucket`
- Check IAM permissions on bucket
- Pipeline will create bucket if it doesn't exist (with proper permissions)

### Kubernetes Deployment Fails

**Symptom**: Pods not starting or deployment stuck.

**Possible Causes**:
1. Docker images not pushed to Artifact Registry
2. Resource limits too low
3. Health checks failing

**Solution**:
- Check Artifact Registry for images
- Verify pod logs: `kubectl logs <pod-name> -n stockbusters-app-namespace`
- Check pod status: `kubectl describe pod <pod-name> -n stockbusters-app-namespace`

### Pods Not Ready

**Symptom**: `Wait for pods to be ready` step times out.

**Possible Causes**:
1. Application startup time exceeds 120 seconds
2. Application crashes on startup
3. Resource constraints

**Solution**:
- Check pod logs for errors
- Increase timeout if needed (currently 120s)
- Verify resource requests/limits are adequate

### Empty Deployment Outputs

**Symptom**: `app_url` and `ip_address` are empty in deployment summary.

**Possible Causes**:
1. Pulumi outputs not set correctly
2. Ingress not created
3. LoadBalancer IP not assigned yet

**Solution**:
- Check Pulumi stack outputs: `pulumi stack output --json`
- Verify ingress exists: `kubectl get ingress -n stockbusters-app-namespace`
- Wait for LoadBalancer IP assignment (can take 1-2 minutes)

---

## Best Practices

### Security

1. **Use OIDC**: Never use service account keys in GitHub secrets
2. **Least Privilege**: Grant minimum required permissions to service account
3. **Audit Logs**: Review GCP Cloud Audit Logs regularly
4. **Secrets Management**: Use GCP Secret Manager for application secrets

### Deployment

1. **Test Locally**: Test Pulumi deployments locally before pushing
2. **Incremental Updates**: Use `pulumi up` for safe incremental updates
3. **Monitor Deployments**: Watch pod status and logs during deployment
4. **Rollback Strategy**: Keep previous image versions in Artifact Registry

### Performance

1. **Cache Dependencies**: Leverage Python and Docker caching
2. **Parallel Operations**: Use parallel pod waits where possible
3. **Shallow Clones**: Use shallow checkout for faster execution
4. **Optimize Images**: Use multi-stage Docker builds and layer caching

---

## Summary

The CD Pipeline provides:

✅ **Automated deployment** after successful CI  
✅ **Secure authentication** via Workload Identity Federation (OIDC)  
✅ **Infrastructure as Code** with Pulumi  
✅ **Optimized execution** (7-8 minutes)  
✅ **Health verification** and pod readiness checks  
✅ **Deployment summaries** with URLs and status  

The pipeline ensures that only code that passes all tests and coverage requirements is automatically deployed to production, maintaining high quality and reliability.

For detailed information about the CI pipeline that triggers this deployment, see:

📖 **[CI Pipeline Documentation](CI_PIPELINE.md)**

