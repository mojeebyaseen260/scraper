"""
One-off migration: copy users / jobs / results from the old SQLite database
into PostgreSQL (the new DATABASE_URL target).

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db \
        python migrate_sqlite_to_postgres.py [path/to/coldleads.db] [--wipe]

Default SQLite path: output/coldleads.db
Safe by default: APPENDS into Postgres (existing rows kept; dups skipped).
Pass --wipe to TRUNCATE the Postgres tables first for a clean 1:1 copy
(destructive — only use on an empty/throwaway target).
"""
import os
import sys
import sqlite3

import psycopg2
import psycopg2.extras

HERE = os.path.dirname(__file__)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
WIPE = "--wipe" in sys.argv
sqlite_path = args[0] if args else os.path.join(HERE, "output", "coldleads.db")

if not os.path.exists(sqlite_path):
    sys.exit(f"SQLite DB not found: {sqlite_path}")

# Ensure the Postgres schema exists (runs init_db()).
import database  # noqa: E402  (also validates DATABASE_URL is set)

sl = sqlite3.connect(sqlite_path)
sl.row_factory = sqlite3.Row
pg = psycopg2.connect(os.environ["DATABASE_URL"])
cur = pg.cursor()


def sqlite_cols(table):
    return {r[1] for r in sl.execute(f"PRAGMA table_info({table})").fetchall()}


def get(row, key, default=None):
    return row[key] if key in row.keys() else default


if WIPE:
    cur.execute("TRUNCATE results, jobs, users RESTART IDENTITY CASCADE")
    print("--wipe: cleared Postgres tables for a clean 1:1 copy.")
else:
    print("Appending into Postgres (existing rows kept; pass --wipe for a clean copy).")

# ── Users (preserve ids so job.user_id FKs line up) ──────────
ucols = sqlite_cols("users")
users = sl.execute("SELECT * FROM users").fetchall()
for u in users:
    cur.execute(
        """INSERT INTO users (id, email, password, role, token_version, created_at)
           VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
        (u["id"], u["email"], u["password"], u["role"],
         get(u, "token_version", 0) or 0, u["created_at"]),
    )
cur.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1))")

# ── Jobs ─────────────────────────────────────────────────────
jcols = sqlite_cols("jobs")
jobs = sl.execute("SELECT * FROM jobs").fetchall()
for j in jobs:
    cur.execute(
        """INSERT INTO jobs
           (job_id, user_id, session_id, status, progress, total_tasks, done_tasks,
            state, cities, keywords, max_emails, message, created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (job_id) DO NOTHING""",
        (j["job_id"], get(j, "user_id"), get(j, "session_id", "") or "",
         j["status"], get(j, "progress", 0) or 0, get(j, "total_tasks", 0) or 0,
         get(j, "done_tasks", 0) or 0, get(j, "state", "") or "",
         get(j, "cities", "[]") or "[]", get(j, "keywords", "") or "",
         get(j, "max_emails", 5) or 5, get(j, "message", "") or "", j["created_at"]),
    )

# ── Results (Postgres assigns new ids; dedup on job_id,name,city) ──
results = sl.execute("SELECT * FROM results").fetchall()
batch = [
    (r["job_id"], get(r, "name", ""), get(r, "city", ""), get(r, "state", ""),
     get(r, "phone", ""), get(r, "address", ""), get(r, "rating", ""),
     get(r, "category", ""), get(r, "email", "") or "", get(r, "website", ""))
    for r in results
]
if batch:
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO results
           (job_id, name, city, state, phone, address, rating, category, email, website)
           VALUES %s ON CONFLICT (job_id, name, city) DO NOTHING""",
        batch, page_size=500,
    )

pg.commit()
cur.close(); pg.close(); sl.close()
print(f"Migrated: {len(users)} users, {len(jobs)} jobs, {len(results)} results")
