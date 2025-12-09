import os
import uuid  # Add this line
from datetime import datetime  # Add this line if not already there
from fastapi import APIRouter, Header, HTTPException, Body
from typing import Dict, Any, List, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import service_account
from api.utils.chat_bot_agent import ChatAgent
from api.utils.detailed_page_funcs import (
    get_company_profile,
    get_quant_data,
    get_stocks_data,
    user_pref_stock_selection,
)
from google.auth import default

router = APIRouter()


# Request/Response Models
class ChatMessage(BaseModel):
    "pydantic object for the Chat messages"

    message: str

    class Config:
        extra = "allow"


class ChatResponse(BaseModel):
    "pydantic object for the Chat response"

    chat_id: str
    message: str
    user_preferences: Optional[Dict[str, Any]] = None
    completed: bool = False


class ChatHistory(BaseModel):
    "pydantic object for chat history"

    chat_id: str
    messages: List[Dict[str, str]]
    user_preferences: Optional[Dict[str, Any]] = None


# Initialize
memory = MemorySaver()
load_dotenv(override=True)

# Load credentials with error handling

credentials = None
llm = None

# try:
#     credentials_path = "../secrets/stock-busters-service-account.json"
#     if os.path.exists(credentials_path):
#         credentials = service_account.Credentials.from_service_account_file(credentials_path)
#         llm = ChatVertexAI(model="gemini-2.5-flash", credentials=credentials)
#     else:
#         # Credentials file not found - will be mocked in tests via conftest.py
#         print(f"Info: Credentials file not found at {credentials_path}. LLM will be mocked in tests.")
# except Exception as e:
#     # Any error loading credentials - will be mocked in tests
#     print(f"Info: Could not load credentials: {e}. LLM will be mocked in tests.")


try:
    credentials, project_id = default()
    print(f"Authenticated with project: {project_id}")
    llm = ChatVertexAI(model="gemini-2.5-flash", credentials=credentials)
except Exception as e:
    # Any error loading credentials - will be mocked in tests via conftest.py
    print(f"Info: Could not load credentials: {e}. LLM will be mocked in tests.")

system_prompt = """
You are an AI assistant which is collecting financial requirements from a user. The conversation has already started where the user is about to tell his name. Be polite.

You will be asking questions one by one and if you don't get the answer or asked a clarifying query for your input, answer by explaining politely.
If you already have the user preferences, show it to user and ask if they need any changes. If they do, ask the questions again.

Here are the questions:

Q1: What is your investment horizon: short term (less than 3 months) or long term (3 months or more)?
Q2: What is your risk appetite: low, high?

**Note a user can choose both long term and short term, similary the user can also choose both low risk and high risk, in which case it means both flags will be true. Neither is not an option

In the beginning, confirmation: bool will always be false
When you are able to answer all the questions, you may end conversation by showing the final output.
In the end ask for confirmation from the user saying here is the summary of your preferences, if that looks good, I can generate the recommendations.

**CRITICAL INSTRUCTION: The preference confirmation must be a single summary containing all collected data in the following exact format:**
You will collect data like this.
### For confirmation response, explain the choices in simple words. Your choices will cover below. Also share the collected answers in below template
 
    long_term: boolen Field(description="Long term investment preference.")
    short_term: bool Field(description="Short term investment preference.")
    high_risk: bool Field(description="High risk appetite check.")
    low_risk: bool Field(description="Low risk appetite check.")
Wait for confirmation from the user. Once the user confirms, thank him and tell him while showing their selected prference direct user to click on "generate report" to view recommendations.
"""

# Initialize ChatAgent - will be mocked/replaced in tests if llm is None
if llm is not None:
    abot = ChatAgent(llm, [], system=system_prompt, checkpointer=memory)
else:
    # Create a placeholder - will be replaced by patches in conftest.py
    from unittest.mock import MagicMock

    abot = MagicMock()

# In-memory storage for demo (replace with database in production)
chat_sessions = {}


