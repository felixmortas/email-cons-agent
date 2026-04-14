from langchain.agents import AgentState
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing import Annotated

# Avoid errors when 2 tools are called in the same step and edit the same state value
def take_last(existing, new):
    return new

class State(AgentState):
    messages: Annotated[list[BaseMessage], add_messages]
