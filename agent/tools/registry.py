"""
Tool Registry

Centralizes all available LangChain tools and provides a factory function
to retrieve them for graph initialization.
"""

from .click_element import click_element
from .fill_text_field import fill_text_field
from .complete_step import complete_step


def get_tools() -> list:
    """
    Returns a list of all registered LangChain tools.

    Returns:
        list: List of decorated tool callables ready for LangGraph binding.
    """
    return [click_element, fill_text_field, complete_step]