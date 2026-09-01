"""
SMTP Cold Outreach & Email Delivery Service
Handles SMTP authentication, personalized templating, and bulk outreach with throttling.
"""

import smtplib
import time
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


B2B_EMAIL_TEMPLATES = [
    {
        "id": "decision_maker_intro",
        "name": "👔 Decision Maker Introduction (Highest Reply Rate)",
        "subject": "Quick question regarding {Company}",
        "body": """Hi {Decision_Maker},

I noticed your role leading {Company} in {City} and wanted to reach out directly.

We specialize in helping {Category} companies scale their operations and streamline key workflows with automated tools and qualified B2B lead generation.

Would you be open to a brief 5-minute chat this Thursday to see if this could be valuable for {Company}?

Best regards,
{From_Name}""",
    },
    {
        "id": "cold_storage_partnership",
        "name": "❄️ Cold Storage & Logistics Partnership",
        "subject": "Inquiry: Temperature Controlled Capacity at {Company}",
        "body": """Hi {Decision_Maker},

I came across {Company} while researching top cold storage & refrigerated logistics providers in {City}, {State}.

We are currently working with food & beverage and pharmaceutical distributors looking for dependable cold chain and warehousing facilities in your region.

Do you currently have available pallet capacity or commercial leasing slots available?

Looking forward to connecting,
{From_Name}""",
    },
    {
        "id": "general_b2b_pitch",
        "name": "🚀 General B2B Business Value Proposal",
        "subject": "Growth & efficiency for {Company}",
        "body": """Hello {Decision_Maker},

Hope you're having a productive week.

I'm reaching out because we help businesses in the {Category} industry reduce overhead costs while increasing qualified inbound demand.

I would love to share a couple of quick ideas tailored specifically for {Company} in {City}.

Are you available for a brief call sometime next week?

Warm regards,
{From_Name}""",
    },
]


def render_lead_template(template_text: str, lead: dict, from_name: str = "") -> str:
    """Replace dynamic variable tags like {Company}, {Decision_Maker}, {City} with lead data."""
    dm = lead.get("decision_makers") or ""
    # Extract first person name from DM string (e.g. "Alexander Hayes (CEO)" -> "Alexander Hayes")
    dm_name = dm.split("(")[0].split(";")[0].split("·")[0].strip()
    if not dm_name:
        dm_name = "there"

    replacements = {
        "{Company}": lead.get("name") or "your team",
        "{Decision_Maker}": dm_name,
        "{City}": lead.get("city") or "your city",
        "{State}": lead.get("state") or "",
        "{Category}": lead.get("category") or "business",
        "{Phone}": lead.get("phone") or "",
        "{From_Name}": from_name or "Our Team",
    }

    result = template_text
    for tag, val in replacements.items():
        # Case-insensitive replacement of {Tag} and {{Tag}}
        result = re.sub(re.escape(tag), str(val), result, flags=re.I)
        result = re.sub(re.escape("{" + tag + "}"), str(val), result, flags=re.I)
    return result


def verify_smtp_credentials(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    use_tls: bool = True,
) -> tuple[bool, str]:
    """Test SMTP connection and login credentials."""
    # Clean app password (remove spaces)
    clean_pass = smtp_pass.replace(" ", "")
    clean_user = smtp_user.strip()

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
            if use_tls:
                server.starttls()

        server.login(clean_user, clean_pass)
        server.quit()
        return True, "SMTP connection and authentication successful!"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed (Check email and 16-character App Password): {e.smtp_error.decode('utf-8', 'ignore') if hasattr(e, 'smtp_error') else str(e)}"
    except Exception as e:
        return False, f"SMTP Connection error: {str(e)}"


def send_single_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_name: str,
    to_email: str,
    subject: str,
    body_text: str,
    use_tls: bool = True,
) -> tuple[bool, str]:
    """Send an email using configured SMTP settings."""
    clean_pass = smtp_pass.replace(" ", "")
    clean_user = smtp_user.strip()
    clean_to = to_email.strip()

    msg = MIMEMultipart("alternative")
    sender_header = f"{from_name} <{clean_user}>" if from_name else clean_user
    msg["From"] = sender_header
    msg["To"] = clean_to
    msg["Subject"] = subject

    # Plain text version
    part_text = MIMEText(body_text, "plain", "utf-8")
    msg.attach(part_text)

    # HTML formatted version
    html_content = (
        f"<div style='font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #222;'>"
        f"{body_text.replace(chr(10), '<br>')}"
        f"</div>"
    )
    part_html = MIMEText(html_content, "html", "utf-8")
    msg.attach(part_html)

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if use_tls:
                server.starttls()

        server.login(clean_user, clean_pass)
        server.sendmail(clean_user, [clean_to], msg.as_string())
        server.quit()
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)
