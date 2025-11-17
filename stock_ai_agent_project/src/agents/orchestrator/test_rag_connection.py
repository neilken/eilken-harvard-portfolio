#!/usr/bin/env python3
"""Test script to verify RAG API connection from orchestrator."""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# RAG API configuration
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:9000")
RAG_API_TIMEOUT = int(os.getenv("RAG_API_TIMEOUT", "10"))

def test_health_endpoint():
    """Test the health endpoint."""
    print(f"[TEST] Testing health endpoint: {RAG_API_URL}/health")
    try:
        response = requests.get(f"{RAG_API_URL}/health", timeout=RAG_API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"[SUCCESS] Health check passed: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"[FAIL] Health check failed: Status {response.status_code}")
            return False
    except requests.ConnectionError:
        print(f"[FAIL] Could not connect to RAG API at {RAG_API_URL}")
        print("[INFO] Make sure the RAG service is running: docker run -d --name rag-test-server -p 9000:9000 ac215-rag-test --serve")
        return False
    except Exception as e:
        print(f"[FAIL] Health check error: {e}")
        return False

def test_query_endpoint():
    """Test the query/text endpoint."""
    print(f"\n[TEST] Testing query endpoint: {RAG_API_URL}/query/text")
    
    test_queries = [
        "What is P/E ratio?",
        "quantitative momentum",
        "What is cash per share?",
    ]
    
    for query in test_queries:
        print(f"\n[TEST] Query: {query}")
        try:
            response = requests.post(
                f"{RAG_API_URL}/query/text",
                json={"q": query, "k": 3, "format": "text"},
                timeout=RAG_API_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("found"):
                    answer = data.get("answer", "")
                    source_count = data.get("source_count", 0)
                    print(f"[SUCCESS] Found {source_count} sources")
                    print(f"[ANSWER] {answer[:200]}...")
                else:
                    print(f"[INFO] No information found for query: {query}")
            else:
                print(f"[FAIL] Query failed: Status {response.status_code}")
                print(f"[RESPONSE] {response.text}")
        except requests.Timeout:
            print(f"[FAIL] Query timed out after {RAG_API_TIMEOUT} seconds")
        except requests.ConnectionError:
            print(f"[FAIL] Could not connect to RAG API")
            return False
        except Exception as e:
            print(f"[FAIL] Query error: {e}")
            return False
    
    return True

def test_rag_tool_function():
    """Test the RAG tool function (same as used in orchestrator)."""
    print(f"\n[TEST] Testing RAG tool function (orchestrator style)")
    
    def query_financial_knowledge_base(query: str) -> str:
        """Query the financial knowledge base."""
        try:
            response = requests.post(
                f"{RAG_API_URL}/query/text",
                json={"q": query, "k": 3, "format": "text"},
                timeout=RAG_API_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("found"):
                    return data.get("answer", "No information found.")
                else:
                    return "No relevant information found in knowledge base."
            else:
                return f"Knowledge base unavailable (status: {response.status_code})"
        except requests.Timeout:
            return "Knowledge base query timed out. Please try again."
        except requests.ConnectionError:
            return "Could not connect to knowledge base. Please ensure the RAG service is running."
        except Exception as e:
            return f"Error accessing knowledge base: {str(e)}"
    
    test_query = "What is P/E ratio?"
    print(f"[TEST] Query: {test_query}")
    result = query_financial_knowledge_base(test_query)
    print(f"[RESULT] {result[:300]}...")
    
    if "Error" in result or "unavailable" in result or "Could not connect" in result:
        print("[FAIL] RAG tool function failed")
        return False
    else:
        print("[SUCCESS] RAG tool function works correctly")
        return True

if __name__ == "__main__":
    print("=" * 80)
    print("RAG API Connection Test")
    print("=" * 80)
    print(f"RAG_API_URL: {RAG_API_URL}")
    print(f"RAG_API_TIMEOUT: {RAG_API_TIMEOUT}")
    print("=" * 80)
    
    # Run tests
    health_ok = test_health_endpoint()
    if not health_ok:
        print("\n[ERROR] Health check failed. Please check RAG service status.")
        exit(1)
    
    query_ok = test_query_endpoint()
    if not query_ok:
        print("\n[ERROR] Query tests failed.")
        exit(1)
    
    tool_ok = test_rag_tool_function()
    if not tool_ok:
        print("\n[ERROR] RAG tool function test failed.")
        exit(1)
    
    print("\n" + "=" * 80)
    print("[SUCCESS] All tests passed! RAG API is working correctly.")
    print("=" * 80)

