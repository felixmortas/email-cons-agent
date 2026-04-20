"""Pydantic schemas for LLM structured outputs."""
from pydantic import BaseModel, Field

class URLSelection(BaseModel):
    """Selected URL from search results."""
    
    url: str = Field(
        description="The most likely official homepage URL"
    )

class EmailSelection(BaseModel):
    """Selected email from mailbox read results"""

    id: str = Field(
        description="The email that needs to be opened"
    )

class VerificationCode(BaseModel):
    """Verification code extracted from the email"""

    code: str = Field(
        description="The verification code parsed in the given email"
    )