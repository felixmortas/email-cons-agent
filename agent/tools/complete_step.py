"""
Complete Step Tool

LangChain tool for marking a workflow step as successful and saving the current URL.
"""

from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context


@tool(return_direct=True)
async def complete_step(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Marque la mission actuelle comme réussie et sauvegarde l'URL actuelle.
    """
    page = runtime.context["page"]
    current_url = page.url
    return Command(update={
        "fallback_url": current_url,
        "messages": [ToolMessage(
            content=f"✅ Etape validée et URL sauvegardé : {current_url}",
            tool_call_id=tool_call_id,
        )],
    })