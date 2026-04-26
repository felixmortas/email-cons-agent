"""
Execution Context

Defines the structure for the agent's runtime environment, maintaining state
information including the Playwright page object, website details, user 
identifiers, and service clients throughout the workflow execution.
"""

from typing import TypedDict

class Context(TypedDict):
    """Execution context containing the Playwright page"""
    page: object
    website_name: str
    user_names: list[str | None]
    old_outlook_service: object
    new_outlook_service: object
    llm_name: str