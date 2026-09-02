"""
FastAPI Backend — Cold Storage Scraper SaaS v4
JWT Auth + User dashboard + Super Admin panel
"""

import os
import sys
import re
import uuid
import json
import io
import glob
import time as _time
import threading
from collections import defaultdict
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from locations import LOCATIONS
from extra_locations import EXTRA_LOCATIONS
from scraper_api import run_scrape_job, KEYWORD_CATEGORIES

# Merge all locations: USA from locations.py, rest from extra_locations.py
ALL_LOCATIONS = {"USA": LOCATIONS.get("USA", {}), **EXTRA_LOCATIONS}
from database import (
    create_job, update_job_status, get_job,
    get_jobs_by_user, get_results, get_results_count,
    save_results_bulk, replace_results_bulk, get_all_jobs_admin, reset_stale_jobs, db_ping,
    create_user, get_user_by_email, get_user_by_id,
    get_all_users, get_user_stats, get_admin_stats,
    update_user_role, delete_user, delete_job_data,
    get_oldest_queued_job,
    get_smtp_settings, save_smtp_settings,
    log_outreach_email, get_outreach_history,
)
from auth import (
    hash_password, verify_password, create_token,
    get_current_user, require_admin,
)
from smtp_service import (
    B2B_EMAIL_TEMPLATES,
    render_lead_template,
    verify_smtp_credentials,
    send_single_email,
)

# ── Config from .env ──────────────────────────────────────
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001").split(",")
    if o.strip()
]
# Note: one running job per user is enforced via the queue (see start_scrape),
# so a separate concurrency limit is no longer needed.

# ── Simple in-memory rate limiter for auth endpoints ──────
_rate_lock = threading.Lock()
_rate_data: dict = defaultdict(lambda: {"count": 0, "window_start": 0.0})
AUTH_RATE_LIMIT      = int(os.environ.get("AUTH_RATE_LIMIT", "10"))   # max attempts
AUTH_RATE_WINDOW_SEC = int(os.environ.get("AUTH_RATE_WINDOW", "60"))  # per N seconds
_RATE_CLEANUP_EVERY  = 500   # cleanup stale entries every N calls

_rate_call_count = 0

