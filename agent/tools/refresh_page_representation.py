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
    Rafraîchit la représentation de la page actuelle.

    **CRITIQUE** : Tu ne peux utiliser cet outil QUE s'il est écrit "INDISPONIBLE - Rafraîchit la page" à la suite de "# 🖥️ ÉTAT ACTUEL DE LA PAGE".

    Returns:
        Un message de confirmation de rafraîchissement de la page actuelle

    Example:
        ❌ :
        # 🖥️ ÉTAT ACTUEL DE LA PAGE
        [0] a: "Menu"
        [1] a: "Sign Up" (id=elRegisterButton)
        [2] a: "Forums"
        [3] a: "Guides"
        
        refresh_page_representation()

        
        ✅ :
        # 🖥️ ÉTAT ACTUEL DE LA PAGE
        INDISPONIBLE - Rafraîchit la page

        refresh_page_representation()

    """
    print("[DEBUG] Use tool refresh_page_representation")

    # Wait to be sure the email is received
    time.sleep(5)

    return Command(update={"messages": [ToolMessage(content="Page rafraîchit ! Voir la représentation de la page actuelle dans le prompt système au début de la conversation\n\nATTENTION : ne rappelle surtout pas cet outil !", tool_call_id=tool_call_id)]})
