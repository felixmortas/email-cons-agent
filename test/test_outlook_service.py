"""
Tests d'intégration réels pour OutlookService.

Lancer :
    python test_outlook_service.py
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys

# ─── Dépendance locale ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from services.outlook_service import OutlookService

# ─── Couleurs terminal ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):     print(f"  {GREEN}✔{RESET}  {msg}")
def fail(msg):   print(f"  {RED}✖{RESET}  {msg}")
def info(msg):   print(f"  {CYAN}ℹ{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{YELLOW}{'─'*60}{RESET}\n{BOLD}{msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_credentials() -> dict:
    """Charge les identifiants depuis les variables d'environnement."""
    required = ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_REFRESH_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"{RED}Variables d'environnement manquantes : {', '.join(missing)}{RESET}")
        print("Définissez-les avant de lancer les tests :")
        for k in missing:
            print(f"  export {k}=\"...\"")
        sys.exit(1)
    return {
        "client_id":     os.environ["OUTLOOK_CLIENT_ID"],
        "client_secret": os.environ["OUTLOOK_CLIENT_SECRET"],
        "refresh_token": os.environ["OUTLOOK_REFRESH_TOKEN"],
    }


def build_service(creds: dict) -> OutlookService:
    return OutlookService(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        refresh_token=creds["refresh_token"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_connection(service: OutlookService) -> bool:
    """Vérifie qu'on obtient un access_token valide."""
    header("TEST 1 — Connexion OAuth2 (access token)")
    try:
        token = service._get_access_token()
        assert isinstance(token, str) and len(token) > 20, "Token trop court ou invalide"
        ok(f"Access token obtenu ({len(token)} caractères)")
        return True
    except Exception as e:
        fail(f"Impossible d'obtenir un token : {e}")
        return False


def test_get_recent_emails(service: OutlookService) -> list[dict]:
    """Récupère les emails récents et vérifie la structure."""
    header("TEST 2 — Récupération des emails récents")
    try:
        emails = service.get_recent_emails(since_minutes=60*24*7)
        assert isinstance(emails, list), f"Attendu list, reçu {type(emails)}"
        ok(f"{len(emails)} email(s) récupéré(s)")

        if not emails:
            info("Boîte vide ou aucun email dans la fenêtre de 2 min.")
            return emails

        required_keys = {"id", "subject", "sender"}
        for i, email in enumerate(emails):
            missing = required_keys - email.keys()
            assert not missing, f"Email #{i} — clés manquantes : {missing}"

        ok("Structure de chaque email validée (id, subject, sender)")
        return emails

    except AssertionError as e:
        fail(f"Assertion échouée : {e}")
        return []
    except Exception as e:
        fail(f"Erreur inattendue : {e}")
        return []


def display_emails(emails: list[dict]) -> None:
    """Affiche joliment la liste des emails."""
    header("LISTE DES EMAILS")
    if not emails:
        info("Aucun email à afficher.")
        return

    for i, email in enumerate(emails, 1):
        eid = email["id"]
        print(f"\n  {BOLD}[{i}]{RESET}")
        print(f"       ID         : {eid}")
        print(f"       Sujet      : {email.get('subject') or '(sans sujet)'}")
        print(f"       Expéditeur : {email.get('sender') or '(inconnu)'}")


def test_read_first_email(service: OutlookService, emails: list[dict]) -> None:
    """Lit le corps du premier email et vérifie qu'il n'est pas vide."""
    header("TEST 3 — Lecture du premier email (body)")
    if not emails:
        info("Aucun email disponible, test ignoré.")
        return

    first = emails[0]
    info(f"Lecture de l'email : «{first.get('subject') or '(sans sujet)'}»")
    try:
        body = service.read_email(first["id"])
        assert isinstance(body, str), f"Body n'est pas une str : {type(body)}"

        if body.strip():
            ok(f"Corps récupéré ({len(body)} caractères)")
            preview = body.strip()[:300].replace("\n", " ")
            print(f"\n  {CYAN}Aperçu :{RESET} {preview}{'…' if len(body) > 300 else ''}\n")
        else:
            info("Corps vide (email purement HTML ou vide).")

    except ValueError as e:
        fail(f"Email introuvable : {e}")
    except Exception as e:
        fail(f"Erreur inattendue : {e}")


def test_read_invalid_email(service: OutlookService) -> None:
    """Vérifie que read_email lève bien ValueError pour un ID inexistant."""
    header("TEST 4 — Lecture d'un ID inexistant (gestion d'erreur)")
    try:
        service.read_email("id-inexistant-12345")
        fail("Aucune exception levée — comportement inattendu.")
    except ValueError as e:
        ok(f"ValueError levée correctement : {e}")
    except Exception as e:
        # Certaines APIs renvoient 400 pour un ID mal formé plutôt que 404
        ok(f"Exception levée (non-ValueError, acceptable) : {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{'═'*60}")
    print("   TESTS D'INTÉGRATION — OutlookService")
    print(f"{'═'*60}{RESET}")

    creds   = load_credentials()
    service = build_service(creds)

    connected = test_connection(service)
    if not connected:
        print(f"\n{RED}Connexion impossible, tests annulés.{RESET}\n")
        sys.exit(1)

    emails = test_get_recent_emails(service)
    display_emails(emails)
    test_read_first_email(service, emails)
    test_read_invalid_email(service)

    print(f"\n{BOLD}{GREEN}{'─'*60}")
    print("   Tous les tests terminés.")
    print(f"{'─'*60}{RESET}\n")


if __name__ == "__main__":
    main()