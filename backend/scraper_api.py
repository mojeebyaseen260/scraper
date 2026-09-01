"""
Scraper logic — optimized for speed, accuracy, and scalability
- Async HTTP via httpx for email extraction
- Multi-page email crawling (homepage + /contact + /about)
- Robust email validation and deduplication
- Smarter driver pool with health checks
- Cancellation propagation
"""

import re
import json
import html as _html
import time
import socket
import ipaddress
import warnings
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, parse_qs, quote_plus

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")

import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ── Settings ──────────────────────────────────────────────
import os as _os
_IS_PRODUCTION = _os.environ.get("PRODUCTION", "0") == "1"

def _envi(name, prod, dev):
    return int(_os.environ.get(name, str(prod if _IS_PRODUCTION else dev)))
def _envf(name, prod, dev):
    return float(_os.environ.get(name, str(prod if _IS_PRODUCTION else dev)))

# Every knob is env-overridable so prod (Railway) can be tuned from the
# dashboard without a code change. Defaults: prod lean, dev thorough.
NUM_DRIVERS    = _envi("NUM_DRIVERS",    1,   6)    # Chrome per job
PAGE_WAIT      = _envf("PAGE_WAIT",      0.2, 0.3)
EMAIL_TIMEOUT  = _envi("EMAIL_TIMEOUT",  6,   10)
EMAIL_WORKERS  = _envi("EMAIL_WORKERS",  16,  48)
# Max extra pages (beyond the homepage) to fetch per website while hunting for
# emails. Pages are tried sequentially, best candidates first, with early-stop —
# so one email worker = one connection at a time (no oversubscription), keeping
# the crawl light AND fast while still reaching the real contact page.
MAX_EMAIL_PAGES = _envi("MAX_EMAIL_PAGES", 6, 8)
MAX_PLACES     = _envi("MAX_PLACES",     200, 500)  # per query cap
DRIVER_TIMEOUT = 25
SCROLL_ROUNDS  = _envi("SCROLL_ROUNDS",  60,  150)  # more rounds = more results
SCROLL_PAUSE   = _envf("SCROLL_PAUSE",   0.4, 0.6)  # longer pause = Google loads more
SCROLL_STALL_LIMIT = _envi("SCROLL_STALL_LIMIT", 8, 15)  # patient = more results

# Email crawl paths — lean by default in prod; set EMAIL_DEEP=1 for more coverage.
_EMAIL_PATHS_LEAN = ["", "/contact", "/contact-us", "/about", "/about-us", "/info", "/get-in-touch", "/team"]
_EMAIL_PATHS_FULL = [
    "", "/contact", "/contact-us", "/contact_us", "/contacto", "/kontakt",
    "/about", "/about-us", "/info", "/get-in-touch", "/reach-us", "/connect",
    "/team", "/our-team", "/support", "/locations", "/enquiry", "/contact.html",
]
_EMAIL_DEEP = _os.environ.get("EMAIL_DEEP", "1") == "1"
EMAIL_PATHS = _EMAIL_PATHS_FULL if _EMAIL_DEEP else _EMAIL_PATHS_LEAN

# Hard wall-clock budget for crawling one website (must stay under the
# future-result timeout in scrape_query, else found emails get discarded).
EMAIL_CRAWL_BUDGET = _envi("EMAIL_CRAWL_BUDGET", 12, 25)

# How often (seconds) to re-check connectivity while a job is paused waiting
# for the internet to come back.
NETWORK_RECHECK = _envi("NETWORK_RECHECK", 5, 5)

# Adaptive CPU throttle: if system CPU climbs above CPU_HIGH percent, the job
# gradually slows down (up to CPU_THROTTLE_MAX extra delay per task) so the box
# stays responsive, then eases back to full speed once CPU drops.
CPU_HIGH          = _envi("CPU_HIGH", 70, 70)      # percent
CPU_THROTTLE_MAX  = _envf("CPU_THROTTLE_MAX", 0.30, 0.30)  # 0.30 = up to 30% slower
CPU_CHECK_EVERY   = _envi("CPU_CHECK_EVERY", 4, 4)  # seconds between CPU samples


def _network_up(timeout: float = 3.0) -> bool:
    """Connectivity probe — open a TCP socket to a couple of always-on HTTPS
    hosts (port 443, the same kind of traffic scraping needs). Using 443 (not
    DNS/53, which some networks block) avoids falsely reporting 'down' on a
    working connection."""
    for host in ("www.google.com", "www.cloudflare.com"):
        try:
            with socket.create_connection((host, 443), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _wait_for_network(job_state) -> bool:
    """Block until the internet is back or the job is cancelled. Sets
    job_state['network_down'] so the UI can show a 'waiting for internet'
    status. Returns True when the network is up, False if cancelled."""
    if _network_up():
        return True
    job_state["network_down"] = True
    while not job_state.get("cancelled"):
        if _network_up():
            job_state["network_down"] = False
            return True
        time.sleep(NETWORK_RECHECK)
    return False

# BUG FIX: moved _TRACKING_PARAMS to module level (was recreated on every call)
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "scid", "exid", "tfn", "leadsource",
    "gclid", "fbclid", "msclkid", "ref", "referrer",
    "source", "medium", "campaign", "mc_cid", "mc_eid",
}

# ── Keyword Categories ─────────────────────────────────────
KEYWORD_CATEGORIES = {
    "General Cold Storage": [
        "cold storage", "cold room", "cold store", "cold storage facility",
        "cold storage warehouse", "cold storage company", "cold storage center",
        "cold storage depot", "cold storage unit", "cold storage plant",
        "cold storage building", "cold storage services", "cold storage solutions",
        "cold storage provider", "cold storage operator",
    ],
    "Freezer & Refrigeration": [
        "freezer room", "freezer storage", "freezer warehouse", "freezer facility",
        "blast freezer", "deep freeze storage", "sub zero storage",
        "walk in freezer", "walk in cooler", "commercial freezer",
        "industrial freezer", "refrigerated warehouse", "refrigerated storage",
        "refrigerated distribution", "refrigeration plant", "refrigeration warehouse",
        "chiller room", "chill store", "blast freeze room", "quick freeze room",
    ],
    "Food & Beverage": [
        "food cold storage", "food grade cold storage", "food warehouse",
        "frozen food storage", "frozen food warehouse", "frozen food company",
        "meat cold storage", "frozen meat storage", "beef cold storage",
        "chicken cold storage", "lamb cold storage", "poultry cold storage",
        "fish cold storage", "frozen fish storage", "seafood cold storage",
        "frozen seafood storage", "vegetable cold storage", "frozen vegetable storage",
        "fruit cold storage", "frozen fruit storage", "dairy cold storage",
        "frozen dairy storage", "egg cold storage",
    ],
    "Pharmaceutical & Medical": [
        "pharmaceutical cold storage", "pharma cold storage",
        "medical cold storage", "vaccine storage", "drug cold storage",
        "temperature controlled pharmaceutical", "cold chain pharmaceutical",
        "biomedical cold storage", "laboratory cold storage", "medical clinic",
        "dental clinic", "diagnostic center", "pharmacy wholesale",
    ],
    "Logistics & Supply Chain": [
        "cold chain", "cold chain warehouse", "cold chain facility",
        "cold chain logistics", "cold logistics", "cold storage logistics",
        "temperature controlled warehouse", "controlled temperature storage",
        "refrigerated container", "reefer storage", "cold storage import export",
        "freight forwarding", "logistics company", "trucking company",
    ],
    "Industrial & Commercial": [
        "industrial cold storage", "commercial cold storage",
        "cold storage rental", "cold storage for rent", "cold storage for lease",
        "freezer rental", "cold room rental", "cold storage distributor",
        "cold storage supplier", "cold storage contractor", "commercial HVAC",
    ],
    "Digital & Marketing Agencies": [
        "digital marketing agency", "marketing agency", "advertising agency",
        "seo agency", "web design agency", "software development company",
        "b2b lead generation agency", "branding agency", "social media agency",
    ],
    "Real Estate & Construction": [
        "commercial real estate", "property management company", "real estate developer",
        "general contractor", "commercial builder", "architecture firm", "facility management",
    ],
    "Solar & Energy Solutions": [
        "solar energy company", "commercial solar installer", "solar panel contractor",
        "renewable energy company", "energy efficiency consultant", "industrial electrical contractor",
    ],
}

