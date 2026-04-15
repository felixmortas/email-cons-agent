from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing import Annotated, Optional, TypedDict

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    initial_url: str
    fallback_url: str

class AgentInputState(TypedDict):
    initial_url: str
    fallback_url: Optional[str]