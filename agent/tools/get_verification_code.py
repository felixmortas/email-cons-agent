"""
Get Verification Code Tool

LangChain tool that retrieves a verification code from the Outlook inbox
via the Microsoft Graph API.
"""

from typing import Annotated
import time

from inputimeout import inputimeout, TimeoutOccurred
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime

from agent.context import Context
from agent.tools.utils.email_utils import extract_verification_code, select_verification_email
from services.outlook_service import OutlookService

@tool
async def get_verification_code(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Récupère un code de vérification reçu par email dans la boîte mail de l'utilisateur.
    Avant d'appeler l'outil, soit sûr d'être sur la page qui te demande le code. Parfois, tu peux avoir besoin de cliquer sur un bouton "Suivant" pour recevoir le code.

    Returns:
        Le code extrait (str) ou un message d'erreur si aucun code n'est trouvé.

    Example:
        get_verification_code()
    """
    print("[DEBUG] Use tool get_verification_code")
    print("Wait for mailbox to receive the verification code email...")
    time.sleep(30)
    print("Finished waiting. Use logique of the tool get_verification_code")

    # ── 1. Pull required values from the agent context ────────────────────────
    outlook: OutlookService | None = runtime.context["old_outlook_service"]
    llm_name: str = runtime.context["llm_name"]
    website_name: str = runtime.context["website_name"]

    # ── 2. Run all fallible operations; capture errors without raising ─────────
    # We intentionally avoid calling `interrupt()` inside any of these blocks.
    # Instead we record a human-readable reason so we can trigger the interrupt
    # once, cleanly, outside every try/except.
    code: str | None = None
    error_reason: str | None = None

    if outlook is None:
        # Service was never injected into the context — nothing we can do
        # programmatically, so we will ask the user.
        error_reason = (
            "Impossible de se connecter à la boîte aux lettres (OutlookService n'est pas disponible)."
        )
    else:
        # ── Step A: Select the right email ────────────────────────────────────
        # Fetch recent emails and let the LLM pick the one that most likely
        # contains the verification code for the current website.
        try:
            emails_list = outlook.get_recent_emails()

            if not emails_list:
                # Inbox is empty (within the look-back window) — ask the user.
                error_reason = "Aucun e-mail récent n'a été trouvé dans la boîte de réception."
            else:
                # `select_verification_email` returns the Graph API message ID
                # of the best matching email.
                email_id = select_verification_email(llm_name, website_name, emails_list)

        except Exception as e:
            # Network error, Graph API failure, or LLM selector error.
            error_reason = f"Erreur lors de la récupération des e-mails : {e}"

        # ── Step B: Extract the verification code from the email ──────────────
        # Only attempted if step A succeeded (i.e. no error_reason set yet).
        if error_reason is None:
            try:
                # Retrieve the full email body (HTML stripped to plain text).
                email_content = outlook.read_email(email_id)

                # Ask the LLM to locate and return the verification code.
                code = extract_verification_code(llm_name, email_content)

            except Exception as e:
                # Could not read the email or parse a code out of it.
                error_reason = f"Impossible d'extraire le code de l'e-mail : {e}"

    # ── 3. Human-in-the-loop fallback ─────────────────────────────────────────
    # `interrupt()` MUST NOT be placed inside a try/except block: LangGraph
    # suspends the node by raising a special internal exception, and wrapping
    # it in a bare except would swallow that signal and break the pause/resume
    # mechanism entirely.
    #
    # Placing the single interrupt call here — after all fallible logic — also
    # guarantees that its position in the node is stable across executions,
    # which is required for correct index-based resume matching.
    if error_reason is not None:
        print(f"\n⚠️ {error_reason}")
        try:
            # Wait 300 secondes (5 minutes)
            raw_input = inputimeout(
                prompt="Veuillez entrer le code reçu par email (vous avez 5 min) : ", 
                timeout=300
            ).strip()
            code = raw_input
        except TimeoutOccurred:
            print("\nTerminé : Délai de 5 minutes dépassé.")
            # Ici, on renvoie un message d'erreur au LLM pour qu'il sache qu'il a échoué
            return Command(update={"messages": [ToolMessage(
                content="Erreur : L'utilisateur est absent, termine ici sans invoquer d'outil",
                tool_call_id=tool_call_id,
            )]})

    print("Code retrieved: ")
    print(code)

    # ── 4. Return the code (from email or from the user) ──────────────────────
    return Command(update={"messages": [ToolMessage(
        content=code,
        tool_call_id=tool_call_id,
    )]})