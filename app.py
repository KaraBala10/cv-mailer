"""
Flask Backend API for CV-Mailer
Provides REST API endpoints for the React frontend.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(Path(__file__).resolve().parent / ".env")
from flask_cors import CORS

from code_sender import (
    SEND_DELAY,
    SMTP_PORT,
    SMTP_SERVER,
    TEMPLATE_PATH,
    create_greeting,
    load_email_template,
    send_one,
    validate_configuration,
)
from gmail_oauth import access_token_from_refresh_token, smtp_auth_xoauth2

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _server_oauth_env_configured() -> bool:
    return bool(
        os.getenv("GMAIL_OAUTH_REFRESH_TOKEN", "").strip()
        and os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
    )


def _has_smtp_auth(data: dict) -> bool:
    if (data.get("oauth_access_token") or "").strip():
        return True
    if _server_oauth_env_configured():
        return True
    return False


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
    """Resolve the Google account email for XOAUTH2 / From header (requires userinfo scope)."""
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
    Sender is required for SMTP / MIME unless we can derive it via OAuth userinfo.
    Returns (sender_email, oauth_access_token) with the token reused for SMTP when present.
    """
    oauth_token = _resolve_gmail_access_token(data)
    sender = (data.get("sender_email") or "").strip()
    if not sender and oauth_token:
        sender = _email_from_google_access_token(oauth_token) or ""
    return sender, oauth_token


def _smtp_login_gmail(
    smtp: smtplib.SMTP,
    sender_email: str,
    data: dict,
    *,
    oauth_access_token: str | None = None,
) -> None:
    access_token = (
        oauth_access_token
        if oauth_access_token is not None
        else _resolve_gmail_access_token(data)
    )
    if access_token:
        smtp_auth_xoauth2(smtp, sender_email, access_token)
        return
    raise RuntimeError(
        "Gmail authentication required: Sign in with Google in the app or set "
        "GMAIL_OAUTH_REFRESH_TOKEN + GMAIL_OAUTH_CLIENT_ID + GMAIL_OAUTH_CLIENT_SECRET "
        "on the server."
    )


