"""
Flask Backend API for CV-Mailer
Provides REST API endpoints for the React frontend.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(Path(__file__).resolve().parent / ".env")
from flask_cors import CORS

from code_sender import (
    SEND_DELAY,
    SEND_METHOD,
    SMTP_PORT,
    SMTP_SERVER,
    TEMPLATE_PATH,
    create_greeting,
    load_email_template,
    send_one,
    validate_configuration,
)
from gmail_oauth import access_token_from_refresh_token

# Gmail rejects messages larger than 25 MB; keep a margin for MIME/base64 overhead.
MAX_PDF_BYTES = 15 * 1024 * 1024
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)

# CORS: restrict to comma-separated origins in CORS_ALLOWED_ORIGINS, else allow all (dev default).
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if _cors_origins:
    CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in _cors_origins.split(",") if o.strip()]}})
else:
    CORS(app)

# Reject oversized request bodies early (PDF is base64, so ~1.4x the raw cap plus JSON slack).
app.config["MAX_CONTENT_LENGTH"] = int(MAX_PDF_BYTES * 1.5) + 1 * 1024 * 1024

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _portfolio_section(portfolio_link: str) -> str:
    """HTML snippet for an optional portfolio URL; empty if missing or unsafe."""
    raw = (portfolio_link or "").strip()
    if not raw:
        return ""
    if not urlparse(raw).scheme:
        raw = "https://" + raw
    if urlparse(raw).scheme not in ("http", "https"):
        return ""
    safe_href = escape(raw, quote=True)
    return (
        '<p style="margin: 8px 0 0 0; font-size: 15px;">'
        f'<a href="{safe_href}" style="color: #1a2744; text-decoration: none; '
        'border-bottom: 1px solid #c5a572;">Portfolio</a>'
        "</p>"
    )


def _digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _render_body(
    template: str,
    *,
    greeting: str,
    job_title: str,
    name: str,
    phone_number: str,
    email: str,
    portfolio_section: str,
) -> str:
    return template.format(
        greeting=greeting,
        job_title=job_title,
        name=name,
        phone_number=phone_number,
        email=email,
        portfolio_section=portfolio_section,
    )


def _decode_pdf(pdf_file_base64: str) -> tuple[bytes | None, str | None]:
    """Decode a base64 PDF and enforce the size cap. Returns (data, error_message)."""
    if not pdf_file_base64:
        return None, "PDF file is required"
    try:
        pdf_data = base64.b64decode(pdf_file_base64)
    except Exception as e:  # noqa: BLE001 - surface decode failures to the client
        return None, f"Invalid PDF file data: {str(e)}"
    if len(pdf_data) > MAX_PDF_BYTES:
        mb = MAX_PDF_BYTES / (1024 * 1024)
        return None, f"PDF is too large. Maximum size is {mb:.0f} MB."
    return pdf_data, None


def _server_oauth_env_configured() -> bool:
    return bool(
        os.getenv("GMAIL_OAUTH_REFRESH_TOKEN", "").strip()
        and os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
    )


def _has_gmail_auth(data: dict) -> bool:
    if (data.get("oauth_access_token") or "").strip():
        return True
    if _server_oauth_env_configured():
        return True
    return False


# Back-compat alias for older call sites / mental model.
_has_smtp_auth = _has_gmail_auth


def _resolve_gmail_access_token(data: dict) -> str | None:
    explicit = (data.get("oauth_access_token") or "").strip()
    if explicit:
        return explicit
    if _server_oauth_env_configured():
        return access_token_from_refresh_token(
            os.environ["GMAIL_OAUTH_REFRESH_TOKEN"].strip(),
            os.environ["GMAIL_OAUTH_CLIENT_ID"].strip(),
            os.environ["GMAIL_OAUTH_CLIENT_SECRET"].strip(),
        )
    return None


def _email_from_google_access_token(access_token: str) -> str:
    """Resolve the Google account email for the From header (requires userinfo scope)."""
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        TimeoutError,
    ) as e:
        logger.warning("Google userinfo request failed: %s", e)
        return ""
    return (payload.get("email") or "").strip()


def _resolve_sender_and_oauth_token(data: dict) -> tuple[str, str | None]:
    """
    Resolve sender email + OAuth access token for Gmail API send.

    With OAuth, the From address always comes from Google userinfo for that access
    token (client sender_email is ignored).
    """
    oauth_token = _resolve_gmail_access_token(data)
    if oauth_token:
        sender = _email_from_google_access_token(oauth_token) or ""
        return sender, oauth_token
    sender = (data.get("sender_email") or "").strip()
    return sender, None


class SendRequestError(Exception):
    """Validation error carrying an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class SendContext:
    """Everything needed to render and send: resolved auth, sender, PDF, and template."""

    def __init__(
        self,
        *,
        data: dict,
        sender_email: str,
        oauth_access_token: str,
        job_title: str,
        subject: str,
        name: str,
        phone_number: str,
        portfolio_section: str,
        pdf_data: bytes,
        pdf_filename: str,
        template: str,
    ):
        self.data = data
        self.sender_email = sender_email
        self.oauth_access_token = oauth_access_token
        self.job_title = job_title
        self.subject = subject
        self.name = name
        self.phone_number = phone_number
        self.portfolio_section = portfolio_section
        self.pdf_data = pdf_data
        self.pdf_filename = pdf_filename
        self.template = template

    def render_for(self, recipient: dict, *, fallback_name: str | None = None) -> str:
        greeting = create_greeting(recipient)
        return _render_body(
            self.template,
            greeting=greeting,
            job_title=self.job_title,
            name=self.name or (fallback_name or ""),
            phone_number=self.phone_number,
            email=self.sender_email,
            portfolio_section=self.portfolio_section,
        )

    def send_to(self, to_email: str, body: str) -> None:
        send_one(
            self.oauth_access_token,
            self.sender_email,
            to_email,
            self.subject,
            body,
            attachment_data=self.pdf_data,
            attachment_filename=self.pdf_filename,
        )


