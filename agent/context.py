from typing import Optional, TypedDict

class Context(TypedDict):
    """Execution context containing the Playwright page"""
    page: object
    website_name: str
    user_names: list[str | None]
    old_outlook_service: object
    new_outlook_service: object
    llm_name: str