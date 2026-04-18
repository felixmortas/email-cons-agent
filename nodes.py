"""
Graph nodes for the email-change agent.
Each ReAct node:
- Reads `page` from state (set once by init_page)
- Loads its own system prompt from /prompts/
- Invokes a fresh ReAct agent (with up to MAX_RETRIES retries on ❌)
- Returns only a single AIMessage summary — never the full internal chain

Token usage stays flat because the internal ReAct chain (tool calls +
observations) is discarded after each node; only the final one-sentence
summary is appended to graph state.
"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.runtime import Runtime
from agent.agent import create_email_agent
from agent.context import Context
from models.llm import URLSelection
from state import State, AgentInputState
from context import ContextSchema
from search_engine import search_engine
from nodes_utils import load_prompt, invoke_with_retry

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
    await page.wait_for_timeout(10000)
    return {}

# ── ReAct nodes ───────────────────────────────────────────────────────────────
async def find_login_page(state: AgentInputState, runtime: Runtime[ContextSchema]) -> State:
    """
    Navigate to the website's login page.
    Retries up to MAX_RETRIES times on ❌. Halts graph on persistent failure.
    Returns a summary AIMessage appended to graph state messages.
    """
    print("enter find_login_page")
    function_name = "find_login_page"
    system_prompt = load_prompt(f"{function_name}.md")
    page = runtime.context.page
    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
        input_data=state,
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
    system_prompt = load_prompt(f"{function_name}.md")
    page = runtime.context.page
    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
        input_data=state,
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
    system_prompt = load_prompt(f"{function_name}.md")
    page = runtime.context.page
    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
        input_data=state,
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
    system_prompt = load_prompt(f"{function_name}.md")
    page = runtime.context.page
    content = await invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page),
        page=page,
        context=Context(page=page),
        function_name=function_name,
        input_data=state,
    )
    return {"messages": [AIMessage(content=content, name=function_name)]}