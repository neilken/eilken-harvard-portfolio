"""Orchestrator service - Conversational AI agent with RAG integration."""

import os
import sys
import uuid
import requests
from typing import TypedDict, Annotated
from dotenv import load_dotenv

from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
load_dotenv(override=True)

# Configuration
PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
REGION = os.getenv("VERTEX_REGION")
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:9000")
RAG_API_TIMEOUT = int(os.getenv("RAG_API_TIMEOUT", "10"))


# Agent State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# RAG Query Tool
def query_financial_knowledge_base(query: str) -> str:
    """Query the financial knowledge base for definitions, explanations, and financial concepts.

    Use this tool when the user asks about:
    - Financial terms (e.g., P/E ratio, quantitative momentum, market cap)
    - Investment concepts
    - Financial metrics and their meanings
    - Feature definitions and thresholds from the quantitative model

    Args:
        query: The financial question or term to look up

    Returns:
        A string containing relevant information from the knowledge base
    """
    try:
        response = requests.post(
            f"{RAG_API_URL}/query/text", json={"q": query, "k": 3, "format": "text"}, timeout=RAG_API_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("found"):
                answer = data.get("answer", "No information found.")
                return answer if answer else "No information found."
            else:
                return "No relevant information found in knowledge base."
        else:
            return f"Knowledge base unavailable (status: {response.status_code})"
    except requests.Timeout:
        return "Knowledge base query timed out. Please try again."
    except requests.ConnectionError as e:
        return f"Could not connect to knowledge base at {RAG_API_URL}. Please ensure the RAG service is running. Error: {str(e)}"
    except Exception as e:
        import traceback

        error_details = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[DEBUG] RAG query error: {error_details}", file=sys.stderr)
        return f"Error accessing knowledge base: {str(e)}"


rag_tool = tool(query_financial_knowledge_base)


# Agent Class
class Agent:
    def __init__(self, model, tools, checkpointer, system=""):
        self.system = system
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.call_llm)

        # Add tool handling if tools are provided
        if tools:
            graph.add_node("tools", self.take_action)
            graph.add_conditional_edges("llm", self.should_continue)
            graph.add_edge("tools", "llm")
        else:
            graph.add_edge("llm", END)

        graph.add_edge(START, "llm")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools} if tools else {}
        # Bind tools to model if tools are provided
        self.model = model.bind_tools(tools) if tools else model

    def call_llm(self, state: AgentState):
        messages = state["messages"]
        if self.system:
            # Only add system message if not already present in messages
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=self.system)] + messages
        message = self.model.invoke(messages)
        return {"messages": [message]}

    def should_continue(self, state: AgentState):
        """Determine if we should continue to tools or end."""
        messages = state["messages"]
        last_message = messages[-1]
        # Check if the last message has tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def take_action(self, state: AgentState):
        """Execute tool calls from the last message."""
        messages = state["messages"]
        last_message = messages[-1]
        tool_calls = last_message.tool_calls
        results = []
        for tool_call in tool_calls:
            # Handle both dict and object formats
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_call_id = tool_call.get("id", str(uuid.uuid4()))
            else:
                tool_name = getattr(tool_call, "name", "")
                tool_args = getattr(tool_call, "args", {})
                tool_call_id = getattr(tool_call, "id", str(uuid.uuid4()))

            if tool_name in self.tools:
                try:
                    print(f"[TOOL] Calling {tool_name} with args: {tool_args}")
                    result = self.tools[tool_name].invoke(tool_args)
                    print(f"[TOOL] Result from {tool_name}: {str(result)[:200]}...")  # Log first 200 chars
                    results.append(ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=str(result)))
                except Exception as e:
                    import traceback

                    error_trace = traceback.format_exc()
                    print(f"[ERROR] Tool {tool_name} failed: {e}")
                    print(f"[ERROR] Traceback: {error_trace}")
                    results.append(ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"Error: {str(e)}"))
            else:
                results.append(
                    ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"Tool {tool_name} not found")
                )
        return {"messages": results}


# System Prompt
SYSTEM_PROMPT = """You are an AI assistant which is collecting financial requirements from a user. Start the conversation by introducing yourself. Be polite and ask about their name in a welcoming tone.

You have access to a financial knowledge base tool that can provide definitions and explanations of financial terms, investment concepts, and quantitative model features. Use this tool when users ask questions about financial concepts or when you need to provide accurate explanations.

You will be asking questions one by one and if you don't get the answer or are asked a clarifying query for your input, answer by explaining politely.

Here are the questions:

Q1: What is your risk appetite? low, medium, high?
Q2: What is your investment horizon? short term (less than 3 months), more than 3 months.
Q3: Is there any particular sector you are interested in?

When users ask about financial terms or concepts you're unsure about, use the query_financial_knowledge_base tool to get accurate information.

When you are able to answer all the questions, you may end conversation by showing the final output.

**CRITICAL INSTRUCTION: The final output must be a single summary containing all collected data in the following exact format:**
### Final Financial Requirements
{
    long_term: bool = Field(description="Long term investment preference.")
    short_term: bool = Field(description="Short term investment preference.")
    high_risk: bool = Field(description="High risk appetite check.")
    low_risk: bool = Field(description="Low risk appetite check.")
    sectors: list = Field(description="Preferred investment sectors.")
}
"""


def create_agent(system_prompt=None):
    """Create and return an agent instance."""
    if not PROJECT_ID or not REGION:
        raise ValueError("VERTEX_PROJECT_ID and VERTEX_REGION must be set")

    llm = ChatVertexAI(model="gemini-2.5-flash", project=PROJECT_ID, location=REGION)

    memory = MemorySaver()
    system = system_prompt or SYSTEM_PROMPT

    agent = Agent(llm, [rag_tool], system=system, checkpointer=memory)
    return agent


def chat(agent, user_input: str, thread_id: str = "default"):
    """Run a single chat turn."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.graph.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
    return result["messages"][-1].content


if __name__ == "__main__":
    # Interactive chat interface
    print("=" * 80)
    print("Orchestrator - Financial Advisor with RAG Context")
    print("=" * 80)
    print(f"RAG API URL: {RAG_API_URL}")
    print("Type 'exit' or 'quit' to end the conversation")
    print("=" * 80)
    print()

    try:
        agent = create_agent()
        print("Agent created successfully!")
        print()

        thread_id = "chat-1"

        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            try:
                response = chat(agent, user_input, thread_id=thread_id)
                print(f"Assistant: {response}")
                print()
            except Exception as e:
                print(f"Error: {e}")
                import traceback

                traceback.print_exc()
                print()

    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error starting orchestrator: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