DEFAULT_KEYWORDS = [kw for kws in KEYWORD_CATEGORIES.values() for kw in kws]

# ── Email Patterns ─────────────────────────────────────────
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,63}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_JUNK_RE = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|woff|woff2|ttf|eot|css|js|map|ico)$", re.I
)
_JUNK_HOSTS = {
    "sentry", "example", "domain", "schema", "w3.org", "googleapis",
    "cloudflare", "amazonaws", "microsoft", "apple", "facebook",
    "twitter", "instagram", "linkedin", "youtube", "google",
    "placeholder", "yourdomain", "email.com", "test.com", "sample",
    "noreply", "no-reply", "donotreply",
    # Site-builder / template placeholder & internal hosts
    "mysite.com", "wixpress", "wix.com", "squarespace", "godaddy",
    "gravatar", "sentry.io", "wordpress.com", "shopify",
    # Theme / font-license / demo-template boilerplate emails that get baked into
    # many sites' source (not the business's real address).
    "latofonts", "eyebytes", "sansoxygen", "indiantypefoundry", "jovanny.ru",
    "rfuenzalida", "ndiscovered", "avathan", "micahrich", "mailservice.com",
    "acme.com", "website.com", "mikado.com", "avoidwork", "bhambrabland",
    "foxxmedia", "mail.com", "company.com", "webador", "bravistheme",
    "latofonts.com", "jefftrish", "seventyseven",
    # Placeholder + web-dev-agency emails baked into client sites
    "doe.com", "mystore.com", "americaneagle.com", "kodeak", "zdigital",
    "konta.com", "divicarpentry", "yourcompany", "acme.co", "domain.com",
    # Font foundries & WordPress-theme vendors whose licence/support email is
    # embedded in client sites (recur across many unrelated businesses).
    "aldusleaf", "typemade", "latinotype", "sudtipos", "theme-fusion",
    "themefusion", "dominio.com", "construction.com", "maitegranda",
    "envato", "themeforest", "elementor.com", "fontshop", "webdesignstudio",
}
_JUNK_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "webmaster", "admin@admin",
    "info@info", "test@", "example@", "dev@", "developer@", "designer@", "webdesign@",
}
# Exact addresses that recur across unrelated sites (theme/demo/font authors,
# generic placeholders) — never a real lead.
_JUNK_ADDRESSES = frozenset({
    "impallari@gmail.com", "anapbm@gmail.com", "needhelp@gmail.com",
    "mymail@mailservice.com", "mail@mail.com", "support@website.com",
    "info@company.com", "john@company.com", "j.smith@acme.com",
    "john.smith@work.com", "john.smith@home.com", "dor@mikado.com",
    "office@avathan.com", "mail@example.com", "strettfe@gmail.com",
    "matt@pixelspread.com", "team@latofonts.com",
})
# Placeholder local-parts used in demo content.
_JUNK_LOCALS = {
    "john.smith", "jane.doe", "j.smith", "johndoe", "janedoe", "youremail",
    "yourname", "firstname", "lastname", "mymail", "needhelp", "lorem", "ipsum",
    "email", "name", "user", "usuario", "correo", "nombre",
}

# ── Obfuscated / protected email handling ──────────────────
# Cloudflare "email protection": real address is hex-encoded in data-cfemail / link hash
_CF_ATTR_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
_CF_LINK_RE = re.compile(r'/cdn-cgi/l/email-protection#([0-9a-fA-F]+)')
_MAILTO_RE  = re.compile(r'mailto:([^"\'?>\s]+)', re.I)
# " name [at] domain [dot] com " style obfuscation (bracketed only — safe)
_AT_RE  = re.compile(r'\s*[\(\[\{]\s*at\s*[\)\]\}]\s*', re.I)
_DOT_RE = re.compile(r'\s*[\(\[\{]\s*dot\s*[\)\]\}]\s*', re.I)


def _decode_cfemail(encoded: str) -> str:
    """Decode a Cloudflare-obfuscated email (XOR with first byte)."""
    try:
        key = int(encoded[:2], 16)
        return "".join(
            chr(int(encoded[i:i+2], 16) ^ key)
            for i in range(2, len(encoded), 2)
        )
    except Exception:
        return ""


def _is_valid_email(email: str) -> bool:
    el = email.lower()
    # Malformed: leftover markup/encoding artifacts (%20 spaces, HTML entities,
    # mailto:, backslashes, whitespace). These aren't real addresses.
    if any(c in email for c in ("%", "&", "\\", "<", ">", " ", "\t")) or "mailto" in el:
        return False
    if el.count("@") != 1:
        return False
    host = el.split("@")[-1]
    local = el.split("@")[0]
    # "%20info@…" URL-encoded-space artifact: after % is stripped the local starts
    # with a stray "20" (e.g. "20info", "20sales", "20customerservice").
    if re.match(r"^20(info|sales|admin|contact|support|office|needhelp|customerservice|bjkeane)", local):
        return False
    if _JUNK_RE.search(email):
        return False
    if el in _JUNK_ADDRESSES:
        return False
    if local in _JUNK_LOCALS:
        return False
    if any(j in host for j in _JUNK_HOSTS):
        return False
    if any(el.startswith(p) for p in _JUNK_PREFIXES):
        return False
    if host.startswith("www."):
        return False
    parts = host.split(".")
    if len(parts) < 2 or len(parts[-1]) < 2:
        return False
    if len(local) < 2 or len(local) > 64:
        return False
    return True


# ── HTTP Client ────────────────────────────────────────────
_HTTP_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=40)
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_HTTP_CLIENT = httpx.Client(
    headers=_HTTP_HEADERS,
    timeout=EMAIL_TIMEOUT,
    follow_redirects=False,  # follow manually so each redirect hop is SSRF-checked
    limits=_HTTP_LIMITS,
    verify=False,  # many business sites have self-signed/expired certs
)
_MAX_REDIRECTS = 5


def _clean_url(url: str) -> str:
    """Remove UTM params and tracking tokens from URLs."""
    if not url:
        return ""
    try:
        if "google.com/url" in url:
            qs = parse_qs(urlparse(url).query)
            if "q" in qs:
                url = qs["q"][0]

        parsed = urlparse(url)
        clean_qs = {
            k: v for k, v in parse_qs(parsed.query).items()
            if k.lower() not in _TRACKING_PARAMS
        }
        clean_query = urlencode(clean_qs, doseq=True)
        clean = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, clean_query, ""
        ))
        return clean.rstrip("?&")
    except Exception:
        return url


def _is_public_host(host: str) -> bool:
    """SSRF guard: resolve host and reject loopback/private/link-local/reserved IPs.
    Prevents a scraped/redirected URL from making us hit internal services
    (e.g. http://localhost, 127.0.0.1, 169.254.169.254, 10.x, 192.168.x)."""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def _fetch_page_sync(url: str, timeout: int = EMAIL_TIMEOUT) -> str:
    """Fetch a single page synchronously with SSRF protection, size caps (max 1.5MB),
    and mime-type filtering to prevent OOM / server crash on binary assets."""
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            host = urlparse(url).hostname
            if not _is_public_host(host):
                return ""
            r = _HTTP_CLIENT.get(url, timeout=timeout)
            if r.is_redirect and r.has_redirect_location:
                url = str(r.next_request.url)
                continue
            # Filter non-HTML/text content to protect memory from huge binary downloads
            ct = r.headers.get("content-type", "").lower()
            if ct and not any(t in ct for t in ("text", "html", "xml", "json")):
                return ""
            # Reject oversized responses (>3MB)
            cl = r.headers.get("content-length")
            if cl and cl.isdigit() and int(cl) > 3_000_000:
                return ""
            return r.text[:1_500_000]
        return ""  # too many redirects
    except Exception:
        return ""


