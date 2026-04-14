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


@dataclass
class ContextSchema:
    page: Optional[Page] = field(default=None, init=False)