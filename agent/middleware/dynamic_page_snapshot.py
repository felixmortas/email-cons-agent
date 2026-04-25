"""
Middleware: dynamic_system_prompt — dynamic page snapshot.

Before each call to the LLM, this middleware fetches a fresh
representation of the current web page and injects it into the system prompt,
replacing the {snapshot} placeholder.

Usage in create_email_agent:
    from agent.middleware.dynamic_page_snapshot import make_dynamic_page_snapshot

    snapshot_mw = make_dynamic_page_snapshot(page)

    return create_agent(
        ...
        middleware=[snapshot_mw, trim_messages, fallback],
        ...
    )
"""
from langchain.agents.middleware import dynamic_prompt, ModelRequest

from agent.tools.utils.page_utils import get_page_representation, look_for_any_captcha

SNAPSHOT_PLACEHOLDER = "{snapshot}"
USERNAMES_PLACEHOLDER = "{user_names}"
CAPTCHA_IDENTIFICATOR_PLACEHOLDER = "{captcha_identificator}"

def make_dynamic_page_snapshot(page):
    @dynamic_prompt
    async def _refresh_snapshot(request: ModelRequest) -> str:
        """
        Returns the final system prompt string. 
        LangChain handles the injection into a SystemMessage for you.
        """
        # 1. Get the base system prompt passed to create_agent
        system_prompt = request.system_prompt or ""
        
        # 2. Get the fresh snapshot
        # Note: ensure 'page' is available in your closure from make_dynamic_page_snapshot
        snapshot = await get_page_representation(page)
        if snapshot=="":
            snapshot = "INDISPONIBLE - Rafraîchit la page"

        captcha_identificator = await look_for_any_captcha(page)

        # 3. Return the combined string
        if SNAPSHOT_PLACEHOLDER in system_prompt:
            system_prompt = system_prompt.replace(SNAPSHOT_PLACEHOLDER, snapshot)

        if USERNAMES_PLACEHOLDER in system_prompt:
            system_prompt = system_prompt.replace(USERNAMES_PLACEHOLDER, ", ".join(request.runtime.context['user_names']))
            
        if CAPTCHA_IDENTIFICATOR_PLACEHOLDER in system_prompt:
            system_prompt = system_prompt.replace(CAPTCHA_IDENTIFICATOR_PLACEHOLDER, captcha_identificator)
        
        return system_prompt
    return _refresh_snapshot