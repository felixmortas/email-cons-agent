from typing import Annotated, Optional
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context

# Helper to get the snapshot consistently across tools
async def get_aria_snapshot(page) -> str:
    """Retrieves the YAML-style accessibility snapshot of the page body."""
    print("Enter get aria snapshot")
    return await page.locator("body").aria_snapshot()
    # return await page.ariaSnapshot(mode="ai")

# @tool
# async def read_page_snapshot(runtime: ToolRuntime[Context], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
#     """
#     Returns a YAML representation of the page's semantic structure (Accessibility Tree).
#     Use this to identify roles (button, link, heading) and names for interaction.
#     """
#     print("read snapshot tool")
#     page = runtime.context['page']
#     snapshot = await get_aria_snapshot(page)
#     print("snapshot get")

#     return Command(update={
#         "messages": [ToolMessage(
#             content=f"Current Page Snapshot (YAML):\n{snapshot}",
#             tool_call_id=tool_call_id,
#         )]
#     })

@tool
async def click_element(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    role: str,
    name: str,
) -> Command:
    """
    Clique sur un élément interactif de la page web en le ciblant par son rôle ARIA et son nom d'accessibilité, tels qu'ils apparaissent dans l'instantané ARIA courant.

    Utiliser cet outil pour simuler un clic utilisateur sur des boutons, liens,
    cases à cocher, onglets ou tout autre élément interactif identifiable par ARIA.

    Args:
        role (str): Rôle ARIA de l'élément cible tel qu'il figure dans l'instantané
                    (ex. : "button", "link", "checkbox", "tab", "menuitem", ...).
        name (str): Nom d'accessibilité de l'élément, correspondant à son libellé
                    visible ou à son attribut aria-label
                    (ex. : "Se connecter", "En savoir plus", "Fermer", ...).

    Returns:
        Command: Objet de mise à jour contenant un ToolMessage avec :
            - Une confirmation de succès ou un message d'erreur détaillé.
            - Un nouvel instantané ARIA de la page après le clic, reflétant
            l'état mis à jour (nouvelle page, modal ouverte, contenu rechargé…).

    Examples:
        # Cliquer sur un bouton de soumission
        click_element(role="button", name="Se connecter")

        # Suivre un lien de navigation
        click_element(role="link", name="En savoir plus")

        # Cocher une case
        click_element(role="checkbox", name="Accepter les conditions")

        # Ouvrir un menu déroulant
        click_element(role="menuitem", name="Mon compte")
    """
    print("enter click element tool")
    page = runtime.context["page"]
    
    async def perform_click():
        # Using Playwright's role-based locator which matches the snapshot structure
        locator = page.get_by_role(role, name=name).first
        await locator.click()
        return f"Clic effectué avec succès sur {role} '{name}'"

    try:
        # Attempt to click with a short navigation timeout
        async with page.expect_navigation(wait_until="load", timeout=3000):
            result_msg = await perform_click()
    except Exception:
        # Fallback if no navigation occurs
        try:
            result_msg = await perform_click()
        except Exception as e:
            result_msg = f"❌ Impossible de cliquer sur {role} '{name}': {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{result_msg}\n\Nouvelle page au format Markdown :\n{new_snapshot}",
            tool_call_id=tool_call_id,
        )]
    })

@tool
async def fill_text_field(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    identifier: str,
    role: str = "textbox",
    name: Optional[str] = None,
) -> Command:
    """
    Remplit un champ de saisie avec une valeur confidentielle récupérée depuis le contexte sécurisé de l'agent, en ciblant le champ par son rôle ARIA et son nom d'accessibilité.

    ⚠️  SÉCURITÉ — RÈGLE ABSOLUE :
        Ne jamais transmettre la valeur réelle d'un secret (mot de passe, e-mail…).
        Passer uniquement l'identifiant symbolique correspondant à la clé de
        credentials stockée dans le contexte de l'agent.

    Identifiants symboliques acceptés :
        - "EMAIL"      → adresse e-mail de connexion
        - "PASSWORD"   → mot de passe actuel
        - "NEW_EMAIL"  → nouvelle adresse e-mail (changement de compte)

    Args:
        identifier (str): Clé symbolique du secret à injecter (ex. : "EMAIL",
                        "PASSWORD", "NEW_EMAIL"). Insensible à la casse.
        role (str):       Rôle ARIA du champ cible (défaut : "textbox").
                        Peut être "searchbox", "spinbutton", etc.
        name (str | None): Nom d'accessibilité du champ, correspondant à son
                        libellé ou placeholder dans l'instantané ARIA
                        (ex. : "Adresse e-mail", "Mot de passe").
                        Si None, le premier champ du rôle donné est ciblé.

    Returns:
        Command: Objet de mise à jour contenant un ToolMessage avec :
            - ✅ Confirmation de remplissage réussi avec l'identifiant et le champ ciblé.
            - ❌ Message d'erreur détaillé en cas d'échec de localisation ou de saisie.
            - Un nouvel instantané ARIA de la page après le remplissage.

    Examples:
        # Remplir le champ e-mail
        fill_text_field(identifier="EMAIL", role="textbox", name="Adresse e-mail")

        # Remplir le champ mot de passe
        fill_text_field(identifier="PASSWORD", role="textbox", name="Mot de passe")

        # Remplir un champ de recherche sans nom précis
        fill_text_field(identifier="EMAIL", role="searchbox")

        # Mettre à jour avec une nouvelle adresse e-mail
        fill_text_field(identifier="NEW_EMAIL", role="textbox", name="Nouvel e-mail")
    """
    page = runtime.context['page']
    
    # Logic to retrieve secret from context/env (keeping your original algorithm intent)
    value = runtime.context.get('credentials', {}).get(identifier.lower(), "")
    
    try:
        # Locate by role and name (the name is usually the label or placeholder in the snapshot)
        locator = page.get_by_role(role, name=name).first
        await locator.fill(value)
        response = f"✅ {identifier} saisi dans le {role} '{name}'"
    except Exception as e:
        response = f"❌ Échec de la saisie de {identifier}: {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{response}\n\Nouvelle page au format Markdown :\n{new_snapshot}",
            tool_call_id=tool_call_id,
        )]
    })


def get_tools() -> list:
    return [
        # read_page_snapshot,
        click_element,
        fill_text_field,
    ]