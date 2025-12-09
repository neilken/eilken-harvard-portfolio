# Stock Busters - Deployment Documentation

This directory contains the infrastructure-as-code (IaC) deployment configurations for the Stock Busters application using **Pulumi and Google Cloud Platform (GCP)**.

## 🏗️ Architecture Overview

The Stock Busters application is deployed on **Google Kubernetes Engine (GKE)** with the following components:

- **Frontend**: Next.js application serving the user interface
- **API Service**: FastAPI backend providing stock analysis and recommendations
- **NGINX Ingress Controller**: Load balancer for external traffic routing
- **Workload Identity**: Secure authentication for GCP services (GCS, Vertex AI)

### Infrastructure Components
```
┌─────────────────────────────────────────────────────────┐
│                     Internet                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Load Balancer (IP)  │
          │  NGINX Ingress       │
          └──────────┬───────────┘
                     │
          ┌──────────▼───────────┐
          │   GKE Cluster        │
          │  ┌────────────────┐  │
          │  │  Frontend Pod  │  │
          │  └────────────────┘  │
          │  ┌────────────────┐  │
          │  │  API Pod       │  │
          │  └────────────────┘  │
          │                      │
          │  Workload Identity   │
          └──────────┬───────────┘
                     │
          ┌──────────▼───────────┐
          │   GCP Services       │
          │  - Cloud Storage     │
          │  - Vertex AI         │
          │  - Artifact Registry │
          └──────────────────────┘
```

## 📁 Directory Structure
```
deployment/
├── deploy_images/          # Docker image building and pushing
│   ├── __main__.py        # Pulumi program for building images
│   ├── Pulumi.yaml        # Project configuration
│   └── Pulumi.dev.yaml    # Stack-specific configuration
│
├── deploy_k8s/            # Kubernetes cluster deployment
│   ├── __main__.py        # Main Pulumi orchestration
│   ├── create_network.py  # VPC, subnet, NAT configuration
│   ├── create_cluster.py  # GKE cluster and node pool setup
│   ├── setup_containers.py # Application deployments
│   ├── setup_loadbalancer.py # Ingress configuration
│   ├── Pulumi.yaml        # Project configuration
│   └── Pulumi.dev.yaml    # Stack-specific configuration
│
├── deploy_single_vm/      # Legacy single VM deployment (reference only)
│
├── Dockerfile             # Deployment container image
├── docker-shell.sh        # Container startup script
├── docker-entrypoint.sh   # Container initialization
├── pyproject.toml         # Python dependencies
└── uv.lock               # Locked dependencies
```

## 🚀 Prerequisites

### Required Tools
- Docker Desktop
- Google Cloud SDK (`gcloud`)
- Git
- WSL2 (for Windows users)

### GCP Requirements
1. **GCP Project**: Active project with billing enabled
2. **APIs Enabled**:
   - Kubernetes Engine API
   - Artifact Registry API
   - Compute Engine API
   - Cloud Resource Manager API
   - IAM API

3. **Service Accounts**:
   - **Deployment Service Account** (e.g., `stockbusters-deployment@PROJECT_ID.iam.gserviceaccount.com`)
     - Roles: Kubernetes Engine Admin, Storage Admin, Artifact Registry Admin, Service Account Admin, Service Account Token Creator
   - **Application Service Account** (e.g., `stockbusters-gcp-service-accou@PROJECT_ID.iam.gserviceaccount.com`)
     - Roles: Storage Admin, Vertex AI User, Service Account Token Creator

4. **Service Account Key**: JSON key file for the deployment service account saved as `secrets/deployment.json`

## 🔧 Configuration

### 1. Update `docker-shell.sh`

Edit the environment variables for your GCP project:
```bash
export GCP_PROJECT="your-gcp-project-id"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export PULUMI_BUCKET="gs://${GCP_PROJECT}-pulumi-state-bucket"
```

### 2. Update Pulumi Configurations

**For `deploy_k8s/Pulumi.dev.yaml`:**
```yaml
config:
  gcp:project: your-gcp-project-id
  security:gcp_service_account_email: YOUR_NODE_SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com
  security:gcp_ksa_service_account_email: YOUR_APP_SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com
```

**For `deploy_images/Pulumi.dev.yaml`:**
```yaml
config:
  gcp:project: your-gcp-project-id
```

## 📦 Deployment Steps

### Step 1: Setup Deployment Container
```bash
# Navigate to deployment directory
cd src/deployment

# Start the deployment container
sh docker-shell.sh
```

This will:
- Build the deployment Docker image
- Authenticate with GCP
- Configure Docker for Artifact Registry
- Set up Pulumi backend in GCS
- Drop you into a shell inside the container

### Step 2: Build and Push Docker Images
```bash
# Inside the deployment container
cd /app/deploy_images

# Initialize or select the stack
pulumi stack select dev

# Preview changes
pulumi preview

# Deploy (builds and pushes images to Artifact Registry)
pulumi up

# Note the image tags from the output
```

**What this does:**
- Creates Artifact Registry repository
- Builds Docker images for API and Frontend
- Pushes images with timestamp tags to Artifact Registry

**Expected Duration:** ~15-20 minutes

### Step 3: Deploy Kubernetes Cluster and Applications
```bash
# Navigate to K8s deployment
cd /app/deploy_k8s

# Initialize or select the stack
pulumi stack select dev

# Preview the infrastructure
pulumi preview

# Deploy everything
pulumi up
```

**What this does:**
1. Creates VPC network with subnet, router, and NAT
2. Provisions GKE cluster with node pool
3. Configures Workload Identity
4. Deploys application pods (Frontend, API)
5. Sets up NGINX Ingress Controller
6. Creates external load balancer

