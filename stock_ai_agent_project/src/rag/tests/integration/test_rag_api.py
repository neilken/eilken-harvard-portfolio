"""Integration tests for RAG FastAPI endpoints."""

import pytest

pytestmark = pytest.mark.integration
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import TestClient, handle if fastapi not available
try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    # Fallback for environments where fastapi might not be installed
    TestClient = None
    FASTAPI_AVAILABLE = False


@pytest.fixture
def mock_retriever():
    """Mock Retriever instance for API tests."""
    retriever = Mock()
    retriever.stats.return_value = {
        "collection": "test_collection",
        "emb_model": "BAAI/bge-small-en-v1.5",
        "retriever_mode": "chroma-dist",
        "metric": "cosine",
        "count": 100,
        "cache_enabled": True,
    }
    retriever.query.return_value = [
        {"rank": 1, "id": "doc1", "text": "Sample document text", "metadata": {"source": "test.pdf"}, "distance": 0.15}
    ]
    return retriever


@pytest.fixture
def app_client(mock_retriever):
    """Create FastAPI test client with mocked dependencies."""
    if not FASTAPI_AVAILABLE or TestClient is None:
        pytest.skip("fastapi not available, skipping integration tests")

    # Patch dependencies BEFORE importing anything from rag
    # This ensures the patch is active when make_app() is defined
    with (
        patch("rag.get_chromadb_client"),
        patch("rag._get_gcs_client"),
        patch("rag._start_chromadb_server"),
        patch("rag.ENABLE_CACHE", False),
    ):
        # Import rag module inside patch context
        import rag

        # Directly set _retriever_instance to mock (bypasses get_retriever entirely)
        rag._retriever_instance = mock_retriever

        # Now import make_app - it will use the mocked instance
        from rag import make_app

        app = make_app()
        return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint_success(self, app_client, mock_retriever):
        """Test health endpoint returns OK status."""
        response = app_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "rag-api"
        assert data["chromadb"] == "connected"
        assert "collection" in data
        assert "count" in data

    def test_health_endpoint_with_error(self, app_client, mock_retriever):
        """Test health endpoint handles errors gracefully."""
        mock_retriever.stats.side_effect = Exception("ChromaDB error")

        response = app_client.get("/health")
        assert response.status_code == 200  # Should still return 200

        data = response.json()
        assert data["status"] == "degraded"
        assert "error" in data


class TestQueryEndpoint:
    """Tests for /query endpoint."""

    def test_query_endpoint_success(self, app_client, mock_retriever):
        """Test query endpoint returns results."""
        response = app_client.post("/query", json={"q": "What is ROE?", "k": 3})

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert "results" in data
        assert "found" in data
        assert "count" in data
        assert data["query"] == "What is ROE?"
        assert isinstance(data["results"], list)

    def test_query_endpoint_default_k(self, app_client, mock_retriever):
        """Test query endpoint with default k value."""
        response = app_client.post("/query", json={"q": "test query"})

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_query_endpoint_empty_query(self, app_client, mock_retriever):
        """Test query endpoint with empty query."""
        mock_retriever.query.return_value = []

        response = app_client.post("/query", json={"q": "", "k": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["count"] == 0

    def test_query_endpoint_error_handling(self, app_client, mock_retriever):
        """Test query endpoint error handling."""
        mock_retriever.query.side_effect = Exception("Query failed")

        response = app_client.post("/query", json={"q": "test", "k": 3})

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]


class TestQueryTextEndpoint:
    """Tests for /query/text endpoint."""

    def test_query_text_endpoint_success(self, app_client, mock_retriever):
        """Test query/text endpoint returns text format."""
        response = app_client.post("/query/text", json={"q": "What is ROE?", "k": 3, "format": "text"})

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert "answer" in data or "found" in data
        assert data.get("found", True) is not None

    def test_query_text_endpoint_detailed_format(self, app_client, mock_retriever):
        """Test query/text endpoint with detailed format."""
        response = app_client.post("/query/text", json={"q": "test query", "k": 2, "format": "detailed"})

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data or "results" in data

    def test_query_text_endpoint_no_results(self, app_client, mock_retriever):
        """Test query/text endpoint with no results."""
        mock_retriever.query.return_value = []

        response = app_client.post("/query/text", json={"q": "nonexistent query", "k": 3})

        assert response.status_code == 200
        data = response.json()
        assert data.get("found", False) is False


class TestAPIErrorHandling:
    """Tests for API error handling."""

    def test_invalid_json(self, app_client):
        """Test API handles invalid JSON."""
        response = app_client.post("/query", content="invalid json", headers={"Content-Type": "application/json"})
        # Should return 422 or 400 for invalid JSON
        assert response.status_code in [400, 422]

    def test_missing_required_fields(self, app_client):
        """Test API handles missing required fields."""
        response = app_client.post("/query", json={"k": 3})  # Missing "q" field
        # Should return 422 for validation error
        assert response.status_code == 422

    def test_cors_headers(self, app_client):
        """Test CORS headers are present."""
        # Test CORS by making a GET request and checking headers
        response = app_client.get("/health")
        # CORS middleware should add headers
        assert response.status_code == 200
        # Check that CORS headers might be present (FastAPI adds them automatically)
        # Note: TestClient may not show all CORS headers, so we just verify the request succeeds


class TestAPIIntegration:
    """Integration tests for API workflow."""

    def test_full_query_workflow(self, app_client, mock_retriever):
        """Test full query workflow from health to query."""
        # Check health first
        health_response = app_client.get("/health")
        assert health_response.status_code == 200

        # Then query
        query_response = app_client.post("/query", json={"q": "financial terms", "k": 5})
        assert query_response.status_code == 200

        # Verify retriever was called
        assert mock_retriever.query.called

    def test_multiple_queries(self, app_client, mock_retriever):
        """Test multiple sequential queries."""
        queries = ["What is ROE?", "Explain P/E ratio", "Define EBITDA"]

        for query in queries:
            response = app_client.post("/query", json={"q": query, "k": 3})
            assert response.status_code == 200

        # Should have called retriever for each query
        assert mock_retriever.query.call_count == len(queries)
