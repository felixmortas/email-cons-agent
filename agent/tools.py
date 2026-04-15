import os
from typing import Annotated
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain.tools import InjectedToolCallId, tool, ToolRuntime
from agent.context import Context

async def extract_interactive_elements(page):
    elements = await page.evaluate("""
    () => {
        const roles = [
            "button", "link", "textbox", "checkbox", "radio"
        ];

        function getRole(el) {
            return el.getAttribute("role") || el.tagName.toLowerCase();
        }

        function getName(el) {
            return (
                el.innerText ||
                el.getAttribute("aria-label") ||
                el.getAttribute("alt") ||
                ""
            ).trim();
        }

        return Array.from(document.querySelectorAll("button, a, input, [role]"))
            .map(el => {
                return {
                    role: getRole(el),
                    name: getName(el),
                    id: el.id || "",
                    class: el.className || "",
                    type: el.type || "",
                };
            });
    }
    """)
    return elements

async def format_elements(elements):
    lines = []
    display_index = 0  # Counter for valid elements

    for el in elements:
        name = el["name"]
        element_id = el["id"]
        element_type = el["type"]

        # Filter: Skip elements that have no name, no id, and no type
        if not name and not element_id and not element_type:
            continue

        attrs = []
        if element_id:
            attrs.append(f"id={element_id}")
        if element_type:
            attrs.append(f"type={element_type}")

        attr_str = f" [{' '.join(attrs)}]" if attrs else ""
        display_name = name if name else "[no-name]"

        # Use the display_index and then increment it
        lines.append(f"- [{display_index}] {el['role']}: {display_name}{attr_str}")
        display_index += 1

    return "\n".join(lines)

async def get_page_representation(page):
    elements = await extract_interactive_elements(page)
    return await format_elements(elements)

# ── LangChain Tools ──────────────────────────────────────────────────────────

@tool
async def click_element(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    index: int,
) -> Command:
    """
    Clique sur un élément interactif en utilisant son INDEX tel qu'affiché dans la représentation actuelle de la page.

    ⚠️ IMPORTANT :
    - L'index correspond EXACTEMENT à celui affiché dans la liste des éléments interactifs.
    - Toujours choisir l'index le plus pertinent selon le contexte utilisateur.

    L'index permet de sélectionner des éléments même lorsqu'ils n'ont :
    - pas de texte
    - pas de nom accessible (ex: boutons icône comme "account")

    Args:
        index (int): Position de l'élément dans la liste affichée (ex: [0], [1], [2], ...)

    Returns:
        Command contenant :
        - Résultat du clic (succès ou erreur)
        - Nouvelle représentation de la page

    Examples:
        click_element(index=3)  # Clique sur le 4ème élément affiché
    """

    page = runtime.context["page"]

    # 🔥 même logique que ton extractor → cohérence parfaite
    locator = page.locator("button, a, input, [role]")

    count = await locator.count()

    # ❌ sécurité index
    if index < 0 or index >= count:
        result = f"❌ Index {index} invalide (max: {count-1})"

        return Command(update={
            "messages": [ToolMessage(
                content=result,
                tool_call_id=tool_call_id,
            )]
        })

    element = locator.nth(index)

    # 🔍 debug info (très utile pour LLM + logs)
    try:
        tag = await element.evaluate("el => el.tagName")
        el_id = await element.get_attribute("id")
        text = await element.inner_text()
    except:
        tag, el_id, text = "?", "", ""

    # ❌ visibilité
    try:
        visible = await element.is_visible()
        if not visible:
            result = f"❌ Élément index {index} non visible"

            return Command(update={
                "messages": [ToolMessage(
                    content=result,
                    tool_call_id=tool_call_id,
                )]
            })
    except:
        pass

    # 🚀 clic avec gestion navigation
    try:
        async with page.expect_navigation(wait_until="load", timeout=5000):
            await element.click()
        result = f"✅ Click (nav) sur index {index} ({tag} id={el_id})"

    except Exception:
        try:
            await element.click()
            result = f"✅ Click (no-nav) sur index {index} ({tag} id={el_id})"
        except Exception as e:
            result = f"❌ Erreur click index {index}: {str(e)}"

    return Command(update={
        "messages": [ToolMessage(
            content=result,
            tool_call_id=tool_call_id,
        )]
    })

@tool
async def fill_text_field(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
    index: int,
    identifier: str,
) -> Command:
    """
    Remplit un champ de saisie en utilisant un ciblage hybride :
    - Index issu du snapshot (prioritaire)
    - Fallback DOM intelligent

    🔐 RÉCUPÉRATION DES SECRETS :
        Les credentials sont chargés depuis le fichier `.env`
        via les variables d'environnement.

        Clés attendues :
            - EMAIL
            - PASSWORD
            - NEW_EMAIL

    ⚠️ SÉCURITÉ :
        Aucune valeur réelle n'est exposée au LLM.

    STRATÉGIE :

    1. 🎯 Index → correspond directement au snapshot
    2. 🔁 Fallback DOM :
        - input[type=email]
        - input[type=password]
        - autres heuristiques

    Args:
        index (int): Index du champ dans le snapshot
        identifier (str): "EMAIL", "PASSWORD", "NEW_EMAIL"

    Returns:
        Command avec résultat + nouveau snapshot
    """

    page = runtime.context["page"]

    # 🔐 1. Lecture depuis .env
    value = os.getenv(identifier.upper())

    if not value:
        return Command(update={
            "messages": [ToolMessage(
                content=f"❌ Variable d'environnement '{identifier}' introuvable dans .env",
                tool_call_id=tool_call_id,
            )]
        })

    try:
        # 🎯 2. Ciblage principal via index
        elements = await page.locator("input, textarea, [contenteditable=true]").all()

        if index < len(elements):
            await elements[index].fill(value)
            result = f"✅ {identifier} rempli via index {index}"
        else:
            raise Exception("Index hors limite")

    except Exception as e:
        # 🔁 3. Fallback intelligent
        try:
            locator = None

            if identifier.upper() == "EMAIL":
                locator = page.locator("input[type='email']").first

            elif identifier.upper() == "PASSWORD":
                locator = page.locator("input[type='password']").first

            elif identifier.upper() == "NEW_EMAIL":
                locator = page.locator("input[type='email']").nth(1)

            if locator and await locator.count() > 0:
                await locator.fill(value)
                result = f"✅ {identifier} rempli via fallback DOM"

            else:
                raise Exception("Aucun champ trouvé")

        except Exception as fallback_error:
            result = f"❌ Erreur: {str(e)} | Fallback: {str(fallback_error)}"


    return Command(update={
        "messages": [ToolMessage(
            content=result,
            tool_call_id=tool_call_id,
        )]
    })

@tool
async def complete_step(
    runtime: ToolRuntime[Context],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Marque l'étape actuelle comme réussie et sauvegarde l'URL actuelle.
    À appeler juste avant de renvoyer le message final avec ✅.
    """
    page = runtime.context["page"]
    current_url = page.url
    
    return Command(
        update={
            # Met à jour le state du Graph parent
            "fallback_url": current_url,
            "messages": [ToolMessage(
                content=f"✅ Étape sauvegardée à l'URL : {current_url}",
                tool_call_id=tool_call_id,
            )]
        }
    )

def get_tools() -> list:
    return [
        click_element,
        fill_text_field,
        complete_step,
    ]