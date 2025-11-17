#!/usr/bin/env python3
"""Containerized end-to-end test for orchestrator RAG integration.

Tests:
1. End-to-end LLM integration: Whether the LLM calls the RAG tool during a conversation
2. Tool invocation during chat: Whether the agent routes to the tool when financial questions are asked
3. Context usage: Whether the LLM uses retrieved RAG context in its answers

Usage:
    python test_containerized.py
    
    Or in Docker:
    docker run --rm --network host -v $(pwd)/.env:/workspace/.env orchestrator-test python test_containerized.py
"""

import os
import sys
import time
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv

# Import orchestrator
from orchestrator import create_agent, chat

# Load environment variables
load_dotenv(override=True)

# RAG API URL - default to host.docker.internal for Docker containers
# This allows connecting to services running on the host machine
RAG_API_URL = os.getenv("RAG_API_URL", "http://host.docker.internal:9000")
RAG_API_TIMEOUT = int(os.getenv("RAG_API_TIMEOUT", "10"))


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details = []
    
    def add_pass(self, test_name: str, details: str = ""):
        self.passed += 1
        self.details.append(("PASS", test_name, details))
    
    def add_fail(self, test_name: str, details: str = ""):
        self.failed += 1
        self.details.append(("FAIL", test_name, details))
    
    def add_warn(self, test_name: str, details: str = ""):
        self.warnings += 1
        self.details.append(("WARN", test_name, details))
    
    def print_summary(self):
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Warnings: {self.warnings}")
        print("\nDetails:")
        for status, name, details in self.details:
            symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
            print(f"  {symbol} {name}")
            if details:
                print(f"    {details}")
        print("=" * 80)


