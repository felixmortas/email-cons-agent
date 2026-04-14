import re
from typing import Annotated, Optional
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context

# ── Actionable ARIA roles ───────────────────────────────────────────────────

# Roles required by the LLM to call `click_element` or `fill_text_field`
_ACTIONABLE_ROLES = {
    # Clickable
    "button", "link", "checkbox", "radio", "tab", "menuitem",
    "menuitemcheckbox", "menuitemradio", "option", "switch",
    "treeitem", "gridcell", "columnheader", "rowheader",
    # Seizable
    "textbox", "searchbox", "spinbutton", "combobox", "listbox",
    "slider", "scrollbar",
    # Useful navigation containers (included for context)
    "navigation", "banner", "main", "form", "dialog",
    "alertdialog", "menu", "menubar", "tablist", "toolbar",
    "listitem",  # kept only when it contains an actionable child
}

# Purely decorative/informational line → always ignored
_IGNORED_ROLES = {
    "img", "image", "separator", "presentation", "none",
    "paragraph", "contentinfo", "status", "log", "timer",
    "progressbar", "meter", "marquee",
}

# Regex that captures (indentation, role, name_fragment)
# Examples of ARIA Playwright lines:
#   - button "Se connecter"
#   - link "Accueil":
#   - textbox "Adresse e-mail"
#   - heading "Mon compte" [level=2]
_LINE_RE = re.compile(
    r'^(?P<indent>\s*)'
    r'-\s+'
    r'(?P<role>[a-zA-Z]+)'
    r'(?:\s+"(?P<name>[^"]*)")?'
    r'(?P<rest>.*)'
)


def clean_aria_snapshot(snapshot: str) -> str:
    """
    Filters an ARIA Playwright snapshot (YAML-like format) to retain
    only the lines useful for `click_element` and `fill_text_field`.

    Strategy:
      1. Parse each line to extract (indentation, role, name).
      2. Keep only lines whose role is actionable.
      3. Remove purely informational heading/img/paragraph/etc. blocks.
      4. Collapse consecutive empty lines.

    Args:
        snapshot: Raw text returned by page.locator(“body”).aria_snapshot()

    Returns:
        Streamlined snapshot, ready to be injected into the LLM prompt.
    """
    lines = snapshot.splitlines()
    kept: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Empty lines or purely structural lines with no function → skip
        if not stripped or stripped.startswith("#"):
            continue

        match = _LINE_RE.match(line)
        if not match:
            # ARIA attribute without a hyphen (e.g., value continuation) → ignored
            continue

        role = match.group("role").lower()
        name = match.group("name") or ""
        indent = match.group("indent")
        rest = match.group("rest").strip()

        # Roles explicitly ignored
        if role in _IGNORED_ROLES:
            continue

        # Headings: We keep only level 1 headings
        # (page title) to provide the minimum context
        if role == "heading":
            level_match = re.search(r'\[level=(\d+)\]', rest)
            level = int(level_match.group(1)) if level_match else 99
            if level <= 1 and name:
                kept.append(f"{indent}- heading \"{name}\"")
            continue

        # Plain text with no clickable elements
        if role == "text":
            continue

        # Actionable step: We'll rebuild the line properly
        if role in _ACTIONABLE_ROLES:
            # We keep the name and, for links, the URL if available
            url_match = re.search(r'/url:\s*(\S+)', rest)
            url_part = f"  →  {url_match.group(1)}" if url_match else ""

            if name:
                kept.append(f"{indent}- {role} \"{name}\"{url_part}")
            else:
                # Unnamed container (e.g., navigation, form) → keep it to
                # indicate the section, but without a superfluous name
                kept.append(f"{indent}- {role}{url_part}")
            continue

        # Any other role not listed → silently ignored

    # Remove duplicate empty rows and return
    result_lines: list[str] = []
    prev_blank = False
    for l in kept:
        is_blank = not l.strip()
        if is_blank and prev_blank:
            continue
        result_lines.append(l)
        prev_blank = is_blank

    return "\n".join(result_lines)


# ── Helper snapshot ───────────────────────────────────────────────────────────

async def get_aria_snapshot(page, clean: bool = True) -> str:
    """
    Retrieves the ARIA snapshot of the page.

    Args:
        page:  Playwright Page instance.
        clean: If True (default), applies clean_aria_snapshot() before
               returning the text, significantly reducing the size
               sent to the LLM.
    """
    print("Enter get aria snapshot")
    raw = await page.locator("body").aria_snapshot()
    return clean_aria_snapshot(raw) if clean else raw


# ── Outils LangChain ──────────────────────────────────────────────────────────

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
        locator = page.get_by_role(role, name=name).first
        await locator.click()
        return f"✅ Clic effectué avec succès sur {role} '{name}'"

    try:
        async with page.expect_navigation(wait_until="load", timeout=10000):
            result_msg = await perform_click()
    except Exception:
        try:
            result_msg = await perform_click()
        except Exception as e:
            result_msg = f"❌ Impossible de cliquer sur {role} '{name}' ou timeout mais click peut-être réussi : {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{result_msg}\nNouvelle page au format Markdown :\n{new_snapshot}",
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
    value = runtime.context.get('credentials', {}).get(identifier.lower(), "")

    try:
        locator = page.get_by_role(role, name=name).first
        await locator.fill(value)
        response = f"✅ {identifier} saisi dans le {role} '{name}'"
    except Exception as e:
        response = f"❌ Échec de la saisie de {identifier}: {str(e)}"

    new_snapshot = await get_aria_snapshot(page)
    return Command(update={
        "messages": [ToolMessage(
            content=f"{response}\nPage au format Markdown :\n{new_snapshot}",
            tool_call_id=tool_call_id,
        )]
    })


def get_tools() -> list:
    return [
        click_element,
        fill_text_field,
    ]