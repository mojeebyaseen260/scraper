"""
SQLite database layer — users + jobs + results.
"""

import os
import json
import sqlite3
import threading
from typing import Optional
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "coldleads.db"))

# Thread-local connections — each thread gets its own SQLite connection.
# WAL mode allows concurrent reads across threads; writes are serialized via _write_lock.
_local = threading.local()
_write_lock = threading.Lock()
_init_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        c = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-32000")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        _local.conn = c
    return _local.conn


@contextmanager
def _cursor(commit: bool = False):
    conn = _get_conn()
    if commit:
        with _write_lock:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
    else:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


def db_ping() -> bool:
    try:
        with _cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _safe_json_loads(val, default=None):
    if not val:
        return default
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


def init_db():
    with _init_lock:
        with _cursor(commit=True) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT UNIQUE NOT NULL,
                    password      TEXT NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'user',
                    token_version INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id      TEXT PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id),
                    session_id  TEXT DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'pending',
                    progress    INTEGER DEFAULT 0,
                    total_tasks INTEGER DEFAULT 0,
                    done_tasks  INTEGER DEFAULT 0,
                    state       TEXT DEFAULT '',
                    cities      TEXT DEFAULT '[]',
                    keywords    TEXT DEFAULT '',
                    max_emails  INTEGER DEFAULT 5,
                    message     TEXT DEFAULT '',
                    country     TEXT DEFAULT 'USA',
                    created_at  TEXT NOT NULL
                )
            """)
            # Checkpoint of finished (city|keyword) tasks per job, so an
            # interrupted job can resume without re-scraping completed work.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS completed_tasks (
                    job_id   TEXT NOT NULL,
                    task_key TEXT NOT NULL,
                    PRIMARY KEY (job_id, task_key)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id   TEXT NOT NULL,
                    name     TEXT,
                    city     TEXT,
                    state    TEXT,
                    phone    TEXT,
                    address  TEXT,
                    rating   TEXT,
                    category TEXT,
                    email    TEXT DEFAULT '',
                    social   TEXT DEFAULT '',
                    website  TEXT,
                    decision_makers TEXT DEFAULT '',
                    UNIQUE(job_id, name, city)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS smtp_settings (
                    user_id      INTEGER PRIMARY KEY REFERENCES users(id),
                    smtp_host    TEXT DEFAULT 'smtp.gmail.com',
                    smtp_port    INTEGER DEFAULT 587,
                    smtp_user    TEXT DEFAULT '',
                    smtp_pass    TEXT DEFAULT '',
                    from_name    TEXT DEFAULT '',
                    use_tls      INTEGER DEFAULT 1,
                    daily_limit  INTEGER DEFAULT 500,
                    delay_sec    REAL DEFAULT 3.0,
                    updated_at   TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS outreach_logs (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id          INTEGER REFERENCES users(id),
                    job_id           TEXT DEFAULT '',
                    recipient_email  TEXT NOT NULL,
                    company_name     TEXT DEFAULT '',
                    decision_maker   TEXT DEFAULT '',
                    subject          TEXT DEFAULT '',
                    body             TEXT DEFAULT '',
                    status           TEXT NOT NULL,
                    error_message    TEXT DEFAULT '',
                    sent_at          TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_results_job ON results(job_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_completed_job ON completed_tasks(job_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_outreach_user ON outreach_logs(user_id)")
        # Migrate older databases that predate newer columns.
        _migrate_add_column("jobs", "country", "TEXT DEFAULT 'USA'")
        _migrate_add_column("jobs", "relevant_only", "INTEGER DEFAULT 0")
        _migrate_add_column("jobs", "categories", "TEXT DEFAULT ''")
        _migrate_add_column("results", "social", "TEXT DEFAULT ''")
        _migrate_add_column("results", "decision_makers", "TEXT DEFAULT ''")
    _seed_admin()


def _migrate_add_column(table: str, col: str, decl: str):
    """Add a column to an existing table if it doesn't already have it."""
    with _cursor() as cur:
        cols = {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        with _cursor(commit=True) as cur:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


_DEFAULT_ADMIN_PASSWORD = "Admin@123"


def _seed_admin():
    import sys
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users")
        if cur.fetchone()["n"]:
            return
    from auth import hash_password
    email    = os.environ.get("ADMIN_EMAIL",    "admin@coldleads.com")
    password = os.environ.get("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)
    with _cursor(commit=True) as cur:
        cur.execute(
            "INSERT OR IGNORE INTO users (email, password, role, created_at) VALUES (?, ?, ?, ?)",
            (email, hash_password(password), "admin", datetime.now().isoformat()),
        )


def reset_stale_jobs():
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE jobs SET status='error', message='Server was restarted' "
            "WHERE status IN ('running', 'pending')"
        )


# ── Users ──────────────────────────────────────────────────
def create_user(email: str, password_hash: str, role: str = "user") -> int:
    with _cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO users (email, password, role, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, role, datetime.now().isoformat()),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        return _row_to_dict(cur.fetchone())


def get_user_by_id(user_id: int) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_dict(cur.fetchone())


def get_all_users() -> list:
    with _cursor() as cur:
        cur.execute("SELECT id, email, role, created_at FROM users ORDER BY id")
        return [_row_to_dict(r) for r in cur.fetchall()]


def update_user_role(user_id: int, role: str):
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE users SET role = ?, token_version = token_version + 1 WHERE id = ?",
            (role, user_id),
        )


