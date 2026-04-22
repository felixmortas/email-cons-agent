import os

from langchain.agents import create_agent
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents.middleware import ToolCallLimitMiddleware, ModelCallLimitMiddleware

from agent.tools import get_tools
from agent.middleware.model_fallback import fallback
from agent.middleware.dynamic_page_snapshot import make_dynamic_page_snapshot
from agent.state import State
from agent.context import Context

def create_email_agent(system_prompt, page, model_name: str = "mistral-large-latest"):
    if model_name.startswith("gemini"):
        model = ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv('GOOGLE_API_KEY')) # gemini-3-flash-preview gemini-2.5-pro gemini-2.5-flash gemini-2.5-flash-lite gemini-2.5-flash-lite-preview-09-2025 gemini-2.5-flash-native-audio-preview-12-2025 gemini-2.5-flash-preview-tts gemini-2.0-flash gemini-2.0-flash-lite

    elif model_name.startswith("mistral"):
        model = ChatMistralAI(model=model_name, api_key=os.getenv('MISTRAL_API_KEY'))

    else:
        raise ValueError(f"Modèle non supporté : {model_name}. Utilisez un modèle 'gemini-*' ou 'mistral-*'.")
    
    page_snapshot = make_dynamic_page_snapshot(page)

    # Allow only one use of this tool so the agent doesn't run in an infinite loop. If used another time, end ReAct agent invocation
    refresh_page_limit = ToolCallLimitMiddleware(
        run_limit=1,                                # max 1 call
        tool_name="refresh_page_representation",    # only for this tool
        exit_behavior="end"                         # bloc the tool use instead of crashing
    )

    call_tracker = ModelCallLimitMiddleware(run_limit=7, exit_behavior="end")


    return create_agent(
        model=model, 
        tools=get_tools(), 
        state_schema=State, 
        context_schema=Context, 
        middleware=[call_tracker,
                    page_snapshot,
                    fallback,
                    refresh_page_limit],
        system_prompt=system_prompt,
        debug=False
    )