@router.get("/{model}/chats")
async def get_chats(
    model: str,
    x_session_id: str = Header(None, alias="X-Session-ID"),
    limit: Optional[int] = None,
):
    """
    Get all chat sessions for a user
    Returns list of chat sessions with their IDs and message count
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required")

    user_chats = []
    for chat_id, session in chat_sessions.items():
        if session.get("user_id") == x_session_id:
            # Generate title from first user message
            messages = session.get("messages", [])
            title = "New Chat"
            if messages:
                first_user_msg = next((msg for msg in messages if msg.get("role") == "user"), None)
                if first_user_msg:
                    # Use first 50 characters of first user message as title
                    content = first_user_msg.get("content", "")
                    title = content[:50] + ("..." if len(content) > 50 else "")

            user_chats.append(
                {
                    "chat_id": chat_id,
                    "title": title,
                    "message_count": len(messages),
                    "user_preferences": session.get("user_preferences"),
                }
            )

    if limit:
        user_chats = user_chats[:limit]

    return {"chats": user_chats}


@router.get("/{model}/chats/{chat_id}")
async def get_chat(model: str, chat_id: str, x_session_id: str = Header(None, alias="X-Session-ID")):
    """
    Get a specific chat session by ID
    Returns full chat history
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required")

    if chat_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Chat not found")

    session = chat_sessions[chat_id]
    if session.get("user_id") != x_session_id:
        raise HTTPException(status_code=403, detail="Access denied")
    print("user_pref inside model_chat_chatid=", session.get("user_preferences"))
    return ChatHistory(
        chat_id=chat_id,
        messages=session.get("messages", []),
        user_preferences=session.get("user_preferences"),
    )


@router.post("/{model}/chats")
async def start_chat(
    model: str,
    message: Dict[str, Any] = Body(...),
    x_session_id: str = Header(None, alias="X-Session-ID"),
):
    """
    Start a new chat session
    Returns chat_id and first AI response
    """
    print(f"=== START CHAT ENDPOINT HIT ===")
    print(f"Model: {model}")
    print(f"Session ID: {x_session_id}")
    # print(f"Received raw message: {message}")
    print(f"Message type: {type(message)}")

    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required")

    # Extract message content
    message_content = message.get("message", "")
    if not message_content:
        raise HTTPException(status_code=400, detail="Message content is required")

    print(f"Message content: {message_content}")

    # Generate new chat ID
    import uuid

    chat_id = str(uuid.uuid4())

    # Create config with thread_id
    config = {"configurable": {"thread_id": chat_id}}

    # Welcome message
    welcome_message = "Welcome to Stock Busters. I'm your AI assistant, and I'm here to help you gather your financial requirements. To start, may I please know your name?"

    # Initialize session
    chat_sessions[chat_id] = {
        "user_id": x_session_id,
        "messages": [
            {"role": "assistant", "content": welcome_message},
            {"role": "user", "content": message_content},
        ],
        "user_preferences": None,
    }

    # Get AI response
    response = abot.graph.invoke({"messages": [{"role": "user", "content": message_content}]}, config=config)

    ai_message = response["messages"][-1].content
    user_pref = response.get("user_pref", {})

    # Update session
    chat_sessions[chat_id]["messages"].append({"role": "assistant", "content": ai_message})

    if user_pref:
        chat_sessions[chat_id]["user_preferences"] = user_pref

    return ChatResponse(
        chat_id=chat_id,
        message=ai_message,
        user_preferences=user_pref if user_pref else None,
        completed=user_pref.get("confirmation", False) if user_pref else False,
    )


@router.post("/{model}/chats/{chat_id}")
async def continue_chat(
    model: str,
    chat_id: str,
    message: Dict[str, Any] = Body(...),
    x_session_id: str = Header(None, alias="X-Session-ID"),
):
    """
    Continue an existing chat session
    Returns AI response
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required")

    if chat_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Chat not found")

    session = chat_sessions[chat_id]
    if session.get("user_id") != x_session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Extract message content
    message_content = message.get("message", "")
    if not message_content:
        raise HTTPException(status_code=400, detail="Message content is required")

    # Add user message to history
    session["messages"].append({"role": "user", "content": message_content})

    # Create config with thread_id
    config = {"configurable": {"thread_id": chat_id}}

    # Get AI response
    response = abot.graph.invoke({"messages": [{"role": "user", "content": message_content}]}, config=config)

    ai_message = response["messages"][-1].content
    user_pref = response.get("user_pref", {})

    # Update session
    session["messages"].append({"role": "assistant", "content": ai_message})

    if user_pref:
        session["user_preferences"] = user_pref
        print("user preference in model_chat_chat_id", user_pref)

    return ChatResponse(
        chat_id=chat_id,
        message=ai_message,
        user_preferences=user_pref if user_pref else None,
        completed=user_pref.get("confirmation", False) if user_pref else False,
    )
