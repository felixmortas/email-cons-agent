"""
Click Element Tool

LangChain tool for clicking interactive elements using their stable DOM index.
"""

from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context
from .page_utils import locate_by_agent_index, wait_for_dom_stable


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

    # Snapshot DOM avant le clic
    before = await page.evaluate("document.body.innerHTML.length")

    # ── JUST ONE click ──────────────────────────────────────────────────────────
    try:
        await element.click(timeout=5000)
    except Exception as e:
        result = f"❌ Erreur de clic [{index}]: {type(e).__name__}: {e}"
        return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})

    # ── See what happened after the click ─────────────────────────────
    result = None

    # Case 1: Page navigation triggered
    try:
        await page.wait_for_load_state("load", timeout=8000)
        # We check to make sure the URL has changed or that the DOM has completely changed
        await wait_for_dom_stable(page, timeout_ms=3000)
        result = f"✅ Clic (nav) [{index}] {tag} id={el_id} « {text} »"
    except Exception:
        pass  # No navigation → continue

    # Case 2: DOM manipulation without navigation (menu, popup, toggle, etc.)
    if result is None:
        try:
            await page.wait_for_function(
                f"document.body.innerHTML.length !== {before}",
                timeout=2000,
            )
            await page.wait_for_timeout(300)  # Let the animations finish
            await wait_for_dom_stable(page, timeout_ms=2000)
            result = f"✅ Clic (dom-mutation) [{index}] {tag} id={el_id} « {text} »"
        except Exception:
            pass  # No mutations detected

    # Case 3: Element disappeared after the click (popup closed, item removed from the DOM, etc.)
    if result is None:
        try:
            await locate_by_agent_index(page, index)
        except ValueError:
            result = f"✅ Clic (élément disparu post-clic) [{index}] {tag} id={el_id} « {text} »"

    # Case 4: Silent click (focus, aria-selected, standalone attribute…)
    if result is None:
        await page.wait_for_timeout(300)
        result = f"✅ Clic (no-change) [{index}] {tag} id={el_id} « {text} »"

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})