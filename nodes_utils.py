"""
Email-Change Agent Utilities & Core Logic

This module provides essential orchestration logic and configuration for the email-change 
automation agent. It handles dynamic prompt loading, state management, and robust 
error recovery through a ReAct-based retry mechanism.
"""

from pathlib import Path
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphInterrupt
from agent.agent import create_email_agent
from agent.context import Context
from agent.tools.stop_execution import StopExecutionError
from state import AgentInputState

# ── Configuration ────────────────────────────────────────────────────────────
PROMPTS_DIR = Path(__file__).parent / "prompts"
MAX_RETRIES = 3

def _load_prompt(filename: str) -> str:
    """Read a system prompt markdown file from the prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

async def _invoke_with_retry(
    agent_factory,
    page,
    context: Context,
    function_name: str,
    input_data: AgentInputState,
    max_retries: int = MAX_RETRIES,
) -> str:
    """
    Invoke a ReAct agent up to `max_retries` times.
    The agent is considered successful when its last message is a ToolMessage from the `complete_step` tool.
    If an AIMessage is the last message, the agent is recreated from scratch (fresh system prompt & ARIA snapshot) and retried.

    Args:
        agent_factory: Zero-argument async callable that returns a compiled ReAct agent.
        page: Playwright Page instance (used to refresh ARIA on retries).
        context: Agent context forwarded to `ainvoke`.
        function_name: Human-readable node name used in logging and error messages.
        max_retries: Maximum number of attempts (default: MAX_RETRIES = 3).

    Returns:
        The final message content string (starting with ✅).

    Raises:
        GraphInterrupt: Raised after `max_retries` failed attempts. Halts the graph and surfaces the last error.
    """
    last_content = " "
    fallback_url = input_data.get("fallback_url") or input_data.get("initial_url")

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"[{function_name}] Retry {attempt}: Reset to {fallback_url}")
            await page.goto(fallback_url, wait_until="load")
        agent = agent_factory()
        inputs = {"messages": [HumanMessage("A partir de l'historique de la conversation et de la représentation de la page actuelle, analyse la situation. Créer un plan étape par étpae pour arriver à remplir ta mission et améliore le à chaque itération. Ensuite, appelle les outils dont tu as besoin")]}
        try:
            result = await agent.ainvoke(inputs, context=context)
        except StopExecutionError as e:
            # Tool explicitly requested a halt — surface it as a GraphInterrupt
            raise GraphInterrupt(
                f"[{function_name}] stop_execution called: {e.reason}"
            )
        
        messages = result["messages"]
        last_content = messages[-1].content

        for message in reversed(messages):
            if isinstance(message, ToolMessage):
                if message.name == "complete_step":
                    return last_content

        print(
            f"[{function_name}] Attempt {attempt}/{max_retries} failed: "
            f"{last_content}"
        )

    # All retries exhausted — halt the graph
    raise GraphInterrupt(
        f"[{function_name}] Failed after {max_retries} attempts. "
        f"Last error: {last_content}"
    )

async def create_and_invoke_agent_with_retry(state, runtime, function_name) -> str:
    system_prompt = _load_prompt(f"{function_name}.md")
    page = runtime.context.page
    llm_name = runtime.context.llm
    context = Context(
        page=page, 
        website_name=runtime.context.website_name, 
        user_names=runtime.context.user_names, 
        old_outlook_service=runtime.context.old_outlook_service, 
        new_outlook_service=runtime.context.new_outlook_service, 
        llm_name=llm_name
    )

    content = await _invoke_with_retry(
        agent_factory=lambda: create_email_agent(system_prompt, page, llm_name),
        page=page,
        context=context,
        function_name=function_name,
        input_data=state,
    )
    return content
