"""
CV-Mailer for Job Applications
A professional email automation tool for sending CVs to potential employers.
"""

# Standard library imports
import logging
import smtplib

# Email-related imports
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

# =============================================================================
# STATIC CONFIGURATION CONSTANTS
# =============================================================================

# SMTP Configuration (Static - Gmail settings)
SMTP_SERVER: str = "smtp.gmail.com"
SMTP_PORT: int = 587
SEND_DELAY: float = 1.0  # Delay between emails in seconds

# File Paths (Static)
TEMPLATE_PATH: str = "email_template.html"

# Recipients List - Add company name for personalized greetings
RECIPIENTS: List[Dict[str, str]] = [
    # {"email": "info@genius-planet.com", "company": "Genius Planet"},
    # {"email": "info@dolftech.com", "company": "Dolf Tech"},
    # {"email": "info@veracodia.com", "company": "VeraCodia"},
    # {"email": "Eymtax@gmail.com", "company": "Eymtax"},
    # {"email": "ceo@hdour.com", "company": "hdour"},
    # {"email": "info@chamona.com", "company": "chamona"},
    # {"email": "lausanne.a@shiftconsults.com"},
    # {
    #     "email": "Mazaddimashq@gmail.com",
    #     "company": "Mazad Dimashq",
    # },
    # {"email": "info@gshub.co", "company": "Gshub"},
    # {"email": "a.warasneh@taqnyat.sa", "company": "Taqnyat"},
    # {"email": "info@pro-wave.net", "company": "Pro Wave"},
    # {
    #     "email": "captaincar.9133@gmail.com",
    #     "company": "Captain Car",
    # },
    # {"email": "a.alrayess@tarynix.com", "company": "Tarynix"},
    # {"email": "info@rar-it.com", "company": "Rar IT"},
    # {"email": "sales@bluerayws.com", "company": "Blue Ray"},
    # {"email": "sales@NovaGroups.net", "company": "Nova Group"},
    # {"email": "sales@icrcompany.net", "company": "ICR"},
    # {"email": "sally-al-janan@tikram-group.sy", "company": "Tfadal"},
    # {"email": "hind@gshub.co", "company": "gshub"},
    # {"email": "hr@geniusplanetacademy.com", "company": "Genius Planet"},
    # {"email": "jobs@job-shop.net", "company": ""},
    # {"email": "info@alrounq.com", "company": "Al Rounq"},
    # {"email": "info@khubrat.com", "company": ""},
]

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# EMAIL FUNCTIONS
# =============================================================================


def load_email_template(template_path: str) -> str:
    """
    Load HTML email template from file.

    Args:
        template_path: Path to the HTML template file

    Returns:
        str: HTML template content

    Raises:
        FileNotFoundError: If template file doesn't exist
        IOError: If template file cannot be read
    """
    template_file = Path(template_path)
    if not template_file.exists():
        raise FileNotFoundError(f"Email template not found: {template_path}")

    try:
        with template_file.open("r", encoding="utf-8") as file:
            template_content = file.read()
        logger.info(f"Successfully loaded email template from: {template_path}")
        return template_content
    except IOError as e:
        logger.error(f"Failed to read template file: {e}")
        raise


def build_message(
    sender: str,
    to_email: str,
    subject: str,
    body_text: str,
    attachment_path: Optional[str] = None,
    attachment_data: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> MIMEMultipart:
    """
    Build a MIME multipart email message with optional attachment.

    Args:
        sender: Email address of the sender
        to_email: Email address of the recipient
        subject: Email subject line
        body_text: Email body content
        attachment_path: Path to attachment file (optional, if attachment_data is not provided)
        attachment_data: File data as bytes (optional, if attachment_path is not provided)
        attachment_filename: Filename for attachment when using attachment_data

    Returns:
        MIMEMultipart: Complete email message ready for sending

    Raises:
        FileNotFoundError: If attachment file doesn't exist
    """
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    # Attach HTML content
    msg.attach(MIMEText(body_text, "html", "utf-8"))

    # Handle attachment from file data (preferred for API)
    if attachment_data:
        logger.info(f"Attaching file from data: {attachment_filename}")
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{attachment_filename}"'
        )
        msg.attach(part)
    # Handle attachment from file path (for backward compatibility)
    elif attachment_path:
        attachment_file = Path(attachment_path)
        if not attachment_file.exists():
            raise FileNotFoundError(f"Attachment not found: {attachment_path}")

        logger.info(f"Attaching file: {attachment_file.name}")

        part = MIMEBase("application", "octet-stream")
        with attachment_file.open("rb") as file:
            part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{attachment_file.name}"'
        )
        msg.attach(part)

    return msg


def send_one(
    smtp: smtplib.SMTP,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachment: Optional[str] = None,
    attachment_data: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> None:
    """
    Send a single email message.

    Args:
        smtp: SMTP server connection
        sender: Email address of the sender
        recipient: Email address of the recipient
        subject: Email subject line
        body: Email body content
        attachment: Path to attachment file (optional, if attachment_data is not provided)
        attachment_data: File data as bytes (optional, if attachment is not provided)
        attachment_filename: Filename for attachment when using attachment_data

    Raises:
        smtplib.SMTPException: If email sending fails
    """
    msg = build_message(
        sender,
        recipient,
        subject,
        body,
        attachment_path=attachment,
        attachment_data=attachment_data,
        attachment_filename=attachment_filename,
    )
    smtp.sendmail(sender, [recipient], msg.as_string())


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def validate_configuration(check_recipients: bool = True) -> None:
    """
    Validate that all required configuration is present.

    Args:
        check_recipients: If True, validate that RECIPIENTS list is not empty.
                         Set to False when recipients are provided via API.
    """
    if check_recipients and not RECIPIENTS:
        raise RuntimeError(
            "No recipients configured. Please add at least one recipient."
        )

    template_path = Path(TEMPLATE_PATH)
    if not template_path.exists():
        raise FileNotFoundError(f"Email template not found: {TEMPLATE_PATH}")


def create_greeting(recipient: Dict[str, str]) -> str:
    """Create personalized greeting for the recipient."""
    company = recipient.get("company", "").strip()
    if company:
        return f"{company} Hiring Team"
    return "Hiring Team"


# Note: The main() function has been removed as all functionality
# is now handled through the Flask API (app.py)
# Users provide all dynamic values (email, password, subject, etc.) through the web interface