def check_rag_service() -> bool:
    """Check if RAG service is available."""
    try:
        response = requests.get(f"{RAG_API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"[✓] RAG service is running")
            print(f"    Collection: {data.get('collection')}")
            print(f"    Chunks: {data.get('count')}")
            return True
        else:
            print(f"[✗] RAG service health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"[✗] Cannot connect to RAG service: {e}")
        return False


def test_direct_rag_query(results: TestResults) -> bool:
    """Test direct RAG query to verify service works."""
    print("\n[TEST] Direct RAG Query")
    print("-" * 80)
    
    try:
        response = requests.post(
            f"{RAG_API_URL}/query/text",
            json={"q": "What is P/E ratio?", "k": 3, "format": "text"},
            timeout=RAG_API_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("found"):
                answer = data.get("answer", "")
                print(f"[✓] RAG query successful")
                print(f"    Answer length: {len(answer)} chars")
                print(f"    Preview: {answer[:200]}...")
                results.add_pass("Direct RAG Query", f"Retrieved {len(answer)} chars")
                return True
            else:
                print(f"[✗] RAG query returned no results")
                results.add_fail("Direct RAG Query", "No results found")
                return False
        else:
            print(f"[✗] RAG query failed: {response.status_code}")
            results.add_fail("Direct RAG Query", f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"[✗] RAG query error: {e}")
        results.add_fail("Direct RAG Query", str(e))
        return False


def test_tool_invocation(results: TestResults, agent) -> bool:
    """Test 1: Whether the agent routes to the tool when financial questions are asked."""
    print("\n[TEST 1] Tool Invocation During Chat")
    print("-" * 80)
    print("Testing: Whether the agent routes to the RAG tool when financial questions are asked")
    
    financial_queries = [
        "What is P/E ratio?",
        "Explain quantitative momentum",
        "What does cash per share mean?",
    ]
    
    tool_calls_found = 0
    total_queries = len(financial_queries)
    
    for i, query in enumerate(financial_queries, 1):
        print(f"\n  Query {i}/{total_queries}: {query}")
        print("  " + "-" * 76)
        
        try:
            # Capture stdout to detect tool calls
            import io
            from contextlib import redirect_stdout
            
            stdout_capture = io.StringIO()
            with redirect_stdout(stdout_capture):
                response = chat(agent, query, thread_id=f"test_tool_{i}")
            
            output = stdout_capture.getvalue()
            
            # Check if tool was called
            tool_called = "[TOOL] Calling" in output or "query_financial_knowledge_base" in output
            
            if tool_called:
                tool_calls_found += 1
                print(f"  [✓] Tool was called")
                # Extract tool call details
                if "[TOOL] Calling" in output:
                    tool_line = [line for line in output.split('\n') if "[TOOL] Calling" in line][0]
                    print(f"  {tool_line}")
            else:
                print(f"  [✗] Tool was NOT called")
                print(f"  Response: {response[:200]}...")
            
            print(f"  Answer length: {len(response)} chars")
            
        except Exception as e:
            print(f"  [✗] Error: {e}")
            import traceback
            traceback.print_exc()
    
    success_rate = tool_calls_found / total_queries
    
    if success_rate >= 0.67:  # At least 2/3 of queries should trigger tool
        results.add_pass(
            "Tool Invocation",
            f"Tool called in {tool_calls_found}/{total_queries} financial queries ({success_rate*100:.0f}%)"
        )
        return True
    elif success_rate >= 0.33:
        results.add_warn(
            "Tool Invocation",
            f"Tool called in only {tool_calls_found}/{total_queries} financial queries ({success_rate*100:.0f}%)"
        )
        return False
    else:
        results.add_fail(
            "Tool Invocation",
            f"Tool called in only {tool_calls_found}/{total_queries} financial queries ({success_rate*100:.0f}%)"
        )
        return False


def test_context_usage(results: TestResults, agent) -> bool:
    """Test 2: Whether the LLM uses retrieved RAG context in its answers."""
    print("\n[TEST 2] Context Usage in Answers")
    print("-" * 80)
    print("Testing: Whether the LLM uses retrieved RAG context in its answers")
    
    # First, get the expected context from RAG
    test_query = "What is P/E ratio?"
    
    try:
        # Get direct RAG response
        rag_response = requests.post(
            f"{RAG_API_URL}/query/text",
            json={"q": test_query, "k": 3, "format": "text"},
            timeout=RAG_API_TIMEOUT
        )
        if rag_response.status_code != 200:
            results.add_fail("Context Usage", "Could not retrieve RAG context for comparison")
            return False
        
        rag_data = rag_response.json()
        if not rag_data.get("found"):
            results.add_fail("Context Usage", "RAG returned no context")
            return False
        
        rag_context = rag_data.get("answer", "").lower()
        rag_keywords = set()
        # Extract key terms from RAG context (simple approach)
        for word in ["ratio", "price", "earnings", "pe", "p/e", "valuation", "multiple"]:
            if word in rag_context:
                rag_keywords.add(word)
        
        print(f"  RAG context keywords: {rag_keywords}")
        
        # Get LLM response through orchestrator
        import io
        from contextlib import redirect_stdout
        
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            llm_response = chat(agent, test_query, thread_id="test_context")
        
        output = stdout_capture.getvalue()
        llm_text = llm_response.lower()
        
        # Check if tool was called
        tool_called = "[TOOL] Calling" in output
        if not tool_called:
            results.add_warn("Context Usage", "Tool was not called, cannot verify context usage")
            return False
        
        # Check if LLM response contains keywords from RAG context
        found_keywords = [kw for kw in rag_keywords if kw in llm_text]
        keyword_match_rate = len(found_keywords) / len(rag_keywords) if rag_keywords else 0
        
        print(f"  LLM response keywords found: {found_keywords}")
        print(f"  Keyword match rate: {keyword_match_rate*100:.0f}%")
        print(f"  LLM response preview: {llm_response[:300]}...")
        
        if keyword_match_rate >= 0.5:  # At least 50% of keywords should appear
            results.add_pass(
                "Context Usage",
                f"Found {len(found_keywords)}/{len(rag_keywords)} RAG keywords in LLM response ({keyword_match_rate*100:.0f}%)"
            )
            return True
        elif keyword_match_rate >= 0.25:
            results.add_warn(
                "Context Usage",
                f"Found only {len(found_keywords)}/{len(rag_keywords)} RAG keywords in LLM response ({keyword_match_rate*100:.0f}%)"
            )
            return False
        else:
            results.add_fail(
                "Context Usage",
                f"Found only {len(found_keywords)}/{len(rag_keywords)} RAG keywords in LLM response ({keyword_match_rate*100:.0f}%)"
            )
            return False
            
    except Exception as e:
        print(f"  [✗] Error: {e}")
        import traceback
        traceback.print_exc()
        results.add_fail("Context Usage", str(e))
        return False


def test_end_to_end_integration(results: TestResults, agent) -> bool:
    """Test 3: End-to-end LLM integration - full conversation flow."""
    print("\n[TEST 3] End-to-End LLM Integration")
    print("-" * 80)
    print("Testing: Full conversation flow with RAG tool integration")
    
    conversation = [
        "Hello, I'm interested in learning about financial terms.",
        "What is quantitative momentum?",
        "Can you explain P/E ratio?",
        "What does market cap mean?",
    ]
    
    tool_calls_made = 0
    total_turns = len(conversation)
    thread_id = "test_e2e"
    
    print(f"  Simulating conversation with {total_turns} turns...")
    
    try:
        import io
        from contextlib import redirect_stdout
        
        for i, user_msg in enumerate(conversation, 1):
            print(f"\n  Turn {i}: User: {user_msg}")
            
            stdout_capture = io.StringIO()
            with redirect_stdout(stdout_capture):
                response = chat(agent, user_msg, thread_id=thread_id)
            
            output = stdout_capture.getvalue()
            
            # Check if tool was called
            if "[TOOL] Calling" in output:
                tool_calls_made += 1
                print(f"    [✓] Tool called")
            else:
                print(f"    [ ] No tool call")
            
            print(f"    Response: {response[:150]}...")
            time.sleep(0.5)  # Small delay between turns
        
        tool_call_rate = tool_calls_made / total_turns
        
        print(f"\n  Summary:")
        print(f"    Tool calls: {tool_calls_made}/{total_turns} turns")
        print(f"    Tool call rate: {tool_call_rate*100:.0f}%")
        
        # For a conversation with financial questions, we expect at least some tool calls
        # (not all turns will be financial questions)
        if tool_calls_made >= 2:  # At least 2 out of 4 financial questions should trigger tool
            results.add_pass(
                "End-to-End Integration",
                f"Tool called {tool_calls_made} times in {total_turns} conversation turns"
            )
            return True
        elif tool_calls_made >= 1:
            results.add_warn(
                "End-to-End Integration",
                f"Tool called only {tool_calls_made} time(s) in {total_turns} conversation turns"
            )
            return False
        else:
            results.add_fail(
                "End-to-End Integration",
                f"Tool was never called in {total_turns} conversation turns"
            )
            return False
            
    except Exception as e:
        print(f"  [✗] Error: {e}")
        import traceback
        traceback.print_exc()
        results.add_fail("End-to-End Integration", str(e))
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("CONTAINERIZED ORCHESTRATOR RAG INTEGRATION TESTS")
    print("=" * 80)
    
    results = TestResults()
    
    # Check RAG service
    print("\n[STEP 1] Checking RAG Service...")
    if not check_rag_service():
        print("\n[✗] RAG service is not available. Please ensure it's running.")
        print(f"    Expected URL: {RAG_API_URL}")
        results.print_summary()
        sys.exit(1)
    
    # Test direct RAG query
    if not test_direct_rag_query(results):
        print("\n[✗] Direct RAG query failed. Cannot proceed with integration tests.")
        results.print_summary()
        sys.exit(1)
    
    # Create agent
    print("\n[STEP 2] Creating Orchestrator Agent...")
    try:
        agent = create_agent()
        print("[✓] Agent created successfully")
    except ValueError as e:
        print(f"[✗] Configuration error: {e}")
        print("    Please check VERTEX_PROJECT_ID and VERTEX_REGION in .env file")
        results.add_fail("Agent Creation", str(e))
        results.print_summary()
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        if "credentials" in error_msg.lower() or "authentication" in error_msg.lower():
            print(f"[✗] Authentication error: {e}")
            print("\n    Google Cloud credentials are required to test LLM integration.")
            print("    Options:")
            print("    1. Set GOOGLE_APPLICATION_CREDENTIALS to a service account key file")
            print("    2. Mount the key file in Docker: -v /path/to/key.json:/workspace/credentials.json")
            print("    3. Set environment: GOOGLE_APPLICATION_CREDENTIALS=/workspace/credentials.json")
            print("\n    Note: Application Default Credentials (ADC) don't work in Docker on local machines.")
        else:
            print(f"[✗] Failed to create agent: {e}")
            import traceback
            traceback.print_exc()
        results.add_fail("Agent Creation", error_msg)
        results.print_summary()
        sys.exit(1)
    
    # Run tests
    print("\n[STEP 3] Running Integration Tests...")
    print("=" * 80)
    
    test_tool_invocation(results, agent)
    test_context_usage(results, agent)
    test_end_to_end_integration(results, agent)
    
    # Print summary
    results.print_summary()
    
    # Exit code
    if results.failed == 0:
        print("\n[SUCCESS] All critical tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some tests failed. Review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