def _build_send_context(data: dict, *, require_name_phone: bool = True) -> SendContext:
    """
    Resolve auth + sender, validate shared fields, decode the PDF, and load the template.
    Raises SendRequestError on any validation failure.
    """
    if not _has_gmail_auth(data):
        raise SendRequestError(
            "Gmail sign-in required: use Google OAuth in the app or "
            "configure server OAuth env vars (refresh token + client id/secret)."
        )

    sender_email, oauth_access_token = _resolve_sender_and_oauth_token(data)
    if not oauth_access_token:
        raise SendRequestError(
            "Gmail authentication required: Sign in with Google in the app or set "
            "GMAIL_OAUTH_REFRESH_TOKEN + GMAIL_OAUTH_CLIENT_ID + GMAIL_OAUTH_CLIENT_SECRET "
            "on the server."
        )
    if not sender_email:
        raise SendRequestError(
            "Sender email is required (or sign in with Google so we can "
            "detect it — userinfo.email scope must be granted)."
        )

    job_title = (data.get("job_title") or "").strip()
    if not job_title:
        raise SendRequestError("Job title is required")

    subject = (data.get("subject") or "").strip()
    if not subject:
        raise SendRequestError("Subject is required")

    name = (data.get("name") or "").strip()
    phone_number = _digits_only(data.get("phone_number") or "")
    if require_name_phone:
        if not name:
            raise SendRequestError("Name is required")
        if not phone_number:
            raise SendRequestError("Phone number is required")

    pdf_data, pdf_error = _decode_pdf(data.get("pdf_file", ""))
    if pdf_error:
        raise SendRequestError(pdf_error)

    try:
        validate_configuration(check_recipients=False)
    except Exception as e:  # noqa: BLE001
        raise SendRequestError(f"Configuration error: {str(e)}", status=500) from e

    try:
        template = load_email_template(TEMPLATE_PATH)
    except Exception as e:  # noqa: BLE001
        raise SendRequestError(f"Template loading error: {str(e)}", status=500) from e

    return SendContext(
        data=data,
        sender_email=sender_email,
        oauth_access_token=oauth_access_token,
        job_title=job_title,
        subject=subject,
        name=name,
        phone_number=phone_number,
        portfolio_section=_portfolio_section(data.get("portfolio_link", "")),
        pdf_data=pdf_data,
        pdf_filename=data.get("pdf_filename", "CV.pdf"),
        template=template,
    )


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "message": "Email sender API is running"})


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration for the UI."""
    return jsonify(
        {
            "template_path": TEMPLATE_PATH,
            "send_method": SEND_METHOD,
            "smtp_server": SMTP_SERVER,
            "smtp_port": SMTP_PORT,
            "send_delay": SEND_DELAY,
            "max_pdf_bytes": MAX_PDF_BYTES,
            "job_title": "",  # User enters in UI; empty default
            "subject": "",  # Empty default, user will provide
            "server_oauth_configured": _server_oauth_env_configured(),
            "google_oauth_client_id": (
                os.getenv("GOOGLE_OAUTH_WEB_CLIENT_ID", "").strip()
                or os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
            ),
        }
    )


@app.route("/api/preview-email", methods=["POST"])
def preview_email():
    """Render the email HTML template for UI preview (no send)."""
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        job_title = (data.get("job_title") or "").strip()
        phone_number = _digits_only(data.get("phone_number") or "")
        sender_email = (data.get("email") or "").strip() or "you@example.com"
        company = (data.get("company") or "").strip()
        portfolio_section = _portfolio_section(data.get("portfolio_link", ""))

        if not name:
            return jsonify({"error": "Name is required"}), 400
        if not job_title:
            return jsonify({"error": "Job title is required"}), 400
        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400

        try:
            email_template = load_email_template(TEMPLATE_PATH)
        except Exception as e:
            return (
                jsonify({"error": f"Template loading error: {str(e)}"}),
                500,
            )

        greeting = create_greeting({"email": "", "company": company})
        body = _render_body(
            email_template,
            greeting=greeting,
            job_title=job_title,
            name=name,
            phone_number=phone_number,
            email=sender_email,
            portfolio_section=portfolio_section,
        )

        return jsonify(
            {
                "success": True,
                "html": body,
                "subject": (data.get("subject") or "").strip(),
            }
        )
    except Exception as e:
        logger.error(f"Preview email error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/recipients", methods=["POST"])
def send_emails():
    """Send emails to a list of recipients via the Gmail API."""
    try:
        data = request.get_json() or {}
        recipients = data.get("recipients", [])
        if not recipients:
            return jsonify({"error": "No recipients provided"}), 400

        try:
            ctx = _build_send_context(data)
        except SendRequestError as e:
            return jsonify({"error": e.message}), e.status

        results = []
        successful_sends = 0
        failed_sends = 0

        for recipient in recipients:
            to_email = (recipient.get("email") or "").strip()
            if not to_email:
                continue
            if not _is_valid_email(to_email):
                results.append(
                    {
                        "email": to_email,
                        "status": "error",
                        "message": "Invalid email address",
                    }
                )
                failed_sends += 1
                continue

            body = ctx.render_for(recipient)
            try:
                logger.info(f"Sending email to: {to_email}")
                ctx.send_to(to_email, body)
                logger.info(f"✅ Successfully sent to {to_email}")
                results.append(
                    {
                        "email": to_email,
                        "status": "success",
                        "message": "Email sent successfully",
                    }
                )
                successful_sends += 1
            except Exception as e:
                logger.error(f"❌ Failed to send to {to_email}: {e}")
                results.append(
                    {"email": to_email, "status": "error", "message": str(e)}
                )
                failed_sends += 1

            if len(recipients) > 1:
                time.sleep(SEND_DELAY)

        return jsonify(
            {
                "success": True,
                "message": f"Email sending completed. Success: {successful_sends}, Failed: {failed_sends}",
                "results": results,
                "summary": {
                    "successful": successful_sends,
                    "failed": failed_sends,
                    "total": len(recipients),
                },
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/send-single", methods=["POST"])
def send_single_email():
    """Send a single email to one recipient."""
    try:
        data = request.get_json() or {}
        recipient = data.get("recipient", {})
        to_email = (recipient.get("email") or "").strip()

        if not to_email:
            return (
                jsonify({"success": False, "error": "Email address is required"}),
                400,
            )
        if not _is_valid_email(to_email):
            return (
                jsonify({"success": False, "error": "Invalid email address"}),
                400,
            )

        try:
            ctx = _build_send_context(data)
        except SendRequestError as e:
            return jsonify({"success": False, "error": e.message}), e.status

        body = ctx.render_for(recipient)
        try:
            ctx.send_to(to_email, body)
            return jsonify(
                {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                }
            )
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return (
                jsonify({"success": False, "error": f"Failed to send email: {str(e)}"}),
                500,
            )

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"success": False, "error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/test-email", methods=["POST"])
def test_email():
    """Send a test email to a single recipient (name/phone optional; sender used as fallback)."""
    try:
        data = request.get_json() or {}
        test_email_addr = (data.get("email") or "").strip()

        if not test_email_addr:
            return jsonify({"error": "Email address is required"}), 400
        if not _is_valid_email(test_email_addr):
            return jsonify({"error": "Invalid email address"}), 400

        try:
            ctx = _build_send_context(data, require_name_phone=False)
        except SendRequestError as e:
            return jsonify({"error": e.message}), e.status

        recipient = {"email": test_email_addr, "company": data.get("company", "")}
        body = ctx.render_for(recipient, fallback_name=ctx.sender_email)

        try:
            ctx.send_to(test_email_addr, body)
            return jsonify(
                {
                    "success": True,
                    "message": f"Test email sent successfully to {test_email_addr}",
                }
            )
        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, host="0.0.0.0", port=port)