# Strip web designer / developer / theme-maker attribution blocks
_DESIGNER_CREDIT_RE = re.compile(
    r'(?i)(?:website|site|theme|portal|design)?\s*(?:designed|developed|created|built|powered|maintained|hosted)\s+by[^<\n]{1,160}',
    re.I
)
_FOOTER_CREDIT_TAG_RE = re.compile(
    r'(?i)<(?:footer|div|p|span|a)[^>]*(?:credit|designer|developer|author|attribution|theme-info|site-info)[^>]*>.*?</(?:footer|div|p|span|a)>',
    re.I | re.S
)
_TEL_RE = re.compile(r'href\s*=\s*["\']tel:([^"\'?>\s]+)["\']', re.I)

# ── Decision Maker Extraction ──────────────────────────────
_DM_ROLES_REGEX = (
    r"(?:Chief\s+Executive\s+Officer|CEO|Founder|Co-Founder|Owner|Co-Owner|President|"
    r"Vice\s+President|VP|Principal|Managing\s+Director|MD|General\s+Manager|GM|"
    r"Chief\s+Operating\s+Officer|COO|Chief\s+Financial\s+Officer|CFO|Chief\s+Technology\s+Officer|CTO|"
    r"Chief\s+Marketing\s+Officer|CMO|Executive\s+Director|Managing\s+Partner|Partner|"
    r"(?:(?:Warehouse|Facility|Plant|General|Branch|Regional|Commercial|Operations|Logistics|Supply\s+Chain|Marketing|Sales|Business\s+Development|Fleet|Distribution)\s+)*(?:Director|Manager|Head|Lead|Officer|President|VP|Executive))"
)
_DECISION_MAKER_ROLES_RE = re.compile(rf"\b{_DM_ROLES_REGEX}\b", re.I)
_JSON_LD_RE = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)

# Name + Title pattern: "John Doe, CEO & Founder" or "Sarah Jenkins - Marketing Director" or "Mike Ross (General Manager)"
_DM_NAME_FIRST_RE = re.compile(
    r'(?:^|[\n>•\-])\s*'
    r'([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,2})'
    r'\s*(?:[-–—|,:]|\s+is\s+(?:the\s+)?|\s*\n\s*|\s*\()\s*'
    r'(' + _DM_ROLES_REGEX + r'[^<\n,\(\)]*)'
    r'(?:\))?',
    re.I
)

# Title + Name pattern: "CEO: John Doe" or "Founder & Owner - Sarah Connor"
_DM_TITLE_FIRST_RE = re.compile(
    r'(?:^|[\n>•\-])\s*'
    r'(' + _DM_ROLES_REGEX + r'[^<\n:,–—|]*)'
    r'\s*(?:[-–—|:]|\s*\n\s*)\s*'
    r'([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,2})\b',
    re.I
)


def extract_phone_from_html(html: str) -> str:
    """Extract first valid business phone number from website HTML (e.g. from tel: links),
    ignoring any numbers inside web-designer credit blocks."""
    if not html:
        return ""
    clean_html = _FOOTER_CREDIT_TAG_RE.sub("", html)
    clean_html = _DESIGNER_CREDIT_RE.sub("", clean_html)
    for m in _TEL_RE.finditer(clean_html):
        raw = m.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        if 7 <= len(digits) <= 15 and digits != "1234567890" and digits != "0123456789":
            return raw
    return ""


def extract_decision_makers_from_html(html: str, max_items: int = 4) -> list[str]:
    """Extract key decision makers (Name, Title, Email, Phone) from HTML."""
    if not html:
        return []

    clean_html = _FOOTER_CREDIT_TAG_RE.sub("", html)
    clean_html = _DESIGNER_CREDIT_RE.sub("", clean_html)

    found: list[str] = []
    seen_names: set[str] = set()

    # 1. JSON-LD Schema.org Person extraction
    for script in _JSON_LD_RE.finditer(clean_html):
        try:
            data = json.loads(script.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                graph = item.get("@graph", [item]) if isinstance(item, dict) else []
                for obj in graph:
                    if isinstance(obj, dict) and obj.get("@type") in ("Person", "http://schema.org/Person"):
                        name = (obj.get("name") or "").strip()
                        job = (obj.get("jobTitle") or obj.get("role") or "").strip()
                        email = (obj.get("email") or "").strip()
                        phone = (obj.get("telephone") or "").strip()
                        if name and job and _DECISION_MAKER_ROLES_RE.search(job):
                            nk = name.lower()
                            if nk not in seen_names and len(name.split()) in (2, 3):
                                seen_names.add(nk)
                                extra = []
                                if email and _is_valid_email(email): extra.append(email)
                                if phone: extra.append(phone)
                                label = f"{name} ({job}" + (f" · {' · '.join(extra)}" if extra else "") + ")"
                                found.append(label)
        except Exception:
            pass

    # 2. Plain text / HTML regex extraction
    text = _html.unescape(clean_html)
    text_clean = re.sub(r'<(?:script|style)[^>]*>.*?</(?:script|style)>', '', text, flags=re.I | re.S)
    text_lines = re.sub(r'<[^>]+>', '\n', text_clean)

    for m in _DM_NAME_FIRST_RE.finditer(text_lines):
        name = m.group(1).strip()
        title = m.group(2).strip()
        nk = name.lower()
        if nk not in seen_names and len(name.split()) in (2, 3):
            if not any(w in nk for w in ("cold", "storage", "company", "limited", "group", "service", "center", "about", "contact", "home", "page", "website", "privacy", "terms", "our", "the", "meet", "view")):
                seen_names.add(nk)
                found.append(f"{name} ({title})")
                if len(found) >= max_items:
                    break

    if len(found) < max_items:
        for m in _DM_TITLE_FIRST_RE.finditer(text_lines):
            title = m.group(1).strip()
            name = m.group(2).strip()
            nk = name.lower()
            if nk not in seen_names and len(name.split()) in (2, 3):
                if not any(w in nk for w in ("cold", "storage", "company", "limited", "group", "service", "center", "about", "contact", "home", "page", "website", "privacy", "terms", "our", "the", "meet", "view")):
                    seen_names.add(nk)
                    found.append(f"{name} ({title})")
                    if len(found) >= max_items:
                        break

    return found[:max_items]


def extract_emails_from_html(html: str) -> list[str]:
    """Extract and validate emails from HTML — handles plain text, mailto:,
    HTML entities, Cloudflare-protected, and '(at)/(dot)' obfuscated addresses,
    while stripping designer/developer/theme-maker credit blocks."""
    if not html:
        return []

    # Strip web designer / developer / theme attribution blocks so their emails aren't extracted
    clean_html = _FOOTER_CREDIT_TAG_RE.sub("", html)
    clean_html = _DESIGNER_CREDIT_RE.sub("", clean_html)

    found, seen = [], set()
    candidates: list[str] = []

    # 1. Cloudflare email protection (very common on business sites)
    for m in _CF_ATTR_RE.finditer(clean_html):
        d = _decode_cfemail(m.group(1))
        if d:
            candidates.append(d)
    for m in _CF_LINK_RE.finditer(clean_html):
        d = _decode_cfemail(m.group(1))
        if d:
            candidates.append(d)

    # 2. Decode HTML entities (e.g. info&#64;site&#46;com) for everything else
    text = _html.unescape(clean_html)

    # 3. Explicit mailto: links
    for m in _MAILTO_RE.finditer(text):
        candidates.append(m.group(1))

    # 4. De-obfuscate "name [at] domain [dot] com" then run the plain regex
    deob = _DOT_RE.sub(".", text)
    deob = _AT_RE.sub("@", deob)
    candidates.extend(m.group(0) for m in _EMAIL_RE.finditer(text))
    candidates.extend(m.group(0) for m in _EMAIL_RE.finditer(deob))

    for e in candidates:
        e = e.strip().strip(".,;:")
        el = e.lower()
        if el and el not in seen and _is_valid_email(e):
            seen.add(el)
            found.append(e)
    return found


# Links worth following for emails: contact/about/team pages, in any language /
# spelling. Discovering these from the homepage catches the many sites whose
# contact URL isn't one of the fixed guesses (e.g. /reach-us-today, /find-us).
_CONTACT_HINT_RE = re.compile(
    r"contact|about|team|leadership|management|executives|staff|people|directors|founders|"
    r"reach|connect|get[-_]?in[-_]?touch|kontakt|contacto|"
    r"support|enquir|inquir|location|find[-_]?us|impressum|who[-_]?we[-_]?are",
    re.I,
)
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)


