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
    print(f"Enter Click_element, index {index}")
    page = runtime.context["page"]

    try:
        element = await locate_by_agent_index(page, index)
        print(element)
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

    result = None

    # Click with navigation handling
    # — Try 1 : clic avec navigation de page —
    try:
        print("Try 1 : expect_navigation")
        async with page.expect_navigation(wait_until="load", timeout=8000):
            await element.click()
        await wait_for_dom_stable(page, timeout_ms=3000)
        result = f"✅ Clic (nav) [{index}] {tag} id={el_id} « {text} »"
        print(result)
    except Exception as e1:
        print(f"Try 1 échoué ({type(e1).__name__}) → Try 2")

    # — Try 2 : clic sans navigation (popup, toggle, etc.) —
    if result is None:
        try:
            print("Try 2 : clic simple + attente stabilité DOM")
            before = await page.evaluate("document.body.innerHTML.length")

            # Re-localiser l'élément : il a pu être recréé dans le DOM
            try:
                element = await locate_by_agent_index(page, index)
            except ValueError:
                # L'élément a disparu (ex: le popup s'est fermé au Try 1 malgré l'erreur)
                # Le clic a quand même fonctionné !
                await page.wait_for_timeout(300)
                result = f"✅ Clic (élément disparu post-clic) [{index}] {tag} id={el_id} « {text} »"
                print(result)
                await wait_for_dom_stable(page, timeout_ms=3000)

            if result is None:
                await element.click(timeout=5000)

                # Attendre un changement DOM OU un délai fixe si rien ne change
                try:
                    await page.wait_for_function(
                        f"document.body.innerHTML.length !== {before}",
                        timeout=2000,
                    )
                    after = await page.evaluate("document.body.innerHTML.length")
                    print(f"DOM changé : {before} → {after}")
                except Exception:
                    # Pas de changement DOM détecté : clic sur un élément statique (focus, etc.)
                    print("Pas de changement DOM détecté, on considère le clic réussi")

                await page.wait_for_timeout(300)  # laisser les animations se terminer
                result = f"✅ Clic (no-nav) [{index}] {tag} id={el_id} « {text} »"
                await wait_for_dom_stable(page, timeout_ms=2000)
                print(result)

        except Exception as e2:
            result = f"❌ Erreur de clic [{index}]: {type(e2).__name__}: {e2}"
            print(result)

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})