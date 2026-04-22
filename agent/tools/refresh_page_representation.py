"""
Refresh page reprensentation

LangChain tool that do nothing, so the next LLM call retrieves the actual page representation.
"""

from typing import Annotated
import time

from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool


@tool
async def refresh_page_representation(
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Rafraîchit la représentation de la page actuelle si elle est indisponible ou incohérente avec la dernière action.

    **CRITIQUE** : Attention ! N'utilise l'outil que si la représentation de la page actuelle n'est pas disponible. 
    N'utilise jamais cet outil après avoir uniquement utilisé "fill_text_field".

    Returns:
        Un message de confirmation de rafraîchissement de la page actuelle

    Example:
        get_verification_code(sender="Auchan")
    """
    print("[DEBUG] Use tool refresh_page_representation")

    # Wait to be sure the email is received
    time.sleep(5)

    return Command(update={"messages": [ToolMessage(content="Page en cours de rafraichissement ... Voir la représentation de la page actuelle", tool_call_id=tool_call_id)]})