**Expected Duration:** ~20-25 minutes (cluster creation is the longest part)

### Step 4: Verify Deployment
```bash
# Export kubeconfig
pulumi stack output kubeconfig --show-secrets > kubeconfig.yaml
export KUBECONFIG=kubeconfig.yaml

# Check cluster status
kubectl get nodes

# Check application pods
kubectl get pods -n stockbusters-app-namespace

# Check services and ingress
kubectl get svc,ingress -n stockbusters-app-namespace

# Get application URL
pulumi stack output app_url
```

## 🌐 Accessing the Application

After successful deployment:
```bash
# Get the application URL
pulumi stack output app_url
```

The application will be accessible at: `http://<EXTERNAL-IP>.sslip.io`

Example: `http://34.60.47.248.sslip.io`

## 🔍 Monitoring and Debugging

### View Application Logs
```bash
# API logs
kubectl logs -n stockbusters-app-namespace deployment/api -f

# Frontend logs
kubectl logs -n stockbusters-app-namespace deployment/frontend -f

# Ingress controller logs
kubectl logs -n stockbusters-app-namespace deployment/nginx-f5-...-nginx-ingress-controller -f
```

### Check Pod Status
```bash
# Get all resources in the namespace
kubectl get all -n stockbusters-app-namespace

# Describe a specific pod
kubectl describe pod <pod-name> -n stockbusters-app-namespace

# Get events
kubectl get events -n stockbusters-app-namespace --sort-by='.lastTimestamp'
```

### Debug Pod Issues
```bash
# Shell into a pod
kubectl exec -it <pod-name> -n stockbusters-app-namespace -- /bin/bash

# Check environment variables
kubectl exec <pod-name> -n stockbusters-app-namespace -- env
```

## 🔄 Updating the Application

### Update Application Code

1. Make changes to your code
2. Rebuild and push images:
```bash
   cd /app/deploy_images
   pulumi up
```

3. Restart deployments to use new images:
```bash
   cd /app/deploy_k8s
   kubectl rollout restart deployment/api -n stockbusters-app-namespace
   kubectl rollout restart deployment/frontend -n stockbusters-app-namespace
```

### Update Infrastructure
```bash
cd /app/deploy_k8s

# Make changes to Pulumi code
# Preview changes
pulumi preview

# Apply changes
pulumi up
```

## 🗑️ Cleanup and Teardown

### Destroy Kubernetes Resources
```bash
cd /app/deploy_k8s
pulumi destroy
```

This will remove:
- All Kubernetes resources
- GKE cluster and node pool
- Load balancers
- VPC network components

**Note:** Artifact Registry images are retained by default.

### Destroy Docker Images
```bash
cd /app/deploy_images
pulumi destroy
```

## ⚠️ Troubleshooting

### Common Issues

#### 1. Workload Identity 403 Errors

**Symptom:** API logs show `Permission 'iam.serviceAccounts.getAccessToken' denied`

**Solution:**
- Add **Service Account Token Creator** role to the application service account
- Restart API pods: `kubectl rollout restart deployment/api -n stockbusters-app-namespace`

#### 2. Image Pull Errors

**Symptom:** Pods stuck in `ImagePullBackOff`

**Solution:**
- Verify images exist in Artifact Registry
- Check Workload Identity configuration
- Verify node service account has Artifact Registry Reader role

#### 3. Ingress Not Getting External IP

**Symptom:** Ingress shows `<pending>` for ADDRESS

**Solution:**
- Wait 2-5 minutes for load balancer provisioning
- Check NGINX Ingress Controller logs
- Verify service type is LoadBalancer

#### 4. Namespace Stuck Deleting

**Symptom:** `pulumi destroy` times out on namespace deletion

**Solution:**
```bash
kubectl patch namespace <namespace> -p '{"metadata":{"finalizers":[]}}' --type=merge
```

## 📊 Cost Estimation

**Monthly costs for default configuration:**

- GKE Cluster (Standard): ~$73/month
- Node Pool (e2-medium, 1 node): ~$25/month
- Load Balancer: ~$18/month
- Artifact Registry Storage: ~$0.10/GB/month
- Network Egress: Variable

**Total estimated: ~$116-150/month**

**Cost optimization tips:**
- Use smaller machine types (e2-small, e2-micro)
- Reduce to single-zone cluster
- Use preemptible nodes for dev/test
- Enable GKE Autopilot for production

## 🔐 Security Best Practices

1. **Service Accounts**: Use dedicated service accounts with minimal permissions
2. **Workload Identity**: Always use Workload Identity instead of service account keys in pods
3. **Secrets Management**: Never commit secrets to Git; use Google Secret Manager for production
4. **Network Policies**: Implement Kubernetes Network Policies for pod-to-pod communication
5. **Image Security**: Regularly scan images for vulnerabilities using Artifact Registry scanning
6. **RBAC**: Configure proper Kubernetes RBAC roles

## 📚 Additional Resources

- [Pulumi GCP Documentation](https://www.pulumi.com/docs/clouds/gcp/)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Workload Identity Setup](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Pulumi and kubectl logs
3. Consult GCP documentation
4. Contact the development team

## 📝 Version History

- **v1.0** (December 2025): Initial Kubernetes deployment on GCP
  - GKE cluster with Workload Identity
  - NGINX Ingress with external load balancer
  - Automated Docker image builds with Pulumi

---

**Last Updated:** December 7, 2025  
**Maintained By:** Stock Busters Team
