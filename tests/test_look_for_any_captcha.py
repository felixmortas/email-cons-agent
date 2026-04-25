"""
Tests for `look_for_any_captcha` (agent.tools.page_utils).

Test strategy
-------------
Unit tests (this module, class TestLookForAnyCaptchaUnit)
    - Fully isolated: the Playwright `Page` object and its child elements are
      replaced by `AsyncMock` instances.  No browser process is started.
    - Cover the logical branches of `look_for_any_captcha`:
        * first selector matches and element is visible  → warning returned
        * element found but not visible                  → empty string
        * query_selector raises an exception             → exception swallowed, loop continues
        * no selector matches at all                     → empty string
        * every known selector pattern is individually reachable
    - Fast and hermetic: suitable for CI without Playwright installed.

Integration tests (class TestLookForAnyCaptchaIntegration)
    - Use a real Chromium browser via Playwright (requires the `page` fixture).
    - Inject synthetic HTML that reproduces real-world CAPTCHA markup.
    - One test loads an actual HTML fixture from disk (Discord login page).
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Page

from agent.tools.utils.page_utils import look_for_any_captcha


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_page(element_visible: bool | None) -> MagicMock:
    """
    Build a minimal mock of a Playwright `Page`.

    Parameters
    ----------
    element_visible:
        - True  → query_selector returns a visible element
        - False → query_selector returns an element that is NOT visible
        - None  → query_selector returns None (element absent from DOM)
    """
    page = MagicMock()

    if element_visible is None:
        # Simulate an absent DOM element
        page.query_selector = AsyncMock(return_value=None)
    else:
        element = MagicMock()
        element.is_visible = AsyncMock(return_value=element_visible)
        page.query_selector = AsyncMock(return_value=element)

    return page


# ---------------------------------------------------------------------------
# Unit tests — no browser, pure logic
# ---------------------------------------------------------------------------

class TestLookForAnyCaptchaUnit:
    """
    Isolated unit tests for `look_for_any_captcha`.

    Every Playwright API call is replaced by an AsyncMock so that these tests
    run without a browser and complete in milliseconds.
    """

    @pytest.mark.asyncio
    async def test_returns_warning_when_first_selector_matches(self):
        """
        A visible element matched by the very first selector must trigger the
        warning message and short-circuit the loop (no further selectors are
        checked).
        """
        page = _make_page(element_visible=True)

        result = await look_for_any_captcha(page)

        assert "⚠️ ATTENTION" in result
        assert "CAPTCHA A ÉTÉ DÉTECTÉ" in result
        assert "interrupt_graph" in result
        # The loop should have stopped after the first hit
        page.query_selector.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_element_not_visible(self):
        """
        An element present in the DOM but not visible (display:none, etc.)
        must NOT be treated as a detected CAPTCHA.
        """
        page = _make_page(element_visible=False)

        result = await look_for_any_captcha(page)

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_element_found(self):
        """
        When query_selector returns None for every selector, the function must
        return an empty string.
        """
        page = _make_page(element_visible=None)

        result = await look_for_any_captcha(page)

        assert result == ""

    @pytest.mark.asyncio
    async def test_exception_in_query_selector_is_swallowed(self):
        """
        If query_selector raises (e.g. frame detached, timeout), the exception
        must be caught silently and the loop must continue with the next
        selector.  The final result depends on the remaining selectors.
        """
        page = MagicMock()
        page.query_selector = AsyncMock(side_effect=Exception("frame detached"))

        # Should not raise, and no captcha detected
        result = await look_for_any_captcha(page)

        assert result == ""

    @pytest.mark.asyncio
    async def test_exception_on_first_selector_then_match_on_second(self):
        """
        Even if the first selector raises, a visible element on the second
        selector must still produce the warning.
        """
        page = MagicMock()
        visible_element = MagicMock()
        visible_element.is_visible = AsyncMock(return_value=True)

        # First call raises, second call returns a visible element
        page.query_selector = AsyncMock(
            side_effect=[Exception("boom"), visible_element]
        )

        result = await look_for_any_captcha(page)

        assert "⚠️ ATTENTION" in result

    @pytest.mark.asyncio
    async def test_exception_on_is_visible_is_swallowed(self):
        """
        If is_visible() itself raises, the bare `except` must catch it and the
        loop must continue without crashing.
        """
        page = MagicMock()
        element = MagicMock()
        element.is_visible = AsyncMock(side_effect=Exception("stale element"))
        page.query_selector = AsyncMock(return_value=element)

        result = await look_for_any_captcha(page)

        assert result == ""

    # -- Individual selector coverage ----------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("selector", [
        "iframe[src*='hcaptcha']",
        "iframe[src*='recaptcha']",
        "iframe[data-hcaptcha-widget-id]",
        "textarea[name='h-captcha-response']",
        ".g-recaptcha",
        "#h-captcha-response",
        "iframe[title*='captcha']",
    ])
    async def test_each_selector_can_trigger_detection(self, selector: str):
        """
        For every CSS selector in captcha_patterns, verify that a match on
        that selector alone is sufficient to return the warning.

        This guards against accidentally removing or misspelling a pattern.
        """
        page = MagicMock()
        visible_element = MagicMock()
        visible_element.is_visible = AsyncMock(return_value=True)

        async def _query(sel):
            # Return a visible element only for the selector under test
            return visible_element if sel == selector else None

        page.query_selector = AsyncMock(side_effect=_query)

        result = await look_for_any_captcha(page)

        assert "⚠️ ATTENTION" in result, (
            f"Selector '{selector}' did not trigger detection"
        )

    # -- Return-value shape --------------------------------------------------

    @pytest.mark.asyncio
    async def test_warning_contains_graphinterrupt_keyword(self):
        """
        The keyword 'GraphInterrupt' must appear in the warning so that the
        LLM agent can parse the instruction to call the interrupt tool.
        """
        page = _make_page(element_visible=True)
        result = await look_for_any_captcha(page)
        assert "interrupt_graph" in result

    @pytest.mark.asyncio
    async def test_no_captcha_returns_exact_empty_string(self):
        """
        The no-captcha path must return exactly `""`, not None or whitespace,
        so callers can safely use `if result:` as the detection guard.
        """
        page = _make_page(element_visible=None)
        result = await look_for_any_captcha(page)
        assert result == ""
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Integration tests — real Playwright browser
# ---------------------------------------------------------------------------

class TestLookForAnyCaptchaIntegration:
    """
    Integration tests that spin up a real Chromium browser via the `page`
    fixture provided by pytest-playwright.

    These tests are slower and require `playwright install chromium`.
    """

    @pytest.mark.asyncio(loop_scope="session")
    async def test_hcaptcha_iframe_detected(self, page: Page):
        """
        An hCaptcha iframe injected into the page must be detected as visible
        and trigger the warning message.
        """
        await page.set_content("""
            <html>
                <body>
                    <h1>Page de test</h1>
                    <iframe src="https://hcaptcha.com/checksite/..."
                            data-hcaptcha-widget-id="123"></iframe>
                    <textarea name="h-captcha-response"
                              style="display:block;"></textarea>
                </body>
            </html>
        """)

        result = await look_for_any_captcha(page)

        assert "⚠️ ATTENTION" in result
        assert "CAPTCHA A ÉTÉ DÉTECTÉ" in result
        assert "interrupt_graph" in result

    @pytest.mark.asyncio(loop_scope="session")
    async def test_clean_page_not_detected(self, page: Page):
        """
        A page with no CAPTCHA markup must return an empty string.
        """
        await page.set_content("""
            <html>
                <body>
                    <h1>Bienvenue sur un site normal</h1>
                    <p>Aucun robot ici.</p>
                </body>
            </html>
        """)

        result = await look_for_any_captcha(page)

        assert result == ""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_hidden_recaptcha_not_detected(self, page: Page):
        """
        A CAPTCHA element hidden via `display:none` must NOT be treated as a
        visible blocker (is_visible returns False for hidden elements).
        """
        await page.set_content("""
            <div class="g-recaptcha" style="display:none;"></div>
        """)

        result = await look_for_any_captcha(page)

        assert result == ""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_captcha_detection_on_real_discord_file(self, page: Page):
        """
        Load a real HTML fixture captured from the Discord login page, which
        is known to embed a CAPTCHA widget.  Verifies that the function works
        against production-like markup rather than hand-crafted HTML.
        """
        current_dir = os.path.dirname(__file__)
        file_path = os.path.join(current_dir, "fixtures", "Discord.html")
        local_url = f"file://{os.path.abspath(file_path)}"

        await page.goto(local_url)

        result = await look_for_any_captcha(page)

        assert "⚠️ ATTENTION" in result