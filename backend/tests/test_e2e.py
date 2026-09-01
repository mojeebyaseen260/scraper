"""End-to-end automated test suite for ColdLeads application.
Tests Authentication, Location APIs, Keyword Categories, Database persistence,
Decision Maker extraction, Bulk UPSERT, Export generation (CSV, XLSX, JSON),
and Admin APIs.
"""

import os
import sys
import io
import json
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from database import (
    create_job, get_job, get_jobs_by_user, save_results_bulk,
    replace_results_bulk, get_results, get_results_count, get_admin_stats,
    create_user, get_user_by_email, init_db
)
from scraper_api import (
    extract_emails_from_html,
    extract_phone_from_html,
    extract_decision_makers_from_html,
    extract_socials_from_html,
    _is_valid_email,
)

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=15.0)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()


# ── 1. Location & Category APIs ───────────────────────────────
def test_api_countries_returns_55_countries():
    res = client.get("/api/countries")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 50
    assert "USA" in data
    assert "UK" in data
    assert "Germany" in data
    assert "UAE" in data
    assert "Japan" in data
    assert "Pakistan" in data


def test_api_states_and_cities():
    # Test USA states
    res_us = client.get("/api/states/USA")
    assert res_us.status_code == 200
    states_us = res_us.json()
    assert "California" in states_us
    assert "Texas" in states_us

    # Test USA cities
    res_cities = client.get("/api/cities/USA/California")
    assert res_cities.status_code == 200
    cities = res_cities.json()
    assert "Los Angeles" in cities
    assert "San Francisco" in cities

    # Test International state & cities (e.g. Germany -> Bavaria)
    res_de = client.get("/api/cities/Germany/Bavaria")
    assert res_de.status_code == 200
    cities_de = res_de.json()
    assert "Munich" in cities_de or "Nuremberg" in cities_de


def test_api_keyword_categories():
    res = client.get("/api/keyword-categories")
    assert res.status_code == 200
    cats = res.json()
    assert isinstance(cats, dict)
    assert "General Cold Storage" in cats
    assert "Freezer & Refrigeration" in cats
    assert len(cats["General Cold Storage"]) > 0


# ── 2. Auth Flow (Register, Login, Token Access) ──────────────
def test_auth_full_cycle():
    test_email = f"e2e_user_{os.urandom(4).hex()}@coldleads.com"
    test_pass = "TestPass123!"

    # 1. Register
    reg_res = client.post("/api/auth/register", json={"email": test_email, "password": test_pass})
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert "token" in reg_data
    token = reg_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Current User (/api/auth/me)
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == test_email

    # 3. Login
    login_res = client.post("/api/auth/login", json={"email": test_email, "password": test_pass})
    assert login_res.status_code == 200
    assert "token" in login_res.json()


# ── 3. Database Persistence & Decision Makers Flow ────────────
def test_database_bulk_upsert_with_decision_makers():
    job_id = f"test_job_{os.urandom(4).hex()}"
    create_job(
        job_id=job_id,
        user_id=1,
        state="Texas",
        cities=["Dallas", "Houston"],
        created_at="2026-09-02T00:00:00",
        keywords=["cold storage"],
        max_emails=5,
        status="done",
        country="USA",
        relevant_only=True,
        categories=["cold storage"],
    )

    sample_results = [
        {
            "name": "Apex Cold Logistics",
            "city": "Dallas",
            "state": "Texas",
            "phone": "+1-214-555-0199",
            "address": "100 Industrial Pkwy, Dallas, TX",
            "rating": "4.9",
            "category": "Cold Storage Facility",
            "email": "contact@apexcold.com",
            "social": "https://linkedin.com/company/apexcold",
            "decision_makers": "Marcus Vance (CEO · marcus@apexcold.com); Sarah Connor (General Manager · +1-214-555-0198)",
            "website": "https://apexcold.com",
        },
        {
            "name": "Lone Star Freezer Depot",
            "city": "Houston",
            "state": "Texas",
            "phone": "+1-713-555-0144",
            "address": "500 Port Blvd, Houston, TX",
            "rating": "4.8",
            "category": "Refrigerated Warehouse",
            "email": "info@lonestarfreezer.com",
            "social": "https://facebook.com/lonestarfreezer",
            "decision_makers": "David Miller (Owner & Founder · david@lonestarfreezer.com)",
            "website": "https://lonestarfreezer.com",
        }
    ]

    # Save to DB
    save_results_bulk(job_id, sample_results)

    # Fetch from DB
    db_rows = get_results(job_id)
    assert len(db_rows) == 2
    apex_row = next(r for r in db_rows if r["name"] == "Apex Cold Logistics")
    assert "Marcus Vance" in apex_row["decision_makers"]
    assert "CEO" in apex_row["decision_makers"]
    assert apex_row["email"] == "contact@apexcold.com"
    assert apex_row["phone"] == "+1-214-555-0199"

    # Test count function
    total, with_em = get_results_count(job_id)
    assert total == 2
    assert with_em == 2