def _get_client_ip(request: Request) -> str:
    """Get real client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

def _check_rate_limit(request: Request):
    global _rate_call_count
    ip = _get_client_ip(request)
    now = _time.time()
    with _rate_lock:
        # Periodically evict stale entries to prevent unbounded growth
        _rate_call_count += 1
        if _rate_call_count % _RATE_CLEANUP_EVERY == 0:
            stale = [k for k, v in _rate_data.items()
                     if now - v["window_start"] > AUTH_RATE_WINDOW_SEC * 2]
            for k in stale:
                del _rate_data[k]

        entry = _rate_data[ip]
        if now - entry["window_start"] > AUTH_RATE_WINDOW_SEC:
            entry["count"] = 0
            entry["window_start"] = now
        entry["count"] += 1
        if entry["count"] > AUTH_RATE_LIMIT:
            raise HTTPException(429, f"Too many attempts. Try again in {AUTH_RATE_WINDOW_SEC} seconds.")

app = FastAPI(title="Cold Storage Scraper API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

os.makedirs("output", exist_ok=True)

# In-memory state for active scraping jobs
active_jobs: dict = {}


@app.on_event("startup")
def on_startup():
    """Auto-resume any job that was running/pending when the server stopped
    (it continues from the last checkpoint, skipping completed tasks), then
    start any queued jobs. One active job per user."""
    resumed_users = set()
    try:
        from database import get_resumable_jobs
        for job in get_resumable_jobs():
            uid = job.get("user_id")
            if uid in resumed_users:
                continue  # one active job per user; others wait their turn
            _launch_job(
                job["job_id"], uid, job.get("country", "USA"),
                job.get("state", ""), job.get("cities", []),
                job.get("keywords"), job.get("max_emails", 5),
                relevant_only=bool(job.get("relevant_only", 0)),
                categories=job.get("categories"),
            )
            resumed_users.add(uid)
    except Exception:
        pass

    # Auto-start the oldest queued job for each waiting user (skip those whose
    # job we just resumed).
    queued_user_ids = []
    try:
        from database import _cursor
        with _cursor() as cur:
            cur.execute("SELECT DISTINCT user_id FROM jobs WHERE status='queued'")
            queued_user_ids = [r["user_id"] for r in cur.fetchall() if r["user_id"] is not None]
    except Exception:
        pass
    for uid in queued_user_ids:
        if uid in resumed_users:
            continue
        try:
            _start_next_queued_job(uid)
        except Exception:
            pass


@app.on_event("shutdown")
def on_shutdown():
    """On graceful shutdown, signal all in-flight jobs to stop so their worker
    threads quit the headless Chrome drivers (avoids orphaned browser processes).
    Also persist whatever each job scraped so far."""
    for jid, j in list(active_jobs.items()):
        if j.get("status") in ("running", "pending"):
            # Persist partial results before tearing down
            lock = j.get("results_lock")
            try:
                if lock:
                    with lock:
                        snap = list(j.get("results", {}).values())
                else:
                    snap = list(j.get("results", {}).values())
                if snap:
                    save_results_bulk(jid, snap)
            except Exception:
                pass
            j["status"] = "cancelled"   # progress_updater propagates this to workers
            j["cancelled"] = True
            try:
                update_job_status(jid, status="cancelled", message="Server shutting down")
            except Exception:
                pass
    # Give worker threads a moment to observe cancellation and close their drivers.
    _time.sleep(2.5)


@app.get("/api/health")
def health():
    db_ok = db_ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "down",
        "active_jobs": len(active_jobs),
    }


# ── Auth Models ───────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Auth Routes ───────────────────────────────────────────
@app.post("/api/auth/register")
def register(req: RegisterRequest, request: Request):
    _check_rate_limit(request)
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    email = req.email.strip().lower()
    if get_user_by_email(email):
        raise HTTPException(400, "Email already registered")
    user_id = create_user(email, hash_password(req.password))
    user = get_user_by_id(user_id)
    token = create_token(user_id, email, user["role"], user.get("token_version", 0))
    return {"token": token, "user": {"id": user_id, "email": email, "role": user["role"]}}


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    _check_rate_limit(request)
    email = req.email.strip().lower()
    user = get_user_by_email(email)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"], user.get("token_version", 0))
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": int(current_user["sub"]),
        "email": current_user["email"],
        "role": current_user["role"],
    }


# ── Keywords ──────────────────────────────────────────────
@app.get("/api/keyword-categories")
def get_keyword_categories():
    return KEYWORD_CATEGORIES


# ── Locations ─────────────────────────────────────────────
@app.get("/api/countries")
def get_countries():
    return sorted(ALL_LOCATIONS.keys())


@app.get("/api/states")
def get_states():
    return sorted(LOCATIONS.get("USA", {}).keys())


@app.get("/api/states/{country}")
def get_states_by_country(country: str):
    c = ALL_LOCATIONS.get(country)
    if not c:
        raise HTTPException(404, "Country not found")
    return sorted(c.keys())


@app.get("/api/cities/{state}")
def get_cities(state: str):
    usa = LOCATIONS.get("USA", {})
    if state not in usa:
        raise HTTPException(404, "State not found")
    return usa[state]


@app.get("/api/cities/{country}/{region}")
def get_cities_by_region(country: str, region: str):
    c = ALL_LOCATIONS.get(country)
    if not c:
        raise HTTPException(404, "Country not found")
    cities = c.get(region)
    if cities is None:
        raise HTTPException(404, "Region not found")
    return cities


# ── Scrape Models ─────────────────────────────────────────
class ScrapeRequest(BaseModel):
    country: str = "USA"
    state: str
    cities: list[str]
    keywords: Optional[list[str]] = None
    max_emails: int = 5
    relevant_only: bool = False
    categories: Optional[list[str]] = None


# ── Scrape Routes ──────────────────────────────────────────
@app.post("/api/scrape/start")
def start_scrape(
    req: ScrapeRequest,
    current_user: dict = Depends(get_current_user),
):
    cities = [c.strip() for c in req.cities if c.strip()]
    state  = req.state.strip()
    country = req.country.strip() or "USA"
    if not state:
        raise HTTPException(400, "State is required")
    if not cities:
        raise HTTPException(400, "At least one city is required")

    user_id = int(current_user["sub"])
    job_id = str(int(_time.time() * 1000))[-8:] + uuid.uuid4().hex[:4]
    created_at = datetime.now().isoformat()

    # One running job per user. If the user already has one active, queue this
    # one — it auto-starts when the running job finishes.
    with _queue_lock:
        has_active = _user_has_active_job(user_id)
        if has_active:
            create_job(
                job_id, user_id, state, cities, created_at,
                keywords=req.keywords, max_emails=req.max_emails,
                status="queued", message="Queued — will start when your current job finishes.",
                country=country, relevant_only=req.relevant_only, categories=req.categories,
            )
            return {"job_id": job_id, "status": "queued",
                    "message": "Queued — it will start automatically when your current job finishes."}

        create_job(
            job_id, user_id, state, cities, created_at,
            keywords=req.keywords, max_emails=req.max_emails, status="pending",
            country=country, relevant_only=req.relevant_only, categories=req.categories,
        )
        _launch_job(job_id, user_id, country, state, cities, req.keywords, req.max_emails,
                    relevant_only=req.relevant_only, categories=req.categories)

    return {"job_id": job_id, "status": "pending"}


# ── Per-user job queue (one running job at a time, auto-start next) ──
_queue_lock = threading.Lock()


def _user_has_active_job(user_id: int) -> bool:
    """True if the user currently has a running/pending job in memory."""
    return any(
        j.get("user_id") == user_id and j.get("status") in ("running", "pending")
        for j in active_jobs.values()
    )


def _launch_job(job_id, user_id, country, state, cities, keywords, max_emails, relevant_only=False, categories=None):
    """Register the job in memory and run it in a dedicated daemon thread."""
    active_jobs[job_id] = {
        "status":      "pending",
        "progress":    0,
        "total_tasks": 0,
        "done_tasks":  0,
        "results":     {},
        "message":     "Starting...",
        "user_id":     user_id,
        "country":     country,
        "state":       state,
        "cities":      cities,
    }
    threading.Thread(
        target=_run_job,
        kwargs=dict(
            job_id=job_id, user_id=user_id, country=country, state=state,
            cities=cities, keywords=keywords, max_emails=max_emails,
            relevant_only=relevant_only, categories=categories,
        ),
        daemon=True,
        name=f"scrape-{job_id}",
    ).start()


def _start_next_queued_job(user_id: int):
    """After a job ends, auto-start the user's oldest queued job (if any)."""
    with _queue_lock:
        if _user_has_active_job(user_id):
            return
        nxt = get_oldest_queued_job(user_id)
        if not nxt:
            return
        _launch_job(
            nxt["job_id"], user_id,
            nxt.get("country", "USA"),
            nxt.get("state", ""),
            nxt.get("cities", []), nxt.get("keywords"), nxt.get("max_emails", 5),
            relevant_only=bool(nxt.get("relevant_only", 0)),
            categories=nxt.get("categories"),
        )


