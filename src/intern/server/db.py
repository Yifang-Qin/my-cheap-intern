import sqlite3
import json
import uuid
from datetime import datetime, timezone, timedelta

_db_path = ""

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    config TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'running',
    tags TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS metric_meta (
    run_id TEXT NOT NULL REFERENCES runs(id),
    key TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'scalar',
    direction TEXT NOT NULL DEFAULT 'neutral',
    description TEXT NOT NULL DEFAULT '',
    aggregation TEXT NOT NULL DEFAULT 'last',
    PRIMARY KEY (run_id, key)
);

CREATE TABLE IF NOT EXISTS metric_points (
    run_id TEXT NOT NULL REFERENCES runs(id),
    key TEXT NOT NULL,
    step INTEGER NOT NULL,
    value REAL NOT NULL,
    timestamp TEXT NOT NULL,
    PRIMARY KEY (run_id, key, step)
);

CREATE TABLE IF NOT EXISTS log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    step INTEGER,
    level TEXT NOT NULL DEFAULT 'info',
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
"""


def set_db_path(path: str):
    global _db_path
    _db_path = path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: str):
    set_db_path(path)
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Project operations ---

def create_project(name: str, description: str = "") -> dict:
    conn = get_connection()
    project_id = str(uuid.uuid4())
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
        (project_id, name, description, _now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row)


def get_project_by_name(name: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_projects() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, COUNT(r.id) as run_count, MAX(r.started_at) as last_active_at
        FROM projects p LEFT JOIN runs r ON p.id = r.project_id
        GROUP BY p.id ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Run operations ---

def _parse_run(row) -> dict:
    r = dict(row)
    r["config"] = json.loads(r["config"])
    r["tags"] = json.loads(r["tags"])
    return r


def create_run(project_id: str, run_id: str | None, name: str | None,
               config: dict, tags: list[str]) -> dict:
    conn = get_connection()
    now = _now()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if not name:
        name = f"run-{ts}"
    if not run_id:
        safe = name.replace(" ", "-").lower()
        run_id = f"{safe}-{ts}"
    conn.execute(
        "INSERT INTO runs (id, project_id, name, config, status, tags, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, project_id, name, json.dumps(config), "running", json.dumps(tags), now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    return _parse_run(row)


STALE_TIMEOUT = timedelta(minutes=5)


def _check_stale_running(conn: sqlite3.Connection, run_id: str, run: dict) -> dict:
    """If a run is 'running' but has no recent activity, mark it as crashed."""
    if run["status"] != "running":
        return run
    last_ts = conn.execute(
        "SELECT MAX(timestamp) as ts FROM metric_points WHERE run_id = ?", (run_id,)
    ).fetchone()["ts"]
    if not last_ts:
        last_ts = conn.execute(
            "SELECT MAX(timestamp) as ts FROM log_entries WHERE run_id = ?", (run_id,)
        ).fetchone()["ts"]
    if not last_ts:
        last_ts = run["started_at"]
    try:
        last_dt = datetime.fromisoformat(last_ts)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return run
    if datetime.now(timezone.utc) - last_dt > STALE_TIMEOUT:
        finished_at = _now()
        conn.execute("UPDATE runs SET status = 'crashed', finished_at = ? WHERE id = ?",
                     (finished_at, run_id))
        conn.commit()
        run["status"] = "crashed"
        run["finished_at"] = finished_at
    return run


def get_run(run_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        conn.close()
        return None
    run = _parse_run(row)
    run = _check_stale_running(conn, run_id, run)
    conn.close()
    return run


def list_runs(project_id: str, status: str | None = None) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM runs WHERE project_id = ?"
    params: list = [project_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY started_at DESC"
    rows = conn.execute(sql, params).fetchall()
    runs = [_parse_run(r) for r in rows]
    runs = [_check_stale_running(conn, r["id"], r) for r in runs]
    conn.close()
    return runs


def update_run_status(run_id: str, status: str):
    conn = get_connection()
    finished_at = _now() if status in ("finished", "crashed") else None
    conn.execute("UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
                 (status, finished_at, run_id))
    conn.commit()
    conn.close()


def search_runs(project_id: str, query: str | None = None, tags: list[str] | None = None,
                status: str | None = None, started_after: str | None = None,
                started_before: str | None = None) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM runs WHERE project_id = ?"
    params: list = [project_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    if started_after:
        sql += " AND started_at >= ?"
        params.append(started_after)
    if started_before:
        sql += " AND started_at <= ?"
        params.append(started_before)
    if query:
        sql += " AND (name LIKE ? OR tags LIKE ? OR config LIKE ?)"
        q = f"%{query}%"
        params.extend([q, q, q])
    sql += " ORDER BY started_at DESC"
    rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        r = _parse_run(row)
        if tags and not all(t in r["tags"] for t in tags):
            continue
        meta_rows = conn.execute("SELECT key FROM metric_meta WHERE run_id = ?", (r["id"],)).fetchall()
        r["metric_keys"] = [m["key"] for m in meta_rows]
        results.append(r)
    conn.close()
    return results


def delete_run(run_id: str):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM metric_points WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM metric_meta WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM log_entries WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.close()


def delete_project(project_id: str):
    conn = get_connection()
    with conn:
        run_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM runs WHERE project_id = ?", (project_id,)
        ).fetchall()]
        for rid in run_ids:
            conn.execute("DELETE FROM metric_points WHERE run_id = ?", (rid,))
            conn.execute("DELETE FROM metric_meta WHERE run_id = ?", (rid,))
            conn.execute("DELETE FROM log_entries WHERE run_id = ?", (rid,))
        conn.execute("DELETE FROM runs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.close()


# --- Metric operations ---

def define_metric(run_id: str, key: str, type: str = "scalar", direction: str = "neutral",
                  description: str = "", aggregation: str = "last"):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO metric_meta (run_id, key, type, direction, description, aggregation) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, key, type, direction, description, aggregation),
    )
    conn.commit()
    conn.close()


def insert_metric_points(run_id: str, points: list[dict]):
    conn = get_connection()
    now = _now()
    # Auto-define metric_meta for any new keys (INSERT OR IGNORE keeps existing definitions)
    seen_keys = {p["key"] for p in points}
    for key in seen_keys:
        conn.execute(
            "INSERT OR IGNORE INTO metric_meta (run_id, key, type, direction, description, aggregation) "
            "VALUES (?, ?, 'scalar', 'neutral', '', 'last')",
            (run_id, key),
        )
    for p in points:
        conn.execute(
            "INSERT OR REPLACE INTO metric_points (run_id, key, step, value, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, p["key"], p["step"], p["value"], p.get("timestamp") or now),
        )
    conn.commit()
    conn.close()


def get_metric_series(run_id: str, key: str, start_step: int | None = None,
                      end_step: int | None = None, downsample: int | None = None) -> list[dict]:
    conn = get_connection()
    sql = "SELECT step, value, timestamp FROM metric_points WHERE run_id = ? AND key = ?"
    params: list = [run_id, key]
    if start_step is not None:
        sql += " AND step >= ?"
        params.append(start_step)
    if end_step is not None:
        sql += " AND step <= ?"
        params.append(end_step)
    sql += " ORDER BY step"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if downsample and len(result) > downsample:
        indices = [int(i * (len(result) - 1) / (downsample - 1)) for i in range(downsample)]
        result = [result[i] for i in indices]
    return result


def get_metric_metas(run_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM metric_meta WHERE run_id = ?", (run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Log operations ---

def insert_logs(run_id: str, entries: list[dict]):
    conn = get_connection()
    now = _now()
    for e in entries:
        conn.execute(
            "INSERT INTO log_entries (run_id, step, level, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (run_id, e.get("step"), e.get("level", "info"), e["content"], e.get("timestamp") or now),
        )
    conn.commit()
    conn.close()


def get_logs(run_id: str, level: str | None = None, keyword: str | None = None,
             limit: int = 100) -> list[dict]:
    conn = get_connection()
    sql = "SELECT step, level, content, timestamp FROM log_entries WHERE run_id = ?"
    params: list = [run_id]
    if level:
        sql += " AND level = ?"
        params.append(level)
    if keyword:
        sql += " AND content LIKE ?"
        params.append(f"%{keyword}%")
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