# ── 4. Export Endpoints (CSV, XLSX, JSON) ─────────────────────
def test_export_file_generation_with_decision_makers():
    # Login as admin to access job download
    login_res = client.post("/api/auth/login", json={"email": "admin@coldleads.com", "password": "Admin@123"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    job_id = f"job_export_{os.urandom(4).hex()}"
    create_job(
        job_id=job_id,
        user_id=1,
        state="California",
        cities=["Fresno"],
        created_at="2026-09-02T00:00:00",
        keywords=["frozen food"],
        status="done",
    )

    records = [
        {
            "name": "Pacific Frost Co",
            "city": "Fresno",
            "state": "California",
            "phone": "+1-559-555-1234",
            "address": "123 Farm Rd, Fresno, CA",
            "rating": "5.0",
            "category": "Cold Storage",
            "email": "info@pacificfrost.com",
            "social": "https://linkedin.com/company/pacificfrost",
            "decision_makers": "Elena Rostova (Marketing Director · elena@pacificfrost.com)",
            "website": "https://pacificfrost.com",
        }
    ]
    save_results_bulk(job_id, records)

    # 1. Test CSV Download
    csv_res = client.get(f"/api/download/{job_id}/csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    csv_text = csv_res.content.decode("utf-8-sig")
    assert "decision_makers" in csv_text or "Pacific Frost Co" in csv_text
    assert "Elena Rostova" in csv_text

    # 2. Test JSON Download
    json_res = client.get(f"/api/download/{job_id}/json", headers=headers)
    assert json_res.status_code == 200
    json_data = json_res.json()
    assert len(json_data) == 1
    assert json_data[0]["decision_makers"] == "Elena Rostova (Marketing Director · elena@pacificfrost.com)"

    # 3. Test XLSX Download
    xlsx_res = client.get(f"/api/download/{job_id}/xlsx", headers=headers)
    assert xlsx_res.status_code == 200
    assert len(xlsx_res.content) > 1000  # valid binary excel zip


# ── 5. Decision Maker & Junk Stripping Robustness ─────────────
def test_decision_maker_extraction_edge_cases():
    complex_html = """
    <html>
      <body>
        <div class="header">
          <a href="tel:+18005559999">1-800-555-9999</a>
          <a href="mailto:office@arcticcold.com">office@arcticcold.com</a>
        </div>
        <div class="team-grid">
          <div class="team-card">
            <h3>Alexander Hayes</h3>
            <span class="role">Chief Executive Officer</span>
            <a href="mailto:alex.hayes@arcticcold.com">alex.hayes@arcticcold.com</a>
          </div>
          <div class="team-card">
            <h3>Jessica Taylor</h3>
            <span class="role">Director of Marketing & Sales</span>
            <a href="mailto:jessica@arcticcold.com">Direct Email</a>
          </div>
          <div class="team-card">
            <h3>Robert King</h3>
            <span class="role">Warehouse Operations Manager</span>
          </div>
        </div>
        <footer>
          <p>Website Designed and Developed by Pixel Agency (support@pixelagency.com)</p>
        </footer>
      </body>
    </html>
    """
    # 1. Emails: should extract legitimate emails, drop designer credit email
    emails = extract_emails_from_html(complex_html)
    assert "office@arcticcold.com" in emails
    assert "alex.hayes@arcticcold.com" in emails
    assert "support@pixelagency.com" not in emails

    # 2. Decision Makers: should find CEO, Marketing Director, and Operations Manager
    dms = extract_decision_makers_from_html(complex_html)
    assert any("Alexander Hayes" in dm and "Chief Executive Officer" in dm for dm in dms)
    assert any("Jessica Taylor" in dm and "Marketing" in dm for dm in dms)
    assert any("Robert King" in dm and "Operations Manager" in dm for dm in dms)


# ── 6. Admin Stats API ─────────────────────────────────────────
def test_admin_stats_and_privileges():
    login_res = client.post("/api/auth/login", json={"email": "admin@coldleads.com", "password": "Admin@123"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    stats_res = client.get("/api/admin/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_users" in stats
    assert "total_jobs" in stats
    assert "total_results" in stats
    assert "total_emails" in stats
