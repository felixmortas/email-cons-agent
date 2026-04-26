"""
Email Change Workflow Graph

Defines the LangGraph state machine responsible for automating the email update process. 
This graph handles URL discovery, browser initialization, authentication, and navigation 
to security settings to perform the final email change.
"""

from langgraph.graph import StateGraph, START, END

from context import ContextSchema
from state import State
from nodes import find_url, init_page, find_login_page, login, open_email_settings, change_email

# ===================== BUILDING THE GRAPH =====================
builder = StateGraph(State, context_schema=ContextSchema)

builder.add_node("find_url", find_url)
builder.add_node("init_page", init_page)
builder.add_node("find_login_page", find_login_page)
builder.add_node("login", login)
builder.add_node("open_email_settings", open_email_settings)
builder.add_node("change_email", change_email)

# ===================== CONDITIONAL EDGES =====================
def is_url_missing(state: State) -> bool:
    initial_url = state.get("initial_url")
    return initial_url is None

# ===================== EDGES =====================
builder.add_conditional_edges(START, is_url_missing, {True: "find_url", False: "init_page"})
builder.add_edge("find_url", "init_page")
builder.add_edge("init_page", "find_login_page")
builder.add_edge("find_login_page", "login")
builder.add_edge("login", "open_email_settings")
builder.add_edge("open_email_settings", "change_email")
builder.add_edge("change_email", END)

graph = builder.compile()
