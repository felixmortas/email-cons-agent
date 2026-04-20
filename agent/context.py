from typing import Optional, TypedDict

class Context(TypedDict):
    """Execution context containing the Playwright page"""
    page: object
    website_name: Optional[str]
    outlook_service: Optional[object]
    llm_name: Optional[str] = "mistral-small-latest"