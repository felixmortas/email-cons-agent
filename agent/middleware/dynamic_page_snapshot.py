"""
Middleware : dynamic_system_prompt — snapshot de page dynamique.

Avant chaque appel au LLM, ce middleware récupère une représentation
fraîche de la page web courante et l'injecte dans le system prompt,
en remplaçant le placeholder {snapshot}.

Usage dans create_email_agent :
    from agent.middleware.dynamic_page_snapshot import make_dynamic_page_snapshot

    snapshot_mw = make_dynamic_page_snapshot(page)

    return create_agent(
        ...
        middleware=[snapshot_mw, trim_messages, fallback],
        ...
    )
"""

from langchain.agents.middleware import dynamic_prompt, ModelRequest

from agent.tools import get_page_representation

SNAPSHOT_PLACEHOLDER = "{snapshot}"

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

        # 3. Return the combined string
        if SNAPSHOT_PLACEHOLDER in system_prompt:
            return system_prompt.replace(SNAPSHOT_PLACEHOLDER, snapshot)
        
        return f"{system_prompt}\n\n## 🖥️ ÉTAT ACTUEL DE LA PAGE\n{snapshot}"
    return _refresh_snapshot