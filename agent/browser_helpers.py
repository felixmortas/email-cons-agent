import os

from langchain.tools import ToolRuntime

from agent.context import Context

async def extract_semantic_html(page) -> str:
    """
    Returns compact page elements with semantic context for LLM navigation decisions.
    Captures headings, forms, alerts, nav landmarks and interactive elements.
    """
    elements = await page.evaluate("""() => {
        const INTERACTIVE = 'button, a[href], input, select, textarea, [role="button"]';
        const SEMANTIC    = 'h1, h2, h3, [role="alert"], [role="status"], [role="dialog"], '
                          + '[aria-live], form, nav, main, .error, .success, .step, '
                          + '[class*="error"], [class*="success"], [class*="step"], '
                          + '[class*="confirm"], [class*="modal"]';

        const seen = new Set();

        function attrs(el) {
            const parts = [];
            if (el.id)                        parts.push(`id="${el.id}"`);
            if (el.name)                      parts.push(`name="${el.name}"`);
            if (el.type)                      parts.push(`type="${el.type}"`);
            if (el.placeholder)               parts.push(`placeholder="${el.placeholder}"`);
            if (el.getAttribute('href'))      parts.push(`href="${el.getAttribute('href')}"`);
            if (el.getAttribute('role'))      parts.push(`role="${el.getAttribute('role')}"`);
            if (el.getAttribute('aria-label')) parts.push(`aria-label="${el.getAttribute('aria-label')}"`);
            if (el.disabled)                  parts.push('disabled');
            if (el.required)                  parts.push('required');
            return parts.length ? ' ' + parts.join(' ') : '';
        }

        function isVisible(el) {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0
                && getComputedStyle(el).visibility !== 'hidden'
                && getComputedStyle(el).display    !== 'none';
        }

        function serialize(el) {
            if (seen.has(el)) return null;
            seen.add(el);

            const tag  = el.tagName.toLowerCase();
            const text = (el.innerText || el.value || '').trim().slice(0, 120);
            const a    = attrs(el);

            return text
                ? `<${tag}${a}>${text}</${tag}>`
                : `<${tag}${a}/>`;
        }

        const results = [];
                                   
        if (document.title) {
            results.push(`<title>${document.title}</title>`);
        }


        // 1. Semantic landmarks first (page context / current step)
        document.querySelectorAll(SEMANTIC).forEach(el => {
            if (isVisible(el)) {
                const s = serialize(el);
                if (s) results.push(s);
            }
        });

        // 2. Interactive elements
        document.querySelectorAll(INTERACTIVE).forEach(el => {
            if (isVisible(el)) {
                const s = serialize(el);
                if (s) results.push(s);
            }
        });

        return results;
    }""")
    return "\n".join(elements)

async def _click_element(
    runtime: ToolRuntime[Context],
    text: str,
    tag_name: str,
    id_name: str,
    class_name: str,
    type_name: str
) -> str:
    """
    Clicks element using exact match strategies:
    - Mode 1: text + tag
    - Mode 2: tag + id/class/type
    Clicks first visible element only. No partial/regex matching.
    """
    page = runtime.context["page"]

    async def try_click(selector: str, label: str) -> str | None:
        try:
            locator = page.locator(selector).first
            if await locator.count() > 0 and await locator.is_visible():
                await locator.scroll_into_view_if_needed()
                await locator.click(timeout=5000)
                return f"✅ Clicked: {label}"
        except Exception:
            pass
        return None

    # ── MODE 1: text + tag → <tag>text</tag> ──────────────────
    if text and tag_name:
        label = f"<{tag_name}>{text}</{tag_name}>"
        result = await try_click(f"{tag_name}:has-text('{text}')", label)
        return result or f"❌ Not found: {label}"

    # ── MODE 2: tag + id/class/type → <tag id='x' class='y'> ──
    if tag_name and (id_name or class_name or type_name):
        selector = tag_name
        attrs = ""
        if id_name:
            selector += f"#{id_name}"
            attrs += f' id="{id_name}"'
        if class_name:
            selector += f".{class_name.split(' ')}"
            attrs += f' class="{class_name}"'
        if type_name:
            selector += f"[type='{type_name}']"
            attrs += f' type="{type_name}"'

        label = f"<{tag_name} {attrs.strip()}>"
        result = await try_click(selector, label)
        return result or f"❌ Not found: {label}"

    # ── INVALID PARAMETERS ─────────────────────────────────────
    return "❌ Invalid params: provide (text + tag_name) OR (tag_name + id_name/class_name)"

async def _fill_text_field(
    runtime: ToolRuntime[Context],
    identifier: str,
    element_tag: str,
    element_id: str,
    element_class: str,
    element_type: str
) -> str:
    """
    Fills field using ONE UNIQUE selector.
    The selector is choosed using a unique combination of: tag and/or id and/or class and/or type.
    The 'identifier' parameter determines which credential to use.
        
    Args:
        identifier: 'EMAIL' | 'PASSWORD' | 'NEW_EMAIL' (REQUIRED)
        element_tag: HTML tag from read_page_html (e.g., 'input') (REQUIRED)
        element_id: HTML id from read_page_html (e.g., 'email', 'passwd')
        element_class: HTML class from read_page_html (e.g., 'account_input')
        element_type: HTML type from read_page_html (e.g., 'email', 'password')
    """
    page = runtime.context["page"]
    value = os.environ.get(identifier, "")
    
    if not value:
        return f"❌ os.environ['{identifier}'] is empty"
    
# Build selector by appending each attribute if present
    selector = element_tag or "*"
    
    if element_id:
        selector += f"#{element_id}"
    
    if element_class:
        # Handle multiple classes: "foo bar" → ".foo.bar"
        classes = ".".join(cls for cls in element_class.split() if cls)
        selector += f".{classes}"
    
    if element_type:
        selector += f"[type='{element_type}']"
    
    try:
        locator = page.locator(selector).first
        if await locator.count() > 0 and await locator.is_visible():
            await locator.fill(value, timeout=5000)
            return f"✅ Filled '{selector}'"
        return f"❌ Element not visible: {selector}"
    except Exception as e:
        return f"❌ Failed: {selector} — {str(e)[:80]}"

async def _navigate_to_url(runtime: ToolRuntime[Context], url: str) -> str:
    """
    Directs the browser to a specific URL.
    """
    page = runtime.context["page"]
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    
    return f"Navigated to {url}"
