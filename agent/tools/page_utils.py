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
    and returns a textual representation of the page, interleaved with visible
    text nodes in DOM order.

    Strategy:
    - Works entirely in JavaScript via a single `page.evaluate` call to ensure
      the injected index matches the snapshot exactly.
    - Filters out invisible elements (hidden, off-screen, zero dimensions).
    - Text elements (headings, paragraphs, labels, li, span, td, th) are included
      in DOM order but are NOT indexed (not clickable).
    - Elements without a name/id/type are kept in the DOM but marked `[no-name]`.

    Args:
        page: Playwright page instance.

    Returns:
        A formatted string snapshot of interactive and text elements in DOM order.
    """
    await wait_for_dom_stable(page, timeout_ms=3000)

    snapshot: list[dict] = await page.evaluate("""
        () => {
            const INTERACTIVE_SELECTOR = "button, a, input, textarea, select, [role='button'], [role='link'], [role='textbox'], [role='checkbox'], [role='radio'], [role='menuitem'], [role='menu'], [role='menubar'], [role='option'], [role='dialog'], [role='listbox'], [contenteditable='true']";
            const TEXT_SELECTOR = "h1, h2, h3, h4, h5, h6, p, label, li, span, td, th, caption, figcaption, blockquote, dt, dd";

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

            document.querySelectorAll("[data-agent-index]").forEach(el => el.removeAttribute("data-agent-index"));

            const interactiveElements = new Set(document.querySelectorAll(INTERACTIVE_SELECTOR));
            const textElements = new Set(document.querySelectorAll(TEXT_SELECTOR));

            const allCandidates = Array.from(
                document.querySelectorAll(INTERACTIVE_SELECTOR + ", " + TEXT_SELECTOR)
            );

            const snapshot = [];
            let agentIndex = 0;

            // Collect interactive names to deduplicate text elements
            const interactiveNames = new Set();
            for (const el of allCandidates) {
                if (interactiveElements.has(el) && isVisible(el)) {
                    const name = getName(el);
                    if (name && name !== "[no-name]") interactiveNames.add(name);
                }
            }

            for (const el of allCandidates) {
                if (!isVisible(el)) continue;

                const isInteractive = interactiveElements.has(el);

                if (isInteractive) {
                    const name = getName(el);
                    const id   = el.id || "";
                    const role = el.getAttribute("role") || el.tagName.toLowerCase();
                    const type = el.type || "";

                    if (!name && !id && !type) continue;

                    el.setAttribute("data-agent-index", String(agentIndex));

                    snapshot.push({
                        kind:  "interactive",
                        index: agentIndex,
                        role:  getRole(el),
                        name:  name || "[no-name]",
                        id,
                        type,
                    });

                    agentIndex++;

                } else {
                    if (el.querySelector(INTERACTIVE_SELECTOR)) continue;

                    const text = (el.innerText || "").trim().replace(/\\s+/g, ' ').slice(0, 125);
                    if (!text) continue;

                    // Skip text elements that duplicate an interactive element's name
                    if (interactiveNames.has(text)) continue;

                    snapshot.push({
                        kind: "text",
                        text,
                    });
                }
            }

            return snapshot;
        }
    """)

    lines = []
    for el in snapshot:
        if el["kind"] == "interactive":
            info = f"[{el['index']}] {el['role']}: \"{el['name']}\""
            attrs = []
            if el["id"]:   attrs.append(f"id={el['id']}")
            if el["type"]: attrs.append(f"type={el['type']}")
            attr_str = f" ({', '.join(attrs)})" if attrs else ""
            lines.append(f"{info}{attr_str}")
        else:
            lines.append(el["text"])

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