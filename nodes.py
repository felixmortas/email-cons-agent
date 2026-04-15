"""
Graph nodes for the email-change agent.

Each ReAct node:
  1. Reads `page` from state (set once by init_page)
  2. Loads its own system prompt from /prompts/
  3. Invokes a fresh ReAct agent (with up to MAX_RETRIES retries on ❌)
  4. Returns only a single AIMessage summary — never the full internal chain

Token usage stays flat because the internal ReAct chain (tool calls +
observations) is discarded after each node; only the final one-sentence
summary is appended to graph state.
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.errors import GraphInterrupt
from langgraph.runtime import Runtime

from agent.agent import create_email_agent
from agent.context import Context
from agent.tools import get_page_representation
from models.llm import URLSelection
from state import State
from context import ContextSchema
from search_engine import search_engine


# ── Config ────────────────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"
MAX_RETRIES = 3


def _load_prompt(filename: str) -> str:
    """Read a system prompt markdown file."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ── Retry helper ──────────────────────────────────────────────────────────────

async def invoke_with_retry(
    agent_factory,
    page,
    context: Context,
    function_name: str,
    max_retries: int = MAX_RETRIES,
) -> str:
    """
    Invoke a ReAct agent up to `max_retries` times.

    The agent is considered successful when its last message starts with ✅.
    On every ❌ response the agent is recreated from scratch (fresh system
    prompt, fresh ARIA snapshot) and retried.

    Args:
        agent_factory: Zero-argument async callable that returns a compiled
                       ReAct agent. Called once per attempt so each retry
                       starts with a clean message history.
        page:          Playwright Page instance (used to refresh ARIA).
        context:       Agent context forwarded to ainvoke.
        function_name: Human-readable node name used in error messages.
        max_retries:   Maximum number of attempts (default: MAX_RETRIES = 3).

    Returns:
        The final message content string (starting with ✅).

    Raises:
        GraphInterrupt: After `max_retries` failed attempts, which stops
                        the graph entirely and surfaces the last error message.
    """
    last_content = ""

    for attempt in range(1, max_retries + 1):
        aria_content = await get_page_representation(page)
        agent = agent_factory()

        inputs = {
            "messages": [
                HumanMessage(
                    f"Contenu ARIA au format Markdown de la page actuelle du site web\n\n{aria_content}"
                )
            ],
        }

        result = await agent.ainvoke(inputs, context=context)
        last_content = result["messages"][-1].content

        if last_content.startswith("✅"):
            return last_content

        print(
            f"[{function_name}] Attempt {attempt}/{max_retries} failed: "
            f"{last_content[:120]}"
        )

    # All retries exhausted — halt the graph
    raise GraphInterrupt(
        f"[{function_name}] Failed after {max_retries} attempts. "
        f"Last error: {last_content}"
    )


# ── Non-ReAct nodes ───────────────────────────────────────────────────────────

def find_url(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Use the search_engine module to discover the website URL.
    Only reached when `initial_url` is missing from state.
    Writes `initial_url` back to state.
    """
    query = runtime.context.website_name
    search_results = search_engine.search(query=query)
    print(search_results)
    
    llm_name = runtime.context.llm
    model = init_chat_model(llm_name).with_structured_output(URLSelection)
    prompt = f"Given the website name '{query}', pick the most likely official homepage URL from this list: {search_results}. Return the URL in a JSON format without any other text or explanation.\n\nExample output:\n{{\"url\": \"https://www.example.com/\"}}"
    response = model.invoke([HumanMessage(content=prompt)])
    return {"initial_url": response.url}

async def init_page(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate the Playwright page to `initial_url`.
    The `page` object is already in state, injected by main.py before invoke.
    Returns an empty State — page is a live reference, no copy needed.
    """
    page = runtime.context.page
    url: str = state["initial_url"]
    await page.goto(url, wait_until="load")
    return {}


# ── ReAct nodes ───────────────────────────────────────────────────────────────

async def find_login_page(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate to the website's login page.
    Retries up to MAX_RETRIES times on ❌. Halts graph on persistent failure.
    Returns a summary AIMessage appended to graph state messages.
    """
    print("enter find_login_page")
    function_name = "find_login_page"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page

    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
    )

    return {"messages": [AIMessage(content=content, name=function_name)]}


async def login(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Log in using credentials from environment variables (EMAIL, PASSWORD).
    Retries up to MAX_RETRIES times on ❌. Halts graph on persistent failure.
    Returns a summary AIMessage.
    """
    print("enter login")
    function_name = "login"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page

    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
    )

    return {"messages": [AIMessage(content=content, name=function_name)]}


async def open_email_settings(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate to the account section where the email address can be changed.
    Retries up to MAX_RETRIES times on ❌. Halts graph on persistent failure.
    Returns a summary AIMessage.
    """
    print("enter open_email_settings")
    function_name = "open_email_settings"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page

    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
    )

    return {"messages": [AIMessage(content=content, name=function_name)]}


async def change_email(state: State, runtime: Runtime[ContextSchema]) -> State:
    """
    Fill and submit the email change form.
    Retries up to MAX_RETRIES times on ❌. Halts graph on persistent failure.
    Returns a summary AIMessage.
    """
    print("enter change_email")
    function_name = "change_email"
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page

    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
    )

    return {"messages": [AIMessage(content=content, name=function_name)]}