def bump_token_version(user_id: int):
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
            (user_id,),
        )


def delete_user(user_id: int):
    with _cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM results WHERE job_id IN (SELECT job_id FROM jobs WHERE user_id = ?)",
            (user_id,),
        )
        cur.execute(
            "DELETE FROM completed_tasks WHERE job_id IN (SELECT job_id FROM jobs WHERE user_id = ?)",
            (user_id,),
        )
        cur.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))


def get_user_stats(user_id: int) -> dict:
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM jobs WHERE user_id = ?", (user_id,))
        job_count = cur.fetchone()["n"]
        cur.execute(
            "SELECT COUNT(*) AS n FROM results r JOIN jobs j ON r.job_id = j.job_id WHERE j.user_id = ?",
            (user_id,),
        )
        result_count = cur.fetchone()["n"]
        cur.execute(
            "SELECT COUNT(*) AS n FROM results r JOIN jobs j ON r.job_id = j.job_id "
            "WHERE j.user_id = ? AND r.email != ''",
            (user_id,),
        )
        email_count = cur.fetchone()["n"]
    return {"job_count": job_count, "result_count": result_count, "email_count": email_count}


# ── Jobs ───────────────────────────────────────────────────
def create_job(job_id: str, user_id: int, state: str, cities: list, created_at: str,
               keywords: list = None, max_emails: int = 5, status: str = "pending",
               message: str = "", country: str = "USA", relevant_only: bool = False,
               categories: list = None):
    with _cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO jobs
               (job_id, user_id, session_id, status, state, cities, keywords, max_emails, message, country, relevant_only, categories, created_at)
               VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, user_id, status, state, json.dumps(cities),
             json.dumps(keywords) if keywords else "", int(max_emails), message,
             country or "USA", 1 if relevant_only else 0,
             json.dumps(categories) if categories else "", created_at),
        )


# ── Resume / checkpoint ────────────────────────────────────
def mark_task_done(job_id: str, task_key: str):
    with _cursor(commit=True) as cur:
        cur.execute(
            "INSERT OR IGNORE INTO completed_tasks (job_id, task_key) VALUES (?, ?)",
            (job_id, task_key),
        )


def get_done_task_keys(job_id: str) -> set:
    with _cursor() as cur:
        cur.execute("SELECT task_key FROM completed_tasks WHERE job_id = ?", (job_id,))
        return {r["task_key"] for r in cur.fetchall()}


def clear_completed_tasks(job_id: str):
    with _cursor(commit=True) as cur:
        cur.execute("DELETE FROM completed_tasks WHERE job_id = ?", (job_id,))


def get_resumable_jobs() -> list:
    """Jobs that were running/pending when the server stopped — to auto-resume."""
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM jobs WHERE status IN ('running', 'pending') ORDER BY created_at"
        )
        rows = cur.fetchall()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        d["cities"] = _safe_json_loads(d.get("cities"), [])
        d["keywords"] = _safe_json_loads(d.get("keywords"), None)
        d["categories"] = _safe_json_loads(d.get("categories"), None)
        d["country"] = d.get("country") or "USA"
        out.append(d)
    return out


def get_oldest_queued_job(user_id: int) -> dict | None:
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND status = 'queued' ORDER BY created_at LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["cities"] = _safe_json_loads(d.get("cities"), [])
    d["keywords"] = _safe_json_loads(d.get("keywords"), None)
    d["categories"] = _safe_json_loads(d.get("categories"), None)
    return d


def update_job_status(job_id: str, status: str, progress: int = None,
                      total_tasks: int = None, done_tasks: int = None, message: str = None):
    fields, vals = ["status = ?"], [status]
    if progress    is not None: fields.append("progress = ?");    vals.append(progress)
    if total_tasks is not None: fields.append("total_tasks = ?"); vals.append(total_tasks)
    if done_tasks  is not None: fields.append("done_tasks = ?");  vals.append(done_tasks)
    if message     is not None: fields.append("message = ?");     vals.append(message)
    vals.append(job_id)
    with _cursor(commit=True) as cur:
        cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", vals)


def get_job(job_id: str) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["cities"] = _safe_json_loads(d.get("cities"), [])
    return d


def get_jobs_by_user(user_id: int) -> list:
    with _cursor() as cur:
        cur.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = _row_to_dict(row)
        d["cities"] = _safe_json_loads(d.get("cities"), [])
        result.append(d)
    return result


def get_all_jobs_admin() -> list:
    with _cursor() as cur:
        cur.execute(
            """SELECT j.*, u.email AS user_email
               FROM jobs j LEFT JOIN users u ON j.user_id = u.id
               ORDER BY j.created_at DESC"""
        )
        rows = cur.fetchall()
    result = []
    for row in rows:
        d = _row_to_dict(row)
        d["cities"] = _safe_json_loads(d.get("cities"), [])
        result.append(d)
    return result


