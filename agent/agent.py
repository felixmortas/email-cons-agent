import os

from langchain.agents import create_agent
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.tools import get_tools
from agent.middleware.trim_messages import make_trim_messages
from agent.middleware.model_fallback import fallback
from agent.state import State
from agent.context import Context

def create_email_agent(system_prompt, page, model_name: str = "mistral-large-latest"):
    if model_name.startswith("gemini"):
        model = ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv('GOOGLE_API_KEY')) # gemini-3-flash-preview gemini-2.5-pro gemini-2.5-flash gemini-2.5-flash-lite gemini-2.5-flash-lite-preview-09-2025 gemini-2.5-flash-native-audio-preview-12-2025 gemini-2.5-flash-preview-tts gemini-2.0-flash gemini-2.0-flash-lite
        trim_messages = make_trim_messages(is_gemini=True)

    elif model_name.startswith("mistral"):
        model = ChatMistralAI(model=model_name, api_key=os.getenv('MISTRAL_API_KEY'))
        trim_messages = make_trim_messages(is_gemini=False)

    else:
        raise ValueError(f"Modèle non supporté : {model_name}. Utilisez un modèle 'gemini-*' ou 'mistral-*'.")
    

    return create_agent(
        model=model, 
        tools=get_tools(), 
        state_schema=State, 
        context_schema=Context, 
        middleware=[trim_messages, 
                    fallback],
        system_prompt=system_prompt,
        debug=True
    )