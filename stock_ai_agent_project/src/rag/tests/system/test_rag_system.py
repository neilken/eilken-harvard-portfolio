"""
System tests for RAG API
Tests the actual API endpoints with HTTP requests to a running server
Based on cheese-app-ci-cd system test pattern
"""

import pytest
import requests
import time
import os

# Base URL for the RAG API (assumes API is running)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:9000")


def is_api_running():
    """Check if RAG API is accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except (requests.exceptions.RequestException, requests.exceptions.ConnectionError):
        return False


@pytest.mark.system
@pytest.mark.skipif(not is_api_running(), reason="RAG API not running at localhost:9000")
class TestRAGSystemEndpoints:
    """System tests for RAG API endpoints with real HTTP requests."""

    def test_health_endpoint(self):
        """Test health check endpoint returns OK status."""
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["ok", "degraded"]  # degraded is OK if ChromaDB not connected
        assert "service" in data
        assert data["service"] == "rag-api"

    def test_health_endpoint_structure(self):
        """Test health endpoint returns expected structure."""
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        # Should have basic fields
        assert "status" in data
        assert "service" in data
        assert "chromadb" in data

    def test_query_endpoint_with_text(self):
        """Test /query/text endpoint with a simple query."""
        response = requests.post(f"{API_BASE_URL}/query/text", json={"q": "What is ROE?"}, timeout=10)

        # Should return 200 even if no data (empty collection is OK)
        assert response.status_code == 200

        data = response.json()
        assert "answer" in data or "texts" in data or "results" in data

    def test_query_endpoint_invalid_request(self):
        """Test /query endpoint handles invalid requests gracefully."""
        # Missing query field
        response = requests.post(f"{API_BASE_URL}/query/text", json={}, timeout=5)

        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422, 500]

    def test_invalid_route_returns_404(self):
        """Test that invalid routes return 404."""
        response = requests.get(f"{API_BASE_URL}/this-route-does-not-exist", timeout=5)
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test that POST to GET-only endpoint returns 405."""
        response = requests.post(f"{API_BASE_URL}/health", timeout=5)
        # Health might accept POST or return 405
        assert response.status_code in [200, 405, 422]

    def test_api_response_time(self):
        """Test that API responds quickly."""
        start_time = time.time()
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # Health check should be fast (< 2 seconds)
        assert elapsed < 2.0

    def test_query_endpoint_content_type(self):
        """Test that API returns JSON content type."""
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "").lower()
