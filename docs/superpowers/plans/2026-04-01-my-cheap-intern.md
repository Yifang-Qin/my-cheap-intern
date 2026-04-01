# my-cheap-intern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted, AI-native experiment tracking service with Logger SDK, REST API, MCP server, and web panel.

**Architecture:** Single FastAPI process serving REST API, web panel, and MCP endpoint, backed by SQLite. Logger SDK communicates via HTTP. MCP tools provide pre-computed summaries for AI consumers.

**Tech Stack:** Python 3.10+, FastAPI, SQLite (raw SQL), Jinja2 + HTMX + Chart.js, mcp Python SDK, requests

**Spec:** `docs/2026-04-01-my-cheap-intern-design.md`

---

## File Structure

```
src/intern/
├── __init__.py              # SDK public API (init, log, log_text, finish)
├── common/
│   ├── __init__.py
│   └── models.py            # Pydantic request/response models
├── sdk/
│   ├── __init__.py
│   ├── client.py            # Run class with buffering and flush
│   └── api.py               # HTTP client for server communication
└── server/
    ├── __init__.py
    ├── app.py                # FastAPI app factory, auth, router registration, CLI
    ├── db.py                 # SQLite schema + all CRUD operations
    ├── analysis.py           # Trend detection, anomaly detection, summaries
    ├── mcp_server.py         # MCP tools (6 tools) + SSE transport
    ├── routes/
    │   ├── __init__.py
    │   ├── ingest.py         # Write endpoints (POST/PATCH)
    │   └── query.py          # Read endpoints (GET)
    ├── templates/
    │   ├── base.html
    │   ├── project_list.html
    │   ├── run_list.html
    │   └── run_detail.html
    └── static/
        └── style.css
tests/
├── conftest.py              # Shared fixtures (tmp db, test client)
├── test_db.py
├── test_ingest.py
├── test_query.py
├── test_analysis.py
├── test_mcp.py
└── test_sdk.py
pyproject.toml
```

---

### Task 1: Project Scaffolding + Data Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/intern/__init__.py` (empty placeholder)
- Create: `src/intern/common/__init__.py`
- Create: `src/intern/common/models.py`
- Create: `src/intern/sdk/__init__.py`
- Create: `src/intern/server/__init__.py`
- Create: `src/intern/server/routes/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-cheap-intern"
version = "0.1.0"
description = "AI-native experiment tracking for ML researchers"
requires-python = ">=3.10"
dependencies = [
    "requests",
    "pydantic>=2.0",
]

[project.optional-dependencies]
server = [
    "fastapi>=0.100",
    "uvicorn[standard]",
    "jinja2",
    "python-multipart",
    "mcp[cli]",
]
dev = [
    "pytest",
    "httpx",
]

[project.scripts]
intern-server = "intern.server.app:main"
```

- [ ] **Step 2: Create directory structure and empty __init__.py files**

```bash
mkdir -p src/intern/common src/intern/sdk src/intern/server/routes src/intern/server/templates src/intern/server/static tests
touch src/intern/common/__init__.py src/intern/sdk/__init__.py src/intern/server/__init__.py src/intern/server/routes/__init__.py
```

Write `src/intern/__init__.py` as empty placeholder (will be replaced in Task 7):

```python
```

- [ ] **Step 3: Create data models**

Write `src/intern/common/models.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class CreateRunRequest(BaseModel):
    id: str | None = None
    name: str | None = None
    config: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class DefineMetricRequest(BaseModel):
    key: str
    type: str = "scalar"
    direction: str = "neutral"
    description: str = ""
    aggregation: str = "last"


class MetricPointIn(BaseModel):
    key: str
    step: int
    value: float
    timestamp: str | None = None


class LogEntryIn(BaseModel):
    step: int | None = None
    level: str = "info"
    content: str
    timestamp: str | None = None


class UpdateRunRequest(BaseModel):
    status: str
```

- [ ] **Step 4: Install in editable mode and verify**

```bash
cd /Users/fang/Documents/WorkSpace/my-cheap-intern
uv venv && source .venv/bin/activate
uv pip install -e ".[server,dev]"
python -c "from intern.common.models import CreateProjectRequest; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "scaffold: project structure, pyproject.toml, data models"
```

---

### Task 2: Database Layer

**Files:**
- Create: `src/intern/server/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_db.py`:

```python
import pytest
from intern.server.db import (
    init_db, create_project, get_project_by_name, list_projects,
    create_run, get_run, list_runs, update_run_status, search_runs,
    define_metric, insert_metric_points, get_metric_series, get_metric_metas,
    insert_logs, get_logs,
)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_create_and_list_projects(db):
    p = create_project("my-project", "desc")
    assert p["name"] == "my-project"
    assert p["description"] == "desc"

    projects = list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "my-project"
    assert projects[0]["run_count"] == 0


def test_get_project_by_name(db):
    create_project("proj-a")
    result = get_project_by_name("proj-a")
    assert result["name"] == "proj-a"
    assert get_project_by_name("nonexistent") is None


def test_create_and_get_run(db):
    p = create_project("proj")
    r = create_run(p["id"], None, "run-1", {"lr": 0.001}, ["tag1"])
    assert r["name"] == "run-1"
    assert r["status"] == "running"
    assert r["config"]["lr"] == 0.001
    assert r["tags"] == ["tag1"]

    fetched = get_run(r["id"])
    assert fetched["name"] == "run-1"
    assert fetched["config"]["lr"] == 0.001


def test_auto_generate_run_id(db):
    p = create_project("proj")
    r = create_run(p["id"], None, "my-run", {}, [])
    assert "my-run" in r["id"]


def test_list_runs_with_status_filter(db):
    p = create_project("proj")
    r1 = create_run(p["id"], "r1", "run-1", {}, [])
    r2 = create_run(p["id"], "r2", "run-2", {}, [])
    update_run_status("r1", "finished")

    all_runs = list_runs(p["id"])
    assert len(all_runs) == 2

    running = list_runs(p["id"], status="running")
    assert len(running) == 1
    assert running[0]["id"] == "r2"


def test_search_runs(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "grpo-eps0.2", {"epsilon": 0.2}, ["grpo", "sweep"])
    create_run(p["id"], "r2", "grpo-eps0.5", {"epsilon": 0.5}, ["grpo", "sweep"])
    create_run(p["id"], "r3", "sft-baseline", {"lr": 1e-5}, ["sft"])

    results = search_runs(p["id"], query="grpo")
    assert len(results) == 2

    results = search_runs(p["id"], tags=["sft"])
    assert len(results) == 1
    assert results[0]["id"] == "r3"


def test_metric_operations(db):
    p = create_project("proj")
    r = create_run(p["id"], "r1", "run", {}, [])
    define_metric("r1", "loss", direction="lower_better", description="Training loss")
    insert_metric_points("r1", [
        {"key": "loss", "step": 1, "value": 2.0, "timestamp": "2026-01-01T00:00:00"},
        {"key": "loss", "step": 2, "value": 1.5, "timestamp": "2026-01-01T00:01:00"},
        {"key": "loss", "step": 3, "value": 1.0, "timestamp": "2026-01-01T00:02:00"},
    ])

    metas = get_metric_metas("r1")
    assert len(metas) == 1
    assert metas[0]["direction"] == "lower_better"

    series = get_metric_series("r1", "loss")
    assert len(series) == 3
    assert series[0]["value"] == 2.0
    assert series[2]["value"] == 1.0


def test_metric_series_range_and_downsample(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    points = [{"key": "x", "step": i, "value": float(i), "timestamp": "2026-01-01T00:00:00"} for i in range(100)]
    insert_metric_points("r1", points)

    subset = get_metric_series("r1", "x", start_step=10, end_step=20)
    assert len(subset) == 11
    assert subset[0]["step"] == 10

    downsampled = get_metric_series("r1", "x", downsample=10)
    assert len(downsampled) == 10


def test_log_operations(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    insert_logs("r1", [
        {"level": "info", "content": "Started training", "timestamp": "2026-01-01T00:00:00"},
        {"level": "warning", "content": "High loss detected", "timestamp": "2026-01-01T00:01:00"},
        {"level": "error", "content": "OOM error", "timestamp": "2026-01-01T00:02:00"},
    ])

    all_logs = get_logs("r1")
    assert len(all_logs) == 3

    warnings = get_logs("r1", level="warning")
    assert len(warnings) == 1

    keyword = get_logs("r1", keyword="loss")
    assert len(keyword) == 1
    assert "loss" in keyword[0]["content"]

    limited = get_logs("r1", limit=2)
    assert len(limited) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```

