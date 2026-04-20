"""
Get Verification Code Tool

LangChain tool that retrieves a verification code from the Outlook inbox
via the Microsoft Graph API.
"""

from typing import Annotated
import time

from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime

from agent.context import Context
from agent.tools.email_utils import extract_verification_code, select_verification_email
from services.outlook_service import OutlookService


@tool
async def get_verification_code(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    sender: str = "",
) -> Command:
    """
    Récupère un code de vérification reçu par email dans la boîte mail.

    Args:
        sender  — Nom de l'expéditeur du code de vérification
    Returns:
        Le code extrait (str) ou un message d'erreur si aucun code n'est trouvé.

    Example:
        get_verification_code(sender="Auchan")
    """
    # Wait to be sure the email is received
    time.sleep(30)

    # Retrieving the Outlook service from the agent context
    # The context must expose a configured instance of OutlookService.
    outlook: OutlookService | None = runtime.context["outlook_service"]
    if outlook is None:
        return Command(update={"messages": [ToolMessage(
            content="❌ OutlookService non disponible dans le contexte de l'agent.",
            tool_call_id=tool_call_id,
        )]})

    # Search for code
    llm_name = runtime.context["llm_name"]

    # ── Step 1: Select the email ───────────────────────────────────────
    try:
        website_name = runtime.context["website_name"]
        emails_list = outlook.get_recent_emails()

        if not emails_list:
            return Command(update={"messages": [ToolMessage(
                content="❌ Erreur lors de la récupération des emails : aucun email récupéré",
                tool_call_id=tool_call_id,
            )]})
            
        email_id = select_verification_email(llm_name, website_name, emails_list)

    except ValueError as e:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Erreur : {e}",
            tool_call_id=tool_call_id,
        )]})
    except Exception as e:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Erreur lors de la récupération des emails : {e}",
            tool_call_id=tool_call_id,
        )]})

    # ── Step 2: Retrieving the verification code ───────────────────────────────────────

    try:
        email_content = outlook.read_email(email_id)

        code = extract_verification_code(llm_name, email_content)
        

    except ValueError as e:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Erreur : {e}",
            tool_call_id=tool_call_id,
        )]})
    except Exception as e:
        return Command(update={"messages": [ToolMessage(
            content=f"❌ Erreur lors du parsing de l'email : {e}",
            tool_call_id=tool_call_id,
        )]})


    return Command(update={"messages": [ToolMessage(content=code, tool_call_id=tool_call_id)]})