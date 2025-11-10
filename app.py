"""
Flask Backend API for CV-Mailer
Provides REST API endpoints for the React frontend.
"""

import base64
import logging
import os
import smtplib
import time

from flask import Flask, jsonify, request
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

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
        }
    )


@app.route("/api/recipients", methods=["POST"])
def send_emails():
    """Send emails to a list of recipients."""
    try:
        data = request.get_json()
        recipients = data.get("recipients", [])
        sender_email = data.get("sender_email", "").strip()
        app_password = data.get("app_password", "").strip()
        job_title = data.get("job_title", "").strip()
        subject = data.get("subject", "").strip()
        pdf_file_base64 = data.get("pdf_file", "")
        pdf_filename = data.get("pdf_filename", "CV.pdf")
        name = data.get("name", "").strip()
        phone_number = data.get("phone_number", "").strip()

        if not recipients:
            return jsonify({"error": "No recipients provided"}), 400

        if not sender_email:
            return jsonify({"error": "Sender email is required"}), 400

        if not app_password:
            return jsonify({"error": "App password is required"}), 400

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
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                logger.info(f"Connecting to {SMTP_SERVER}:{SMTP_PORT}")
                smtp.ehlo()
                smtp.starttls()
                smtp.login(sender_email, app_password)
                logger.info("Successfully authenticated with SMTP server")

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
        sender_email = data.get("sender_email", "").strip()
        app_password = data.get("app_password", "").strip()
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

        if not sender_email:
            return jsonify({"success": False, "error": "Sender email is required"}), 400

        if not app_password:
            return jsonify({"success": False, "error": "App password is required"}), 400

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
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(sender_email, app_password)
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
        test_email = data.get("email", "").strip()
        sender_email = data.get("sender_email", "").strip()
        app_password = data.get("app_password", "").strip()
        job_title = data.get("job_title", "").strip()
        subject = data.get("subject", "").strip()
        pdf_file_base64 = data.get("pdf_file", "")
        pdf_filename = data.get("pdf_filename", "CV.pdf")

        if not test_email:
            return jsonify({"error": "Email address is required"}), 400

        if not sender_email:
            return jsonify({"error": "Sender email is required"}), 400

        if not app_password:
            return jsonify({"error": "App password is required"}), 400

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

        recipient = {"email": test_email, "company": data.get("company", "")}
        greeting = create_greeting(recipient)
        body = email_template.format(greeting=greeting, job_title=job_title)

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(sender_email, app_password)
                send_one(
                    smtp,
                    sender_email,
                    test_email,
                    subject,
                    body,
                    attachment_data=pdf_data,
                    attachment_filename=pdf_filename,
                )

                return jsonify(
                    {
                        "success": True,
                        "message": f"Test email sent successfully to {test_email}",
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
