"""
ReAct Agent for automated email changing.

Usage:
    python main.py --url https://www.agrosemens.com --website Agrosemens
    python main.py --url https://www.agrosemens.com --website Agrosemens --model mistral-large-latest --no-headless
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from services.outlook_service import OutlookService
load_dotenv()

from context import ContextSchema
from graph import graph
from services.langfuse_engine import langfuse_handler
from services.playwright_session import playwright_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ReAct Agent for automated email changing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            python main.py --url https://www.agrosemens.com --website Agrosemens --model mistral-large-latest --no-headless
            python main.py --url https://www.agrosemens.com --website Agrosemens --model mistral-large-latest
            """,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Website URL to start from",
    )
    parser.add_argument(
        "--website",
        type=str,
        required=True,
        help="Website name for context",
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


async def run(args: argparse.Namespace) -> None:
    context=ContextSchema(website_name=args.website)
    
    context.outlook_service = OutlookService(
        client_id=os.getenv("OUTLOOK_CLIENT_ID"),
        client_secret=os.getenv("OUTLOOK_CLIENT_SECRET"),
        refresh_token=os.getenv("OUTLOOK_REFRESH_TOKEN"),
    )

    async with playwright_session(context=context, headless=args.headless):
        initial_state = {
            "messages": [],
            "initial_url": args.url,
        }

        await graph.ainvoke(
            input=initial_state,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_tags": [args.website]},
            },
            context=context
        )


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()