def _discover_contact_links(html: str, base: str, netloc: str, limit: int = 8) -> list[str]:
    """Pull same-site contact/about/team links out of homepage HTML."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _HREF_RE.finditer(html):
        href = m.group(1).strip()
        if not href or href.lower().startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if not _CONTACT_HINT_RE.search(href):
            continue
        full = urljoin(base, href).split("#")[0]
        p = urlparse(full)
        if p.scheme not in ("http", "https") or p.netloc != netloc:
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
        if len(out) >= limit:
            break
    return out


# Business social profiles worth capturing as an alternate contact channel.
_SOCIAL_RE = re.compile(
    r'https?://(?:[a-z0-9-]+\.)?'
    r'(?:linkedin\.com|facebook\.com|fb\.com|instagram\.com|twitter\.com|x\.com|'
    r'youtube\.com|t\.me|wa\.me|tiktok\.com)/[^\s"\'<>)]+',
    re.I,
)
# Drop share/tracking/widget links — we only want real profile URLs.
_SOCIAL_JUNK = (
    "/sharer", "/share?", "/share.php", "/intent/", "/plugins/", "/dialog/",
    "sharearticle", "share_channel", "/tr?", "javascript", "/embed",
)


def extract_socials_from_html(html: str, limit: int = 4) -> list[str]:
    """Pull business social-profile links (LinkedIn/Facebook/Instagram/…) out of
    a page, skipping share/tracking widgets."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _SOCIAL_RE.finditer(html or ""):
        u = m.group(0).rstrip('",\'.);')
        ul = u.lower()
        if any(j in ul for j in _SOCIAL_JUNK):
            continue
        key = ul.split("?")[0].rstrip("/")
        # Skip bare domain roots (e.g. https://facebook.com/) — not a profile.
        if key.count("/") < 3:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(u.split("?")[0])
        if len(out) >= limit:
            break
    return out


def extract_email(url: str, seen_websites: set, lock: threading.Lock, max_emails: int = 5):
    """Crawl homepage + contact/about/team pages for emails, socials, phone, and decision makers."""
    if not url:
        return "", "", "", ""
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    with lock:
        if base in seen_websites:
            return "", "", "", ""
        seen_websites.add(base)

    all_emails: list[str] = []
    seen_emails: set[str] = set()
    all_socials: list[str] = []
    seen_socials: set[str] = set()
    all_dms: list[str] = []
    seen_dms: set[str] = set()
    discovered_phone: str = ""

    def _collect(html: str) -> None:
        nonlocal discovered_phone
        for e in extract_emails_from_html(html):
            el = e.lower()
            if el not in seen_emails:
                seen_emails.add(el)
                all_emails.append(e)
        for s in extract_socials_from_html(html):
            sk = s.lower().split("?")[0].rstrip("/")
            if sk not in seen_socials:
                seen_socials.add(sk)
                all_socials.append(s)
        for dm in extract_decision_makers_from_html(html):
            dmk = dm.lower()
            if dmk not in seen_dms:
                seen_dms.add(dmk)
                all_dms.append(dm)
        if not discovered_phone:
            discovered_phone = extract_phone_from_html(html)

    deadline = time.time() + EMAIL_CRAWL_BUDGET

    # 1. Homepage first — for its own emails and to discover contact links.
    home = _fetch_page_sync(url)
    if home:
        _collect(home)

    # 2. Build candidate list: links discovered on homepage first
    discovered = _discover_contact_links(home, base, parsed.netloc) if home else []
    candidates: list[str] = []
    seen_c = {url.split("#")[0]}
    for c in discovered + [urljoin(base, p) for p in EMAIL_PATHS[1:]]:
        k = c.split("#")[0]
        if k not in seen_c:
            seen_c.add(k)
            candidates.append(c)

    # 3. Crawl candidate contact/about/team pages
    for page_url in candidates[:MAX_EMAIL_PAGES]:
        if (len(all_emails) >= max_emails and len(all_dms) >= 2) or time.time() > deadline:
            break
        html = _fetch_page_sync(page_url)
        if html:
            _collect(html)

    return (
        ", ".join(all_emails[:max_emails]),
        ", ".join(all_socials[:3]),
        discovered_phone,
        "; ".join(all_dms[:4])
    )