def _dedupe_rows(rows):
    """Strict de-dup for saved results and exports: the list must never repeat a
    phone number, a business name, or an email. Keep the first occurrence; drop a
    later row that reuses a name or phone, and strip any email already seen."""
    seen_name, seen_phone, seen_email, out = set(), set(), set(), []
    for r in rows:
        name = (r.get("name") or "").strip().lower()
        ph = re.sub(r"\D", "", r.get("phone") or "")
        if len(ph) == 11 and ph.startswith("1"):
            ph = ph[1:]
        if (name and name in seen_name) or (ph and ph in seen_phone):
            continue
        if name:
            seen_name.add(name)
        if ph:
            seen_phone.add(ph)
        kept = []
        for e in (r.get("email") or "").split(","):
            e = e.strip()
            el = e.lower()
            if not e or el in seen_email:
                continue
            seen_email.add(el)
            kept.append(e)
        r = dict(r)
        r["email"] = ", ".join(kept)
        out.append(r)
    return out


def _run_job(job_id, user_id, country, state, cities, keywords, max_emails, relevant_only=False, categories=None):
    j = active_jobs[job_id]

    def on_complete(results_dict):
        results_list = _dedupe_rows(list(results_dict.values()))
        replace_results_bulk(job_id, results_list)
        total, with_email = get_results_count(job_id)
        update_job_status(
            job_id,
            status="done",
            progress=100,
            done_tasks=j.get("total_tasks", 0),
            message=f"Done! Found {total} places, {with_email} with email.",
        )

    run_scrape_job(
        job_id=job_id,
        jobs=active_jobs,
        country=country,
        state=state,
        cities=cities,
        keywords=keywords,
        max_emails=max_emails,
        on_complete=on_complete,
        relevant_only=relevant_only,
        categories=categories,
    )

    # Evict old completed jobs from memory (keep at most 20, always keep latest 5 done)
    if len(active_jobs) > 20:
        done_jobs = [
            jid for jid, jdata in active_jobs.items()
            if jdata.get("status") in ("done", "cancelled", "error") and jid != job_id
        ]
        for jid in done_jobs[:-5]:
            active_jobs.pop(jid, None)

    final_status = j.get("status", "done")
    if final_status != "done":
        update_job_status(
            job_id,
            status=final_status,
            progress=j.get("progress", 0),
            done_tasks=j.get("done_tasks", 0),
            message=j.get("message", ""),
        )

    # This job is finished — kick off the user's next queued job, if any.
    try:
        _start_next_queued_job(user_id)
    except Exception:
        pass


