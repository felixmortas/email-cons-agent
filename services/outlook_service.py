import re
import requests
from datetime import datetime, timezone, timedelta


class OutlookService:
    def __init__(self, client_id, client_secret, refresh_token, tenant_id="consumers"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.graph_base = "https://graph.microsoft.com/v1.0/me"

    def _get_access_token(self) -> str:
        """Obtains an access token using the OAuth2 refresh token."""
        data = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/Mail.Read offline_access",
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_secret": self.client_secret,
        }
        response = requests.post(self.token_url, data=data)
        res_json = response.json()

        token = res_json.get("access_token")
        if not token:
            raise Exception(f"Impossible de récupérer l'access_token: {res_json}")
        return token

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    # ─────────────────────────────────────────────
    # LECTURE DE MAILS
    # ─────────────────────────────────────────────

    def get_recent_emails(self, max_results: int = 100, since_minutes: int = 5) -> list[dict]:
        """
        Retrieves the N most recent emails received in the inbox
        over the past `since_minutes` minutes.

        Returns:
            A list of dictionaries with the keys: id, subject, sender.
        """

        since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params = {
            "$top": max_results,
            "$orderby": "receivedDateTime desc",
            "$filter": f"receivedDateTime ge {since}",
            "$select": "id,subject,sender,receivedDateTime,bodyPreview,body",
        }

        headers = self._get_headers()

        emails = []
        for folder in ("inbox", "junkemail"):
            response = requests.get(
                f"{self.graph_base}/mailFolders/{folder}/messages",
                headers=headers,
                params=params,
            )
            if response.status_code != 200:
                raise Exception(f"Erreur dossier {folder} : {response.text}")
                    
            if response.status_code in (404, 400):
                raise ValueError(f"Email introuvable ou ID invalide (id={id}).")

            for msg in response.json().get("value", []):
                emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", ""),
                    "sender": msg.get("sender", {}).get("emailAddress", {}).get("address", ""),
                })

        return emails

    def read_email(self, id: str) -> dict:
        """
        Retrieves a specific email by its Graph API ID.
  
        Args:
            id: The email's unique ID (Microsoft Graph opaque format).
 
        Returns:
            str: body (raw text).
 
        Raises:
            ValueError: If the email is not found (404).
            Exception: For any other Graph API error.
        """
        response = requests.get(
            f"{self.graph_base}/messages/{id}",
            headers=self._get_headers(),
            params={"$select": "id,subject,sender,receivedDateTime,bodyPreview,body"},
        )
 
        if response.status_code == 404:
            raise ValueError(f"Email introuvable (id={id}).")
        if response.status_code != 200:
            raise Exception(f"Erreur Graph API ({response.status_code}) : {response.text}")
 
        msg = response.json()
        body = self._strip_html(msg.get("body", {}).get("content", ""))
        return body

    @staticmethod
    def _strip_html(html: str) -> str:
        """
        Aggressively strips down HTML, retaining only:
          - Visible text (excluding scripts, styles, and comments)
          - URLs (href, src)
          - Image descriptions (alt)
        """
        # 1. Removes HTML comments <!-- ... -->
        html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
 
        # 2. Removes entire invisible blocks (tag and content)
        html = re.sub(r"<(script|style|head|noscript|svg|template)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)

        # 3. Extract href="..." and src="..." → keeps only HTTP(S) URLs
        urls = re.findall(r'(?:href|src)=["\'](\s*https?://[^"\'>\s]+)["\']', html, flags=re.IGNORECASE)
 
        # 4. Excerpt alt="..." → image descriptions
        alts = re.findall(r'alt=["\']([^"\']{2,})["\']', html, flags=re.IGNORECASE)
 
        # 5. Removes all remaining tags
        text = re.sub(r"<[^>]+>", " ", html)
 
        # 6. Decodes common HTML entities
        entities = {
            "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&nbsp;": " ", "&quot;": '"', "&#39;": "'",
            "&apos;": "'", "&laquo;": "«", "&raquo;": "»",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        # Digital entities &#160; or &#x00A0;
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
        text = re.sub(r"&#([0-9]+);", lambda m: chr(int(m.group(1))), text)
 
        # 7. Normalizes spaces
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)
 
        # 8. Put the final result together
        parts = [text]
        # if urls:
        #     parts.append("\n[URLs]\n" + "\n".join(dict.fromkeys(u.strip() for u in urls)))  # dédoublonné, ordre conservé
        # if alts:
        #     parts.append("\n[Images]\n" + "\n".join(dict.fromkeys(a.strip() for a in alts)))
 
        return "\n".join(parts)
 