# ── Selenium Driver ────────────────────────────────────────
def setup_driver():
    opts = Options()
    # 'eager' returns from driver.get() at DOMContentLoaded instead of waiting
    # for every Maps resource/tile to finish — we wait for the results feed
    # ourselves right after. Big per-query speedup on this heavy SPA.
    opts.page_load_strategy = "eager"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-gl-drawing-for-tests")
    opts.add_argument("--log-level=3")
    opts.add_argument("--silent")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    # Trim background work that just slows page loads (no effect on scraped data).
    opts.add_argument("--mute-audio")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-features=Translate,BackForwardCache,MediaRouter")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # BUG FIX: combined both excludeSwitches values into one call (second was overwriting first)
    opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    # Capture network traffic so we can read the /search pagination responses
    # (which hold ALL scrolled results, not just the initial ~20).
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # In Docker/Railway, Chrome + chromedriver are installed at fixed paths and
    # passed via env. Locally these are unset → Selenium Manager auto-resolves.
    chrome_bin = _os.environ.get("CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin
    driver_path = _os.environ.get("CHROMEDRIVER_PATH")
    if driver_path:
        from selenium.webdriver.chrome.service import Service
        d = webdriver.Chrome(service=Service(driver_path), options=opts)
    else:
        # Always local Chrome. (Remote "Browserless" support was removed: a stale
        # or invalid BROWSERLESS_TOKEN in .env silently broke every scrape —
        # webdriver.Remote raised "Invalid API key" and jobs returned 0 results.)
        d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(DRIVER_TIMEOUT)
    return d


# ── Fast path: parse all places from the search page's data blob ──
# Google Maps embeds the full result set (name, phone, website, address,
# rating, category) in window.APP_INITIALIZATION_STATE. Reading it once avoids
# opening each place in a separate page load (the slow part). Indices are
# Google-internal and can change — every access is defensive, and the caller
# falls back to per-place scraping if this yields nothing.
def _safe_idx(arr, *idxs):
    cur = arr
    for i in idxs:
        try:
            cur = cur[i]
        except (IndexError, KeyError, TypeError):
            return None
    return cur


def _looks_like_place(o):
    """A place data array: long list whose [11] is a non-empty name string."""
    return (
        isinstance(o, list) and len(o) > 14
        and isinstance(o[11], str) and o[11].strip()
        and any(isinstance(e, list) for e in o)
    )


def _parse_place_entry(pd):
    name = pd[11]
    website  = _safe_idx(pd, 7, 0)
    phone    = _safe_idx(pd, 178, 0, 0) or _safe_idx(pd, 178, 0, 3)
    address  = _safe_idx(pd, 39)
    if not isinstance(address, str) or not address:
        address = _safe_idx(pd, 18)
    if not isinstance(address, str) or not address:
        comp = _safe_idx(pd, 2)
        address = ", ".join(x for x in comp if isinstance(x, str)) if isinstance(comp, list) else ""
    # Strip a leading "<name>, " that Google sometimes prepends to the address
    if isinstance(address, str) and address.startswith(name + ", "):
        address = address[len(name) + 2:]
    rating   = _safe_idx(pd, 4, 7)
    category = _safe_idx(pd, 13, 0)
    return {
        "name":     name,
        "phone":    phone if isinstance(phone, str) else "",
        "address":  address if isinstance(address, str) else "",
        "rating":   str(rating) if isinstance(rating, (int, float)) else "",
        "category": category if isinstance(category, str) else "",
        "website":  _clean_url(website) if isinstance(website, str) else "",
    }


def _walk_collect(data, places, seen):
    """Recursively find place arrays in a parsed structure and append them."""
    def walk(o, depth=0):
        if depth > 16 or not isinstance(o, list):
            return
        if _looks_like_place(o):
            try:
                parsed = _parse_place_entry(o)
            except Exception:
                parsed = None
            if parsed:
                k = parsed["name"] + "|" + parsed["address"]
                if k not in seen:
                    seen.add(k)
                    places.append(parsed)
            return  # don't recurse into a matched place node
        for x in o:
            walk(x, depth + 1)
    walk(data)


def _collect_from_blob_string(s, places, seen):
    """Parse a result payload and append any place arrays found. Handles the raw
    XSSI-guarded string ()]}') and the {"c":..,"d":")]}'..."} streaming wrapper
    used by /search pagination — which concatenates several JSON objects, so we
    decode them one at a time with raw_decode."""
    if not isinstance(s, str) or not s:
        return

    payloads = []
    if s.startswith("{"):
        decoder = json.JSONDecoder()
        idx, n = 0, len(s)
        while idx < n:
            while idx < n and s[idx] in " \r\n\t":
                idx += 1
            if idx >= n:
                break
            try:
                obj, end = decoder.raw_decode(s, idx)
            except Exception:
                break
            idx = end
            if isinstance(obj, dict) and isinstance(obj.get("d"), str):
                payloads.append(obj["d"])
    else:
        payloads.append(s)

    for p in payloads:
        if not p.startswith(")]}'"):
            continue
        try:
            data = json.loads(p.split("\n", 1)[1] if "\n" in p else p[4:])
        except Exception:
            continue
        _walk_collect(data, places, seen)


def _find_data_blob(driver):
    """The initial result string embedded in window.APP_INITIALIZATION_STATE."""
    try:
        state = driver.execute_script("return window.APP_INITIALIZATION_STATE")
    except Exception:
        return None
    if not state:
        return None
    container = state[3] if len(state) > 3 else None
    values = (container.values() if isinstance(container, dict)
              else container if isinstance(container, list) else [])
    big = None
    for v in values:
        if isinstance(v, list):
            for x in v:
                if isinstance(x, str) and x.startswith(")]}'") and (big is None or len(x) > len(big)):
                    big = x
    return big


def _extract_places_from_search(driver):
    """Parse every place from BOTH the initial embedded blob AND the /search
    pagination responses captured via CDP (so we get all scrolled results, not
    just the first ~20). Returns [] if nothing parses → caller falls back."""
    places, seen = [], set()

    # 1. Initial embedded blob (first page of results)
    big = _find_data_blob(driver)
    if big:
        _collect_from_blob_string(big, places, seen)

    # 2. All /search pagination responses captured from the network log
    try:
        logs = driver.get_log("performance")
    except Exception:
        logs = []
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") != "Network.responseReceived":
                continue
            url = msg["params"]["response"]["url"]
            if "/search?" not in url:
                continue
            rid = msg["params"]["requestId"]
            body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
            _collect_from_blob_string(body.get("body", ""), places, seen)
        except Exception:
            continue

    return places


# ── Scrape one query ───────────────────────────────────────
def scrape_query(driver_box, query, city, state, worker_id, job_state, email_executor):
    """Scrape one Google Maps query. Returns True if the search page loaded
    (the task is complete, even with 0 results), False if it never loaded
    (driver/network failure) so the caller can wait-and-retry."""
    if job_state["cancelled"]:
        return False

    results  = job_state["results"]
    lock     = job_state["lock"]
    seen_web = job_state["seen_websites"]
    max_em   = job_state.get("max_emails", 5)
    _relevant_terms = job_state.get("relevant_terms")   # empty/None = keep all
    _relevant_block = job_state.get("relevant_block")   # compiled regex or None
    _relevant_cats  = job_state.get("relevant_cats")    # user whitelist regex or None
    loaded   = False   # True once the search results page has loaded

    def _get(driver, selectors):
        if isinstance(selectors, str):
            selectors = [selectors]
        for css in selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, css)
                text = el.text.strip()
                if text:
                    return text
            except Exception:
                pass
        return ""

    def _submit_email(website, key):
        """Crawl emails in the background and fill results[key]['email'] when done.
        Non-blocking: the driver immediately moves to the next query instead of
        idling 10-30s waiting for HTTP — big throughput win, same data."""
        if not website:
            return
        with lock:
            job_state["emails_submitted"] += 1
        fut = email_executor.submit(extract_email, website, seen_web, lock, max_em)
        def _done(f, _key=key):
            try:
                res = f.result()
                em = soc = phone = dms = ""
                if isinstance(res, (tuple, list)):
                    if len(res) >= 4:
                        em, soc, phone, dms = res[0], res[1], res[2], res[3]
                    elif len(res) == 2:
                        em, soc = res[0], res[1]
                if em or soc or phone or dms:
                    with lock:
                        if _key in results:
                            if em:
                                results[_key]["email"] = em
                            if soc:
                                results[_key]["social"] = soc
                            if phone and not results[_key].get("phone"):
                                results[_key]["phone"] = phone
                            if dms and not results[_key].get("decision_makers"):
                                results[_key]["decision_makers"] = dms
            except Exception:
                pass
            finally:
                # Count every finished site (email found or not) so the
                # post-scrape "extracting emails" wait knows when it's complete.
                with lock:
                    job_state["emails_done"] += 1
        fut.add_done_callback(_done)

    place_urls = []

    for attempt in range(2):
        if job_state["cancelled"]:
            return
        try:
            driver = driver_box[0]
            # Raise CDP network buffers so the (large) /search pagination
            # response bodies aren't evicted before we read them.
            try:
                # Enough to hold the /search pagination bodies (~a few MB) without
                # bloating memory on small cloud containers.
                driver.execute_cdp_cmd("Network.enable", {
                    "maxTotalBufferSize":    32 * 1024 * 1024,
                    "maxResourceBufferSize": 16 * 1024 * 1024,
                })
            except Exception:
                pass
            search_url = "https://www.google.com/maps/search/" + quote_plus(query)
            driver.get(search_url)
            time.sleep(PAGE_WAIT)

            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='feed']"))
                )
            except Exception:
                pass

            prev_count = 0
            no_change_streak = 0
            for _ in range(SCROLL_ROUNDS):
                # Stop scrolling immediately if the job was cancelled — otherwise
                # a worker keeps scrolling this query for up to ~90s after cancel.
                if job_state["cancelled"]:
                    break
                try:
                    feed = driver.find_element(By.CSS_SELECTOR, "[role='feed']")
                    driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight", feed
                    )
                    time.sleep(SCROLL_PAUSE)

                    current_count = len(driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']"))

                    if current_count == prev_count:
                        # Results stopped growing — only NOW pay for page_source
                        # (full-DOM transfer) to confirm we've truly hit the end.
                        # Skipping it while the list keeps growing is a big speedup
                        # on large queries.
                        no_change_streak += 1
                        page_src = driver.page_source.lower()
                        if (
                            "reached the end of the list" in page_src
                            or "no more results" in page_src
                        ):
                            break
                        if no_change_streak >= SCROLL_STALL_LIMIT:
                            break
                        # Extra wait — Google sometimes needs 1-2s to lazy-load next batch
                        time.sleep(SCROLL_PAUSE * 1.5)
                    else:
                        no_change_streak = 0
                    prev_count = current_count
                except Exception:
                    break

            cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
            place_urls = list({
                c.get_attribute("href")
                for c in cards
                if c.get_attribute("href")
            })
            loaded = True   # search page loaded → this task counts as complete
            break

        except Exception:
            try:
                driver_box[0].quit()
            except Exception:
                pass
            time.sleep(2)
            try:
                driver_box[0] = setup_driver()
            except Exception:
                return False

    # ── FAST PATH: parse every place from the search page in one shot ──
    blob_places = []
    try:
        blob_places = _extract_places_from_search(driver_box[0])
    except Exception:
        blob_places = []

    # Use the fast path if blob captured at least 60% of feed results.
    _feed_n = len(place_urls)
    _fast_ok = bool(blob_places) and (_feed_n == 0 or len(blob_places) >= _feed_n * 0.6)

    if _fast_ok:
        for p in blob_places[:MAX_PLACES]:
            if job_state["cancelled"]:
                break
            name = p["name"]
            # "Only relevant categories" — drop Google's loosely-related padding.
            if (_relevant_terms or _relevant_cats) and not _is_relevant(p.get("category", ""), name, _relevant_terms, _relevant_block, _relevant_cats):
                continue
            # City-independent key: same business found via multiple nearby-city
            # queries collapses to one row (dedup by phone/website/address).
            key = _dedup_key(name, p.get("phone", ""), p.get("website", ""), p.get("address", ""))
            with lock:
                if key not in results:
                    results[key] = {
                        "name":            name,
                        "city":            city,
                        "state":           state,
                        "phone":           p["phone"],
                        "address":         p["address"],
                        "rating":          p["rating"],
                        "category":        p["category"],
                        "email":           "",
                        "social":          "",
                        "decision_makers": "",
                        "website":         p["website"],
                    }
            _submit_email(p["website"], key)
        return True

    # ── FALLBACK: open each place individually (old, slower, more robust) ──
    for purl in place_urls[:MAX_PLACES]:
        if job_state["cancelled"]:
            break
        for attempt in range(2):
            try:
                driver = driver_box[0]
                driver.get(purl)
                time.sleep(PAGE_WAIT)

                # Prefer stable attribute selectors (data-item-id / aria-label),
                # fall back to obfuscated class names which Google rotates often.
                name = _get(driver_box[0], [
                    "h1.DUwDvf", "h1.fontHeadlineLarge",
                    "[role='main'] h1", "div[role='main'] h1", "h1",
                ])
                # Website: use href attribute, not text
                website = ""
                for ws_sel in [
                    "a[data-item-id='authority']",
                    "a[data-tooltip='Open website']",
                    "a[aria-label^='Website']",
                    "a[aria-label*='Website:']",
                    "a[data-item-id*='authority']",
                ]:
                    try:
                        el = driver_box[0].find_element(By.CSS_SELECTOR, ws_sel)
                        raw = el.get_attribute("href") or el.text.strip()
                        if raw:
                            website = _clean_url(raw)
                            break
                    except Exception:
                        pass
                phone   = _get(driver_box[0], [
                    "button[data-item-id*='phone'] .Io6YTe",
                    "button[data-tooltip*='phone'] .Io6YTe",
                    "button[aria-label*='Phone']",
                    "[data-item-id^='phone']",
                    "[data-item-id*='phone']",
                ])
                address = _get(driver_box[0], [
                    "button[data-item-id='address'] .Io6YTe",
                    "button[data-tooltip*='address'] .Io6YTe",
                    "button[aria-label*='Address']",
                    "[data-item-id='address']",
                ])
                rating  = _get(driver_box[0], [
                    ".F7nice span[aria-hidden='true']",
                    ".MW4etd", "span.ceNzKf",
                    "div.F7nice", "[aria-label*='stars']",
                ])
                category = _get(driver_box[0], [
                    ".DkEaL", ".fontBodyMedium .DkEaL",
                    "button[jsaction*='category']",
                ])

                if name and not ((_relevant_terms or _relevant_cats) and not _is_relevant(category, name, _relevant_terms, _relevant_block, _relevant_cats)):
                    key = _dedup_key(name, phone, website, address)
                    with lock:
                        if key not in results:
                            results[key] = {
                                "name":            name,
                                "city":            city,
                                "state":           state,
                                "phone":           phone,
                                "address":         address,
                                "rating":          rating,
                                "category":        category,
                                "email":           "",
                                "social":          "",
                                "decision_makers": "",
                                "website":         website,
                            }
                    _submit_email(website, key)
                break

            except Exception:
                try:
                    driver_box[0].quit()
                except Exception:
                    pass
                time.sleep(2)
                try:
                    driver_box[0] = setup_driver()
                except Exception:
                    break

    return loaded


# ── Row de-duplication key ─────────────────────────────────
def _dedup_key(name: str, phone: str = "", website: str = "", address: str = "") -> str:
    """City-independent business key. Google Maps returns the SAME business for
    many nearby query-cities (radius search), so keying on the query-city stored
    the same business dozens of times. Key on phone → website → address instead,
    so one business = one row no matter how many cities' queries surfaced it.

    Phone/website are keyed ALONE (name excluded): the same number listed under a
    slightly different name ("ABC Architects" vs "ABC Architects Inc") must collapse
    to one row — otherwise the same phone number appears twice. Only the last-resort
    address fallback keeps the name, so two distinct businesses in one building with
    no phone/website aren't wrongly merged. A different phone = a separate entry."""
    n = (name or "").strip().lower()
    digits = re.sub(r"\D", "", phone or "")
    # Normalise US/Canada numbers: "+1 213-555-1000" and "213.555.1000" are the
    # same number — drop the leading "1" country code so they collapse to one key.
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if digits:
        return f"tel:{digits}"
    # Normalise the website: http/https and a leading "www." are the same site.
    w = (website or "").strip().lower()
    w = re.sub(r"^https?://", "", w)
    w = re.sub(r"^www\.", "", w).rstrip("/")
    if w:
        return f"web:{w}"
    return f"{n}|{(address or '').strip().lower()}"


# ── "Only relevant categories" filter ──────────────────────
# Generic (any-niche) qualifiers that don't define a business type — dropped so
# they don't cause false matches (e.g. "services" matching "Financial services").
_RELEVANCE_STOP = {
    "services", "service", "design", "designs", "company", "commercial",
    "residential", "outsource", "remote", "turnkey", "turnaround", "solutions",
    "professional", "consultant", "consulting", "with", "your", "and", "for",
    "the", "firm", "group", "fast", "white", "label", "near",
}


def _keyword_terms(keywords) -> set:
    """5-char stems of the meaningful words in the user's own keywords. Used to
    keep only results whose category relates to what they searched. Generic
    qualifiers (_RELEVANCE_STOP) are dropped — but if a keyword is made up ENTIRELY
    of such words (e.g. "law firm", "spa"), they are kept, because the user
    deliberately searched for them."""
    terms = set()
    for kw in (keywords or []):
        words   = re.findall(r"[a-z]{3,}", (kw or "").lower())
        content = [w for w in words if w not in _RELEVANCE_STOP]
        for w in (content or words):   # all-stopword keyword → use it as-is
            terms.add(w[:5])
    return terms


# Noise categories that leak in via ambiguous keyword-stem collisions (e.g.
# "BIM modeling" → "Modeling agency", "land development" → "Real estate developer").
# These are dropped ONLY when the user did not actually search for them — see
# _active_block(), which removes any entry the user's own keywords reference. So a
# search for "spa" or "law firm" keeps spas / law firms, while an architecture
# search drops them as padding.
_CATEGORY_BLOCK = (
    "modeling agency", "talent agency", "model management", "movie studio",
    "film production", "real estate", "property manage", "attorney", "law firm",
    "lawyer", "legal", "paralegal", "notary", "translation", "government",
    "insurance", "bank", "restaurant", "hotel", "hospital", "dentist", "doctor",
    "salon", "spa", "church", "school", "university", "museum", "library",
    "airport", "apartment", "employment", "recruit", "staffing",
)


def _block_pattern(keywords):
    """Compile the blocklist into one whole-word regex, MINUS anything the user
    actually searched for. If a keyword mentions a blocked term (e.g. keyword
    "day spa" → "spa"), that term is dropped from the block, so the filter stays
    domain-agnostic: you always get what you asked for. Whole-word matching means
    "spa" blocks a spa but not "space planning". Returns None if nothing to block."""
    kw_text = " ".join(keywords or []).lower()
    active = [b for b in _CATEGORY_BLOCK
              if not re.search(r"\b" + re.escape(b) + r"\b", kw_text)]
    if not active:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(b) for b in active) + r")\b")


