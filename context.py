"""
Context Schema

Defines the data structure for the execution context, including user information, 
browser state via Playwright, and services for Outlook integration.
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
    old_outlook_service: OutlookService
    new_outlook_service: OutlookService
    llm: str
