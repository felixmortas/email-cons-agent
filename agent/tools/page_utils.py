"""
Page Utilities Module

Provides low-level functions for interacting with the browser DOM,
including waiting for stability, generating indexed snapshots,
and locating elements by their stable agent index.
"""

from playwright.async_api import Page


async def wait_for_dom_stable(page: Page, timeout_ms: int = 3000) -> None:
    """
    Wait until the DOM stops mutating for a consecutive period.
    Robust for modern frameworks (React, Vue, etc.) that batch updates.

    Args:
        page: Playwright page instance.
        timeout_ms: Maximum time to wait before resolving anyway.
    """
    await page.evaluate("""
        (timeout) => new Promise((resolve) => {
            let timer;
            const observer = new MutationObserver(() => {
                clearTimeout(timer);
                timer = setTimeout(() => {
                    observer.disconnect();
                    resolve();
                }, 300); // 300ms without mutations = stable
            });
            observer.observe(document.body, {
                childList: true, subtree: true, attributes: true
            });
            // Fallback if nothing mutates within the timeout
            setTimeout(() => { observer.disconnect(); resolve(); }, timeout);
        })
    """, timeout_ms)


async def get_page_representation(page: Page) -> str:
    """
    Injects a `data-agent-index` attribute onto every visible interactive element
    and returns a textual representation of the page.

    Strategy:
    - Works entirely in JavaScript via a single `page.evaluate` call to ensure
      the injected index matches the snapshot exactly.
    - Filters out invisible elements (hidden, off-screen, zero dimensions).
    - Elements without a name/id/type are kept in the DOM but marked `[no-name]`.

    Args:
        page: Playwright page instance.

    Returns:
        A formatted string snapshot of interactive elements.
    """
    await wait_for_dom_stable(page, timeout_ms=3000)

    snapshot: list[dict] = await page.evaluate("""
        () => {
            const SELECTOR = "button, a, input, textarea, select, [role='button'], [role='link'], [role='textbox'], [role='checkbox'], [role='radio'], [role='menuitem'], [role='menu'], [role='menubar'], [role='option'], [role='dialog'], [role='listbox'], [contenteditable='true']";

            function isVisible(el) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 || rect.height > 0 || el.getClientRects().length > 0;
            }

            function getRole(el) {
                const ariaRole = el.getAttribute("role");
                if (ariaRole) return ariaRole;
                const tag = el.tagName.toLowerCase();
                if (tag === "input") return el.type || "input";
                return tag;
            }

            function getName(el) {
                let text = "";
                if (el.tagName.toLowerCase() === 'input' && el.placeholder) {
                    text = el.placeholder;
                } else {
                    text = el.innerText || el.getAttribute("aria-label") || el.getAttribute("title") || "";
                    if (!text.trim()) {
                        const img = el.querySelector('img');
                        if (img) text = img.getAttribute('alt') || img.getAttribute('title') || "";
                    }
                }
                return text.trim().replace(/\\s+/g, ' ').slice(0, 100);
            }

            const allElements = Array.from(document.querySelectorAll(SELECTOR));
            allElements.forEach(el => el.removeAttribute("data-agent-index"));

            const snapshot = [];
            let agentIndex = 0;

            for (const el of allElements) {
                if (!isVisible(el)) continue;

                const name = getName(el);
                const id   = el.id || "";
                const role = el.getAttribute("role") || el.tagName.toLowerCase();
                const type = el.type || "";

                if (!name && !id && !type) continue;

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

    lines = []
    for el in snapshot:
        info = f"[{el['index']}] {el['role']}: \"{el['name']}\""
        attrs = []
        if el["id"]: attrs.append(f"id={el['id']}")
        if el["type"]: attrs.append(f"type={el['type']}")
        attr_str = f" ({', '.join(attrs)})" if attrs else ""
        lines.append(f"{info}{attr_str}")

    return "\n".join(lines)


async def locate_by_agent_index(page: Page, index: int):
    """
    Returns the Playwright Locator corresponding to `data-agent-index=<index>`.

    Args:
        page: Playwright page instance.
        index: The stable index injected during snapshot generation.

    Raises:
        ValueError: If the element is not found (DOM changed since snapshot).
    """
    locator = page.locator(f"[data-agent-index='{index}']")
    count = await locator.count()
    if count == 0:
        raise ValueError(
            f"Aucun élément trouvé avec data-agent-index={index}. "
            "Le DOM a probablement changé depuis le dernier appel de l'outil."
            "Réfère toi à la représentation actuelle de la page et réessaye."
        )
    return locator.first