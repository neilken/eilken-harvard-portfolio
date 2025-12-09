# Verification script for Stock Busters deployment
# This script verifies the deployed application is working correctly

param(
    [string]$GCP_PROJECT = "stock-busters-cs115",
    [string]$REGION = "us-central1",
    [string]$CLUSTER_NAME = "stockbusters-app-cluster",
    [string]$NAMESPACE = "stockbusters-app-namespace"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🔍 Stock Busters Deployment Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is available
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: gcloud CLI not found. Please install Google Cloud SDK." -ForegroundColor Red
    exit 1
}

# Check if kubectl is available
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: kubectl not found. Please install kubectl." -ForegroundColor Red
    exit 1
}

# Check if Pulumi is available
if (-not (Get-Command pulumi -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  Warning: Pulumi CLI not found. Skipping Pulumi outputs." -ForegroundColor Yellow
    $usePulumi = $false
} else {
    $usePulumi = $true
}

Write-Host "Step 1: Getting application URL from Pulumi..." -ForegroundColor Yellow
$APP_URL = $null

if ($usePulumi) {
    Push-Location "src/deployment/deploy_k8s"
    try {
        pulumi stack select dev 2>&1 | Out-Null
        $APP_URL = pulumi stack output app_url 2>&1
        if ($APP_URL -match "http") {
            Write-Host "✅ App URL: $APP_URL" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Could not get app URL from Pulumi. Will try to get from ingress." -ForegroundColor Yellow
            $APP_URL = $null
        }
    } catch {
        Write-Host "⚠️  Could not get app URL from Pulumi: $_" -ForegroundColor Yellow
        $APP_URL = $null
    }
    Pop-Location
}

# If we don't have URL from Pulumi, try to get from kubectl
if (-not $APP_URL -or $APP_URL -notmatch "http") {
    Write-Host ""
    Write-Host "Step 2: Getting cluster credentials and checking ingress..." -ForegroundColor Yellow
    
    # Get cluster credentials
    gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION --project $GCP_PROJECT 2>&1 | Out-Null
    
    # Get ingress IP
    $INGRESS_INFO = kubectl get ingress -n $NAMESPACE -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>&1
    if ($INGRESS_INFO -and $INGRESS_INFO -match "^\d+\.\d+\.\d+\.\d+$") {
        $IP = $INGRESS_INFO
        $APP_URL = "http://${IP}.sslip.io"
        Write-Host "✅ Found ingress IP: $IP" -ForegroundColor Green
        Write-Host "✅ App URL: $APP_URL" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Could not get ingress IP. Checking services..." -ForegroundColor Yellow
        $SVC_INFO = kubectl get svc -n $NAMESPACE -o jsonpath='{.items[?(@.spec.type=="LoadBalancer")].status.loadBalancer.ingress[0].ip}' 2>&1
        if ($SVC_INFO -and $SVC_INFO -match "^\d+\.\d+\.\d+\.\d+$") {
            $IP = $SVC_INFO
            $APP_URL = "http://${IP}.sslip.io"
            Write-Host "✅ Found LoadBalancer IP: $IP" -ForegroundColor Green
            Write-Host "✅ App URL: $APP_URL" -ForegroundColor Green
        } else {
            Write-Host "❌ Could not determine app URL. Please check manually." -ForegroundColor Red
            Write-Host "   Run: kubectl get ingress -n $NAMESPACE" -ForegroundColor Yellow
            exit 1
        }
    }
}

Write-Host ""
Write-Host "Step 3: Checking Kubernetes pod status..." -ForegroundColor Yellow
kubectl get pods -n $NAMESPACE

$FRONTEND_READY = (kubectl get pods -n $NAMESPACE -l run=frontend -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>&1) -eq "True"
$API_READY = (kubectl get pods -n $NAMESPACE -l run=api -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>&1) -eq "True"

if ($FRONTEND_READY) {
    Write-Host "✅ Frontend pod is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  Frontend pod is not ready yet" -ForegroundColor Yellow
    Write-Host "   Check logs with: kubectl logs -n $NAMESPACE -l run=frontend" -ForegroundColor Yellow
}

if ($API_READY) {
    Write-Host "✅ API pod is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  API pod is not ready yet" -ForegroundColor Yellow
    Write-Host "   Check logs with: kubectl logs -n $NAMESPACE -l run=api" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 4: Testing application endpoints..." -ForegroundColor Yellow

# Test frontend
Write-Host "Testing frontend: $APP_URL" -ForegroundColor Cyan
try {
    $FRONTEND_RESPONSE = Invoke-WebRequest -Uri $APP_URL -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    if ($FRONTEND_RESPONSE.StatusCode -eq 200) {
        Write-Host "✅ Frontend is responding (HTTP $($FRONTEND_RESPONSE.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Frontend returned HTTP $($FRONTEND_RESPONSE.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Frontend test failed: $_" -ForegroundColor Red
    Write-Host "   The app may still be starting. Wait a few minutes and try again." -ForegroundColor Yellow
}

# Test API
$API_URL = "$APP_URL/api-service"
Write-Host "Testing API: $API_URL" -ForegroundColor Cyan
try {
    $API_RESPONSE = Invoke-WebRequest -Uri $API_URL -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    if ($API_RESPONSE.StatusCode -eq 200) {
        Write-Host "✅ API is responding (HTTP $($API_RESPONSE.StatusCode))" -ForegroundColor Green
        Write-Host "   Response: $($API_RESPONSE.Content.Substring(0, [Math]::Min(100, $API_RESPONSE.Content.Length)))..." -ForegroundColor Gray
    } else {
        Write-Host "⚠️  API returned HTTP $($API_RESPONSE.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ API test failed: $_" -ForegroundColor Red
    Write-Host "   The API may still be starting. Wait a few minutes and try again." -ForegroundColor Yellow
}

# Test API root endpoint
$API_ROOT_URL = "$APP_URL/api-service/"
Write-Host "Testing API root: $API_ROOT_URL" -ForegroundColor Cyan
try {
    $API_ROOT_RESPONSE = Invoke-WebRequest -Uri $API_ROOT_URL -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    if ($API_ROOT_RESPONSE.StatusCode -eq 200) {
        Write-Host "✅ API root endpoint is responding (HTTP $($API_ROOT_RESPONSE.StatusCode))" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  API root endpoint test: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 5: Checking service endpoints..." -ForegroundColor Yellow
kubectl get svc -n $NAMESPACE

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📊 Verification Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "App URL: $APP_URL" -ForegroundColor White
Write-Host "Frontend Ready: $(if ($FRONTEND_READY) { '✅' } else { '⚠️' })" -ForegroundColor $(if ($FRONTEND_READY) { 'Green' } else { 'Yellow' })
Write-Host "API Ready: $(if ($API_READY) { '✅' } else { '⚠️' })" -ForegroundColor $(if ($API_READY) { 'Green' } else { 'Yellow' })
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  View pods: kubectl get pods -n $NAMESPACE" -ForegroundColor White
Write-Host "  View logs: kubectl logs -n $NAMESPACE -l run=frontend" -ForegroundColor White
Write-Host "  View logs: kubectl logs -n $NAMESPACE -l run=api" -ForegroundColor White
Write-Host "  View ingress: kubectl get ingress -n $NAMESPACE" -ForegroundColor White
Write-Host ""
Write-Host "Open in browser: $APP_URL" -ForegroundColor Green