Expected: FAIL (imports fail, module not found)

- [ ] **Step 3: Implement db.py**

Write `src/intern/server/db.py`:

```python
import sqlite3
import json
import uuid
from datetime import datetime, timezone

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
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
        "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
        (project_id, name, description, _now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
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


def get_run(run_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    return _parse_run(row) if row else None


def list_runs(project_id: str, status: str | None = None) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM runs WHERE project_id = ?"
    params: list = [project_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY started_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_parse_run(r) for r in rows]


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/intern/server/db.py tests/test_db.py
git commit -m "feat: database layer with SQLite schema and CRUD operations"
```

---

### Task 3: FastAPI App + Ingest Routes

**Files:**
- Create: `src/intern/server/app.py`
- Create: `src/intern/server/routes/ingest.py`
- Create: `tests/conftest.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Write test fixtures**

Write `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def client(db_path):
    app = create_app(db_path=db_path, api_key="test-key")
    return TestClient(app, headers={"Authorization": "Bearer test-key"})


@pytest.fixture
def sample_project(client):
    resp = client.post("/api/projects", json={"name": "test-project", "description": "Test"})
    return resp.json()


@pytest.fixture
def sample_run(client, sample_project):
    resp = client.post(
        f"/api/projects/{sample_project['name']}/runs",
        json={"name": "test-run", "config": {"lr": 0.001}, "tags": ["test"]},
    )
    return resp.json()
