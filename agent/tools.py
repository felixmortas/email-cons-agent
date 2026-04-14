from typing import Annotated

from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context
from agent.browser_helpers import extract_semantic_html, _click_element, _fill_text_field

@tool
async def read_page_html(runtime: ToolRuntime[Context], tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
    """
    Returns compact page elements: <tag>text</tag> or <tag id="x" class="y" type="z">
    """
    page = runtime.context['page']
    html_content = await extract_semantic_html(page)

    return Command(update={
        'current_url': page.url,
        "messages": [ToolMessage(
            content=f"HTML Content:\n{html_content}",
            tool_call_id=tool_call_id,
        )]
    })


@tool
async def click_element(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    text: str = "",
    tag: str = "",
    id_name: str = "",
    class_name: str = "",
    type_name: str = ""
) -> Command:
    """
    Clicks a DOM element identified by a unique combination of attributes, then returns the updated page elements.

    Provide at least tag and another attribute to uniquely identify the target element.

    Exemple: text, tag OR tag, class_name, type_name

    Args:
        text: Visible text content of the element (e.g. link text); [REQUIRED if possible]
        tag: HTML tag name of the element (e.g. "button", "a", "input"); [REQUIRED]
        id_name: The element's `id` attribute; [REQUIRED if possible]
        class_name: One or more CSS classes on the element (space-separated); [REQUIRED if possible]
        type_name: The element's `type` attribute (e.g. "submit", "checkbox"). [REQUIRED if possible]

    Returns:
        A compact representation of the page elements after the click.
    """
    page = runtime.context["page"]

    navigation_occurred = False

    async def do_click_and_read():
        nonlocal navigation_occurred
        click_response = await _click_element(runtime, text, tag, id_name, class_name, type_name)
        return click_response

    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
            click_response = await do_click_and_read()
        navigation_occurred = True
    except Exception:
        # No navigation — click still happened, just no page change
        click_response = await _click_element(runtime, text, tag, id_name, class_name, type_name)

    html_content = await extract_semantic_html(page)
    return Command(update={
        'current_url': page.url,
        "messages": [ToolMessage(
            content=f"{click_response}\n\nHTML Content:\n{html_content}",
            tool_call_id=tool_call_id,
        )]
    })
    
@tool
async def fill_text_field(
    runtime: ToolRuntime[Context],
    identifier: str,
    element_tag: str,
    element_id: str = "",
    element_class: str = "",
    element_type: str = ""
) -> str:
    """
    Fills field using ONE UNIQUE selector.
    The selector is choosed using a unique combination of: tag and/or id and/or class and/or type.
    The 'identifier' parameter determines which credential to use.
    Read the HTML page again if the filling action fails.
    
    ## ⚠️ CRITICAL - CREDENTIALS HANDLING:
    - NEVER ask for credentials - they are AUTOMATICALLY retrieved from environment variables
    - Use fill_text_field with 'identifier' parameter ONLY:
    - DO NOT pass the 'value' parameter - it's handled automatically

    ## FIELD IDENTIFICATION:
    - The website language can be French or English
    - Email field: look for id containing 'email', type='email' or something relevent
    - Password field: look for id containing 'passwd', 'password', type='password' or something relevent

    ## EXAMPLE CALLS:
    ✅ CORRECT: fill_text_field(tag='input', identifier='email', element_id='email', element_class='account_input', element_type='email')
    ✅ CORRECT: fill_text_field(tag='input', identifier='password', element_id='passwd', element_class='account_input', element_type='password')
        
    Args:
        identifier: 'EMAIL' | 'PASSWORD' | 'NEW_EMAIL' (REQUIRED)
        element_tag: HTML tag from read_page_html (e.g., 'input') (REQUIRED)
        element_id: HTML id from read_page_html (e.g., 'email', 'passwd')
        element_class: HTML class from read_page_html (e.g., 'account_input')
        element_type: HTML type from read_page_html (e.g., 'email', 'password')

    """
    page = runtime.context['page']
    fill_response = await _fill_text_field(runtime, identifier, element_tag, element_id, element_class, element_type)

    if fill_response.startswith('❌'):
        html_content = await extract_semantic_html(page)
        return f"{fill_response}\n\nHTML Content:\n{html_content}"
    return fill_response


@tool
async def complete_step(step: str, runtime: ToolRuntime[Context], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """
    Signals that the step in progress has been completed.

    Args: 
        step: Step of the CURRENT PROGRESS STATE.
    """
    page = runtime.context["page"]
    current_url = page.url

    html_content = await extract_semantic_html(page)

    return Command(update={
        step: True,
        'last_step_url': current_url,
        "messages": [ToolMessage(
            content=f"Step '{step}' marked as complete.\n\nHTML Content: {html_content}",
            tool_call_id=tool_call_id,
        )]
    })



def get_tools() -> list:
    base_tools = [
        read_page_html,
        click_element,
        fill_text_field,
    ]
    return base_tools