def _category_pattern(categories):
    """Compile an explicit user-supplied category whitelist into one whole-word,
    case-insensitive regex (e.g. ["architect","general contractor"]). Whole-word
    matching keeps "Architect"/"Landscape architect" but not "space"↔"spa".
    Returns None when no usable category is given."""
    active = [c.strip().lower() for c in (categories or []) if c and c.strip()]
    if not active:
        return None
    # Word-PREFIX match (leading boundary, no trailing): "architect" catches
    # "Architect", "Architecture firm", "Architectural designer" and the name
    # "DNA Architecture" — so the user needn't list every variant. Leading \b
    # still prevents mid-word hits ("microarchitect").
    return re.compile(r"\b(?:" + "|".join(re.escape(c) for c in active) + r")")


def _is_relevant(category: str, name: str, terms: set, block_re=None, cats_re=None) -> bool:
    """Keep a result only if its **category** is relevant. When the user supplies an
    explicit category whitelist (`cats_re`), that is authoritative: keep only if the
    category matches it (keyword stems / blocklist ignored). Otherwise fall back to
    keyword-stem matching — matching the category (not the name) avoids false hits
    like "Structure Law Group"; `block_re` drops noise categories that collide with a
    keyword stem but that the user did not search for; no category → judge by name."""
    if cats_re is not None:                       # explicit whitelist wins
        cat = (category or "").lower()
        if cat:
            return bool(cats_re.search(cat))
        return bool(name and cats_re.search(name.lower()))  # no category → judge by name
    if not terms:
        return True
    cat = (category or "").lower()
    if cat and block_re is not None and block_re.search(cat):
        return False
    hay = cat if cat else (name or "").lower()   # no category → judge by name
    for w in re.findall(r"[a-z]{3,}", hay):
        if w[:5] in terms:
            return True
    return False


