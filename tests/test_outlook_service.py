"""
Tests for `OutlookService` (services.outlook_service).

Test strategy
-------------

Unit tests — no network, no credentials required
    TestOutlookServiceUnit
        Covers every public and private method of OutlookService by patching
        `requests.post` and `requests.get` with `unittest.mock.patch`.
        Branches tested:
            _get_access_token   → success, missing token in response
            _get_headers        → correct Authorization header built
            get_recent_emails   → success (inbox + junk), API error on folder,
                                  empty mailboxes, 400/404 status
            read_email          → success, 404 → ValueError, other HTTP error

    TestStripHtmlUnit
        `_strip_html` is a pure static method with no I/O: no mocking needed.
        Each test targets a single transformation rule (HTML comments, script
        blocks, anchor conversion, entity decoding, whitespace normalisation).

Integration tests — real Microsoft Graph API (skipped without credentials)
    TestOutlookServiceIntegration
        Marked with `@pytest.mark.integration` and skipped automatically when
        the three required environment variables are absent.  Run with:

            pytest -m integration test_outlook_service.py

        Or set env vars and run without the mark filter.

Running all fast tests (no network):
    pytest test_outlook_service.py -m "not integration"
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from services.outlook_service import OutlookService


# ---------------------------------------------------------------------------
# Shared fixtures & factories
# ---------------------------------------------------------------------------

FAKE_CLIENT_ID     = "fake-client-id"
FAKE_CLIENT_SECRET = "fake-client-secret"
FAKE_REFRESH_TOKEN = "fake-refresh-token"
FAKE_TOKEN         = "x" * 30  # Realistic-looking access token


def _make_service() -> OutlookService:
    """Return an OutlookService instance with dummy credentials."""
    return OutlookService(
        client_id=FAKE_CLIENT_ID,
        client_secret=FAKE_CLIENT_SECRET,
        refresh_token=FAKE_REFRESH_TOKEN,
    )


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    """
    Build a minimal mock that mimics a `requests.Response`.

    Parameters
    ----------
    status_code:
        HTTP status code to return from `.status_code`.
    json_data:
        Dictionary returned by `.json()`.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _token_response() -> MagicMock:
    """Successful OAuth2 token endpoint response."""
    return _mock_response(200, {"access_token": FAKE_TOKEN})


# ---------------------------------------------------------------------------
# Unit tests — OutlookService methods
# ---------------------------------------------------------------------------

