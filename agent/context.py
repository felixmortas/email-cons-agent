from typing import Optional, TypedDict

class Context(TypedDict):
    """Execution context containing the Playwright page"""
    page: object
    website_name: str
    outlook_service: object
    llm_name: str