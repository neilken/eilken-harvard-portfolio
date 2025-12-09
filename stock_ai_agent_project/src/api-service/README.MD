# Stock Busters API Service

A FastAPI-based backend service for the Stock Busters AI-powered financial investment platform. This service provides a conversational AI chatbot that collects user investment preferences and generates personalized stock recommendations.

## Features

- **AI Chatbot**: Conversational interface to collect user investment preferences (horizon, risk appetite)
- **Stock Recommendations**: Combining Quantamental model outputs and user investment preferences to generate stock recommendations
- **Stock Details**: Company profiles, OHLCV data, and quant model metrics for a ticker (company)
- **Report Generation**: Personalized investment reports based on user preferences

## Project Structure

```
api-service/
├── api/
│   ├── routers/
│   │   ├── chatbot_final.py    # Chat endpoints (/chats, /chats/{id})
│   │   └── stock_details.py    # Stock endpoints (/details, /report)
│   ├── utils/
│   │   ├── chat_bot_agent.py   # LangChain agent with Gemini LLM
│   │   ├── detailed_page_funcs.py  # Stock data utilities
│   │   └── get_gcs_bucket.py   # Google Cloud Storage integration
│   └── service.py              # FastAPI app initialization
├── tests/                      # Unit, integration, and system tests
├── Dockerfile                  # Container configuration
├── docker-entrypoint.sh        # Container startup script
├── docker-shell.sh             # Development shell script
├── pyproject.toml              # Python dependencies
└── uv.lock                     # Dependency lock file
```

## Prerequisites

- Python 3.12+
- All dependencies for python libraries are mentioned in pyproject.toml 
- Service account JSON key file

## Installation and Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies using the pyproject.toml
uv sync

# Or using uv (faster)
uv venv
uv pip install -e .
```
### Credentials

Place your service account key at `../secrets/stock-busters-service-account.json` relative to the api directory, or mount it in Docker.

### Docker

```bash
# Run docker-shell.sh to build and run container
sh docker-shell.sh
```

### Running API webserver

The API webserver can be initiated using the command below
```bash
#starting webserver
uvicorn web_server
```
For initial setup,  uv sync might be needed to install all dependencies

```
# Libraries sync up
uv sync
```

Open the link below in a browser for the API webserver

```
 http://localhost:9000
 ```

### Get Stock Details

```bash
curl http://localhost:9000/details/AAPL
```
Testing can also be done using the Fast API doc link 
```
http://localhost:9000/docs
```

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/{model}/chats` | List all chat sessions |
| `POST` | `/{model}/chats` | Start a new chat |
| `GET` | `/{model}/chats/{chat_id}` | Get chat history |
| `POST` | `/{model}/chats/{chat_id}` | Continue a chat |

### Stock Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/details/{ticker}` | Get stock details (profile, OHLCV, quant data) |
| `GET` | `/report` | Get recommendations based on preferences |
| `POST` | `/{model}/chats/{chat_id}/report` | Generate investment report |
| `GET` | `/{model}/reports` | List generated reports |

### Files Description

#### api/utils

- chat_bot_agent : Holds the agent class
- detailed_page_funcs : contains helping functions for the report and individual stocks
- get_gcs_bucket : helping function for connectivity with GCS Bucket

#### api/routers

- chatbot_final.py : Agent instantiation and chatbot conversation
- stock_details.py : Logic for combining user preference and and stock model output





## Data Sources

The service retrieves data from Google Cloud Storage:

| File | Description |
|------|-------------|
| `model_output/combined_quantamental_hybrid_with_factors_and_backtest_with_reasoning.csv` | Quant model scores |
| `model_output/company_profiles.csv` | Company information |
| `model_output/ohlcv_raw.parquet` | Historical stock prices |

## User Preference Model

The chatbot collects the following preferences:

| Field | Type | Description |
|-------|------|-------------|
| `long_term` | bool | Long-term investment horizon (3+ months) |
| `short_term` | bool | Short-term investment horizon (<3 months) |
| `high_risk` | bool | High risk appetite |
| `low_risk` | bool | Low risk appetite |
| `confirmation` | bool | User confirmed preferences |

## Scoring System

Stocks are ranked using three score types:

- **Hybrid Score**: Combined technical + fundamental (used when both horizons selected)
- **Technical Score**: Used for short term trade based upon technical analysis (used for short-term)
- **Fundamental Score**: Used for long term trade based upon fundamanetal analysis (used for long-term)


## CI Pipeline

This project includes a GitHub Actions CI pipeline that runs on every push and pull request to `main` and `develop` branches.

### Pipeline Jobs

| Job | Description |
|-----|-------------|
| **lint** | Runs flake8 for code quality checks |
| **test-unit** | Runs unit tests with coverage |
| **test-integration** | Runs integration tests with coverage |
| **coverage-report** | Combines coverage and enforces 45% minimum |
| **docker-build** | Validates Dockerfile builds successfully |

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (no external deps)
│   ├── test_detailed_page_funcs.py
│   ├── test_chat_bot_agent.py
│   ├── test_utils.py
│   └── test_coverage_boost.py
├── integration/             # Integration tests
│   └── test_models.py
└── system/                  # System tests (requires container)
    └── test_system_api.py
```

### Running Tests Locally

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run both
pytest tests/unit/ tests/integration/ -v

# Run with coverage
pytest tests/unit/ --cov=api --cov-report=html
```