def _check_job_access(job_id: str, user_id: int, is_admin: bool):
    """Raise 403/404 if the user doesn't own this job."""
    if job_id in active_jobs:
        if not is_admin and active_jobs[job_id].get("user_id") != user_id:
            raise HTTPException(403, "Not your job")
        return active_jobs[job_id]
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not is_admin and job["user_id"] != user_id:
        raise HTTPException(403, "Not your job")
    return job


@app.get("/api/scrape/status/{job_id}")
def scrape_status(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"

    if job_id in active_jobs:
        _check_job_access(job_id, user_id, is_admin)
        j = active_jobs[job_id]
        # take a thread-safe snapshot before counting
        lock = j.get("results_lock")
        if lock:
            with lock:
                results_snapshot = list(j.get("results", {}).values())
        else:
            results_snapshot = list(j.get("results", {}).values())
        st = j.get("_job_state") or {}
        em_sub  = st.get("emails_submitted", 0)
        em_done = st.get("emails_done", 0)
        if em_sub:
            email_progress = min(100, int(em_done * 100 / em_sub))
        else:
            email_progress = 100 if j["status"] == "done" else 0
        # Count from the DB too: a resumed job's in-memory dict starts empty, so
        # memory alone would show 0 after a restart even though the data is safe.
        db_total, db_email = get_results_count(job_id)
        return {
            "job_id":        job_id,
            "status":        j["status"],
            "progress":      j["progress"],
            "total_tasks":   j["total_tasks"],
            "done_tasks":    j["done_tasks"],
            "results_count": max(len(results_snapshot), db_total),
            "email_count":   max(sum(1 for r in results_snapshot if r.get("email")), db_email),
            "emails_submitted": em_sub,
            "emails_done":      em_done,
            "email_progress":   email_progress,
            "message":       j.get("message", ""),
        }

    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not is_admin and job["user_id"] != user_id:
        raise HTTPException(403, "Not your job")

    total, with_email = get_results_count(job_id)
    return {
        "job_id":        job_id,
        "status":        job["status"],
        "progress":      job["progress"],
        "total_tasks":   job["total_tasks"],
        "done_tasks":    job["done_tasks"],
        "results_count": total,
        "email_count":   with_email,
        "emails_submitted": 0,
        "emails_done":      0,
        "email_progress":   100 if job["status"] in ("done", "cancelled") else 0,
        "message":       job["message"],
    }


@app.get("/api/scrape/results/{job_id}")
def scrape_results(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    db_results = get_results(job_id) or []
    if job_id in active_jobs:
        live = active_jobs[job_id]
        lock = live.get("results_lock")
        if lock:
            with lock:
                live_results = list(live.get("results", {}).values())
        else:
            live_results = list(live.get("results", {}).values())
        results = _dedupe_rows(live_results + db_results)
        return {"results": results, "total": len(results)}

    results = _dedupe_rows(db_results)
    return {"results": results, "total": len(results)}


@app.post("/api/scrape/pause/{job_id}")
def pause_scrape(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    if job_id in active_jobs:
        live = active_jobs[job_id]
        live["status"] = "paused"
        live["message"] = "Paused by user"
        st = live.get("_job_state")
        if st is not None:
            st["paused"] = True
        update_job_status(job_id, status="paused", message="Paused by user")
        return {"message": "Job paused"}
    return {"message": "Job not active"}


@app.post("/api/scrape/resume/{job_id}")
def resume_scrape(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    if job_id in active_jobs:
        live = active_jobs[job_id]
        live["status"] = "running"
        live["message"] = "Scraping in progress..."
        st = live.get("_job_state")
        if st is not None:
            st["paused"] = False
        update_job_status(job_id, status="running", message="Scraping in progress...")
        return {"message": "Job resumed"}
    return {"message": "Job not active"}


@app.post("/api/scrape/cancel/{job_id}")
def cancel_scrape(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    if job_id in active_jobs:
        live = active_jobs[job_id]
        # Signal the running workers to stop *first* so scraping/scrolling halts
        # promptly, then snapshot whatever was scraped so far.
        live["status"] = "cancelled"
        st = live.get("_job_state")
        if st is not None:
            st["cancelled"] = True
        # Save whatever was scraped so far before cancelling, so the user still sees it
        lock = live.get("results_lock")
        if lock:
            with lock:
                snapshot = list(live.get("results", {}).values())
        else:
            snapshot = list(live.get("results", {}).values())
        snapshot = _dedupe_rows(snapshot)
        if snapshot:
            try:
                replace_results_bulk(job_id, snapshot)
            except Exception:
                pass
    update_job_status(job_id, status="cancelled")
    return {"message": "Cancelled"}


@app.delete("/api/scrape/delete/{job_id}")
def delete_job_route(job_id: str, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    if job_id in active_jobs:
        live = active_jobs[job_id]
        live["status"] = "cancelled"
        live["cancelled"] = True
        st = live.get("_job_state")
        if st is not None:
            st["cancelled"] = True
        active_jobs.pop(job_id, None)

    # BUG FIX: always verify ownership before deleting from DB
    job = get_job(job_id)
    if job:
        if not is_admin and job["user_id"] != user_id:
            raise HTTPException(403, "Not your job")
        delete_job_data(job_id)

    for f in glob.glob(f"output/{job_id}*"):
        try:
            os.remove(f)
        except Exception:
            pass
    return {"message": "Deleted"}


@app.get("/api/jobs")
def list_jobs(current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    db_jobs = get_jobs_by_user(user_id)

    result = []
    for job in db_jobs:
        jid = job["job_id"]
        if jid in active_jobs:
            live = active_jobs[jid]
            lock = live.get("results_lock")
            if lock:
                with lock:
                    results_snap = list(live.get("results", {}).values())
            else:
                results_snap = list(live.get("results", {}).values())
            # A resumed job starts with an empty in-memory dict, so counting only
            # memory would wrongly show 0 after a restart. The DB holds everything
            # flushed so far (incl. previous runs) — take whichever is higher.
            db_total, db_email = get_results_count(jid)
            total      = max(len(results_snap), db_total)
            with_email = max(sum(1 for r in results_snap if r.get("email")), db_email)
            status     = live.get("status", job["status"])
            progress   = live.get("progress", job["progress"])
            message    = live.get("message", job["message"])
            done_tasks  = live.get("done_tasks", 0)
            total_tasks = live.get("total_tasks", 0)
            st = live.get("_job_state") or {}
            em_sub  = st.get("emails_submitted", 0)
            em_done = st.get("emails_done", 0)
            email_progress = (min(100, int(em_done * 100 / em_sub)) if em_sub
                              else (100 if status == "done" else 0))
        else:
            total, with_email = get_results_count(jid)
            status     = job["status"]
            progress   = job["progress"]
            message    = job["message"]
            done_tasks  = job.get("done_tasks", 0)
            total_tasks = job.get("total_tasks", 0)
            em_sub = em_done = 0
            email_progress = 100 if status in ("done", "cancelled") else 0

        result.append({
            "job_id":        jid,
            "status":        status,
            "progress":      progress,
            "done_tasks":    done_tasks,
            "total_tasks":   total_tasks,
            "results_count": total,
            "email_count":   with_email,
            "emails_submitted": em_sub,
            "emails_done":      em_done,
            "email_progress":   email_progress,
            "state":         job["state"],
            "cities_count":  len(job["cities"]),
            "message":       message,
            "created_at":    job["created_at"],
        })

    return result


# ── Download ──────────────────────────────────────────────
@app.get("/api/download/{job_id}/{fmt}")
def download_results(
    job_id: str,
    fmt: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = int(current_user["sub"])
    is_admin = current_user.get("role") == "admin"
    _check_job_access(job_id, user_id, is_admin)

    db_results = get_results(job_id) or []
    live_results = []
    if job_id in active_jobs:
        live = active_jobs[job_id]
        lock = live.get("results_lock")
        if lock:
            with lock:
                live_results = list(live.get("results", {}).values())
        else:
            live_results = list(live.get("results", {}).values())

    results = _dedupe_rows(live_results + db_results)

    if not results:
        raise HTTPException(400, "No results yet — job may still be running")

    df = pd.DataFrame(results)
    # Company → Decision Makers → Category → Number → Email → Website, then everything else.
    col_order = ["name", "decision_makers", "category", "phone", "email", "website",
                 "social", "city", "state", "address", "rating"]
    df = df.reindex(columns=[c for c in col_order if c in df.columns])

    # Build a human-friendly filename with the country + region/state, e.g.
    # "USA_California_leads_8513146821db.csv".
    meta = get_job(job_id) or {}
    country = (meta.get("country") or "USA").strip()
    state   = (meta.get("state") or "").strip()
    base = "_".join(p for p in [country, state, "leads", job_id] if p)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") or f"leads_{job_id}"

    if fmt == "csv":
        path = f"output/{job_id}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return FileResponse(path, filename=f"{base}.csv", media_type="text/csv")

    elif fmt == "xlsx":
        path = f"output/{job_id}.xlsx"
        df.to_excel(path, index=False)
        return FileResponse(
            path,
            filename=f"{base}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    elif fmt == "json":
        content = json.dumps(results, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={base}.json"},
        )

    raise HTTPException(400, "Format must be csv, xlsx, or json")


# ── Admin Routes ───────────────────────────────────────────
@app.get("/api/admin/stats")
def admin_stats(current_user: dict = Depends(require_admin)):
    stats = get_admin_stats()
    stats["active_jobs"] = sum(
        1 for j in active_jobs.values() if j.get("status") == "running"
    )
    return stats


@app.get("/api/admin/users")
def admin_list_users(current_user: dict = Depends(require_admin)):
    users = get_all_users()
    for u in users:
        u.update(get_user_stats(u["id"]))
    return users


@app.get("/api/admin/users/{uid}/jobs")
def admin_user_jobs(uid: int, current_user: dict = Depends(require_admin)):
    jobs = get_jobs_by_user(uid)
    result = []
    for job in jobs:
        jid = job["job_id"]
        if jid in active_jobs:
            live = active_jobs[jid]
            lock = live.get("results_lock")
            if lock:
                with lock:
                    snap = list(live.get("results", {}).values())
            else:
                snap = list(live.get("results", {}).values())
            total      = len(snap)
            with_email = sum(1 for r in snap if r.get("email"))
            job["status"]   = live.get("status", job["status"])
            job["progress"] = live.get("progress", job["progress"])
        else:
            total, with_email = get_results_count(jid)
        result.append({
            **job,
            "results_count": total,
            "email_count":   with_email,
            "cities_count":  len(job["cities"]),
        })
    return result


@app.get("/api/admin/jobs")
def admin_all_jobs(current_user: dict = Depends(require_admin)):
    jobs = get_all_jobs_admin()
    result = []
    for job in jobs:
        jid = job["job_id"]
        if jid in active_jobs:
            live = active_jobs[jid]
            lock = live.get("results_lock")
            if lock:
                with lock:
                    snap = list(live.get("results", {}).values())
            else:
                snap = list(live.get("results", {}).values())
            total      = len(snap)
            with_email = sum(1 for r in snap if r.get("email"))
            job["status"]   = live.get("status", job["status"])
            job["progress"] = live.get("progress", job["progress"])
        else:
            total, with_email = get_results_count(jid)
        result.append({
            **job,
            "results_count": total,
            "email_count":   with_email,
            "cities_count":  len(job["cities"]),
        })
    return result


@app.put("/api/admin/users/{uid}/role")
def admin_change_role(uid: int, body: dict, current_user: dict = Depends(require_admin)):
    role = body.get("role")
    if role not in ("user", "admin"):
        raise HTTPException(400, "Role must be 'user' or 'admin'")
    if uid == int(current_user["sub"]):
        raise HTTPException(400, "Cannot change your own role")
    update_user_role(uid, role)
    return {"message": "Role updated"}


@app.delete("/api/admin/users/{uid}")
def admin_delete_user(uid: int, current_user: dict = Depends(require_admin)):
    if uid == int(current_user["sub"]):
        raise HTTPException(400, "Cannot delete yourself")
    delete_user(uid)
    return {"message": "User deleted"}


# ── SMTP & Cold Outreach Endpoints ─────────────────────────
class SMTPSettingsRequest(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    from_name: str = ""
    use_tls: bool = True
    daily_limit: int = 500
    delay_sec: float = 3.0


class SMTPTestRequest(BaseModel):
    to_email: str
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = ""
    smtp_pass: Optional[str] = ""
    use_tls: Optional[bool] = True


class OutreachSendRequest(BaseModel):
    leads: list[dict]
    subject: str
    body: str
    job_id: Optional[str] = ""
    delay_sec: Optional[float] = 3.0


@app.get("/api/smtp/settings")
def get_smtp_route(current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    settings = get_smtp_settings(user_id)
    if not settings:
        return {
            "configured": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "from_name": "",
            "use_tls": True,
            "daily_limit": 500,
            "delay_sec": 3.0,
        }
    return {
        "configured": bool(settings.get("smtp_user") and settings.get("smtp_pass")),
        "smtp_host": settings.get("smtp_host", "smtp.gmail.com"),
        "smtp_port": settings.get("smtp_port", 587),
        "smtp_user": settings.get("smtp_user", ""),
        "from_name": settings.get("from_name", ""),
        "use_tls": bool(settings.get("use_tls", 1)),
        "daily_limit": settings.get("daily_limit", 500),
        "delay_sec": settings.get("delay_sec", 3.0),
        "has_pass": bool(settings.get("smtp_pass")),
    }


@app.post("/api/smtp/settings")
def save_smtp_route(req: SMTPSettingsRequest, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    save_smtp_settings(
        user_id=user_id,
        smtp_host=req.smtp_host.strip(),
        smtp_port=req.smtp_port,
        smtp_user=req.smtp_user.strip(),
        smtp_pass=req.smtp_pass.strip(),
        from_name=req.from_name.strip(),
        use_tls=1 if req.use_tls else 0,
        daily_limit=req.daily_limit,
        delay_sec=req.delay_sec,
    )
    return {"message": "SMTP Settings saved successfully"}


@app.post("/api/smtp/test")
def test_smtp_route(req: SMTPTestRequest, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    settings = get_smtp_settings(user_id) or {}
    
    host = req.smtp_host or settings.get("smtp_host", "smtp.gmail.com")
    port = req.smtp_port or settings.get("smtp_port", 587)
    user = req.smtp_user or settings.get("smtp_user", "")
    pwd = req.smtp_pass or settings.get("smtp_pass", "")
    use_tls = req.use_tls if req.use_tls is not None else bool(settings.get("use_tls", 1))

    if not user or not pwd:
        raise HTTPException(400, "SMTP username/email and App Password are required")

    ok, msg = verify_smtp_credentials(host, port, user, pwd, use_tls=use_tls)
    if not ok:
        raise HTTPException(400, f"SMTP Test Failed: {msg}")

    # Send a real test email
    sent_ok, send_msg = send_single_email(
        smtp_host=host,
        smtp_port=port,
        smtp_user=user,
        smtp_pass=pwd,
        from_name="ColdLeads Verification",
        to_email=req.to_email.strip(),
        subject="ColdLeads — SMTP Verification Successful! ✅",
        body_text="Congratulations!\n\nYour SMTP email integration with ColdLeads is working perfectly.\nYou are ready to send automated cold outreach campaigns to verified decision makers.",
        use_tls=use_tls,
    )
    if not sent_ok:
        raise HTTPException(400, f"Verification failed to send email: {send_msg}")

    return {"message": f"Test email sent successfully to {req.to_email}!"}


@app.get("/api/outreach/templates")
def get_outreach_templates():
    return B2B_EMAIL_TEMPLATES


@app.post("/api/outreach/send")
def send_outreach_campaign(req: OutreachSendRequest, current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    settings = get_smtp_settings(user_id)
    if not settings or not settings.get("smtp_user") or not settings.get("smtp_pass"):
        raise HTTPException(400, "Please configure and save your SMTP email settings first")

    if not req.leads:
        raise HTTPException(400, "No leads selected for outreach")

    host = settings["smtp_host"]
    port = settings["smtp_port"]
    user = settings["smtp_user"]
    pwd = settings["smtp_pass"]
    from_name = settings.get("from_name", "")
    use_tls = bool(settings.get("use_tls", 1))
    delay = max(1.0, req.delay_sec or settings.get("delay_sec", 3.0))

    sent_count = 0
    fail_count = 0
    errors = []

    for lead in req.leads:
        raw_email = lead.get("email") or ""
        # Get first valid email if multiple are present
        to_email = raw_email.split(",")[0].strip()
        if not to_email or "@" not in to_email:
            continue

        # Render personalized subject & body
        subject = render_lead_template(req.subject, lead, from_name=from_name)
        body = render_lead_template(req.body, lead, from_name=from_name)

        ok, err = send_single_email(
            smtp_host=host,
            smtp_port=port,
            smtp_user=user,
            smtp_pass=pwd,
            from_name=from_name,
            to_email=to_email,
            subject=subject,
            body_text=body,
            use_tls=use_tls,
        )

        status = "sent" if ok else "failed"
        if ok:
            sent_count += 1
        else:
            fail_count += 1
            errors.append(f"{to_email}: {err}")

        log_outreach_email(
            user_id=user_id,
            job_id=req.job_id or "",
            recipient_email=to_email,
            company_name=lead.get("name", ""),
            decision_maker=lead.get("decision_makers", ""),
            subject=subject,
            body=body,
            status=status,
            error_message="" if ok else err,
        )

        # Respect throttle delay between emails
        _time.sleep(delay)

    return {
        "total": len(req.leads),
        "sent": sent_count,
        "failed": fail_count,
        "errors": errors[:5],
        "message": f"Campaign completed: {sent_count} sent successfully, {fail_count} failed.",
    }


@app.get("/api/outreach/history")
def get_outreach_history_route(current_user: dict = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    logs = get_outreach_history(user_id, limit=200)
    return logs


# ── Serve React frontend (production) ─────────────────────
if getattr(sys, "frozen", False):
    _BUNDLE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    _FRONTEND_DIST = os.path.join(_BUNDLE, "frontend", "dist")
    if not os.path.isdir(_FRONTEND_DIST):
        _FRONTEND_DIST = os.path.join(os.path.dirname(sys.executable), "_internal", "frontend", "dist")
else:
    _FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(_FRONTEND_DIST):
    # Serve static assets (js, css, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    # Catch-all: serve index.html for all non-API routes (React Router fix)
    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    def serve_react(full_path: str):
        # Unknown API paths should 404 as JSON, not silently return the SPA shell.
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        _index = os.path.join(_FRONTEND_DIST, "index.html")
        with open(_index, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