# ── Worker thread ──────────────────────────────────────────
def worker_thread(worker_id, task_queue, job_state, email_executor, job_id):
    from database import mark_task_done
    try:
        driver_box = [setup_driver()]
    except Exception:
        return

    while True:
        if job_state["cancelled"]:
            break
        while job_state.get("paused") and not job_state.get("cancelled"):
            time.sleep(1)
        if job_state["cancelled"]:
            break
        try:
            query, city, state, task_key = task_queue.get(timeout=5)
        except Empty:
            break

        requeued = False
        t_start = time.time()
        try:
            # No proactive network probe in the hot path (keeps scraping fast).
            # We only check connectivity when a task actually fails, below.
            ok = scrape_query(driver_box, query, city, state, worker_id, job_state, email_executor)
            if ok:
                # Checkpoint: this task is complete → never re-scraped on resume.
                try:
                    mark_task_done(job_id, task_key)
                except Exception:
                    pass
            elif not job_state["cancelled"] and not _network_up():
                # Network dropped mid-task → wait for it to return, then requeue
                # so the task is retried (it was NOT checkpointed).
                if _wait_for_network(job_state) and not job_state["cancelled"]:
                    task_queue.put((query, city, state, task_key))
                    requeued = True
            else:
                # Non-network failure — checkpoint it so we don't loop forever.
                try:
                    mark_task_done(job_id, task_key)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if not requeued:
                with job_state["lock"]:
                    job_state["done_tasks"] += 1
            task_queue.task_done()
            # Adaptive throttle: when CPU is hot, pause proportional to how long
            # this task took (throttle=0.30 → ~30% slower). Lets the box cool
            # down; ramps back to full speed as CPU recovers.
            th = job_state.get("throttle", 0.0)
            if th > 0 and not job_state["cancelled"]:
                time.sleep((time.time() - t_start) * th)

    try:
        driver_box[0].quit()
    except Exception:
        pass


