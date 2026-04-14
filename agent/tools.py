from typing import Annotated, Optional
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context

# Helper to get the snapshot consistently across tools
async def get_aria_snapshot(page) -> str:
    """Retrieves the YAML-style accessibility snapshot of the page body."""
    print("Enter get aria snapshot")
    return await page.locator("body").aria_snapshot()
    # return await page.ariaSnapshot(mode="ai")

# @tool
# async def read_page_snapshot(runtime: ToolRuntime[Context], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
#     """
#     Returns a YAML representation of the page's semantic structure (Accessibility Tree).
#     Use this to identify roles (button, link, heading) and names for interaction.
#     """
#     print("read snapshot tool")
#     page = runtime.context['page']
#     snapshot = await get_aria_snapshot(page)
#     print("snapshot get")

#     return Command(update={
#         "messages": [ToolMessage(
#             content=f"Current Page Snapshot (YAML):\n{snapshot}",
#             tool_call_id=tool_call_id,
#         )]
#     })

@tool
async def click_element(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    role: str,
    name: str,
) -> Command:
    """
    Clicks an element based on its ARIA role and accessible name found in the snapshot.
    
    Example: role="button", name="Sign In" or role="link", name="Learn More"
    """
    print("enter click element tool")
    page = runtime.context["page"]
    
    async def perform_click():
        # Using Playwright's role-based locator which matches the snapshot structure
        locator = page.get_by_role(role, name=name).first
        await locator.click()
        return f"Successfully clicked {role} '{name}'"

    try:
        # Attempt to click with a short navigation timeout
        async with page.expect_navigation(wait_until="load", timeout=3000):
            result_msg = await perform_click()
    except Exception:
        # Fallback if no navigation occurs
        try:
            result_msg = await perform_click()
        except Exception as e:
            result_msg = f"❌ Failed to click {role} '{name}': {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{result_msg}\n\nNew Page Snapshot:\n{new_snapshot}",
            tool_call_id=tool_call_id,
        )]
    })

@tool
async def fill_text_field(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    identifier: str,
    role: str = "textbox",
    name: Optional[str] = None,
) -> Command:
    """
    Fills a text field using credentials. Matches field by role (usually 'textbox') and name.
    
    ## ⚠️ CREDENTIALS:
    - Pass 'EMAIL', 'PASSWORD', or 'NEW_EMAIL' to identifier.
    - DO NOT pass the actual secret value.
    """
    page = runtime.context['page']
    
    # Logic to retrieve secret from context/env (keeping your original algorithm intent)
    value = runtime.context.get('credentials', {}).get(identifier.lower(), "")
    
    try:
        # Locate by role and name (the name is usually the label or placeholder in the snapshot)
        locator = page.get_by_role(role, name=name).first
        await locator.fill(value)
        response = f"✅ Filled {identifier} into {role} '{name}'"
    except Exception as e:
        response = f"❌ Failed to fill {identifier}: {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{response}\n\nNew Page Snapshot:\n{new_snapshot}",
            tool_call_id=tool_call_id,
        )]
    })


def get_tools() -> list:
    return [
        # read_page_snapshot,
        click_element,
        fill_text_field,
    ]