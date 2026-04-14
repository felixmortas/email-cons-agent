from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

from context import ContextSchema

@asynccontextmanager
async def playwright_session(context: ContextSchema, headless: bool = True):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=500)
        context.page = await browser.new_page()
        try:
            yield context
        finally:
            await context.page.close()
