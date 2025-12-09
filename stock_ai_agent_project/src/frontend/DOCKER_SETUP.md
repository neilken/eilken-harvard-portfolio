# Docker Network Setup - Quick Reference

## Overview

Stock Busters uses a custom Docker network (`stockbusters-app-network`) to enable communication between frontend and backend services.

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              stockbusters-app-network                           │
│                                                                 │
│  ┌─────────────────────────┐      ┌──────────────────────┐    │
│  │  stockbusters-app-      │      │   Frontend Dev       │    │
│  │  api-service            │◄─────┤   (Next.js)          │    │
│  │  (FastAPI)              │      │   Port: 3000         │    │
│  │  Port: 9000             │      │                      │    │
│  └─────────────────────────┘      └──────────────────────┘    │
│           │                                                     │
│           ▼                                                     │
│  GCS: fin-data-bucket-115 (Quantamental Models)                │
│  ChromaDB: stock-busters-chroma-bucket:8000                    │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Backend (API Service)

```bash
cd api-service  # backend directory
./docker-shell.sh
```

**What it does:**
- Creates `stockbusters-app-network` if not exists
- Builds image: `stockbusters-app-api-service`
- Mounts volumes: code, secrets, persistent storage
- Exposes port 9000
- Sets environment variables for GCP & ChromaDB

### 2. Start Frontend

```bash
cd frontend
npm run dev
```

### 3. Access Application

- **Frontend**: http://localhost:3000
- **API**: http://localhost:9000
- **API Docs**: http://localhost:9000/docs

## Environment Configuration

### Backend (docker-shell.sh)

```bash
# Project Configuration
GCP_PROJECT="stock-busters-cs115"
GCS_BUCKET_NAME="fin-data-bucket-115"
CHROMADB_HOST="stock-busters-chroma-bucket"
CHROMADB_PORT=8000

# Volume Mounts
/app                    → Application code
/secrets                → GCP service account JSON
/persistent             → Persistent data storage

# Container Settings
Image: stockbusters-app-api-service
Port: 9000:9000
Network: stockbusters-app-network
Mode: Development (DEV=1)
```

### Frontend (.env.development)

```env
NEXT_PUBLIC_BASE_API_URL=http://localhost:9000
NEXTAUTH_SECRET="gHDgDM7d7hcKJWMwqvYzH/6gEZ8gM4Yv5V76Qc/9d/s="
NEXTAUTH_URL=http://localhost:3000
PORT=3000
CHOKIDAR_USEPOLLING=true
```

## Docker Commands

### Check Running Container

```bash
docker ps | grep stockbusters-app-api-service
```

### View Logs

```bash
docker logs stockbusters-app-api-service
```

### Check Network

```bash
docker network inspect stockbusters-app-network
```

### Stop Container

```bash
docker stop stockbusters-app-api-service
```

## Troubleshooting

### Backend Not Accessible

```bash
# Test API
curl http://localhost:9000/api/health

# Check container
docker ps | grep stockbusters-app-api-service

# View logs
docker logs stockbusters-app-api-service
```

### Port Already in Use

```bash
# Find process on port 9000
lsof -i :9000

# Kill process
kill -9 <PID>
```

### Restart Everything

```bash
# Stop container
docker stop stockbusters-app-api-service

# Remove network (optional)
docker network rm stockbusters-app-network

# Start fresh
cd api-service
./docker-shell.sh
```

### GCP Credentials Error

Ensure secrets directory contains `stock-busters-service-account.json`:
```bash
ls ../../../secrets/stock-busters-service-account.json
```

## Development Workflow

### Daily Start

```bash
# Terminal 1: Backend
cd api-service
./docker-shell.sh

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Backend Changes

Container has live code mounting - changes reflect automatically.
If you need to rebuild:
```bash
docker stop stockbusters-app-api-service
./docker-shell.sh
```

### Frontend Changes

Hot reload enabled - save and see changes instantly.

## Key Points

- **Network Name**: `stockbusters-app-network` (auto-created by docker-shell.sh)
- **Backend Container**: `stockbusters-app-api-service` on port 9000
- **Frontend Dev Server**: Port 3000
- **Live Mounting**: Code changes reflect automatically (no rebuild needed)
- **GCP Integration**: Requires service account JSON in secrets directory
- **ChromaDB**: Connected at `stock-busters-chroma-bucket:8000`

---

**Stock Busters** - Docker Network Setup Guide
