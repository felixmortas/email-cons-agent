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
    parser.add_argument(
        "--model",
        type=str,
        default="mistral-large-latest",
        help="Model name (e.g. mistral-large-latest, gemini-3-flash-preview)",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser in headless mode",
    )
    return parser.parse_args()

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

async def run(args: argparse.Namespace, full_data: dict, working_file: str, email_cible: str, exclusions: list, new_email: str) -> None:
    
    outlook_service = OutlookService(
        client_id=os.getenv("OUTLOOK_CLIENT_ID"),
        client_secret=os.getenv("OUTLOOK_CLIENT_SECRET"),
        refresh_token=os.getenv("OUTLOOK_REFRESH_TOKEN"),
    )

    # Process
    for i, item in enumerate(full_data.get('items', [])):
        login = item.get('login', {})

        # Filter: Only the target email and items that are not excluded are processed
        if login.get('username') != email_cible or i in exclusions:
            continue

        # We update the OS environment so that the agent's tools can access it
        os.environ["PASSWORD"] = login.get('password', '')
            
        print(f"Processing of {item.get('name')}...")

        context=ContextSchema(website_name=item.get('name'))
        context.outlook_service = outlook_service

        uris = login.get('uris', [])
        first_uri = uris[0].get('uri') if uris else None
        initial_state = {
            "messages": [],
            "initial_url": first_uri,
        }

        async with playwright_session(context=context, headless=args.headless):

            final_state = await graph.ainvoke(
                input=initial_state,
                config={
                    "callbacks": [langfuse_handler],
                    "metadata": {"langfuse_tags": [item.get('name')]},
                },
                context=context
            )

            messages = final_state["messages"]
            try:
                result = messages[-1].content
            except IndexError:
                result = "❌ Echec"

            success = result.startswith('✅')
            
            # 7. Update vault if success
            if success:
                print(f"✅ Succès pour {item.get('name')}")
                
                # UPDATE JSON
                # We modify the full_data object directly
                full_data['items'][i]['login']['username'] = new_email
                
                # Save immediately to the copy to avoid losing data
                save_full_json(working_file, full_data)
                print(f"Fichier {working_file} mis à jour.")


def main() -> None:
    args = parse_args()
    original_file = "data/bitwarden_export_20260421213304.json"
    
    # 1. Creating a working copy
    working_file = create_working_copy(original_file)
    print(f"Fichier de travail créé : {working_file}")

    # 2. Loading data from the copy
    full_data = load_full_json(working_file)
    
    # 3. Reading the email to change
    if os.getenv("EMAIL") is None:
        email_cible = input("Entrez l'adresse email à modifier : ")
        os.environ["EMAIL"] = email_cible
    else:
        email_cible = os.environ["EMAIL"]

    # 4. Display for selection (Exclusions)
    print("\nSites trouvés :")
    indices_valides = []
    for i, item in enumerate(full_data.get('items', [])):
        if item.get('login', {}).get('username') == email_cible:
            print(f"{i}: {item.get('name')}")
            indices_valides.append(i)

    exclusion_input = input("\nEntrez les index à EXCLURE (ex: 1, 5) ou vide : ")
    exclusions = [int(x.strip()) for x in exclusion_input.split(',') if x.strip().isdigit()]

    # 5. Reading the new email
    if os.getenv("NEW_EMAIL") is None:
        new_email = input("Entrez la nouvelle adresse email : ")
        os.environ["NEW_EMAIL"] = new_email
    else:
        new_email = os.environ["NEW_EMAIL"]


    # 6. Start of treatment
    asyncio.run(run(args, full_data, working_file, email_cible, exclusions, new_email))


if __name__ == "__main__":
    main()