"""Gmail OAuth helpers and HTTPS send via the Gmail API (no SMTP)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

# Full mail scope covers Gmail API send; userinfo resolves the From address.
GMAIL_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/userinfo.email",
]
# Back-compat aliases used elsewhere in the project.
GMAIL_SMTP_SCOPES = GMAIL_SCOPES
GMAIL_SMTP_SCOPE = GMAIL_SCOPES[0]

GMAIL_SEND_URL = (
    "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send"
    "?uploadType=media"
)


def access_token_from_refresh_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> str:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=GMAIL_SCOPES,
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("OAuth token refresh did not return an access token")
    return creds.token


def send_mime_via_gmail_api(access_token: str, mime_bytes: bytes) -> dict:
    """
    Send a pre-built RFC 822 MIME message through Gmail over HTTPS.

    Uses the media upload endpoint so PDF attachments are not limited by the
    small JSON ``raw`` body path (important on free hosts that block SMTP).
    """
    if not (access_token or "").strip():
        raise RuntimeError("Gmail access token is required to send mail")
    if not mime_bytes:
        raise ValueError("MIME message is empty")

    req = urllib.request.Request(
        GMAIL_SEND_URL,
        data=mime_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token.strip()}",
            "Content-Type": "message/rfc822",
            "Content-Length": str(len(mime_bytes)),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(detail)
            message = (
                err_json.get("error", {}).get("message")
                or err_json.get("error_description")
                or detail
            )
        except json.JSONDecodeError:
            message = detail or str(e)
        logger.error("Gmail API HTTP %s: %s", e.code, message)
        raise RuntimeError(f"Gmail API error ({e.code}): {message}") from e
    except urllib.error.URLError as e:
        logger.error("Gmail API network error: %s", e)
        raise RuntimeError(f"Gmail API network error: {e}") from e