# ── Main job runner ────────────────────────────────────────
def run_scrape_job(job_id, jobs, country, state, cities, keywords=None, max_emails=5,
                   on_complete=None, relevant_only=False, categories=None):
    j = jobs[job_id]
    j["status"] = "running"

    kws = keywords if keywords else DEFAULT_KEYWORDS

    from database import update_job_status as _update_status
    from database import save_results_bulk as _save_results
    from database import get_done_task_keys, get_results

    # Resume support: skip (city|keyword) tasks already checkpointed as done.
    done_keys = get_done_task_keys(job_id)

    initial_results = {}
    initial_seen_websites = set()
    if done_keys:
        try:
            for r in get_results(job_id):
                rk = _dedup_key(r.get("name", ""), r.get("phone", ""), r.get("website", ""), r.get("address", ""))
                initial_results[rk] = r
                ws = r.get("website")
                if ws:
                    p = urlparse(ws if ws.startswith("http") else f"https://{ws}")
                    if p.netloc:
                        initial_seen_websites.add(f"{p.scheme}://{p.netloc}")
        except Exception:
            pass

    task_queue = Queue()
    total = 0
    for city in cities:
        for kw in kws:
            total += 1
            task_key = f"{city}|{kw}"
            if task_key in done_keys:
                continue  # already completed in a previous (interrupted) run
            # Use actual country name in query for non-USA countries
            query = f"{kw} {city} {state} {country}"
            task_queue.put((query, city, state, task_key))

    remaining = task_queue.qsize()
    initial_done = total - remaining
    j["total_tasks"] = total
    if initial_done and remaining:
        j["message"] = f"Resuming… {initial_done}/{total} already done"
    elif initial_done and not remaining:
        j["message"] = "Resuming… finishing up"
    else:
        j["message"] = f"Scraping {len(cities)} cities × {len(kws)} keywords..."

    _update_status(job_id, status="running", total_tasks=total,
                   done_tasks=initial_done, message=j["message"])

    job_state = {
        "results":       initial_results,
        "lock":          threading.Lock(),
        "seen_websites": initial_seen_websites,
        "cancelled":     False,
        "done_tasks":    initial_done,
        "max_emails":    max_emails,
        # Email-extraction progress: emails run in the background while scraping;
        # after scraping finishes we wait for these and show a "extracting" status.
        "emails_submitted": 0,
        "emails_done":      0,
        "phase":            "scraping",   # "scraping" → "emails" → done
        "network_down":     False,        # True while paused waiting for internet
        "throttle":         0.0,          # 0..CPU_THROTTLE_MAX — extra delay when CPU is hot
        "cpu":              0,            # last measured system CPU %
        # When "Only relevant categories" is on, keep results whose category/name
        # matches these keyword stems; empty set = keep everything (filter off).
        "relevant_terms":   _keyword_terms(kws) if relevant_only else set(),
        "relevant_block":   _block_pattern(kws) if relevant_only else None,
        # Explicit user category whitelist (optional). When set it overrides the
        # keyword-stem filter: keep only results whose category matches the list.
        "relevant_cats":    _category_pattern(categories) if (relevant_only and categories) else None,
    }
    base_scrape_msg = j["message"]        # restored when throttle eases back off
    j["results"] = job_state["results"]
    j["results_lock"] = job_state["lock"]  # expose lock so HTTP handlers can take safe snapshots
    j["_job_state"] = job_state            # expose so the cancel endpoint can flip "cancelled" instantly

    # Watchdog: if no task completes for this long, a worker/Chrome has hung —
    # stop the job instead of leaving it "running" forever.
    STUCK_TIMEOUT = int(_os.environ.get("JOB_STUCK_TIMEOUT", "300"))

    def progress_updater():
        tick = 0
        last_done = -1
        last_progress_ts = time.time()
        while j["status"] in ("running", "pending"):
            done = job_state["done_tasks"]
            j["done_tasks"] = done
            j["progress"] = int(done * 100 / total) if total else 100
            # Adaptive-throttle notice (scraping phase, network up).
            if job_state.get("phase") == "scraping" and not job_state.get("network_down"):
                if job_state.get("throttle", 0.0) > 0:
                    j["message"] = (f"⚙️ CPU {int(job_state.get('cpu', 0))}% high — "
                                    f"auto-slowed to keep the server stable")
                elif j.get("message") != base_scrape_msg:
                    j["message"] = base_scrape_msg   # eased back to full speed
            if done != last_done:
                last_done = done
                last_progress_ts = time.time()
            elif job_state.get("phase") == "emails":
                # Scraping is finished; we're intentionally waiting on background
                # email extraction. done_tasks won't change here — don't let the
                # no-progress watchdog mistake this for a hung worker.
                last_progress_ts = time.time()
            elif job_state.get("network_down"):
                # Paused waiting for the internet to come back — not a hung
                # worker. Hold the watchdog and surface a clear status.
                last_progress_ts = time.time()
                j["message"] = "Internet down — waiting to resume…"
            elif time.time() - last_progress_ts > STUCK_TIMEOUT:
                # No progress for too long → mark stalled and stop workers.
                j["status"] = "error"
                j["message"] = "Stalled — no progress (a worker hung). Stopped."
                job_state["cancelled"] = True
                try:
                    with job_state["lock"]:
                        snap = list(job_state["results"].values())
                    if snap:
                        _save_results(job_id, snap)
                    _update_status(job_id, status="error",
                                   progress=j["progress"], done_tasks=done,
                                   message=j["message"])
                except Exception:
                    pass
                break
            tick += 1
            if tick % 7 == 0:
                try:
                    _update_status(
                        job_id, status="running",
                        progress=j["progress"],
                        done_tasks=done,
                        total_tasks=total,
                    )
                    # Periodic flush so a crash/cancel never loses scraped data
                    with job_state["lock"]:
                        snapshot = list(job_state["results"].values())
                    if snapshot:
                        _save_results(job_id, snapshot)
                except Exception:
                    pass
            time.sleep(1.5)
            # Check cancellation after sleep so workers stop promptly
            if j.get("status") == "cancelled":
                job_state["cancelled"] = True
                break
        # Also propagate if loop exited due to while condition (status became cancelled)
        if j.get("status") == "cancelled":
            job_state["cancelled"] = True
    threading.Thread(target=progress_updater, daemon=True).start()

    def cpu_monitor():
        """Watch system CPU; ramp job_state['throttle'] up when CPU is hot
        (>CPU_HIGH) and ease it back down when CPU recovers — so workers slow
        themselves ~30% under load, then return to full speed automatically."""
        try:
            import psutil
        except Exception:
            return  # psutil not installed → throttling simply disabled
        while j["status"] in ("running", "pending"):
            try:
                cpu = psutil.cpu_percent(interval=CPU_CHECK_EVERY)
            except Exception:
                time.sleep(CPU_CHECK_EVERY)
                continue
            job_state["cpu"] = cpu
            cur = job_state.get("throttle", 0.0)
            if cpu > CPU_HIGH:
                cur = min(CPU_THROTTLE_MAX, cur + 0.10)   # ramp up quickly
            else:
                cur = max(0.0, cur - 0.05)                 # ease back gradually
            job_state["throttle"] = cur
    threading.Thread(target=cpu_monitor, daemon=True).start()

    try:
        num_workers = min(NUM_DRIVERS, max(1, remaining))
        email_executor = ThreadPoolExecutor(max_workers=EMAIL_WORKERS)
        try:
            threads = []
            for i in range(num_workers):
                t = threading.Thread(
                    target=worker_thread,
                    args=(i + 1, task_queue, job_state, email_executor, job_id),
                    daemon=True,
                )
                t.start()
                threads.append(t)
                time.sleep(0.3)
            # Wait for workers, but never block forever on a hung one: once the
            # job is cancelled/stalled, give a short grace then move on (the
            # abandoned daemon thread + its Chrome get cleaned on restart).
            while any(t.is_alive() for t in threads):
                time.sleep(2)
                if job_state["cancelled"] or j.get("status") in ("cancelled", "error"):
                    grace = time.time() + 30
                    for t in threads:
                        t.join(timeout=max(0.1, grace - time.time()))
                    break

            # ── Scraping done → wait for background email extraction to finish,
            #    showing a live "Extracting emails…" status. Emails are still
            #    pulled in parallel (no speed loss) — we just surface the wait
            #    instead of silently blocking on executor shutdown. ──
            if not job_state["cancelled"] and j.get("status") not in ("cancelled", "error"):
                job_state["phase"] = "emails"
                while not job_state["cancelled"]:
                    with job_state["lock"]:
                        sub = job_state["emails_submitted"]
                        dn  = job_state["emails_done"]
                    if dn >= sub:
                        break
                    j["message"] = f"Scraping done — extracting emails… {dn}/{sub} sites"
                    j["progress"] = 100
                    try:
                        _update_status(job_id, status="running", progress=100,
                                       done_tasks=total, message=j["message"])
                    except Exception:
                        pass
                    time.sleep(1.5)
        finally:
            # Drains any still-running email tasks (instant if the loop above
            # already finished them). cancel_futures drops queued-but-unstarted
            # email work so a cancelled job doesn't keep crawling.
            email_executor.shutdown(wait=True, cancel_futures=True)
    except Exception as e:
        j["status"] = "error"
        j["message"] = str(e)
        return

    if j["status"] != "cancelled":
        j["status"] = "done"
        j["progress"] = 100
        j["done_tasks"] = total
        j["message"] = f"Done! Found {len(job_state['results'])} places."
        if on_complete:
            try:
                on_complete(job_state["results"])
            except Exception:
                pass
        else:
            try:
                import json, os
                os.makedirs("output", exist_ok=True)
                results_list = list(job_state["results"].values())
                with open(f"output/{job_id}_results.json", "w", encoding="utf-8") as f:
                    json.dump(results_list, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