def delete_job_data(job_id: str):
    with _cursor(commit=True) as cur:
        cur.execute("DELETE FROM results WHERE job_id = ?", (job_id,))
        cur.execute("DELETE FROM completed_tasks WHERE job_id = ?", (job_id,))
        cur.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))


# ── Results ────────────────────────────────────────────────
def save_results_bulk(job_id: str, results: list):
    if not results:
        return
    rows = [
        (
            job_id,
            r.get("name", ""), r.get("city", ""), r.get("state", ""),
            r.get("phone", ""), r.get("address", ""), r.get("rating", ""),
            r.get("category", ""), r.get("email", ""), r.get("social", ""),
            r.get("website", ""), r.get("decision_makers", ""),
        )
        for r in results
    ]
    # Chunk into batches of 500 to keep each transaction fast
    chunk = 500
    for i in range(0, len(rows), chunk):
        with _cursor(commit=True) as cur:
            cur.executemany(
                """INSERT INTO results
                   (job_id, name, city, state, phone, address, rating, category, email, social, website, decision_makers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(job_id, name, city) DO UPDATE SET
                       email   = CASE WHEN excluded.email != '' THEN excluded.email ELSE results.email END,
                       social  = CASE WHEN excluded.social != '' THEN excluded.social ELSE results.social END,
                       decision_makers = CASE WHEN excluded.decision_makers != '' THEN excluded.decision_makers ELSE results.decision_makers END,
                       phone   = excluded.phone,
                       address = excluded.address,
                       website = excluded.website""",
                rows[i:i+chunk],
            )


def replace_results_bulk(job_id: str, results: list):
    """Clear a job's saved results, then insert the given (de-duplicated) list.
    Used at job completion so the stored data exactly matches the final de-duped
    set — snapshots saved mid-run (which may contain same-name branch rows) don't
    linger in the DB."""
    with _cursor(commit=True) as cur:
        cur.execute("DELETE FROM results WHERE job_id = ?", (job_id,))
    save_results_bulk(job_id, results)


def get_results(job_id: str) -> list:
    with _cursor() as cur:
        cur.execute("SELECT * FROM results WHERE job_id = ? ORDER BY id", (job_id,))
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_results_count(job_id: str) -> tuple[int, int]:
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM results WHERE job_id = ?", (job_id,))
        total = cur.fetchone()["n"]
        cur.execute(
            "SELECT COUNT(*) AS n FROM results WHERE job_id = ? AND email != ''",
            (job_id,),
        )
        with_email = cur.fetchone()["n"]
    return total, with_email


def get_admin_stats() -> dict:
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users");   total_users = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM jobs");     total_jobs = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM results");  total_results = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM results WHERE email != ''")
        total_emails = cur.fetchone()["n"]
    return {
        "total_users": total_users, "total_jobs": total_jobs,
        "total_results": total_results, "total_emails": total_emails,
    }


# ── SMTP & Outreach Database Operations ─────────────────────
def get_smtp_settings(user_id: int) -> Optional[dict]:
    with _cursor() as cur:
        cur.execute("SELECT * FROM smtp_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def save_smtp_settings(
    user_id: int,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
    from_name: str = "",
    use_tls: int = 1,
    daily_limit: int = 500,
    delay_sec: float = 3.0,
):
    now = datetime.now().isoformat()
    with _cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO smtp_settings (
                user_id, smtp_host, smtp_port, smtp_user, smtp_pass,
                from_name, use_tls, daily_limit, delay_sec, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                smtp_host   = excluded.smtp_host,
                smtp_port   = excluded.smtp_port,
                smtp_user   = excluded.smtp_user,
                smtp_pass   = CASE WHEN excluded.smtp_pass != '' THEN excluded.smtp_pass ELSE smtp_settings.smtp_pass END,
                from_name   = excluded.from_name,
                use_tls     = excluded.use_tls,
                daily_limit = excluded.daily_limit,
                delay_sec   = excluded.delay_sec,
                updated_at  = excluded.updated_at
        """, (user_id, smtp_host, smtp_port, smtp_user, smtp_pass, from_name, use_tls, daily_limit, delay_sec, now))


def log_outreach_email(
    user_id: int,
    recipient_email: str,
    status: str,
    job_id: str = "",
    company_name: str = "",
    decision_maker: str = "",
    subject: str = "",
    body: str = "",
    error_message: str = "",
):
    now = datetime.now().isoformat()
    with _cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO outreach_logs (
                user_id, job_id, recipient_email, company_name, decision_maker,
                subject, body, status, error_message, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, job_id, recipient_email, company_name, decision_maker, subject, body, status, error_message, now))


def get_outreach_history(user_id: int, limit: int = 200) -> list:
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM outreach_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))
        return [_row_to_dict(r) for r in cur.fetchall()]


# Initialize on import
init_db()
