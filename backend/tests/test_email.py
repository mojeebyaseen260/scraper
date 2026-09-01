"""Tests for email extraction, validation, URL cleaning, and the SSRF guard.
These run fully offline — no network or Chrome required."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scraper_api import (  # noqa: E402
    extract_emails_from_html,
    extract_phone_from_html,
    extract_decision_makers_from_html,
    _is_valid_email,
    _decode_cfemail,
    _is_public_host,
    _clean_url,
)


# ── Email validation ──────────────────────────────────────
def test_valid_business_email():
    assert _is_valid_email("info@coldstore.com")


def test_reject_image_and_placeholder():
    assert not _is_valid_email("logo@2x.png")
    assert not _is_valid_email("noreply@example.com")
    assert not _is_valid_email("hello@mysite.com")          # Wix placeholder
    assert not _is_valid_email("abc@sentry.wixpress.com")   # internal
    assert not _is_valid_email("dev@agency.com")            # web agency prefix
    assert not _is_valid_email("info@webdesignstudio.com")  # web design host
    assert not _is_valid_email("theme@themeforest.net")     # theme marketplace


# ── Decision Maker Extraction ──────────────────────────────
def test_extract_decision_makers_from_text():
    html = """
    <div>
        <h2>Our Leadership Team</h2>
        <p><strong>John Doe</strong>, CEO & Founder</p>
        <p><strong>Sarah Jenkins</strong> - Marketing Director</p>
        <p><strong>Michael Chang</strong> - General Manager</p>
    </div>
    """
    dms = extract_decision_makers_from_html(html)
    assert any("John Doe" in d and "CEO" in d for d in dms)
    assert any("Sarah Jenkins" in d and "Marketing Director" in d for d in dms)
    assert any("Michael Chang" in d and "General Manager" in d for d in dms)


def test_extract_decision_makers_from_json_ld():
    html = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Robert Smith",
        "jobTitle": "Owner & President",
        "email": "robert@smithlogistics.com",
        "telephone": "+1-555-987-6543"
    }
    </script>
    """
    dms = extract_decision_makers_from_html(html)
    assert len(dms) >= 1
    assert "Robert Smith" in dms[0]
    assert "President" in dms[0] or "Owner" in dms[0]
    assert "robert@smithlogistics.com" in dms[0]


def test_strip_designer_attribution():
    html = """
    <div>
        <p>Main contact: info@realbusiness.com</p>
        <div class="footer-credit">Website Designed by WebCrafters (hello@webcrafters.com)</div>
    </div>
    """
    emails = extract_emails_from_html(html)
    assert "info@realbusiness.com" in emails
    assert "hello@webcrafters.com" not in emails


def test_extract_phone_from_html():
    html = '<p>Call our depot at <a href="tel:+14155550199">+1 (415) 555-0199</a></p>'
    assert extract_phone_from_html(html) == "+14155550199"


# ── Extraction modes ──────────────────────────────────────
def test_plain_text_email():
    assert extract_emails_from_html("<p>contact@coldchain.net</p>") == ["contact@coldchain.net"]


def test_mailto_link():
    html = '<a href="mailto:sales@texasice.com?subject=hi">Email</a>'
    assert extract_emails_from_html(html) == ["sales@texasice.com"]


def test_html_entity_encoded():
    html = "Contact: info&#64;dallascold&#46;com today"
    assert extract_emails_from_html(html) == ["info@dallascold.com"]


def test_bracketed_obfuscation():
    html = "reach us at admin [at] frozenhub [dot] com"
    assert extract_emails_from_html(html) == ["admin@frozenhub.com"]


def test_cloudflare_protected():
    key = 0x7a
    real = "info@coldstore.com"
    enc = "%02x" % key + "".join("%02x" % (ord(c) ^ key) for c in real)
    assert _decode_cfemail(enc) == real
    html = f'<a data-cfemail="{enc}">[email&#160;protected]</a>'
    assert extract_emails_from_html(html) == [real]


def test_no_false_positive_from_words():
    # "category" / "water" must not yield bogus emails
    assert extract_emails_from_html("Our category page and water tank info") == []


# ── SSRF guard ────────────────────────────────────────────
def test_ssrf_blocks_internal():
    for h in ["127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0"]:
        assert _is_public_host(h) is False, h


def test_ssrf_allows_public_ip():
    assert _is_public_host("8.8.8.8") is True


# ── URL cleaning ──────────────────────────────────────────
def test_clean_url_strips_tracking():
    out = _clean_url("https://x.com/page?utm_source=g&id=5&gclid=abc")
    assert "utm_source" not in out and "gclid" not in out and "id=5" in out

