"""
Tool Registry

Centralizes all available LangChain tools and provides a factory function
to retrieve them for graph initialization.
"""

from ..verify_new_email import verify_new_email
from ..click_element import click_element
from ..fill_text_field import fill_text_field
from ..complete_step import complete_step
from ..get_verification_code import get_verification_code
from ..refresh_page_representation import refresh_page_representation


def get_tools() -> list:
    """
    Returns a list of all registered LangChain tools.

    Returns:
        list: List of decorated tool callables ready for LangGraph binding.
    """
    return [click_element, fill_text_field, get_verification_code, verify_new_email, refresh_page_representation, complete_step]