#!/usr/bin/env python3
"""
One-time helper: run OAuth in a browser and print a refresh token for Gmail SMTP.

Prerequisites:
  - Google Cloud project with OAuth consent screen (add your Google account as test user
    if the app is in Testing).
  - OAuth 2.0 Client ID of type "Desktop app" (download JSON) OR Web client with
    http://localhost in authorized redirect URIs for InstalledAppFlow.

Usage:
  Put GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET in the repo root .env file, or:
  export GMAIL_OAUTH_CLIENT_ID=...
  export GMAIL_OAUTH_CLIENT_SECRET=...
  python scripts/get_gmail_refresh_token.py

Or pass a Google client secrets JSON path:
  python scripts/get_gmail_refresh_token.py /path/to/client_secret.json

Copy the printed refresh token into GMAIL_OAUTH_REFRESH_TOKEN on the server.
Scope used: https://mail.google.com/ (required for Gmail SMTP XOAUTH2).
"""

import json
import os
import sys
from pathlib import Path

# Allow running from repo root without installing the package
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from gmail_oauth import GMAIL_SMTP_SCOPE  # noqa: E402


def _load_repo_dotenv() -> None:
    """Load repo root .env into os.environ (does not override existing vars)."""
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_repo_dotenv()
    secrets_path = sys.argv[1] if len(sys.argv) > 1 else None
    if secrets_path:
        client_config_path = Path(secrets_path)
        if not client_config_path.is_file():
            print(f"File not found: {client_config_path}", file=sys.stderr)
            sys.exit(1)
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_config_path), scopes=[GMAIL_SMTP_SCOPE]
        )
    else:
        cid = os.environ.get("GMAIL_OAUTH_CLIENT_ID", "").strip()
        csec = os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
        if not cid or not csec:
            print(
                "Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET, or pass "
                "a client_secret JSON file path.",
                file=sys.stderr,
            )
            sys.exit(1)
        client_config = {
            "installed": {
                "client_id": cid,
                "client_secret": csec,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(
            client_config, scopes=[GMAIL_SMTP_SCOPE]
        )

    creds = flow.run_local_server(port=0, open_browser=True)
    if not creds.refresh_token:
        print(
            "No refresh token returned. Try revoking app access for this client in "
            "Google Account settings, then run again with prompt=consent (or use a "
            "Desktop OAuth client JSON from Google Cloud).",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Refresh token (set as GMAIL_OAUTH_REFRESH_TOKEN on the server):")
    print(creds.refresh_token)
    print("\nOptional: authorized user info")
    print(json.dumps({"client_id": creds.client_id, "token_uri": creds.token_uri}))


if __name__ == "__main__":
    main()
