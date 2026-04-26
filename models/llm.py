"""
Pydantic Schemas for LLM Structured Outputs

This module defines the data structures used to enforce type safety and 
schema validation for the Large Language Model's structured responses. 
It includes schemas for URL selection, email identification, and 
verification data extraction.
"""

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

class VerificationURL(BaseModel):
    """Verification URL extracted from the email"""

    url: str = Field(
        description="The verification URL parsed in the given email"
    )