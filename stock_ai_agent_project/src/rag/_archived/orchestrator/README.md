# AC215 Orchestrator - Financial Investment Advisor

Conversational AI agent that collects user financial requirements and provides investment recommendations. Integrates with the RAG knowledge base for financial term definitions and explanations.

## Overview

The orchestrator uses:
- **LangGraph**: For building stateful, multi-step conversational flows
- **Google Vertex AI (Gemini)**: As the LLM for conversation
- **Gradio**: For the web-based chat interface
- **RAG API**: For querying financial knowledge base

## Architecture

```
User Input → Orchestrator → LangGraph Agent → Gemini LLM
                                    ↓
                            RAG Tool (optional)
                                    ↓
                            RAG API → ChromaDB
```

## Features

- **Conversational Flow**: Collects user investment preferences through natural conversation
- **RAG Integration**: Automatically queries financial knowledge base for term definitions
- **Tool Support**: Uses LangChain tools for extensible functionality
- **Gradio UI**: Simple web interface for interacting with the agent

## Prerequisites

- Python 3.11+
- Google Cloud Project with Vertex AI enabled
- RAG service running (default: http://localhost:9000)
- Google Cloud authentication configured

## Setup

### 1. Install Dependencies

Using `uv` (recommended):
```bash
uv sync
```

Or using `pip`:
```bash
pip install -e .
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your configuration:

```bash
cp .env.example .env
```

Required variables:
- `VERTEX_PROJECT_ID`: Your GCP project ID
- `VERTEX_REGION`: GCP region (e.g., `us-central1`)
- `RAG_API_URL`: URL of the RAG service (default: `http://localhost:9000`)

### 3. Authenticate with Google Cloud

Option A: Service Account Key
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

Option B: Application Default Credentials
```bash
gcloud auth application-default login
```

## Usage

### Running the Notebook

```bash
jupyter notebook Orchestrator_01.ipynb
```

### Running with Docker

Build the image:
```bash
docker build -t ac215-orchestrator -f src/agents/orchestrator/Dockerfile .
```

Run the container:
```bash
docker run -it -p 7860:7860 \
  --env-file src/agents/orchestrator/.env \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  -v /path/to/key.json:/path/to/key.json:ro \
  ac215-orchestrator
```

Access the Gradio UI at: http://localhost:7860

### Integration with RAG Service

The orchestrator automatically queries the RAG service when users ask about financial terms. Ensure the RAG service is running:

```bash
# In another terminal
cd src/rag
python rag.py --serve
```

The orchestrator will call the RAG API at the configured `RAG_API_URL`.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VERTEX_PROJECT_ID` | GCP project ID | Required |
| `VERTEX_REGION` | GCP region | `us-central1` |
| `RAG_API_URL` | RAG service URL | `http://localhost:9000` |
| `RAG_API_TIMEOUT` | RAG API timeout (seconds) | `10` |
| `GRADIO_SERVER_PORT` | Gradio server port | `7860` |

### RAG Integration

The orchestrator uses the `query_financial_knowledge_base` tool to:
- Answer questions about financial terms (e.g., "What is P/E ratio?")
- Provide definitions from the quantitative model
- Explain investment concepts

The tool automatically calls the RAG `/query/text` endpoint.

## Development

### Project Structure

```
src/agents/orchestrator/
├── Orchestrator_01.ipynb    # Main notebook
├── Dockerfile                # Container definition
├── pyproject.toml            # Dependencies
├── .env.example              # Environment template
└── README.md                 # This file
```

### Converting Notebook to Python Script

For production deployment, you may want to convert the notebook to a Python script:

```bash
jupyter nbconvert --to python Orchestrator_01.ipynb
```

Then update the Dockerfile to run the Python script instead.

## Troubleshooting

### RAG Service Connection Error

**Error**: `Could not connect to knowledge base`

**Solution**:
1. Verify RAG service is running: `curl http://localhost:9000/health`
2. Check `RAG_API_URL` in `.env` file
3. In Docker/K8s, use service name: `http://rag-service:9000`

### Vertex AI Authentication Error

**Error**: `Google Cloud authentication failed`

**Solution**:
1. Verify `GOOGLE_APPLICATION_CREDENTIALS` is set correctly
2. Or run `gcloud auth application-default login`
3. Check that the service account has Vertex AI permissions

### Gradio Port Already in Use

**Error**: `Address already in use`

**Solution**:
1. Change `GRADIO_SERVER_PORT` in `.env`
2. Or kill the process using the port: `lsof -ti:7860 | xargs kill`

## Integration with Other Services

### Kubernetes Deployment

For MS5, deploy as separate services:

```yaml
# orchestrator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: orchestrator
        image: ac215-orchestrator:latest
        env:
        - name: RAG_API_URL
          value: "http://rag-service:9000"
        - name: VERTEX_PROJECT_ID
          valueFrom:
            secretKeyRef:
              name: gcp-secrets
              key: project-id
```

### Docker Compose

```yaml
services:
  rag:
    build: ./src/rag
    ports:
      - "9000:9000"
  
  orchestrator:
    build: ./src/agents/orchestrator
    ports:
      - "7860:7860"
    environment:
      RAG_API_URL: http://rag:9000
    depends_on:
      - rag
```

## Testing

Test the RAG integration:

```python
# In notebook or Python script
from orchestrator import query_financial_knowledge_base

result = query_financial_knowledge_base("What is P/E ratio?")
print(result)
```

## Next Steps

1. **Convert to Python Script**: For easier deployment
2. **Add Structured Output**: Use Pydantic models for preference extraction
3. **Add Persistence**: Store conversations in database
4. **Add Authentication**: Secure the Gradio interface
5. **Add Monitoring**: Track usage and performance

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Vertex AI](https://python.langchain.com/docs/integrations/chat/vertex_ai)
- [Gradio Documentation](https://www.gradio.app/docs/)
- [RAG Integration Guide](../rag/INTEGRATION_CHANGES.md)

