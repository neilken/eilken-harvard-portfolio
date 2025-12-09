from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class user_preference(BaseModel):
    """User investment preferences"""

    long_term: bool = Field(description="Long term investment preference.")
    short_term: bool = Field(description="Short term investment preference.")
    high_risk: bool = Field(description="High risk appetite check.")
    low_risk: bool = Field(description="Low risk appetite check.")
    # sectors: list = Field(description="Preferred investment sectors.")
    completed: bool = Field(description="Indicates if all information has been collected.")
    confirmation: bool = Field(description="Indicates if the user has confirmed the populated user preferences")


class ChatAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_pref: Dict[str, Any]


class ChatAgent:
    def __init__(self, model, tools, checkpointer, system=""):
        self.system = system
        graph = StateGraph(ChatAgentState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("validate_llm", self.validate_llm)
        graph.add_edge(START, "llm")
        graph.add_edge("llm", "validate_llm")
        graph.add_edge("validate_llm", END)
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model

    def call_llm(self, state: ChatAgentState):
        """Call the LLM with the current messages"""
        messages = state["messages"]
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        message = self.model.invoke(messages)
        return {"messages": [message]}

    def validate_llm(self, state: ChatAgentState):
        """Validate and extract structured output from LLM response"""
        last_message = state["messages"][-1]
        # print(dir(state))
        validate_resp = self.model.with_structured_output(user_preference).invoke([last_message])
        val_dict = validate_resp.model_dump()

        if val_dict.get("completed"):
            return {"user_pref": val_dict}
        else:
            return {"user_pref": {}}
