
# Milestone 2 — Finance Data Ingestion Pipeline (Docker + GCS)

This module builds an **end-to-end finance data ingestion pipeline** for the StockBusters project.  
It automatically downloads **S&P 500 stock data** from Yahoo Finance, computes **technical indicators**,  
and uploads the processed datasets directly to **Google Cloud Storage (GCS)** — with **no local file storage** required.

The pipeline performs the following tasks:

1. **Download the S&P 500 ticker list** from a designated GCS bucket.  
2. **Fetch OHLCV data** (Open, High, Low, Close, Volume) for all tickers using `yfinance`, in parallelized chunks.  
3. **Transform** raw data from wide to long format.  
4. **Enhance** each ticker’s time series with over 90 **technical indicators** (SMA, RSI, MACD, ATR, MFI, etc.) using the `ta` library.  
5. **Filter core features** relevant for modeling (trend, momentum, volatility, volume).  
6. **Upload final datasets** back to the GCS bucket in CSV format.

This module implements a **containerized data ingestion pipeline** that downloads financial data (S&P 500 tickers and historical OHLCV data), processes it with Python, and uploads results to a Google Cloud Storage (GCS) bucket.  

---

##  Folder Structure
```text
AC215_StockBusters/
│
├── src/
│ └── fin_data_download/
│ ├── data_download.py # Main ingestion script
│ ├── gcs_utils.py # Helper utilities for GCS I/O
│ ├── requirements.txt # Python dependencies
│ ├── Dockerfile # Container build definition
│ └── .dockerignore # Excluded files from Docker context
│ └── README.md # This documentation
│ └── pyproject.toml
│
├── notebooks/
│ └── finance_data_download.ipynb # Development notebook version
│
│
├── README.md # This documentation 
└── .gitignore # Ignore cache, venv, and secrets
```

## Key Files

| File | Purpose |
|------|----------|
| `data_download.py` | Main executable script — orchestrates GCS I/O, data download, feature generation, and uploads |
| `gcs_utils.py` | Contains helper methods for authenticated GCS client initialization and file operations |
| `Dockerfile` | Defines a reproducible runtime image with all dependencies preinstalled |
| `requirements.txt` | Lists packages for manual installation if Docker is not used |
| `pyproject.toml` | Metadata for modern build systems (`uv` or `pip` compatible) |

---

##  GCP Configuration

The script reads the following environment variables:

| Variable | Description | Example |
|-----------|--------------|----------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON file (only needed outside GCP) | `/app/secrets/stock-busters-service-account.json` |
| `GCP_BUCKET` | Target GCS bucket name | `fin-data-bucket-115` |
| `GCP_TICKER_PATH` | Path to S&P 500 ticker list CSV in bucket | `SP500_list.csv` |
| `START_DATE` | Start date for historical data | `2019-01-01` |
| `END_DATE` | End date for historical data | `2025-09-30` |
| `YF_CHUNK_SIZE` | Number of tickers to download per batch | `50` |
| `YF_SLEEP_SEC` | Sleep time between batches (to avoid rate limits) | `1.0` |

---

##  Running with Docker


##  Prerequisites

Before building the image, make sure you have:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed  
- Access to the team’s **Google Cloud Project**  
- A valid **service account JSON key** with permission to read/write the target GCS bucket  
- The environment variable `GOOGLE_APPLICATION_CREDENTIALS` pointing to that JSON file 

---

### **Local (with service account key)**

##  GCS Setup

1. Create GCP bucket (`fin-data-bucket-115`).  
2. Upload the input CSVs to the bucket root Ex. gs://fin-data-bucket/SP500_list.csv  This file contains the list of S&P500
3. Place service account key outside: Milestone2/secrets/service_account.json

The container will:

1. Download the ticker list from GCS

2. Fetch historical OHLCV data via yfinance (5 years)

3. Compute technical indicators

4. Upload processed file back to the same GCS bucket

5. Fetch the income statement and balance sheet and upload to the same GCS bucket

### Build the image
docker build -f src/fin_data_download/Dockerfile -t fin-data-pipeline .

### Run the container, mounting local secrets folder
docker run --rm -it \
  -v "$PWD/../../secrets:/app/secrets" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/app/secrets/stock-busters-service-account.json" \
  -e GCP_BUCKET="fin-data-bucket-115" \
  fin-data-pipeline

### Example output
Below is a sample of docker run output


<img width="1247" height="948" alt="image" src="https://github.com/user-attachments/assets/8a355b17-3532-4a43-9b0f-e0fa69bd97bf" />

Files are upload to GCP Bucket 

<img width="1902" height="673" alt="image" src="https://github.com/user-attachments/assets/92154830-2538-41e2-adf2-7fc8a441a66d" />

---

