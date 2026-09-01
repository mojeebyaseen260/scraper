import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import (
    init_db,
    create_user,
    get_user_by_email,
    save_smtp_settings,
    get_smtp_settings,
    log_outreach_email,
    get_outreach_history,
)
from smtp_service import (
    render_lead_template,
    verify_smtp_credentials,
    send_single_email,
    B2B_EMAIL_TEMPLATES,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_smtp_database_crud():
    user = get_user_by_email("smtp_test@coldleads.com")
    if not user:
        user_id = create_user("smtp_test@coldleads.com", "hashed_pw")
    else:
        user_id = user["id"]

    save_smtp_settings(
        user_id=user_id,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="test@coldleads.com",
        smtp_pass="njbd rjtd rvrz scuh",
        from_name="ColdLeads Team",
        use_tls=1,
        daily_limit=500,
        delay_sec=2.5,
    )

    settings = get_smtp_settings(user_id)
    assert settings is not None
    assert settings["smtp_user"] == "test@coldleads.com"
    assert settings["smtp_host"] == "smtp.gmail.com"
    assert settings["smtp_port"] == 587
    assert settings["from_name"] == "ColdLeads Team"
    assert settings["daily_limit"] == 500


def test_render_lead_template():
    lead = {
        "name": "Apex Freeze Cold Vault Co",
        "decision_makers": "Marcus Vance (Chief Executive Officer)",
        "city": "Chicago",
        "state": "IL",
        "category": "Cold Storage & Warehousing",
        "phone": "+1 312-555-0192",
    }
    template_text = "Hi {Decision_Maker}, I noticed {Company} in {City}."
    rendered = render_lead_template(template_text, lead, from_name="Sarah")
    assert "Hi Marcus Vance" in rendered
    assert "Apex Freeze Cold Vault Co" in rendered
    assert "Chicago" in rendered


def test_outreach_logging_and_history():
    user = get_user_by_email("smtp_test2@coldleads.com")
    if not user:
        user_id = create_user("smtp_test2@coldleads.com", "hashed_pw")
    else:
        user_id = user["id"]

    log_outreach_email(
        user_id=user_id,
        recipient_email="ceo@apexfreeze.com",
        status="sent",
        job_id="job-123",
        company_name="Apex Freeze",
        decision_maker="Marcus Vance",
        subject="Quick question",
        body="Hi Marcus...",
    )

    history = get_outreach_history(user_id)
    assert len(history) >= 1
    latest = history[0]
    assert latest["recipient_email"] == "ceo@apexfreeze.com"
    assert latest["status"] == "sent"
    assert latest["company_name"] == "Apex Freeze"


@patch("smtplib.SMTP")
def test_verify_smtp_credentials_success(mock_smtp):
    instance = MagicMock()
    mock_smtp.return_value = instance

    ok, msg = verify_smtp_credentials(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="user@gmail.com",
        smtp_pass="njbd rjtd rvrz scuh",
        use_tls=True,
    )
    assert ok is True
    assert "successful" in msg
    instance.starttls.assert_called_once()
    instance.login.assert_called_once_with("user@gmail.com", "njbdrjtdrvrzscuh")


@patch("smtplib.SMTP")
def test_send_single_email_success(mock_smtp):
    instance = MagicMock()
    mock_smtp.return_value = instance

    ok, msg = send_single_email(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="user@gmail.com",
        smtp_pass="njbd rjtd rvrz scuh",
        from_name="John Doe",
        to_email="lead@target.com",
        subject="Hello Lead",
        body_text="Great to connect.",
        use_tls=True,
    )
    assert ok is True
    instance.sendmail.assert_called_once()
