from typing import Annotated
import time

from inputimeout import inputimeout
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime

from agent.context import Context
from agent.tools.email_utils import extract_verification_url, select_verification_email
from services.outlook_service import OutlookService

@tool
async def verify_new_email(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Vérifie la nouvelle adresse e-mail dans Outlook après un changement d'adresse.
    Cet outil doit être appelé une fois que le changement d'adresse e-mail a été confirmé.

    Returns:
        Un dictionnaire de mise à jour d'état contenant un AIMessage indiquant la réussite, une réussite partielle (modifié mais non vérifié) ou un échec.
    """
    print("[DEBUG] Enter verify new email step")

    # Identifier used to tag outgoing AIMessages so the graph can trace
    # which node produced them.
    function_name="verify_new_email"
        
    # Give the mail server time to deliver the verification email before
    # we start polling the inbox.
    print("Wait for mailbox to receive the verification code email...")
    time.sleep(30)
    print("Finished waiting. Use logique of the node verify_new_email")

    # ── 1. Pull required values from the agent context ────────────────────────
    outlook: OutlookService | None = runtime.context["new_outlook_service"]
    llm_name: str = runtime.context["llm_name"]
    website_name: str = runtime.context["website_name"]

    # ── 2. Run all fallible operations; capture errors without raising ─────────
    # We intentionally avoid calling `interrupt()` inside any of these blocks.
    # Instead we record a human-readable reason so we can trigger the interrupt
    # once, cleanly, outside every try/except.
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

        # ── Step B: Extract the verification URL from the email ──────────────
        # Only attempted if step A succeeded (i.e. no error_reason set yet).
        if error_reason is None:
            try:
                # Retrieve the full email body (HTML stripped to plain text).
                email_content = outlook.read_email(email_id)

                # Ask the LLM to locate and return the verification code.
                url = extract_verification_url(llm_name, email_content)

            except Exception as e:
                # Could not read the email or parse a URL out of it.
                error_reason = f"Impossible d'extraire l'URL de l'e-mail : {e}"
    
    # ── 3. Human-in-the-loop fallback ─────────────────────────────────────────
    # Placing the single interrupt call here — after all fallible logic — guarantees 
    # that its position in the node is stable across executions,
    # which is required for correct index-based resume matching.
    if error_reason is not None:
        # URL has not been retrieved from the email: ask the user to verify the new email itself and give a feedback.
        print(f"\n⚠️ {error_reason}")
        try:
            # Wait 300 secondes (5 minutes)
            raw_input = inputimeout(
                prompt="Veuillez vérifier l'email depuis votre boite mail et confirmer en écrivant \"ok\" (vous avez 5 min) : ", 
                timeout=300
            ).strip().lower()
            
            if raw_input=="ok":
                # User said the new email has been verified. 
                # Complete the step.
                return Command(update={"messages": [ToolMessage(content="✅ Email changé avec succès et vérifié par l'utilisateur. Complète la tâche", name=function_name)]}, tool_call_id=tool_call_id)
            
            # User said the new email has not been verified. 
            # Complete the step anyway.
            return Command(update={"messages": [ToolMessage(content="✅ Email changé avec succès, besoin de vérification dans la boîte mail de l'utilisateur. Complète la tâche.", name=function_name)]}, tool_call_id=tool_call_id)

        except inputimeout.TimeoutOccurred:
            # User did not answer. Complete the step anyway
            print("\nTerminé : Délai de 5 minutes dépassé.")
            # Ici, on renvoie un message d'erreur au LLM pour qu'il sache qu'il a échoué
            return Command(update={"messages": [ToolMessage(content="Erreur : L'utilisateur est absent. Tu peux quand même compléter l'étape.")]}, tool_call_id=tool_call_id)

    print("URL retrieved: ")
    print(url)

    try:
        runtime.context.page.goto(url, wait_until="load")
    except Exception as e:
        # Almost everything worked fine: Could just not navigate to the URL extracted from the email.
        return Command(update={"messages": [ToolMessage(content=f"Impossible d'accéder à l'URL de vérification : {e}. Tu peux quand même compléter l'étape.", name=function_name)]}, tool_call_id=tool_call_id)

    # Everything worked fine: email as been retrieved, read, and URL has been navigated to to verify the new email
    return Command(update={"messages": [ToolMessage(content="✅ Email changé et vérifié avec succès. Complète la tâche.", name=function_name)]}, tool_call_id=tool_call_id)
