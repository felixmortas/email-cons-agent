"""
ReAct Agent for automated email changing.

Usage:
    python main.py --url https://www.agrosemens.com --website Agrosemens
    python main.py --url https://www.agrosemens.com --website Agrosemens --model mistral-large-latest --no-headless
"""

import argparse
import asyncio
from datetime import datetime
import json
import os
import shutil

from dotenv import load_dotenv
load_dotenv()

from context import ContextSchema
from graph import graph
from services.langfuse_engine import langfuse_handler
from services.playwright_session import playwright_session
from services.outlook_service import OutlookService
from services.gui_exclusion import selectionner_sites_gui
from services.user_names_manager import get_user_names

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ReAct Agent for automated email changing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            python main.py --no-headless
            python main.py
            """,
    )

    parser.add_argument("--website", type=str, default=None, help="Nom exact du site à traiter (mode site unique)")
    parser.add_argument("--url", type=str, default=None, help="URL à utiliser à la place de celle du vault")
    parser.add_argument("--model", type=str, default="mistral-small-latest", help="Model name (e.g. mistral-large-latest, gemini-3-flash-preview)",)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser in headless mode",)

    return parser.parse_args()

def _build_outlook_service() -> OutlookService:
    """Instantiate OutlookService from environment variables."""
    return OutlookService(
        client_id=os.getenv("OUTLOOK_CLIENT_ID"),
        client_secret=os.getenv("OUTLOOK_CLIENT_SECRET"),
        refresh_token=os.getenv("OUTLOOK_REFRESH_TOKEN"),
    )

def create_working_copy(original_path: str) -> str:
    """Creates a timestamped copy of the file and returns the new path."""
    name, ext = os.path.splitext(original_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_path = f"{name}_copie_{timestamp}{ext}"
    shutil.copy2(original_path, new_path)
    return new_path

def load_full_json(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_full_json(file_path: str, data: dict):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def validate_and_correct_uri(uri: str) -> str | None:
    """
    Validates and corrects a URI by ensuring it is a valid web URL.
    Adds 'https://www.' prefix if missing, and rejects Android app URIs.

    Args:
        uri (str): The URI to validate and correct.

    Returns:
        str | None: The corrected URI if valid, otherwise None.
    """
    if not uri:
        return None

    # Reject Android app URIs (e.g., intent://, market://)
    if uri.startswith(('intent:', 'market:', 'android-app:')):
        return None

    # Add 'https://www.' if the URI is missing a scheme
    if not uri.startswith(('http://', 'https://')):
        uri = f'https://www.{uri}'

    # Basic check to ensure the URI looks like a valid web URL
    try:
        from urllib.parse import urlparse
        result = urlparse(uri)
        if not all([result.scheme, result.netloc]):
            return None
    except:
        return None

    return uri


async def _process_site(
    *,
    name: str,
    llm_name: str,
    uri: str | None,
    user_names: list[str],
    headless: bool,
    outlook_service: OutlookService,
    # Callback invoked on success so callers can persist state their own way
    on_success,
) -> bool:
    """
    Core processing unit for a single website.
    Isolated from any JSON/credential concerns.

    Returns True on success, False otherwise.
    """
    print(f"Processing {name}...")

    context = ContextSchema(website_name=name, user_names=user_names, outlook_service=outlook_service, llm=llm_name)

    corrected_uri = validate_and_correct_uri(uri)

    initial_state = {
        "messages": [],
        "initial_url": corrected_uri,
    }

    async with playwright_session(context=context, headless=headless):
        final_state = await graph.ainvoke(
            input=initial_state,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_tags": [name]},
            },
            context=context,
        )

        messages = final_state["messages"]
        try:
            result = messages[-1].content
        except IndexError:
            result = "❌ Echec"

        success = result.startswith("✅ Email changé avec succès")

        if success:
            print(f"✅ Succès pour {name}")
            await on_success()

        return success


async def run_single(website: str, url: str | None, user_names: list[str], llm_name: str, headless: bool) -> None:
    """
    Single-site mode: triggered when --website is passed via CLI.

    Credentials (PASSWORD) are read exclusively from the environment.
    The JSON credentials file is never touched here.
    """
    # Parse remaining args (model, headless…) without re-declaring them
    outlook_service = _build_outlook_service()

    # No-op on_success: caller is responsible for any persistence
    async def on_success():
        pass

    await _process_site(
        name=website,
        uri=url,
        llm_name=llm_name,
        user_names=user_names,
        headless=headless,
        outlook_service=outlook_service,
        on_success=on_success,
    )


async def run_batch(
    full_data: dict,
    working_file: str,
    email_cible: str,
    exclusions: list,
    new_email: str,
    user_names: list[str],
    llm_name: str,
    headless: bool,
) -> None:
    """
    Batch mode: iterates over all matching items from the JSON vault.
    Persists updates to working_file after each successful processing.
    """
    outlook_service = _build_outlook_service()

    for i, item in enumerate(full_data.get("items", [])):
        login = item.get("login", {})

        # Filter: only the target email, skip excluded indices
        if login.get("username") != email_cible or i in exclusions:
            continue

        # Resolve password
        os.environ["PASSWORD"] = login.get("password")

        uris = login.get("uris", [])
        first_raw_uri = uris[0].get("uri") if uris else None

        # Closure captures i/item/full_data for deferred write-on-success
        def make_on_success(idx: int):
            async def on_success():
                # Update email in-place and persist immediately
                full_data["items"][idx]["login"]["username"] = new_email
                save_full_json(working_file, full_data)
                print(f"Fichier {working_file} mis à jour.")
            return on_success

        await _process_site(
            name=item.get("name"),
            uri=first_raw_uri,
            llm_name=llm_name,
            user_names=user_names,
            headless=headless,
            outlook_service=outlook_service,
            on_success=make_on_success(i),
        )


def main() -> None:
    args = parse_args()

    # Get user names, nicknames or initials to find Profil page
    user_names = get_user_names()

    # ── Single-site mode ────────────────────────────────────────────────────
    if args.website:
        # PASSWORD must already be set in the environment by the caller
        asyncio.run(run_single(website=args.website, url=args.url, user_names=user_names, llm_name=args.model, headless=args.headless))
        return

    # ── Batch mode (reads credentials from JSON vault) ───────────────────────
    original_file = "data/bitwarden_export_20260421213304.json"

    # 1. Create a working copy to avoid mutating the original
    working_file = create_working_copy(original_file)
    print(f"Fichier de travail créé : {working_file}")

    # 2. Load vault data from the copy
    full_data = load_full_json(working_file)

    # 3. Resolve target email (env var or interactive prompt)
    if os.getenv("EMAIL") is None:
        email_cible = input("Entrez l'adresse email à modifier : ")
        os.environ["EMAIL"] = email_cible
    else:
        email_cible = os.environ["EMAIL"]

    # 4. Resolve new email
    if os.getenv("NEW_EMAIL") is None:
        new_email = input("Entrez la nouvelle adresse email : ")
        os.environ["NEW_EMAIL"] = new_email
    else:
        new_email = os.environ["NEW_EMAIL"]

    # 5. Let user exclude specific sites via GUI
    exclusions = selectionner_sites_gui(full_data, email_cible)

    # 6. Run the batch
    asyncio.run(run_batch(full_data, working_file, email_cible, exclusions, new_email, user_names, args.model, args.headless))


if __name__ == "__main__":
    # Required on macOS when using multiprocessing with a GUI
    import multiprocessing
    multiprocessing.freeze_support()

    main()