@contextmanager
def _gmail_smtp_session(
    sender_email: str,
    data: dict,
    *,
    oauth_access_token: str | None = None,
):
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        logger.info("Connecting to %s:%s", SMTP_SERVER, SMTP_PORT)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        _smtp_login_gmail(
            smtp,
            sender_email,
            data,
            oauth_access_token=oauth_access_token,
        )
        logger.info("Successfully authenticated with SMTP server")
        yield smtp


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "message": "Email sender API is running"})


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration (static SMTP settings)."""
    return jsonify(
        {
            "template_path": TEMPLATE_PATH,
            "smtp_server": SMTP_SERVER,
            "smtp_port": SMTP_PORT,
            "send_delay": SEND_DELAY,
            "job_title": "Software Engineer and Developer",  # Default job title
            "subject": "",  # Empty default, user will provide
            "server_oauth_configured": _server_oauth_env_configured(),
            "google_oauth_client_id": (
                os.getenv("GOOGLE_OAUTH_WEB_CLIENT_ID", "").strip()
                or os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
            ),
        }
    )


@app.route("/api/recipients", methods=["POST"])
def send_emails():
    """Send emails to a list of recipients."""
    try:
        data = request.get_json()
        recipients = data.get("recipients", [])
        job_title = data.get("job_title", "").strip()
        subject = data.get("subject", "").strip()
        pdf_file_base64 = data.get("pdf_file", "")
        pdf_filename = data.get("pdf_filename", "CV.pdf")
        name = data.get("name", "").strip()
        phone_number = data.get("phone_number", "").strip()

        if not recipients:
            return jsonify({"error": "No recipients provided"}), 400

        if not _has_smtp_auth(data):
            return (
                jsonify(
                    {
                        "error": (
                            "Gmail sign-in required: use Google OAuth in the app or "
                            "configure server OAuth env vars (refresh token + client id/secret)."
                        )
                    }
                ),
                400,
            )

        sender_email, oauth_for_smtp = _resolve_sender_and_oauth_token(data)

        if not sender_email:
            return (
                jsonify(
                    {
                        "error": (
                            "Sender email is required (or sign in with Google so we can "
                            "detect it — userinfo.email scope must be granted)."
                        )
                    }
                ),
                400,
            )

        if not job_title:
            return jsonify({"error": "Job title is required"}), 400

        if not subject:
            return jsonify({"error": "Subject is required"}), 400

        if not pdf_file_base64:
            return jsonify({"error": "PDF file is required"}), 400

        if not name:
            return jsonify({"error": "Name is required"}), 400

        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400

        # Decode base64 PDF
        try:
            pdf_data = base64.b64decode(pdf_file_base64)
        except Exception as e:
            return jsonify({"error": f"Invalid PDF file data: {str(e)}"}), 400

        # Validate configuration (skip recipients check since they come from request)
        try:
            validate_configuration(check_recipients=False)
        except Exception as e:
            return jsonify({"error": f"Configuration error: {str(e)}"}), 500

        # Load email template
        try:
            email_template = load_email_template(TEMPLATE_PATH)
        except Exception as e:
            return jsonify({"error": f"Template loading error: {str(e)}"}), 500

        results = []
        successful_sends = 0
        failed_sends = 0

        try:
            with _gmail_smtp_session(
                sender_email, data, oauth_access_token=oauth_for_smtp
            ) as smtp:
                for recipient in recipients:
                    to_email = recipient.get("email", "").strip()
                    if not to_email:
                        continue

                    greeting = create_greeting(recipient)
                    body = email_template.format(
                        greeting=greeting,
                        job_title=job_title,
                        name=name,
                        phone_number=phone_number,
                        email=sender_email,
                    )

                    try:
                        logger.info(f"Sending email to: {to_email}")
                        send_one(
                            smtp,
                            sender_email,
                            to_email,
                            subject,
                            body,
                            attachment_data=pdf_data,
                            attachment_filename=pdf_filename,
                        )
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

                    # Add delay between emails
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

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return jsonify({"error": f"SMTP error: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/send-single", methods=["POST"])
def send_single_email():
    """Send a single email to one recipient."""
    try:
        data = request.get_json()
        recipient = data.get("recipient", {})
        to_email = recipient.get("email", "").strip()
        job_title = data.get("job_title", "").strip()
        subject = data.get("subject", "").strip()
        pdf_file_base64 = data.get("pdf_file", "")
        pdf_filename = data.get("pdf_filename", "CV.pdf")
        name = data.get("name", "").strip()
        phone_number = data.get("phone_number", "").strip()

        if not to_email:
            return (
                jsonify({"success": False, "error": "Email address is required"}),
                400,
            )

        if not _has_smtp_auth(data):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "Gmail sign-in required: use Google OAuth in the app or "
                            "configure server OAuth env vars (refresh token + client id/secret)."
                        ),
                    }
                ),
                400,
            )

        sender_email, oauth_for_smtp = _resolve_sender_and_oauth_token(data)

        if not sender_email:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "Sender email is required (or sign in with Google so we can "
                            "detect it — userinfo.email scope must be granted)."
                        ),
                    }
                ),
                400,
            )

        if not job_title:
            return jsonify({"success": False, "error": "Job title is required"}), 400

        if not subject:
            return jsonify({"success": False, "error": "Subject is required"}), 400

        if not pdf_file_base64:
            return jsonify({"success": False, "error": "PDF file is required"}), 400

        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400

        if not phone_number:
            return jsonify({"success": False, "error": "Phone number is required"}), 400

        # Decode base64 PDF
        try:
            pdf_data = base64.b64decode(pdf_file_base64)
        except Exception as e:
            return (
                jsonify(
                    {"success": False, "error": f"Invalid PDF file data: {str(e)}"}
                ),
                400,
            )

        # Validate configuration
        try:
            validate_configuration(check_recipients=False)
        except Exception as e:
            return (
                jsonify({"success": False, "error": f"Configuration error: {str(e)}"}),
                500,
            )

        # Load email template
        try:
            email_template = load_email_template(TEMPLATE_PATH)
        except Exception as e:
            return (
                jsonify(
                    {"success": False, "error": f"Template loading error: {str(e)}"}
                ),
                500,
            )

        greeting = create_greeting(recipient)
        body = email_template.format(
            greeting=greeting,
            job_title=job_title,
            name=name,
            phone_number=phone_number,
            email=sender_email,
        )

        try:
            with _gmail_smtp_session(
                sender_email, data, oauth_access_token=oauth_for_smtp
            ) as smtp:
                send_one(
                    smtp,
                    sender_email,
                    to_email,
                    subject,
                    body,
                    attachment_data=pdf_data,
                    attachment_filename=pdf_filename,
                )

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
    """Send a test email to a single recipient."""
    try:
        data = request.get_json()
        test_email_addr = data.get("email", "").strip()
        job_title = data.get("job_title", "").strip()
        subject = data.get("subject", "").strip()
        pdf_file_base64 = data.get("pdf_file", "")
        pdf_filename = data.get("pdf_filename", "CV.pdf")

        if not test_email_addr:
            return jsonify({"error": "Email address is required"}), 400

        if not _has_smtp_auth(data):
            return (
                jsonify(
                    {
                        "error": (
                            "Gmail sign-in required: use Google OAuth in the app or "
                            "configure server OAuth env vars (refresh token + client id/secret)."
                        )
                    }
                ),
                400,
            )

        sender_email, oauth_for_smtp = _resolve_sender_and_oauth_token(data)

        if not sender_email:
            return (
                jsonify(
                    {
                        "error": (
                            "Sender email is required (or sign in with Google so we can "
                            "detect it — userinfo.email scope must be granted)."
                        )
                    }
                ),
                400,
            )

        if not job_title:
            return jsonify({"error": "Job title is required"}), 400

        if not subject:
            return jsonify({"error": "Subject is required"}), 400

        if not pdf_file_base64:
            return jsonify({"error": "PDF file is required"}), 400

        # Decode base64 PDF
        try:
            pdf_data = base64.b64decode(pdf_file_base64)
        except Exception as e:
            return jsonify({"error": f"Invalid PDF file data: {str(e)}"}), 400

        # Validate configuration (skip recipients check since they come from request)
        try:
            validate_configuration(check_recipients=False)
        except Exception as e:
            return jsonify({"error": f"Configuration error: {str(e)}"}), 500

        # Load email template
        try:
            email_template = load_email_template(TEMPLATE_PATH)
        except Exception as e:
            return jsonify({"error": f"Template loading error: {str(e)}"}), 500

        recipient = {"email": test_email_addr, "company": data.get("company", "")}
        greeting = create_greeting(recipient)
        body = email_template.format(greeting=greeting, job_title=job_title)

        try:
            with _gmail_smtp_session(
                sender_email, data, oauth_access_token=oauth_for_smtp
            ) as smtp:
                send_one(
                    smtp,
                    sender_email,
                    test_email_addr,
                    subject,
                    body,
                    attachment_data=pdf_data,
                    attachment_filename=pdf_filename,
                )

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
    app.run(debug=True, host="0.0.0.0", port=port)
