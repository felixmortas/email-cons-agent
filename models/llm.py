"""Pydantic schemas for LLM structured outputs."""
from pydantic import BaseModel, Field

class URLSelection(BaseModel):
    """Selected URL from search results."""
    
    url: str = Field(
        description="The most likely official homepage URL"
    )