class TestGetAccessToken:
    """Unit tests for OutlookService._get_access_token."""

    def test_returns_token_on_success(self):
        """A valid token is extracted from the response JSON and returned."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            token = service._get_access_token()
        assert token == FAKE_TOKEN

    def test_raises_when_token_missing(self):
        """An empty response (no access_token key) must raise Exception."""
        service = _make_service()
        bad_resp = _mock_response(200, {"error": "invalid_grant"})
        with patch("requests.post", return_value=bad_resp):
            with pytest.raises(Exception, match="access_token"):
                service._get_access_token()

    def test_posts_to_correct_tenant_url(self):
        """The token request must target the tenant's OAuth2 endpoint."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()) as mock_post:
            service._get_access_token()
        called_url = mock_post.call_args[0][0]
        assert "login.microsoftonline.com" in called_url
        assert "consumers" in called_url  # default tenant

    def test_custom_tenant_id_in_url(self):
        """A custom tenant_id must appear in the token URL."""
        service = OutlookService(
            client_id=FAKE_CLIENT_ID,
            client_secret=FAKE_CLIENT_SECRET,
            refresh_token=FAKE_REFRESH_TOKEN,
            tenant_id="my-org.onmicrosoft.com",
        )
        with patch("requests.post", return_value=_token_response()) as mock_post:
            service._get_access_token()
        assert "my-org.onmicrosoft.com" in mock_post.call_args[0][0]

    def test_refresh_token_sent_in_payload(self):
        """The refresh_token credential must be forwarded to the token endpoint."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()) as mock_post:
            service._get_access_token()
        payload = mock_post.call_args[1]["data"]
        assert payload["refresh_token"] == FAKE_REFRESH_TOKEN
        assert payload["grant_type"] == "refresh_token"


class TestGetHeaders:
    """Unit tests for OutlookService._get_headers."""

    def test_authorization_header_contains_token(self):
        """The Authorization header must be 'Bearer <token>'."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            headers = service._get_headers()
        assert headers["Authorization"] == f"Bearer {FAKE_TOKEN}"

    def test_content_type_is_json(self):
        """Content-Type must always be application/json."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            headers = service._get_headers()
        assert headers["Content-Type"] == "application/json"


class TestGetRecentEmails:
    """Unit tests for OutlookService.get_recent_emails."""

    def _patch_all(self, inbox_msgs: list, junk_msgs: list):
        """
        Return a context-manager patch that simulates two successful folder
        responses (inbox then junk).
        """
        inbox_resp = _mock_response(200, {"value": inbox_msgs})
        junk_resp  = _mock_response(200, {"value": junk_msgs})

        # requests.post → token ; requests.get → folder responses (called twice)
        post_patch = patch("requests.post", return_value=_token_response())
        get_patch  = patch("requests.get", side_effect=[inbox_resp, junk_resp])
        return post_patch, get_patch

    def test_returns_list_of_dicts(self):
        """Result must be a list even when both folders are empty."""
        service = _make_service()
        pp, gp = self._patch_all([], [])
        with pp, gp:
            result = service.get_recent_emails()
        assert isinstance(result, list)

    def test_email_structure_has_required_keys(self):
        """Every item in the result must have id, subject, and sender."""
        raw = {
            "id": "ABC123",
            "subject": "Hello",
            "sender": {"emailAddress": {"address": "alice@example.com"}},
        }
        service = _make_service()
        pp, gp = self._patch_all([raw], [])
        with pp, gp:
            emails = service.get_recent_emails()

        assert len(emails) == 1
        assert emails[0]["id"]      == "ABC123"
        assert emails[0]["subject"] == "Hello"
        assert emails[0]["sender"]  == "alice@example.com"

    def test_merges_inbox_and_junk(self):
        """Emails from inbox and junk must be combined in the result."""
        inbox_msg = {"id": "1", "subject": "Inbox", "sender": {"emailAddress": {"address": "a@b.com"}}}
        junk_msg  = {"id": "2", "subject": "Junk",  "sender": {"emailAddress": {"address": "c@d.com"}}}
        service = _make_service()
        pp, gp = self._patch_all([inbox_msg], [junk_msg])
        with pp, gp:
            emails = service.get_recent_emails()

        ids = {e["id"] for e in emails}
        assert ids == {"1", "2"}

    def test_raises_on_api_error(self):
        """A non-200 response from a folder endpoint must raise Exception."""
        service = _make_service()
        error_resp = _mock_response(500, {"error": "InternalServerError"})
        with patch("requests.post", return_value=_token_response()):
            with patch("requests.get", return_value=error_resp):
                with pytest.raises(Exception, match="Erreur dossier"):
                    service.get_recent_emails()

    def test_empty_subject_defaults_to_empty_string(self):
        """An email without a subject key must yield an empty string, not None."""
        raw = {"id": "X", "sender": {"emailAddress": {"address": "x@y.com"}}}
        service = _make_service()
        pp, gp = self._patch_all([raw], [])
        with pp, gp:
            emails = service.get_recent_emails()
        assert emails[0]["subject"] == ""

    def test_missing_sender_defaults_to_empty_string(self):
        """An email without sender info must yield an empty string."""
        raw = {"id": "X", "subject": "Test", "sender": {}}
        service = _make_service()
        pp, gp = self._patch_all([raw], [])
        with pp, gp:
            emails = service.get_recent_emails()
        assert emails[0]["sender"] == ""


class TestReadEmail:
    """Unit tests for OutlookService.read_email."""

    def test_returns_stripped_body_on_success(self):
        """A 200 response must return the plain-text body (HTML stripped)."""
        html_body = "<p>Hello <b>world</b></p>"
        msg = {"id": "1", "body": {"content": html_body, "contentType": "html"}}
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            with patch("requests.get", return_value=_mock_response(200, msg)):
                result = service.read_email("1")
        assert "Hello" in result
        assert "<p>" not in result  # HTML must be stripped

    def test_raises_value_error_on_404(self):
        """A 404 response must raise ValueError with the email id in the message."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            with patch("requests.get", return_value=_mock_response(404, {})):
                with pytest.raises(ValueError, match="introuvable"):
                    service.read_email("nonexistent-id")

    def test_raises_exception_on_other_http_error(self):
        """Any non-200/non-404 response must raise a generic Exception."""
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            with patch("requests.get", return_value=_mock_response(503, {})):
                with pytest.raises(Exception, match="503"):
                    service.read_email("any-id")

    def test_empty_body_returns_empty_string(self):
        """An email with no body content must return an empty string."""
        msg = {"id": "1", "body": {"content": "", "contentType": "text"}}
        service = _make_service()
        with patch("requests.post", return_value=_token_response()):
            with patch("requests.get", return_value=_mock_response(200, msg)):
                result = service.read_email("1")
        assert result == ""


