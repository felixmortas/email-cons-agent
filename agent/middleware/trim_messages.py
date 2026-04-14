from langchain.agents.middleware import before_model
from state import State
from langchain.tools import ToolRuntime
from langchain.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from agent.context import Context

def make_trim_messages(is_gemini: bool = False):
    # Middleware to keep only the last 2 messages
    @before_model
    def _trim_messages(state: State, runtime: ToolRuntime[Context]):
        """
        Keep only:
        - The system prompt (automatically injected by create_agent)
        - The last 2 conversation messages if Mistral AI
        - The last complete exchange (HumanMessage → AIMessage → ToolMessage(s)) if Google Gemini
        """
        messages = state["messages"]

        if len(messages) <= 2:
            return {"messages": messages}

        # Start from the last 2 messages
        trimmed = messages[-2:]

        # Walk back to include the full AIMessage group (multiple tool responses)
        while trimmed and trimmed[0].type == "tool":
            start_idx = len(messages) - len(trimmed) - 1
            if start_idx < 0:
                break
            trimmed = messages[start_idx:]

        # Gemini requires that an AIMessage with tool_calls is preceded by a HumanMessage
        if is_gemini and trimmed and trimmed[0].type != "human":
            trimmed = [HumanMessage(content="."), *trimmed]


        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *trimmed
            ]
        }
    return _trim_messages