```

- [ ] **Step 2: Write failing tests for ingest routes**

Write `tests/test_ingest.py`:

```python
def test_create_project(client):
    resp = client.post("/api/projects", json={"name": "my-proj", "description": "A project"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "my-proj"


def test_create_project_idempotent(client):
    client.post("/api/projects", json={"name": "proj"})
    resp = client.post("/api/projects", json={"name": "proj"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "proj"


def test_auth_required(db_path):
    from fastapi.testclient import TestClient
    from intern.server.app import create_app
    app = create_app(db_path=db_path, api_key="secret")
    no_auth = TestClient(app)
    resp = no_auth.post("/api/projects", json={"name": "x"})
    assert resp.status_code == 401


def test_create_run(client, sample_project):
    resp = client.post(
        f"/api/projects/{sample_project['name']}/runs",
        json={"name": "run-1", "config": {"lr": 0.001}, "tags": ["grpo"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "run-1"
    assert data["status"] == "running"
    assert data["config"]["lr"] == 0.001


def test_create_run_auto_creates_project(client):
    resp = client.post(
        "/api/projects/new-proj/runs",
        json={"name": "run-1", "config": {}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_define_metric(client, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/metrics/define",
        json={"key": "loss", "direction": "lower_better", "description": "Training loss"},
    )
    assert resp.status_code == 200


def test_write_metrics(client, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/metrics",
        json=[
            {"key": "loss", "step": 1, "value": 2.0},
            {"key": "loss", "step": 2, "value": 1.5},
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_write_logs(client, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/logs",
        json=[
            {"level": "info", "content": "Started", "step": 0},
            {"level": "warning", "content": "High loss", "step": 10},
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_update_run_status(client, sample_run):
    resp = client.patch(
        f"/api/runs/{sample_run['id']}",
        json={"status": "finished"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_ingest.py -v
```

Expected: FAIL (app module not found)

- [ ] **Step 4: Implement app.py and ingest routes**

Write `src/intern/server/app.py`:

```python
import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends


def _make_verify_api_key(api_key: str):
    def verify_api_key(request: Request):
        if not api_key:
            return
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return verify_api_key


def create_app(db_path: str | None = None, api_key: str = "") -> FastAPI:
    app = FastAPI(title="my-cheap-intern")
    app.state.api_key = api_key

    if db_path:
        from intern.server.db import init_db
        init_db(db_path)

    verify = _make_verify_api_key(api_key)

    from intern.server.routes.ingest import router as ingest_router
    from intern.server.routes.query import router as query_router
    app.include_router(ingest_router, prefix="/api", dependencies=[Depends(verify)])
    app.include_router(query_router, prefix="/api", dependencies=[Depends(verify)])

    return app


def main():
    import uvicorn
    port = int(os.environ.get("INTERN_PORT", "8080"))
    api_key = os.environ.get("INTERN_API_KEY", "")
    data_dir = os.environ.get("INTERN_DATA_DIR", str(Path.home() / ".intern"))
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db_path = str(Path(data_dir) / "data.db")

    app = create_app(db_path=db_path, api_key=api_key)
    uvicorn.run(app, host="0.0.0.0", port=port)
```

Write `src/intern/server/routes/ingest.py`:

```python
from datetime import datetime, timezone
from fastapi import APIRouter
from intern.common.models import (
    CreateProjectRequest, CreateRunRequest, DefineMetricRequest,
    MetricPointIn, LogEntryIn, UpdateRunRequest,
)
from intern.server import db

router = APIRouter()


@router.post("/projects")
def create_project(req: CreateProjectRequest):
    existing = db.get_project_by_name(req.name)
    if existing:
        return existing
    return db.create_project(req.name, req.description)


@router.post("/projects/{project}/runs")
def create_run(project: str, req: CreateRunRequest):
    p = db.get_project_by_name(project)
    if not p:
        p = db.create_project(project)
    return db.create_run(p["id"], req.id, req.name, req.config, req.tags)


@router.post("/runs/{run_id}/metrics/define")
def define_metric(run_id: str, req: DefineMetricRequest):
    db.define_metric(run_id, req.key, req.type, req.direction, req.description, req.aggregation)
    return {"status": "ok"}


@router.post("/runs/{run_id}/metrics")
def write_metrics(run_id: str, points: list[MetricPointIn]):
    now = datetime.now(timezone.utc).isoformat()
    data = [p.model_dump() for p in points]
    for d in data:
        if not d.get("timestamp"):
            d["timestamp"] = now
    db.insert_metric_points(run_id, data)
    return {"status": "ok", "count": len(points)}


@router.post("/runs/{run_id}/logs")
def write_logs(run_id: str, entries: list[LogEntryIn]):
    now = datetime.now(timezone.utc).isoformat()
    data = [e.model_dump() for e in entries]
    for d in data:
        if not d.get("timestamp"):
            d["timestamp"] = now
    db.insert_logs(run_id, data)
    return {"status": "ok", "count": len(entries)}


@router.patch("/runs/{run_id}")
def update_run(run_id: str, req: UpdateRunRequest):
    db.update_run_status(run_id, req.status)
    return {"status": "ok"}
```

Write a placeholder `src/intern/server/routes/query.py` so imports don't fail:

```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_ingest.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/intern/server/app.py src/intern/server/routes/ tests/conftest.py tests/test_ingest.py
git commit -m "feat: FastAPI app with auth and ingest routes"
```

---

### Task 4: Query Routes

**Files:**
- Modify: `src/intern/server/routes/query.py`
- Create: `tests/test_query.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_query.py`:

```python
def test_list_projects(client, sample_project):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "test-project"


def test_list_runs(client, sample_project, sample_run):
    resp = client.get(f"/api/projects/{sample_project['name']}/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-run"


def test_list_runs_status_filter(client, sample_project, sample_run):
    resp = client.get(f"/api/projects/{sample_project['name']}/runs?status=finished")
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    resp = client.get(f"/api/projects/{sample_project['name']}/runs?status=running")
    assert len(resp.json()) == 1


def test_get_run_detail(client, sample_run):
    resp = client.get(f"/api/runs/{sample_run['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-run"
    assert "metric_metas" in data


def test_get_run_not_found(client):
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


def test_get_metric_series(client, sample_run):
    client.post(
        f"/api/runs/{sample_run['id']}/metrics",
        json=[
            {"key": "loss", "step": 1, "value": 2.0},
            {"key": "loss", "step": 2, "value": 1.5},
            {"key": "loss", "step": 3, "value": 1.0},
        ],
    )
    resp = client.get(f"/api/runs/{sample_run['id']}/metrics/loss")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_get_logs(client, sample_run):
    client.post(
        f"/api/runs/{sample_run['id']}/logs",
        json=[
            {"level": "info", "content": "hello"},
            {"level": "warning", "content": "uh oh"},
        ],
    )
    resp = client.get(f"/api/runs/{sample_run['id']}/logs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get(f"/api/runs/{sample_run['id']}/logs?level=warning")
    assert len(resp.json()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_query.py -v
```

Expected: FAIL (endpoints return 405 or empty)

- [ ] **Step 3: Implement query routes**

Replace `src/intern/server/routes/query.py`:

```python
from fastapi import APIRouter, HTTPException
from intern.server import db

router = APIRouter()


@router.get("/projects")
def list_projects():
    return db.list_projects()


@router.get("/projects/{project}/runs")
def list_runs(project: str, status: str | None = None):
    p = db.get_project_by_name(project)
    if not p:
        return []
    return db.list_runs(p["id"], status=status)


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404)
    metas = db.get_metric_metas(run_id)
    run["metric_metas"] = metas
    return run


@router.get("/runs/{run_id}/metrics/{key}")
def get_metric_series(run_id: str, key: str, start_step: int | None = None,
                      end_step: int | None = None, downsample: int | None = None):
    return db.get_metric_series(run_id, key, start_step, end_step, downsample)


@router.get("/runs/{run_id}/logs")
def get_logs(run_id: str, level: str | None = None, keyword: str | None = None,
             limit: int = 100):
    return db.get_logs(run_id, level=level, keyword=keyword, limit=limit)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_query.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/intern/server/routes/query.py tests/test_query.py
git commit -m "feat: query routes for projects, runs, metrics, logs"
```

---

### Task 5: Analysis Module

**Files:**
- Create: `src/intern/server/analysis.py`
- Create: `tests/test_analysis.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_analysis.py`:

```python
import pytest
from intern.server.analysis import compute_trend, detect_anomalies, compute_metric_stats, compute_log_summary
from intern.server.db import init_db, create_project, create_run, define_metric, insert_metric_points, insert_logs


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_trend_increasing():
    assert compute_trend([1.0, 2.0, 3.0, 4.0, 5.0]) == "increasing"


def test_trend_decreasing():
    assert compute_trend([5.0, 4.0, 3.0, 2.0, 1.0]) == "decreasing"


def test_trend_stable():
    assert compute_trend([3.0, 3.0, 3.0, 3.0, 3.0]) == "stable"


def test_trend_short():
    assert compute_trend([1.0]) == "stable"


def test_detect_anomalies_none():
    values = [1.0] * 30
    steps = list(range(30))
    assert detect_anomalies(steps, values) == []


def test_detect_anomalies_spike():
    values = [1.0] * 25 + [100.0]
    steps = list(range(26))
    anomalies = detect_anomalies(steps, values, window=20)
    assert 25 in anomalies


def test_compute_metric_stats(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    define_metric("r1", "loss", direction="lower_better", description="Loss")
    points = [{"key": "loss", "step": i, "value": 10.0 - i * 0.1, "timestamp": "2026-01-01T00:00:00"}
              for i in range(50)]
    insert_metric_points("r1", points)

    stats = compute_metric_stats("r1", "loss")
    assert stats["trend"] == "decreasing"
    assert stats["direction"] == "lower_better"
    assert stats["latest"] == pytest.approx(5.1)
    assert stats["min"] < stats["max"]
    assert "anomaly_steps" in stats


def test_compute_log_summary(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    insert_logs("r1", [
        {"level": "info", "content": "ok", "timestamp": "2026-01-01T00:00:00"},
        {"level": "warning", "content": "watch out", "timestamp": "2026-01-01T00:01:00"},
        {"level": "warning", "content": "another warning", "timestamp": "2026-01-01T00:02:00"},
        {"level": "error", "content": "boom", "timestamp": "2026-01-01T00:03:00"},
    ])

    summary = compute_log_summary("r1")
    assert summary["total"] == 4
    assert summary["warnings"] == 2
    assert summary["errors"] == 1
    assert len(summary["recent_warnings"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analysis.py -v
```

Expected: FAIL (imports fail)

- [ ] **Step 3: Implement analysis.py**

Write `src/intern/server/analysis.py`:

```python
import math
from intern.server.db import get_connection


def compute_trend(values: list[float]) -> str:
    n = len(values)
    if n < 2:
        return "stable"
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return "stable"
    slope = numerator / denominator
    if y_mean == 0:
        threshold = 0.01
    else:
        threshold = abs(y_mean) * 0.05
    if slope > threshold:
        return "increasing"
    elif slope < -threshold:
        return "decreasing"
    return "stable"


def detect_anomalies(steps: list[int], values: list[float], window: int = 20) -> list[int]:
    if len(values) < window + 1:
        return []
    anomalies = []
    for i in range(window, len(values)):
        w = values[i - window:i]
        mean = sum(w) / len(w)
        variance = sum((v - mean) ** 2 for v in w) / len(w)
        std = math.sqrt(variance) if variance > 0 else 0
        if std > 0 and abs(values[i] - mean) > 3 * std:
            anomalies.append(steps[i])
    return anomalies


def compute_metric_stats(run_id: str, key: str) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT step, value FROM metric_points WHERE run_id = ? AND key = ? ORDER BY step",
        (run_id, key),
    ).fetchall()
    meta = conn.execute(
        "SELECT * FROM metric_meta WHERE run_id = ? AND key = ?",
        (run_id, key),
    ).fetchone()
    conn.close()

    if not rows:
        return {}

    steps = [r["step"] for r in rows]
    values = [r["value"] for r in rows]
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance) if variance > 0 else 0.0

    trend_window = min(50, n)
    trend = compute_trend(values[-trend_window:])
    anomaly_steps = detect_anomalies(steps, values)

    result = {
        "latest": values[-1],
        "min": min(values),
        "max": max(values),
        "mean": round(mean, 6),
        "std": round(std, 6),
        "trend": trend,
        "anomaly_steps": anomaly_steps,
    }
    if meta:
        result["direction"] = meta["direction"]
        result["description"] = meta["description"]
    return result


def compute_log_summary(run_id: str) -> dict:
    conn = get_connection()
    total = conn.execute(
        "SELECT COUNT(*) as c FROM log_entries WHERE run_id = ?", (run_id,)
    ).fetchone()["c"]
    warnings = conn.execute(
        "SELECT COUNT(*) as c FROM log_entries WHERE run_id = ? AND level = 'warning'", (run_id,)
    ).fetchone()["c"]
    errors = conn.execute(
        "SELECT COUNT(*) as c FROM log_entries WHERE run_id = ? AND level = 'error'", (run_id,)
    ).fetchone()["c"]
    recent = conn.execute(
        "SELECT content FROM log_entries WHERE run_id = ? AND level = 'warning' ORDER BY timestamp DESC LIMIT 3",
        (run_id,),
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "warnings": warnings,
        "errors": errors,
        "recent_warnings": [r["content"] for r in recent],
    }


def compute_duration(started_at: str, finished_at: str | None) -> str:
    if not finished_at:
        return "running"
    from datetime import datetime
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(finished_at)
    delta = end - start
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_analysis.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/intern/server/analysis.py tests/test_analysis.py
git commit -m "feat: analysis module with trend detection, anomaly detection, summaries"
```

---

### Task 6: MCP Server

**Files:**
- Create: `src/intern/server/mcp_server.py`
- Modify: `src/intern/server/app.py`
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Test MCP tool logic directly (not through SSE transport — that's integration-level).

Write `tests/test_mcp.py`:

```python
import json
import pytest
from intern.server.db import (
    init_db, create_project, create_run, define_metric,
    insert_metric_points, insert_logs, update_run_status,
)
from intern.server.mcp_server import handle_tool_call


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def populated_db(db):
    p = create_project("llm-postrain")
    r1 = create_run(p["id"], "run-a", "grpo-eps0.2", {"epsilon": 0.2, "lr": 1e-5}, ["grpo", "sweep"])
    r2 = create_run(p["id"], "run-b", "grpo-eps0.5", {"epsilon": 0.5, "lr": 1e-5}, ["grpo", "sweep"])
    define_metric("run-a", "reward/mean", direction="higher_better", description="Mean reward")
    define_metric("run-b", "reward/mean", direction="higher_better", description="Mean reward")
    insert_metric_points("run-a", [
        {"key": "reward/mean", "step": i, "value": 0.1 + i * 0.02, "timestamp": "2026-01-01T00:00:00"}
        for i in range(50)
    ])
    insert_metric_points("run-b", [
        {"key": "reward/mean", "step": i, "value": 0.2 + i * 0.025, "timestamp": "2026-01-01T00:00:00"}
        for i in range(50)
    ])
    insert_logs("run-a", [
        {"level": "info", "content": "started", "timestamp": "2026-01-01T00:00:00"},
        {"level": "warning", "content": "reward spike", "timestamp": "2026-01-01T00:01:00"},
    ])
    update_run_status("run-a", "finished")
    return {"project": p, "runs": [r1, r2]}


def test_list_projects(populated_db):
    result = handle_tool_call("list_projects", {})
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["name"] == "llm-postrain"


def test_search_runs(populated_db):
    result = handle_tool_call("search_runs", {"project": "llm-postrain", "query": "grpo"})
    data = json.loads(result)
    assert len(data) == 2


def test_search_runs_with_tags(populated_db):
    result = handle_tool_call("search_runs", {"project": "llm-postrain", "tags": ["sweep"]})
    data = json.loads(result)
    assert len(data) == 2


def test_get_run_summary(populated_db):
    result = handle_tool_call("get_run_summary", {"run_ids": ["run-a"]})
    data = json.loads(result)
    assert len(data) == 1
    summary = data[0]
    assert summary["run_id"] == "run-a"
    assert summary["status"] == "finished"
    assert "reward/mean" in summary["metrics"]
    assert summary["metrics"]["reward/mean"]["trend"] == "increasing"
    assert "std" in summary["metrics"]["reward/mean"]
    assert "latest" in summary["metrics"]["reward/mean"]
    assert summary["log_summary"]["warnings"] == 1


def test_compare_runs(populated_db):
    result = handle_tool_call("compare_runs", {"run_ids": ["run-a", "run-b"]})
    data = json.loads(result)
    assert "epsilon" in data["config_diff"]
    assert "reward/mean" in data["metrics_table"]
    assert data["ranking"]["reward/mean"][0] == "run-b"  # higher latest value


def test_get_metric_series(populated_db):
    result = handle_tool_call("get_metric_series", {"run_id": "run-a", "key": "reward/mean"})
    data = json.loads(result)
    assert len(data) == 50


def test_get_metric_series_downsample(populated_db):
    result = handle_tool_call("get_metric_series", {
        "run_id": "run-a", "key": "reward/mean", "downsample": 10
    })
    data = json.loads(result)
    assert len(data) == 10


def test_get_logs(populated_db):
    result = handle_tool_call("get_logs", {"run_id": "run-a"})
    data = json.loads(result)
    assert len(data) == 2


def test_get_logs_filtered(populated_db):
    result = handle_tool_call("get_logs", {"run_id": "run-a", "level": "warning"})
    data = json.loads(result)
    assert len(data) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mcp.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement mcp_server.py**

Write `src/intern/server/mcp_server.py`:

```python
import json
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import mcp.types as types

from intern.server import db
from intern.server.analysis import compute_metric_stats, compute_log_summary, compute_duration

server = Server("my-cheap-intern")

_api_key = ""


def set_api_key(key: str):
    global _api_key
    _api_key = key


# --- Tool logic (testable without MCP transport) ---

def handle_tool_call(name: str, arguments: dict) -> str:
    if name == "list_projects":
        result = db.list_projects()

    elif name == "search_runs":
        project = db.get_project_by_name(arguments["project"])
        if not project:
            return json.dumps({"error": f"Project '{arguments['project']}' not found"})
        result = db.search_runs(
            project_id=project["id"],
            query=arguments.get("query"),
            tags=arguments.get("tags"),
            status=arguments.get("status"),
            started_after=arguments.get("started_after"),
            started_before=arguments.get("started_before"),
        )

    elif name == "get_run_summary":
        result = []
        for run_id in arguments["run_ids"]:
            run = db.get_run(run_id)
            if not run:
                continue
            metas = db.get_metric_metas(run_id)
            metrics = {}
            for meta in metas:
                stats = compute_metric_stats(run_id, meta["key"])
                metrics[meta["key"]] = stats
            log_summary = compute_log_summary(run_id)
            duration = compute_duration(run["started_at"], run.get("finished_at"))
            result.append({
                "run_id": run_id,
                "config": run["config"],
                "status": run["status"],
                "duration": duration,
                "metrics": metrics,
                "log_summary": log_summary,
            })

    elif name == "compare_runs":
        run_ids = arguments["run_ids"]
        metric_keys = arguments.get("metric_keys")
        runs = [db.get_run(rid) for rid in run_ids]
        runs = [r for r in runs if r]

        # Config diff: only keys that differ
        all_config_keys = set()
        for r in runs:
            all_config_keys.update(r["config"].keys())
        config_diff = {}
        for key in sorted(all_config_keys):
            values = {r["id"]: r["config"].get(key) for r in runs}
            if len(set(str(v) for v in values.values())) > 1:
                config_diff[key] = values

        # Shared metric keys
        if not metric_keys:
            key_sets = []
            for r in runs:
                metas = db.get_metric_metas(r["id"])
                key_sets.append(set(m["key"] for m in metas))
            metric_keys = sorted(set.intersection(*key_sets)) if key_sets else []

        # Metrics table + ranking
        metrics_table = {}
        ranking = {}
        for key in metric_keys:
            metrics_table[key] = {}
            for r in runs:
                stats = compute_metric_stats(r["id"], key)
                metrics_table[key][r["id"]] = stats
            direction = metrics_table[key].get(runs[0]["id"], {}).get("direction", "neutral")
            sorted_ids = sorted(
                [r["id"] for r in runs],
                key=lambda rid: metrics_table[key].get(rid, {}).get("latest", 0),
                reverse=(direction != "lower_better"),
            )
            ranking[key] = sorted_ids

        result = {"config_diff": config_diff, "metrics_table": metrics_table, "ranking": ranking}

    elif name == "get_metric_series":
        result = db.get_metric_series(
            arguments["run_id"], arguments["key"],
            start_step=arguments.get("start_step"),
            end_step=arguments.get("end_step"),
            downsample=arguments.get("downsample"),
        )

    elif name == "get_logs":
        result = db.get_logs(
            arguments["run_id"],
            level=arguments.get("level"),
            keyword=arguments.get("keyword"),
            limit=arguments.get("limit", 100),
        )

    else:
        result = {"error": f"Unknown tool: {name}"}

    return json.dumps(result, default=str, indent=2)


# --- MCP protocol handlers ---

TOOLS = [
    types.Tool(
        name="list_projects",
        description="List all projects with run count and last active time",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="search_runs",
        description="Search runs by name, tags, config values within a project",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "query": {"type": "string", "description": "Fuzzy search across run name, tags, config"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Exact tag match (AND)"},
                "status": {"type": "string", "enum": ["running", "finished", "crashed"]},
                "started_after": {"type": "string", "description": "ISO datetime filter"},
                "started_before": {"type": "string", "description": "ISO datetime filter"},
            },
            "required": ["project"],
        },
    ),
    types.Tool(
        name="get_run_summary",
        description="Pre-computed summary of runs with trends, anomalies, log stats",
        inputSchema={
            "type": "object",
            "properties": {"run_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["run_ids"],
        },
    ),
    types.Tool(
        name="compare_runs",
        description="Side-by-side comparison: config diff, metrics ranking",
        inputSchema={
            "type": "object",
            "properties": {
                "run_ids": {"type": "array", "items": {"type": "string"}},
                "metric_keys": {"type": "array", "items": {"type": "string"}, "description": "Defaults to all shared keys"},
            },
            "required": ["run_ids"],
        },
    ),
    types.Tool(
        name="get_metric_series",
        description="Raw metric time series data",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "key": {"type": "string"},
                "start_step": {"type": "integer"},
                "end_step": {"type": "integer"},
                "downsample": {"type": "integer", "description": "Downsample to N points"},
            },
            "required": ["run_id", "key"],
        },
    ),
    types.Tool(
        name="get_logs",
        description="Text log entries with filtering by level and keyword",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "level": {"type": "string", "enum": ["info", "warning", "error"]},
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["run_id"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    result_text = handle_tool_call(name, arguments)
    return [types.TextContent(type="text", text=result_text)]


# --- SSE transport + Starlette app ---

sse = SseServerTransport("/messages/")


async def handle_sse(request):
    auth = request.headers.get("authorization", "")
    if _api_key and (not auth.startswith("Bearer ") or auth[7:] != _api_key):
        return Response(status_code=401)
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


mcp_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
    ],
)
```

- [ ] **Step 4: Mount MCP in app.py**

Add to `src/intern/server/app.py` in `create_app()`, after the router includes:

```python
    # Mount MCP server
    from intern.server.mcp_server import mcp_app, set_api_key
    set_api_key(api_key)
    app.mount("/mcp", mcp_app)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_mcp.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/intern/server/mcp_server.py src/intern/server/app.py tests/test_mcp.py
git commit -m "feat: MCP server with 6 tools (list, search, summary, compare, series, logs)"
```

---

### Task 7: Logger SDK

**Files:**
- Create: `src/intern/sdk/api.py`
- Create: `src/intern/sdk/client.py`
- Modify: `src/intern/__init__.py`
- Create: `tests/test_sdk.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_sdk.py`:

```python
import pytest
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture
def server(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    app = create_app(db_path=db_path, api_key="test-key")
    return TestClient(app)


@pytest.fixture
def server_url(server):
    # TestClient uses a special base_url
    return server


def test_sdk_api_create_project(server):
    from intern.sdk.api import create_project
    with patch("intern.sdk.api.requests") as mock_req:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "123", "name": "proj"}
        mock_req.post.return_value = mock_resp
        result = create_project("http://localhost:8080", "key", "proj")
        assert result["name"] == "proj"
        mock_req.post.assert_called_once()


def test_sdk_client_buffering():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        # Log fewer than 50 items - should not flush
        for i in range(10):
            run.log({"loss": float(i)}, step=i)
        mock_send.assert_not_called()

        # Manually flush
        run.flush()
        mock_send.assert_called_once()
        points = mock_send.call_args[0][3]
        assert len(points) == 10

        # Clean up timer
        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_client_auto_flush_on_50():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        for i in range(55):
            run.log({"loss": float(i)}, step=i)
        # Should have flushed once at 50, leaving 5 in buffer
        assert mock_send.call_count == 1
        assert len(mock_send.call_args[0][3]) == 50

        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_client_finish():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"), \
         patch("intern.sdk.api.update_run") as mock_update:
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log({"loss": 1.0}, step=0)
        run.finish()
        mock_send.assert_called_once()
        mock_update.assert_called_once_with("http://localhost:8080", "key", "run-1", "finished")


def test_sdk_client_log_text():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics"), \
         patch("intern.sdk.api.send_logs") as mock_logs:
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log_text("hello", level="warning", step=5)
        run.flush()
        mock_logs.assert_called_once()
        entries = mock_logs.call_args[0][3]
        assert len(entries) == 1
        assert entries[0]["level"] == "warning"
        assert entries[0]["content"] == "hello"

        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_module_api():
    import intern
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"), \
         patch("intern.sdk.api.update_run"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = intern.init(project="test", name="run-1", server="http://localhost:8080", api_key="key")
        intern.log({"loss": 1.0}, step=0)
        intern.log_text("hello")
        intern.finish()
        mock_send.assert_called()


def test_sdk_step_auto_increment():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log({"a": 1.0})
        run.log({"a": 2.0})
        run.log({"a": 3.0})
        run.flush()
        points = mock_send.call_args[0][3]
        steps = [p["step"] for p in points]
        assert steps == [0, 1, 2]

        run._finished = True
        if run._timer:
            run._timer.cancel()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sdk.py -v
```

Expected: FAIL (modules not found)

- [ ] **Step 3: Implement sdk/api.py**

Write `src/intern/sdk/api.py`:

```python
import requests


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def create_project(server: str, api_key: str, name: str, description: str = "") -> dict:
    resp = requests.post(f"{server}/api/projects",
                         json={"name": name, "description": description},
                         headers=_headers(api_key))
    return resp.json()


def create_run(server: str, api_key: str, project: str, run_id: str | None,
               name: str | None, config: dict, tags: list[str]) -> dict:
    resp = requests.post(f"{server}/api/projects/{project}/runs",
                         json={"id": run_id, "name": name, "config": config, "tags": tags},
                         headers=_headers(api_key))
    return resp.json()


def define_metric(server: str, api_key: str, run_id: str, key: str, **kwargs):
    requests.post(f"{server}/api/runs/{run_id}/metrics/define",
                  json={"key": key, **kwargs},
                  headers=_headers(api_key))


def send_metrics(server: str, api_key: str, run_id: str, points: list[dict]):
    requests.post(f"{server}/api/runs/{run_id}/metrics",
                  json=points,
                  headers=_headers(api_key))


def send_logs(server: str, api_key: str, run_id: str, entries: list[dict]):
    requests.post(f"{server}/api/runs/{run_id}/logs",
                  json=entries,
                  headers=_headers(api_key))


def update_run(server: str, api_key: str, run_id: str, status: str):
    requests.patch(f"{server}/api/runs/{run_id}",
                   json={"status": status},
                   headers=_headers(api_key))
```

- [ ] **Step 4: Implement sdk/client.py**

Write `src/intern/sdk/client.py`:

```python
import threading
import atexit
from datetime import datetime, timezone

from intern.sdk import api


class Run:
    def __init__(self, server: str, api_key: str, project: str, name: str | None = None,
                 run_id: str | None = None, config: dict | None = None,
                 tags: list[str] | None = None):
        self.server = server
        self.api_key = api_key
        self._step = 0
        self._metric_buffer: list[dict] = []
        self._log_buffer: list[dict] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._finished = False

        api.create_project(server, api_key, project)
        result = api.create_run(server, api_key, project, run_id, name, config or {}, tags or [])
        self.run_id = result["id"]
        self.name = result["name"]

        self._start_flush_timer()
        atexit.register(self._cleanup)

    def define_metric(self, key: str, **kwargs):
        api.define_metric(self.server, self.api_key, self.run_id, key, **kwargs)

    def log(self, data: dict, step: int | None = None):
        if step is None:
            step = self._step
            self._step += 1
        else:
            self._step = step + 1
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for key, value in data.items():
                self._metric_buffer.append({
                    "key": key, "step": step, "value": float(value), "timestamp": now,
                })
            if len(self._metric_buffer) >= 50:
                self._flush_locked()

    def log_text(self, content: str, level: str = "info", step: int | None = None):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._log_buffer.append({
                "step": step, "level": level, "content": content, "timestamp": now,
            })
            if len(self._log_buffer) >= 50:
                self._flush_locked()

    def _flush_locked(self):
        if self._metric_buffer:
            points = list(self._metric_buffer)
            self._metric_buffer.clear()
            api.send_metrics(self.server, self.api_key, self.run_id, points)
        if self._log_buffer:
            entries = list(self._log_buffer)
            self._log_buffer.clear()
            api.send_logs(self.server, self.api_key, self.run_id, entries)

    def flush(self):
        with self._lock:
            self._flush_locked()

    def _start_flush_timer(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(30.0, self._timed_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timed_flush(self):
        self.flush()
        if not self._finished:
            self._start_flush_timer()

    def finish(self):
        self._finished = True
        if self._timer:
            self._timer.cancel()
        self.flush()
        api.update_run(self.server, self.api_key, self.run_id, "finished")

    def _cleanup(self):
        if not self._finished:
            self.flush()
            if self._timer:
                self._timer.cancel()
```

- [ ] **Step 5: Write public SDK API**

Replace `src/intern/__init__.py`:

```python
import os
from intern.sdk.client import Run

_current_run: Run | None = None


def init(project: str, name: str | None = None, config: dict | None = None,
         tags: list[str] | None = None, server: str | None = None,
         api_key: str | None = None, run_id: str | None = None) -> Run:
    global _current_run
    server = server or os.environ.get("INTERN_SERVER", "http://localhost:8080")
    api_key = api_key or os.environ.get("INTERN_API_KEY", "")
    _current_run = Run(server=server, api_key=api_key, project=project,
                       name=name, run_id=run_id, config=config, tags=tags)
    return _current_run


def log(data: dict, step: int | None = None):
    _current_run.log(data, step=step)


def log_text(content: str, level: str = "info", step: int | None = None):
    _current_run.log_text(content, level=level, step=step)


def finish():
    global _current_run
    _current_run.finish()
    _current_run = None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_sdk.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/intern/__init__.py src/intern/sdk/ tests/test_sdk.py
git commit -m "feat: logger SDK with buffered upload, auto-flush, module-level API"
```

---

### Task 8: Web Panel

**Files:**
- Create: `src/intern/server/static/style.css`
- Create: `src/intern/server/templates/base.html`
- Create: `src/intern/server/templates/project_list.html`
- Create: `src/intern/server/templates/run_list.html`
- Create: `src/intern/server/templates/run_detail.html`
- Modify: `src/intern/server/app.py`

- [ ] **Step 1: Create static/style.css**

Write `src/intern/server/static/style.css`:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background: #fafafa;
}

h1 { margin-bottom: 20px; }
h2 { margin-bottom: 16px; }

a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }

nav { margin-bottom: 24px; padding: 12px 0; border-bottom: 1px solid #e5e7eb; }
nav a { margin-right: 16px; font-weight: 500; }

table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { background: #f8fafc; font-weight: 600; font-size: 0.85em; text-transform: uppercase; color: #64748b; }

.badge {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.8em; font-weight: 500;
}
.badge-running { background: #dbeafe; color: #1d4ed8; }
.badge-finished { background: #dcfce7; color: #166534; }
.badge-crashed { background: #fee2e2; color: #991b1b; }

.tag {
    display: inline-block; padding: 2px 8px; margin: 2px;
    background: #f1f5f9; border-radius: 4px; font-size: 0.8em; color: #475569;
}

.config-block { background: #f8fafc; padding: 16px; border-radius: 8px; margin-bottom: 20px; font-family: monospace; font-size: 0.9em; white-space: pre-wrap; }

.chart-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; margin-bottom: 24px; }
.chart-card { background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.chart-card h3 { font-size: 0.95em; margin-bottom: 8px; }

.log-entry { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-family: monospace; font-size: 0.85em; }
.log-entry.warning { background: #fffbeb; }
.log-entry.error { background: #fef2f2; }
.log-level { font-weight: 600; margin-right: 8px; }

.filters { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.filters select, .filters input { padding: 6px 12px; border: 1px solid #d1d5db; border-radius: 6px; }
```

- [ ] **Step 2: Create base template**

Write `src/intern/server/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}my-cheap-intern{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
</head>
<body>
    <nav>
        <a href="/">my-cheap-intern</a>
    </nav>
    {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Create project list template**

Write `src/intern/server/templates/project_list.html`:

```html
{% extends "base.html" %}
{% block title %}Projects — my-cheap-intern{% endblock %}
{% block content %}
<h1>Projects</h1>
<table>
    <thead>
        <tr><th>Project</th><th>Runs</th><th>Last Active</th></tr>
    </thead>
    <tbody>
        {% for p in projects %}
        <tr>
            <td><a href="/project/{{ p.name }}">{{ p.name }}</a></td>
            <td>{{ p.run_count }}</td>
            <td>{{ p.last_active_at or '—' }}</td>
        </tr>
        {% endfor %}
        {% if not projects %}
        <tr><td colspan="3">No projects yet.</td></tr>
        {% endif %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 4: Create run list template**

Write `src/intern/server/templates/run_list.html`:

```html
{% extends "base.html" %}
{% block title %}{{ project.name }} — my-cheap-intern{% endblock %}
{% block content %}
<h1>{{ project.name }}</h1>

<div class="filters">
    <select hx-get="/project/{{ project.name }}" hx-target="body" name="status"
            hx-include="[name='status']" hx-push-url="true">
        <option value="">All statuses</option>
        <option value="running" {% if status_filter == 'running' %}selected{% endif %}>Running</option>
        <option value="finished" {% if status_filter == 'finished' %}selected{% endif %}>Finished</option>
        <option value="crashed" {% if status_filter == 'crashed' %}selected{% endif %}>Crashed</option>
    </select>
</div>

<table>
    <thead>
        <tr><th>Run</th><th>Status</th><th>Tags</th><th>Started</th></tr>
    </thead>
    <tbody>
        {% for r in runs %}
        <tr>
            <td><a href="/run/{{ r.id }}">{{ r.name }}</a></td>
            <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
            <td>{% for t in r.tags %}<span class="tag">{{ t }}</span>{% endfor %}</td>
            <td>{{ r.started_at[:19] }}</td>
        </tr>
        {% endfor %}
        {% if not runs %}
        <tr><td colspan="4">No runs found.</td></tr>
        {% endif %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Create run detail template**

Write `src/intern/server/templates/run_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ run.name }} — my-cheap-intern{% endblock %}
{% block content %}
<h1>{{ run.name }} <span class="badge badge-{{ run.status }}">{{ run.status }}</span></h1>

<h2>Config</h2>
<div class="config-block">{{ config_json }}</div>

<h2>Metrics</h2>
<div class="chart-grid">
    {% for key, series in metrics_data.items() %}
    <div class="chart-card">
        <h3>{{ key }}</h3>
        <canvas id="chart-{{ loop.index }}"></canvas>
    </div>
    {% endfor %}
</div>

<h2>Logs</h2>
<div class="filters">
    <select hx-get="/run/{{ run.id }}" hx-target="body" name="log_level" hx-push-url="true">
        <option value="">All levels</option>
        <option value="info">Info</option>
        <option value="warning">Warning</option>
        <option value="error">Error</option>
    </select>
</div>
<div>
    {% for log in logs %}
    <div class="log-entry {{ log.level }}">
        <span class="log-level">{{ log.level }}</span>
        {% if log.step is not none %}[step {{ log.step }}]{% endif %}
        {{ log.content }}
    </div>
    {% endfor %}
    {% if not logs %}
    <p>No logs.</p>
    {% endif %}
</div>

<script>
{% for key, series in metrics_data.items() %}
new Chart(document.getElementById('chart-{{ loop.index }}'), {
    type: 'line',
    data: {
        labels: {{ series | map(attribute='step') | list | tojson }},
        datasets: [{
            label: '{{ key }}',
            data: {{ series | map(attribute='value') | list | tojson }},
            borderColor: 'rgb(37, 99, 235)',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.1,
        }]
    },
    options: {
        responsive: true,
        scales: { x: { title: { display: true, text: 'step' } } },
        plugins: { legend: { display: false } },
    }
});
{% endfor %}
</script>
{% endblock %}
```

- [ ] **Step 6: Add panel routes to app.py**

Add to `src/intern/server/app.py`, in `create_app()` before `return app`:

```python
    # Web panel routes (no auth)
    from pathlib import Path
    from fastapi import Request
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    import json as _json

    _pkg_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(_pkg_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(_pkg_dir / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def project_list_page(request: Request):
        projects = db.list_projects()
        return templates.TemplateResponse("project_list.html",
                                          {"request": request, "projects": projects})

    @app.get("/project/{name}", response_class=HTMLResponse)
    def run_list_page(request: Request, name: str, status: str | None = None):
        project = db.get_project_by_name(name)
        runs = db.list_runs(project["id"], status=status) if project else []
        return templates.TemplateResponse("run_list.html", {
            "request": request, "project": project, "runs": runs,
            "status_filter": status,
        })

    @app.get("/run/{run_id}", response_class=HTMLResponse)
    def run_detail_page(request: Request, run_id: str, log_level: str | None = None):
        run = db.get_run(run_id)
        metas = db.get_metric_metas(run_id)
        metrics_data = {}
        for meta in metas:
            series = db.get_metric_series(run_id, meta["key"])
            metrics_data[meta["key"]] = series
        logs = db.get_logs(run_id, level=log_level, limit=100)
        return templates.TemplateResponse("run_detail.html", {
            "request": request, "run": run, "metas": metas,
            "metrics_data": metrics_data, "logs": logs,
            "config_json": _json.dumps(run["config"], indent=2),
        })
```

**Important:** The panel routes must be registered **after** the API routers and **before** the MCP mount. The `/static` mount must come before any catch-all routes. Reorder `create_app` so:
1. API routers (prefix `/api`)
2. Panel routes (exact paths `/`, `/project/{name}`, `/run/{run_id}`)
3. MCP mount (`/mcp`)

- [ ] **Step 7: Manual test**

```bash
cd /Users/fang/Documents/WorkSpace/my-cheap-intern
INTERN_API_KEY=test intern-server
```

Open `http://localhost:8080/` in a browser. Verify empty project list renders.

- [ ] **Step 8: Commit**

```bash
git add src/intern/server/templates/ src/intern/server/static/ src/intern/server/app.py
git commit -m "feat: web panel with project list, run list, run detail pages"
```

---

### Task 9: CLI Entry Point + README

**Files:**
- Modify: `src/intern/server/app.py` (already has `main()`)
- Create: `README.md`

- [ ] **Step 1: Verify CLI entry point works**

`main()` is already defined in `app.py` and registered in `pyproject.toml` as `intern-server`. Test it:

```bash
INTERN_API_KEY=test timeout 3 intern-server --help || true
# The server should start (timeout kills it after 3s)
INTERN_API_KEY=test timeout 3 intern-server 2>&1 | head -5
```

Expected: Uvicorn startup output showing server running on port 8080.

- [ ] **Step 2: Create README.md**

Write `README.md`:

```markdown
# my-cheap-intern

AI-native experiment tracking for ML researchers. Like a cheap intern who reads all your dashboards and summarizes them.

## Quick Start

### Install

```bash
pip install my-cheap-intern          # SDK only (training machines)
pip install my-cheap-intern[server]  # Full server
```

### Start Server

```bash
export INTERN_API_KEY=your-secret-key
intern-server
```

Server runs at `http://localhost:8080`. Web panel at `/`, MCP endpoint at `/mcp/sse`.

### Log Experiments

```python
import intern

run = intern.init(
    project="my-project",
    name="experiment-1",
    config={"lr": 1e-5, "epochs": 10},
    tags=["baseline"],
    server="http://your-server:8080",
    api_key="your-secret-key",
)

run.define_metric("loss", direction="lower_better")

for step in range(100):
    intern.log({"loss": compute_loss()}, step=step)

intern.finish()
```

### Connect AI Assistant (MCP)

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "my-cheap-intern": {
      "type": "sse",
      "url": "http://your-server:8080/mcp/sse",
      "headers": { "Authorization": "Bearer your-api-key" }
    }
  }
}
```

## Configuration

| Env Variable | Default | Description |
|---|---|---|
| INTERN_PORT | 8080 | Server port |
| INTERN_API_KEY | (required) | Auth key |
| INTERN_DATA_DIR | ~/.intern | Data directory |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "feat: README"
```

---

### Task 10: Integration Smoke Test

**Files:**
- No new files, verify full stack works end-to-end.

- [ ] **Step 1: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS across all test files.

- [ ] **Step 2: End-to-end smoke test with SDK + server**

Write a quick script and run it:

```bash
cat > /tmp/smoke_test.py << 'PYEOF'
import threading, time
from intern.server.app import create_app
from intern.server.db import init_db
import uvicorn

# Start server in background thread
init_db("/tmp/intern_smoke.db")
app = create_app(db_path="/tmp/intern_smoke.db", api_key="smoke")
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=9999, log_level="error"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
time.sleep(1)

# Use SDK
import intern
run = intern.init(project="smoke-test", name="run-1",
                  config={"lr": 0.001}, tags=["smoke"],
                  server="http://127.0.0.1:9999", api_key="smoke")
run.define_metric("loss", direction="lower_better")
for i in range(20):
    intern.log({"loss": 10.0 / (i + 1)}, step=i)
intern.log_text("All good", level="info", step=19)
intern.finish()

# Query via API
import requests
headers = {"Authorization": "Bearer smoke"}
projects = requests.get("http://127.0.0.1:9999/api/projects", headers=headers).json()
assert len(projects) == 1, f"Expected 1 project, got {len(projects)}"
assert projects[0]["name"] == "smoke-test"

runs = requests.get("http://127.0.0.1:9999/api/projects/smoke-test/runs", headers=headers).json()
assert len(runs) == 1
assert runs[0]["status"] == "finished"

series = requests.get(f"http://127.0.0.1:9999/api/runs/{runs[0]['id']}/metrics/loss", headers=headers).json()
assert len(series) == 20

print("Smoke test PASSED")
server.should_exit = True
PYEOF
.venv/bin/python /tmp/smoke_test.py
```

Expected: `Smoke test PASSED`

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
# Only if changes were made during smoke test
git add -A && git commit -m "fix: smoke test fixes"
```
