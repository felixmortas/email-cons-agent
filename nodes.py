"""
Graph nodes for the email-change agent.

Each ReAct node:
  1. Reads `page` from state (set once by init_page)
  2. Loads its own system prompt from /prompts/
  3. Invokes a fresh ReAct agent
  4. Returns only a single AIMessage summary — never the full internal chain

Token usage stays flat because the internal ReAct chain (tool calls +
observations) is discarded after each node; only the final one-sentence
summary is appended to graph state.
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

# from agent import create_email_agent, invoke_email_agent
from agent.agent import create_email_agent
from agent.context import Context
from agent.tools import get_aria_snapshot
from state import State
# from search_engine import search_engine
from context import ContextSchema


# ── Config ────────────────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"

def _load_prompt(filename: str) -> str:
    """Read a system prompt markdown file."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

# ── Non-ReAct nodes ───────────────────────────────────────────────────────────

def find_url(state: State) -> State:
    """
    Use the search_engine module to discover the website URL.
    Only reached when `initial_url` is missing from state.
    Writes `initial_url` back to state.
    """
    print('find_url')
    website_name = state.get("website_name", "")
    # url = search_engine.search(query=website_name)
    return {"initial_url": "url"}


async def init_page(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate the Playwright page to `initial_url`.
    The `page` object is already in state, injected by main.py before invoke.
    Returns an empty State — page is a live reference, no copy needed.
    """
    print('init_page')
    page = runtime.context.page
    url: str  = state["initial_url"]
    await page.goto(url, wait_until="load")
    return {}


# ── ReAct nodes ───────────────────────────────────────────────────────────────

async def find_login_page(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate to the website's login page.
    Returns a summary AIMessage appended to graph state messages.
    """
    print("enter find login page")
    function_name = "find_login_page"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page
    agent = create_email_agent(system_prompt, page)
    aria_content = await get_aria_snapshot(page)

    inputs = {
        "messages": [
            HumanMessage(f"Contenu ARIA au format Markdown de la page actuelle du site web\n\n{aria_content}")
        ],
    }

    result = await agent.ainvoke(inputs, context=Context(page=page))
    last_message = result["messages"][-1]

    return {"messages": [AIMessage(content=last_message.content, name=function_name)]}


async def login(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Log in using credentials from environment variables (EMAIL, PASSWORD).
    Returns a summary AIMessage.
    """
    print("enter login")
    function_name = "login"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page
    agent = create_email_agent(system_prompt, page)
    aria_content = await get_aria_snapshot(page)

    inputs = {
        "messages": [
            HumanMessage(f"Contenu ARIA au format Markdown de la page actuelle du site web\n\n{aria_content}")
        ],
    }

    result = await agent.ainvoke(inputs, context=Context(page=page))
    last_message = result["messages"][-1]

    return {"messages": [AIMessage(content=last_message.content, name=function_name)]}


async def open_email_settings(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate to the account section where the email address can be changed.
    Returns a summary AIMessage.
    """
    function_name = "open_email_settings"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page
    agent = create_email_agent(system_prompt, page)
    aria_content = await get_aria_snapshot(page)

    inputs = {
        "messages": [
            HumanMessage(f"Contenu ARIA au format Markdown de la page actuelle du site web\n\n{aria_content}")
        ],
    }

    result = await agent.ainvoke(inputs, context=Context(page=page))
    last_message = result["messages"][-1]

    return {"messages": [AIMessage(content=last_message.content, name=function_name)]}


async def change_email(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Fill and submit the email change form.
    Returns a summary AIMessage.
    """
    function_name = "change_email"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page
    agent = create_email_agent(system_prompt, page)
    aria_content = await get_aria_snapshot(page)

    inputs = {
        "messages": [
            HumanMessage(f"Contenu ARIA au format Markdown de la page actuelle du site web\n\n{aria_content}")
        ],
    }

    result = await agent.ainvoke(inputs, context=Context(page=page))
    last_message = result["messages"][-1]

    return {"messages": [AIMessage(content=last_message.content, name=function_name)]}
