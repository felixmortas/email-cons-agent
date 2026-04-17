"""
Fill Text Field Tool

LangChain tool for securely filling input fields using environment-stored credentials.
"""

import os
from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context
from .page_utils import locate_by_agent_index, wait_for_dom_stable


@tool
async def fill_text_field(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    index: int,
    identifier: str,
) -> Command:
    """
    Remplit un champ de saisie (input, textarea, contenteditable) en ciblant
    l'élément via son index stable (`data-agent-index`).

    🔐 RÉCUPÉRATION DES SECRETS :
        Les credentials sont lus depuis les variables d'environnement.
        Clés disponibles : EMAIL, PASSWORD, NEW_EMAIL

    ⚠️ SÉCURITÉ : Aucune valeur réelle n'est exposée dans ce message.

    Args:
        index (int): Index du champ tel qu'affiché dans le snapshot.
        identifier (str): Nom de la variable d'environnement à utiliser.
                          Valeurs acceptées : "EMAIL", "PASSWORD", "NEW_EMAIL"

    Returns:
        Résultat du remplissage (succès ou erreur).

    Examples:
        fill_text_field(index=1, identifier="EMAIL")
        fill_text_field(index=2, identifier="PASSWORD")
    """
    page = runtime.context["page"]

    # Resolve secret from environment
    value = os.getenv(identifier.upper())
    if not value:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Variable '{identifier}' non trouvée dans l'environment.",
            tool_call_id=tool_call_id,
        )]})

    # Locate element by stable index
    try:
        element = await locate_by_agent_index(page, index)
    except ValueError as e:
        return Command(update={"messages": [ToolMessage(content=f"❌ {e}", tool_call_id=tool_call_id)]})

    # Fill the field
    try:
        await element.click()              # Focus first
        await element.fill(value)
        await wait_for_dom_stable(page, timeout_ms=3000)  # Allow JS validation to run
        result = f"✅ {identifier} remplit via data-agent-index={index}"
    except Exception as e:
        result = f"❌ Erreur de remplissage [{index}] {identifier}: {e}"

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})