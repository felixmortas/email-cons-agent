"""
Playwright Session Manager

This module provides an asynchronous context manager for handling Playwright browser 
sessions with stealth capabilities. It ensures proper initialization and teardown 
of the Chromium browser instance while integrating with the application's context schema.
"""

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from contextlib import asynccontextmanager

from context import ContextSchema

@asynccontextmanager
async def playwright_session(context: ContextSchema, headless: bool = True):
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=500)
        context.page = await browser.new_page()

        try:
            yield context
        finally:
            await context.page.close()
