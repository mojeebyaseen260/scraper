# ColdLeads — Cold Storage Lead Scraper (SaaS)

A web app that finds cold-storage (and related) businesses across US cities by
scraping Google Maps, crawls their websites for contact emails, and serves the
results through an authenticated dashboard with a super-admin panel.

- **Backend:** FastAPI + SQLite + Selenium (headless Chrome) + httpx
- **Frontend:** React 18 + Vite + React Router
- **Auth:** JWT (bcrypt password hashing, role-based access, token revocation)

> Note: scraping Google Maps may violate Google's Terms of Service. Use
> responsibly and at your own risk.

## Project layout

```
backend/      FastAPI app (main.py), scraper engine (scraper_api.py),
              DB layer (database.py), auth (auth.py), US city data (locations.py)
frontend/     React + Vite SPA
deploy/       VPS setup / update scripts
scraper.py    Standalone legacy CLI scraper (not part of the SaaS)
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Google Chrome installed (Selenium drives it headlessly)

## Local development

### 1. Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate   |   Linux/macOS: source venv/bin/activate
pip install -r ../requirements.txt

cp .env.example .env      # then edit values (see Configuration below)
python -m uvicorn main:app --reload --port 8000
```

On Windows you can also just run `start_backend.bat`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000 (proxies /api to :8000)
```

On Windows: `start_frontend.bat`.

## Configuration (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Secret for signing JWTs — **set a long random value in production** |
| `PRODUCTION` | `1` in production (enables prod scraper tuning + secret warnings) |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Seed admin account on first run |
| `AUTH_RATE_LIMIT` / `AUTH_RATE_WINDOW` | Login/register rate limit |

Each user runs one scrape job at a time; additional submissions are queued and
start automatically when the previous one finishes.

A default admin is created on first run if the DB is empty. **Change the
default password immediately.**

## Production build

```bash
cd frontend && npm run build      # outputs frontend/dist/
```

When `frontend/dist/` exists, the FastAPI backend serves it directly (single
origin), so only the backend needs to run in production. See `deploy/` for the
systemd + Chrome VPS setup.

## Testing

```bash
cd backend
pip install pytest
pytest -q
```

Tests run offline (no network/Chrome) and cover email extraction, validation,
the SSRF guard, URL cleaning, and JWT auth. CI runs them on every push
(`.github/workflows/ci.yml`).

## Output columns

`name`, `city`, `state`, `phone`, `address`, `email`, `website`, `rating`, `category`

Results are exportable as CSV, XLSX, or JSON from the dashboard.