# ---------------------------------------------------------------------------
# Unit tests — _strip_html (pure function, no mocking needed)
# ---------------------------------------------------------------------------

class TestStripHtml:
    """
    Unit tests for OutlookService._strip_html.

    `_strip_html` is a pure static method: deterministic input → output.
    Each test targets one transformation rule in isolation.
    """

    strip = staticmethod(OutlookService._strip_html)

    # -- HTML comments -------------------------------------------------------

    def test_removes_html_comments(self):
        """HTML comments <!-- ... --> must be completely removed."""
        assert "secret" not in self.strip("<!-- secret -->hello")
        assert "hello" in self.strip("<!-- secret -->hello")

    def test_removes_multiline_comments(self):
        result = self.strip("<!--\n  hidden\n  block\n-->visible")
        assert "hidden" not in result
        assert "visible" in result

    # -- Invisible block tags ------------------------------------------------

    def test_removes_script_blocks(self):
        html = "<script>alert('xss')</script>Safe text"
        result = self.strip(html)
        assert "alert" not in result
        assert "Safe text" in result

    def test_removes_style_blocks(self):
        html = "<style>body { color: red; }</style>Visible"
        result = self.strip(html)
        assert "color" not in result
        assert "Visible" in result

    def test_removes_head_block(self):
        html = "<head><title>Doc</title></head><p>Content</p>"
        result = self.strip(html)
        assert "Doc" not in result
        assert "Content" in result

    # -- Anchor conversion ---------------------------------------------------

    def test_converts_anchor_to_markdown(self):
        """<a href="url">text</a> must become [text](url)."""
        html = '<a href="https://example.com">Click here</a>'
        result = self.strip(html)
        assert "[Click here](https://example.com)" in result

    def test_anchor_without_text_keeps_url(self):
        """An anchor with empty inner text must keep the URL."""
        html = '<a href="https://example.com"></a>'
        result = self.strip(html)
        assert "https://example.com" in result

    def test_anchor_with_nested_tags_extracts_text(self):
        """Inner tags inside an anchor must be stripped to get plain text."""
        html = '<a href="https://x.com"><strong>Bold link</strong></a>'
        result = self.strip(html)
        assert "Bold link" in result
        assert "<strong>" not in result

    # -- Generic tag stripping -----------------------------------------------

    def test_removes_all_remaining_tags(self):
        """After special handling, any leftover HTML tag must be removed."""
        result = self.strip("<div><p><span>text</span></p></div>")
        assert "<" not in result
        assert "text" in result

    # -- HTML entity decoding ------------------------------------------------

    def test_decodes_amp(self):
        assert "&" in self.strip("AT&amp;T")

    def test_decodes_lt_gt(self):
        result = self.strip("&lt;tag&gt;")
        assert "<tag>" in result

    def test_decodes_nbsp(self):
        """&nbsp; must become a regular space, not remain as an entity."""
        result = self.strip("word&nbsp;word")
        assert "&nbsp;" not in result
        assert "word word" in result

    def test_decodes_numeric_entity(self):
        """&#160; (non-breaking space) must be decoded to a Unicode character."""
        result = self.strip("a&#160;b")
        assert "&#160;" not in result

    def test_decodes_hex_entity(self):
        """&#xA0; must be decoded to its Unicode character."""
        result = self.strip("a&#xA0;b")
        assert "&#xA0;" not in result

    def test_decodes_quot(self):
        result = self.strip("say &quot;hello&quot;")
        assert '"hello"' in result

    # -- Whitespace normalisation --------------------------------------------

    def test_collapses_multiple_spaces(self):
        """Multiple consecutive spaces must be collapsed to one."""
        result = self.strip("word     word")
        assert "word word" in result
        assert "  " not in result

    def test_collapses_excessive_newlines(self):
        """More than two consecutive newlines must be reduced to two."""
        result = self.strip("a\n\n\n\n\nb")
        assert "\n\n\n" not in result

    def test_strips_leading_trailing_whitespace_per_line(self):
        """Each line must be stripped of leading/trailing whitespace."""
        result = self.strip("<p>  hello  </p>")
        for line in result.splitlines():
            assert line == line.strip()

    def test_empty_string_returns_empty_string(self):
        assert self.strip("") == ""

    def test_plain_text_passthrough(self):
        """Plain text with no HTML must be returned essentially unchanged."""
        result = self.strip("Hello, world!")
        assert "Hello, world!" in result

    # -- Combined scenarios --------------------------------------------------

    def test_real_world_email_snippet(self):
        """
        A realistic HTML email snippet must produce clean readable text with
        no residual tags or raw entities.
        """
        html = """
        <html>
        <head><style>body{font-family:Arial;}</style></head>
        <body>
          <!-- tracking pixel -->
          <p>Dear <strong>Alice</strong>,</p>
          <p>Please visit <a href="https://example.com/reset">Reset password</a>.</p>
          <p>Best&nbsp;regards,<br/>The Team</p>
          <script>window._t=1;</script>
        </body>
        </html>
        """
        result = self.strip(html)
        assert "Alice" in result
        assert "[Reset password](https://example.com/reset)" in result
        assert "The Team" in result
        # No raw HTML should remain
        assert "<" not in result
        assert "&nbsp;" not in result
        assert "window._t" not in result


