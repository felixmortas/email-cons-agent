"""
Data class for managing context and configuration of the email consolidation agent.

This class serves as a container for LLM provider settings and Playwright browser
automation objects. It maintains the state of the browser automation environment
throughout the agent's lifecycle.

Attributes:
    page (Optional[Page]): Active Playwright page/tab instance for interactions.
        Initialized at runtime, not through constructor.
"""
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import Page
from services.outlook_service import OutlookService


@dataclass
class ContextSchema:
    website_name: str
    user_names: list[str | None]
    page: Optional[Page] = field(default=None, init=False)
    outlook_service: OutlookService
    llm: str