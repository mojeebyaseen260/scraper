"""
One-off SQLite->SQLite merge: copy users / jobs / results from a SOURCE db
into the active TARGET db. Safe: appends only, dedups, remaps user ids by email.

Usage:
    python merge_sqlite.py output/coldleads.db coldleads.db
"""
import sys
import sqlite3

src_path = sys.argv[1] if len(sys.argv) > 1 else "output/coldleads.db"
dst_path = sys.argv[2] if len(sys.argv) > 2 else "coldleads.db"

src = sqlite3.connect(src_path)
src.row_factory = sqlite3.Row
dst = sqlite3.connect(dst_path)
dst.row_factory = sqlite3.Row
dst.execute("PRAGMA busy_timeout=10000")
dst.execute("PRAGMA foreign_keys=OFF")

# ── Users: match by email; build src_id -> dst_id map ──────────
id_map = {}
u_new = 0
for u in src.execute("SELECT * FROM users").fetchall():
    row = dst.execute("SELECT id FROM users WHERE email = ?", (u["email"],)).fetchone()
    if row:
        id_map[u["id"]] = row["id"]
        continue
    cur = dst.execute(
        "INSERT INTO users (email, password, role, token_version, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (u["email"], u["password"], u["role"],
         (u["token_version"] if "token_version" in u.keys() else 0) or 0,
         u["created_at"]),
    )
    id_map[u["id"]] = cur.lastrowid
    u_new += 1

# ── Jobs: keyed by job_id; remap user_id; skip existing ────────
j_new = 0
for j in src.execute("SELECT * FROM jobs").fetchall():
    if dst.execute("SELECT 1 FROM jobs WHERE job_id = ?", (j["job_id"],)).fetchone():
        continue
    k = j.keys()
    g = lambda key, d=None: (j[key] if key in k else d)
    dst.execute(
        """INSERT INTO jobs
           (job_id, user_id, session_id, status, progress, total_tasks, done_tasks,
            state, cities, keywords, max_emails, message, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (j["job_id"], id_map.get(g("user_id"), g("user_id")), g("session_id", "") or "",
         j["status"], g("progress", 0) or 0, g("total_tasks", 0) or 0,
         g("done_tasks", 0) or 0, g("state", "") or "", g("cities", "[]") or "[]",
         g("keywords", "") or "", g("max_emails", 5) or 5, g("message", "") or "",
         j["created_at"]),
    )
    j_new += 1

# ── Results: dedup on (job_id, name, city) ─────────────────────
r_new = 0
for r in src.execute("SELECT * FROM results").fetchall():
    k = r.keys()
    g = lambda key, d="": (r[key] if key in k else d)
    cur = dst.execute(
        """INSERT OR IGNORE INTO results
           (job_id, name, city, state, phone, address, rating, category, email, website)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (r["job_id"], g("name"), g("city"), g("state"), g("phone"), g("address"),
         g("rating"), g("category"), g("email") or "", g("website")),
    )
    r_new += cur.rowcount

dst.commit()
print(f"Merged in: {u_new} new users, {j_new} new jobs, {r_new} new results")
for t in ("users", "jobs", "results"):
    n = dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t} total now: {n}")
src.close(); dst.close()