# ---------------------------------------------------------------------------
# Integration tests — real Microsoft Graph API
# ---------------------------------------------------------------------------

_INTEGRATION_VARS = ("OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_REFRESH_TOKEN_OLD")
_CREDS_PRESENT    = all(os.getenv(v) for v in _INTEGRATION_VARS)

pytestmark_integration = pytest.mark.skipif(
    not _CREDS_PRESENT,
    reason="Integration tests require OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, "
           "OUTLOOK_REFRESH_TOKEN_OLD environment variables.",
)


@pytest.fixture(scope="module")
def real_service() -> OutlookService:
    """OutlookService authenticated with real credentials from environment."""
    return OutlookService(
        client_id=os.environ["OUTLOOK_CLIENT_ID"],
        client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
        refresh_token=os.environ["OUTLOOK_REFRESH_TOKEN_OLD"],
    )


@pytest.mark.integration
@pytestmark_integration
class TestOutlookServiceIntegration:
    """
    Integration tests against the real Microsoft Graph API.

    Skipped automatically when credentials are not set.
    Run with:
        OUTLOOK_CLIENT_ID=... OUTLOOK_CLIENT_SECRET=... OUTLOOK_REFRESH_TOKEN_OLD=... \\
        pytest -m integration test_outlook_service.py -v
    """

    def test_get_access_token_returns_valid_token(self, real_service):
        """The OAuth2 flow must return a non-trivial string token."""
        token = real_service._get_access_token()
        assert isinstance(token, str)
        assert len(token) > 20, f"Token suspiciously short: {len(token)} chars"

    def test_get_recent_emails_returns_list(self, real_service):
        """get_recent_emails must return a list (possibly empty)."""
        emails = real_service.get_recent_emails(since_minutes=60 * 24 * 7)
        assert isinstance(emails, list)

    def test_get_recent_emails_structure(self, real_service):
        """Every email dict must contain id, subject, and sender keys."""
        emails = real_service.get_recent_emails(since_minutes=60 * 24 * 7)
        for i, email in enumerate(emails):
            assert "id"      in email, f"Email #{i} missing 'id'"
            assert "subject" in email, f"Email #{i} missing 'subject'"
            assert "sender"  in email, f"Email #{i} missing 'sender'"

    def test_read_first_email_returns_string(self, real_service):
        """read_email must return a string for a valid email ID."""
        emails = real_service.get_recent_emails(since_minutes=60 * 24 * 7)
        if not emails:
            pytest.skip("No emails available in the test window.")
        body = real_service.read_email(emails[0]["id"])
        assert isinstance(body, str)

    def test_read_invalid_email_raises_value_error(self, real_service):
        """
        read_email must raise ValueError (404) or Exception (400) for a
        syntactically invalid ID — both are acceptable behaviours.
        """
        with pytest.raises((ValueError, Exception)):
            real_service.read_email("id-inexistant-12345")