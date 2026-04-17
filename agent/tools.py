import os
from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context


# ── DOM injection + snapshot ─────────────────────────────────────────────────

async def get_page_representation(page) -> str:
    """
    Injects a `data-agent-index` attribute onto every visible interactive element
    and returns a textual representation of the page.

    Strategy:
    - We work entirely on the JavaScript side using a single `page.evaluate` call to
      ensure that the index injected into the DOM is exactly the same as the one displayed
      in the snapshot—there is no possibility of divergence.
    - We filter out invisible elements (offsetParent == null, display:none,
      visibility:hidden) to prevent the agent from clicking on elements
      that are hidden or off-screen.
    - Elements without a name/id/type are kept in the DOM (so that
      data-agent-index remains consistent) but marked [no-name] in the snapshot.
    """
    # 1. On attend d'abord une micro-stabilité avant même de calculer
    await _wait_for_dom_stable(page, timeout_ms=1000)

    snapshot: list[dict] = await page.evaluate("""
    () => {
        const SELECTOR = "button, a, input, textarea, select, [role='button'], [role='link'], [role='textbox'], [role='checkbox'], [role='radio'], [role='menuitem'], [role='menu'], [role='menubar'], [role='option'], [role='dialog'], [role='listbox'], [contenteditable='true']";

        function isVisible(el) {
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }

        function getRole(el) {
            const ariaRole = el.getAttribute("role");
            if (ariaRole) return ariaRole;
            const tag = el.tagName.toLowerCase();
            if (tag === "input") return el.type || "input";
            return tag;
        }

        function getName(el) {
            // Priorité aux textes visibles pour le LLM
            let text = "";
            if (el.tagName.toLowerCase() === 'input' && el.placeholder) {
                text = el.placeholder;
            } else {
                // On récupère le texte, ou l'aria-label, ou le titre de l'image interne
                text = el.innerText || el.getAttribute("aria-label") || el.getAttribute("title") || "";
                
                // Si pas de texte, on cherche dans les images enfants (cas de ton bouton profil)
                if (!text.trim()) {
                    const img = el.querySelector('img');
                    if (img) text = img.getAttribute('alt') || img.getAttribute('title') || "";
                }
            }
            return text.trim().replace(/\\s+/g, ' ').slice(0, 100);
        }

        const allElements = Array.from(document.querySelectorAll(SELECTOR));

        // 2. Remove previous agent indexes to stay idempotent
        allElements.forEach(el => el.removeAttribute("data-agent-index"));

        // 3. Filter visible, assign index, build snapshot
        const snapshot = [];
        let agentIndex = 0;

        for (const el of allElements) {
            if (!isVisible(el)) continue;
                                               
            const name = getName(el);
            const id   = el.id || "";
            const role = el.getAttribute("role") || el.tagName.toLowerCase();
            const type = el.type || "";

            // Ignore the elements without name, id, nor type
            if (!name && !id && !type) continue;                       

            // Anchor the index directly in the DOM
            el.setAttribute("data-agent-index", String(agentIndex));

            snapshot.push({
                index: agentIndex,
                role:  getRole(el),
                name:  name || "[no-name]",
                id,
                type,
            });

            agentIndex++;
        }
        return snapshot;
    }
    """)

    # Formatage Markdown pour le LLM
    lines = []
    for el in snapshot:
        info = f"[{el['index']}] {el['role']}: \"{el['name']}\""
        attrs = []
        if el["id"]: attrs.append(f"id={el['id']}")
        if el["type"]: attrs.append(f"type={el['type']}")
        
        attr_str = f" ({', '.join(attrs)})" if attrs else ""
        lines.append(f"{info}{attr_str}")

    return "\n".join(lines)

# ── Shared helper ─────────────────────────────────────────────────────

async def _locate_by_agent_index(page, index: int):
    """
    Returns the Playwright Locator corresponding to `data-agent-index=<index>`.
    Raise a `ValueError` if the element cannot be found (the DOM has changed since
    the snapshot → the agent must refresh its view).
    """
    locator = page.locator(f"[data-agent-index='{index}']")
    count = await locator.count()
    if count == 0:
        raise ValueError(
            f"Aucun élément avec data-agent-index={index}. "
            "Le DOM a probablement changé depuis le dernier appel d'outil. "
            "Regarde le nouveau DOM et réessaye."
        )
    return locator.first

async def _wait_for_dom_stable(page, timeout_ms: int = 3000):
    """
    Attend que le DOM ne mute plus pendant 300ms consécutives.
    Robuste pour React, Vue, et tout framework qui batch ses updates.
    """
    await page.evaluate("""
        (timeout) => new Promise((resolve) => {
            let timer;
            const observer = new MutationObserver(() => {
                clearTimeout(timer);
                timer = setTimeout(() => {
                    observer.disconnect();
                    resolve();
                }, 300);  // 300ms sans mutation = stable
            });
            observer.observe(document.body, {
                childList: true, subtree: true, attributes: true
            });
            // Fallback si rien ne mute du tout
            setTimeout(() => { observer.disconnect(); resolve(); }, timeout);
        })
    """, timeout_ms)


# ── LangChain Tools ──────────────────────────────────────────────────────────

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
        element = await _locate_by_agent_index(page, index)
    except ValueError as e:
        return Command(update={"messages": [ToolMessage(content=f"❌ {e}", tool_call_id=tool_call_id)]})

    # Debug info
    try:
        tag   = await element.evaluate("el => el.tagName")
        el_id = await element.get_attribute("id") or ""
        text  = (await element.inner_text()).strip()[:60]
        # ✅ Lire aria-controls AVANT le clic
        aria_controls = await element.get_attribute("aria-controls")
    except Exception:
        tag, el_id, text, aria_controls = "?", "", "", None

    # Visibility check
    try:
        if not await element.is_visible():
            return Command(update={"messages": [ToolMessage(
                content=f"❌ Élément [{index}] non visible ({tag} id={el_id})",
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
            await page.wait_for_timeout(6000)  # Let the DOM stabilize
            result = f"✅ Click (no-nav) [{index}] {tag} id={el_id} « {text} »"
        except Exception as e:
            result = f"❌ Erreur click [{index}]: {e}"

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})


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

    # 1. Resolve secret
    value = os.getenv(identifier.upper())
    if not value:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Variable '{identifier}' introuvable dans .env",
            tool_call_id=tool_call_id,
        )]})

    # 2. Locate by stable agent index
    try:
        element = await _locate_by_agent_index(page, index)
    except ValueError as e:
        return Command(update={"messages": [ToolMessage(content=f"❌ {e}", tool_call_id=tool_call_id)]})

    # 3. Fill
    try:
        await element.click()              # Focus the field first
        await element.fill(value)
        await _wait_for_dom_stable(page, timeout_ms=3000)   # Let any JS validation settle
        result = f"✅ {identifier} rempli via data-agent-index={index}"
    except Exception as e:
        result = f"❌ Erreur fill [{index}] {identifier}: {e}"

    return Command(update={"messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]})


@tool(return_direct=True)
async def complete_step(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Marque l'étape actuelle comme réussie et sauvegarde l'URL actuelle.
    À appeler juste avant de renvoyer le message final avec ✅.
    """
    page = runtime.context["page"]
    current_url = page.url

    return Command(update={
        "fallback_url": current_url,
        "messages": [ToolMessage(
            content=f"✅ Étape sauvegardée à l'URL : {current_url}",
            tool_call_id=tool_call_id,
        )],
    })


def get_tools() -> list:
    return [
        click_element,
        fill_text_field,
        complete_step,
    ]