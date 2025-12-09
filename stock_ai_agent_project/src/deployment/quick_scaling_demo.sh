#!/bin/bash

echo "=========================================="
echo "Stock Busters Scaling Demo"
echo "=========================================="
echo ""

echo "1. Current State (Before Scaling)"
echo "-----------------------------------"
kubectl get pods -n stockbusters-app-namespace
kubectl get nodes
echo ""

echo "2. Resource Usage (Before Scaling)"
echo "-----------------------------------"
kubectl top nodes
kubectl top pods -n stockbusters-app-namespace
echo ""

echo "3. Scaling to 3 replicas..."
echo "-----------------------------------"
kubectl scale deployment/api --replicas=3 -n stockbusters-app-namespace
kubectl scale deployment/frontend --replicas=3 -n stockbusters-app-namespace
echo "Waiting for pods to be ready..."
sleep 60

echo ""
echo "4. Scaled State (3 replicas each)"
echo "-----------------------------------"
kubectl get pods -n stockbusters-app-namespace
echo ""

echo "5. Resource Usage (After Scaling)"
echo "-----------------------------------"
kubectl top pods -n stockbusters-app-namespace
echo ""

echo "6. Running Load Test (1000 requests, 50 concurrent)..."
echo "-----------------------------------"
ab -n 1000 -c 50 http://34.60.47.248.sslip.io/ 
echo ""

echo "7. Load Balancer & Services Status"
echo "-----------------------------------"
kubectl get svc -n stockbusters-app-namespace
kubectl get ingress -n stockbusters-app-namespace
echo ""

echo "=========================================="
echo "Demo Complete!"
echo "=========================================="
