"""Gmail SMTP authentication using OAuth2 (XOAUTH2)."""

from __future__ import annotations

import base64
import smtplib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail SMTP + userinfo.email (to resolve the signed-in address on the server).
GMAIL_SMTP_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/userinfo.email",
]
GMAIL_SMTP_SCOPE = GMAIL_SMTP_SCOPES[0]


def build_xoauth2_string(username: str, access_token: str) -> str:
    auth_string = f"user={username}\1auth=Bearer {access_token}\1\1"
    return base64.b64encode(auth_string.encode("utf-8")).decode("ascii")


def smtp_auth_xoauth2(smtp: smtplib.SMTP, username: str, access_token: str) -> None:
    coded = build_xoauth2_string(username, access_token)
    code, resp = smtp.docmd("AUTH", f"XOAUTH2 {coded}")
    if code != 235:
        raise smtplib.SMTPAuthenticationError(code, resp)


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
        scopes=GMAIL_SMTP_SCOPES,
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("OAuth token refresh did not return an access token")
    return creds.token
