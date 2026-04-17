"""
Click Element Tool

LangChain tool for clicking interactive elements using their stable DOM index.
"""

from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context
from .page_utils import locate_by_agent_index


@tool
async def click_element(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    index: int,
) -> Command:
    """
    Clique sur un élément interactif en utilisant son INDEX tel qu'affiché
    dans la représentation actuelle de la page.

    L'index est garanti stable : il est ancré directement dans le DOM via
    l'attribut `data-agent-index` au moment où le snapshot est généré.
    Il n'y a donc aucun risque de décalage entre ce que tu vois et ce qui
    est cliqué.

    Args:
        index (int): Index de l'élément tel qu'affiché dans le snapshot.

    Returns:
        Résultat du clic (succès ou erreur).

    Examples:
        click_element(index=3)  # Clique sur l'élément [3] du snapshot
    """
    page = runtime.context["page"]

    try:
        element = await locate_by_agent_index(page, index)
    except ValueError as e:
        return Command(update={"messages": [ToolMessage(content=f"❌ {e}", tool_call_id=tool_call_id)]})

    # Extract debug info
    try:
        tag   = await element.evaluate("el => el.tagName")
        el_id = await element.get_attribute("id") or ""
        text  = (await element.inner_text()).strip()[:60]
        aria_controls = await element.get_attribute("aria-controls")
    except Exception:
        tag, el_id, text, aria_controls = "?", "", "", None

    # Visibility check
    try:
        if not await element.is_visible():
            return Command(update={"messages": [ToolMessage(
                content=f"❌ L'élement [{index}] n'est pas visible ({tag} id={el_id})",
                tool_call_id=tool_call_id,
            )]})
    except Exception:
        pass

    # Click with navigation handling
    try:
        async with page.expect_navigation(wait_until="load", timeout=8000):
            await element.click()
        result = f"✅ Click (nav) [{index}] {tag} id={el_id} « {text} »"
    except Exception:
        try:
            await element.click()
            await page.wait_for_timeout(6000)  # Allow DOM to stabilize
            result = f"✅ Clic (no-nav) [{index}] {tag} id={el_id} « {text} »"
        except Exception as e:
            result = f"❌ Erreur de clic [{index}]: {e}"

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})