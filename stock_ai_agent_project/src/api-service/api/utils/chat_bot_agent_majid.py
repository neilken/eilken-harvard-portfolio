import requests
import os

# from langchain_openai import ChatOpenAI
from typing import TypedDict
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# from langchain_openai import ChatOpenAI
from langchain_google_vertexai import ChatVertexAI

# from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
# from langchain_community.tools.playwright.utils import create_async_playwright_browser
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# from langchain_core.pydantic_v1 import BaseModel, Field
# from IPython.display import Image, display
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults

# import gradio as gr
import uuid
from dotenv import load_dotenv
from google.oauth2 import service_account
from langgraph.checkpoint.sqlite import SqliteSaver


class user_preference(BaseModel):
    """User investment preferences"""

    long_term: bool = Field(description="Long term investment preference.")
    short_term: bool = Field(description="Short term investment preference.")
    high_risk: bool = Field(description="High risk appetite check.")
    low_risk: bool = Field(description="Low risk appetite check.")
    sectors: list = Field(description="Preferred investment sectors.")
    completed: bool = Field(description="Indicates if all information has been collected.")
    confirmation: bool = Field(description="Indicates if the user has confimed the populated user preferences")

    # name: str = Field(description="The full name of the recipe.")
    # servings: int = Field(description="The number of people the recipe serves.")
    # prep_time_minutes: Optional[int] = Field(None, description="The estimated preparation time in minutes.")
    # ingredients: List[Ingredient] = Field(description="A list of all required ingredients.")


class ChatAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_pref: Dict[str, Any]


# %%
class ChatAgent:
    def __init__(self, model, tools, checkpointer, system=""):
        self.system = system
        graph = StateGraph(ChatAgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("validate_llm", self.validate_llm)
        # graph.add_node("validated_output", self.validated_output)
        # graph.add_node("action", self.take_action)
        # graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: END})
        # graph.add_edge("action", "llm")
        graph.add_edge(START, "llm")
        graph.add_edge("llm", "validate_llm")
        # graph.add_edge("llm", END)
        # graph.add_conditional_edges('validate_llm', self.func_validated, {True: "validated_output", False: END})
        graph.add_edge("validate_llm", END)
        # graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        # self.model = model.bind_tools(tools)
        self.model = model
        # self.model_strt_out = model.with_structured_output(user_preference)

    def call_llm(self, state: ChatAgentState):
        # print("entering LLM")
        messages = state["messages"]
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        message = self.model.invoke(messages)
        return {"messages": [message]}

    def validate_llm(self, state: ChatAgentState):
        # print("entred validate_llm")
        last_message = state["messages"][-1]
        # print(last_message.content)
        validate_resp = self.model.with_structured_output(user_preference).invoke([last_message])
        # print("printing dictionary")
        val_dict = validate_resp.model_dump()
        if val_dict.get("completed"):
            # print("User_preference=", val_dict)
            return {"user_pref": val_dict}

        else:
            return {"user_pref": {}}
