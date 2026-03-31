# my-cheap-intern Design Spec

> AI-native experiment tracking for ML researchers.

**Date:** 2026-04-01
**Status:** Draft

---

## 1. Problem Statement

Current experiment tracking tools (wandb, tensorboard) produce dashboards optimized for human browsing — curves, tables, and logs that require manual inspection. For complex training setups like GRPO, this creates dozens of metrics (clip ratios, reward distributions, loss curves) that demand significant cognitive effort to summarize.

Researchers often end up screenshotting dashboards or manually describing results to AI assistants for analysis. Meanwhile, agentic approaches that let AI browse existing dashboards (e.g., via browser automation) suffer from long, fragile communication chains.

**Core insight:** If experiment data were stored in an AI-queryable format from the start, an AI assistant could generate structured experiment reports in seconds — acting like a cheap intern who reads all your dashboards and summarizes them for you.

## 2. Solution Overview

my-cheap-intern is a self-hosted experiment tracking service with three components:

1. **Logger SDK** — a Python library that researchers call from training scripts to log metrics and text, wire-compatible with wandb's basic API
2. **Server** — a single FastAPI process that stores data in SQLite, serves a lightweight web panel, and exposes an MCP (Model Context Protocol) server
3. **MCP interface** — structured tools that let AI assistants (Claude Code, etc.) query experiment data efficiently

The key differentiator is the MCP layer: instead of AI reading dashboards designed for humans, it queries pre-structured, pre-summarized experiment data through a purpose-built protocol.

### Architecture

```
[Training machines]              [User's server]              [AI consumers]

 training_script.py              ┌──────────────────┐
   intern.init(...)              │  FastAPI Process  │         Claude Code
   intern.log({...})  ──HTTP──>  │  ├─ REST API      │  <─MCP─>  (via MCP)
   intern.log_text()  ──HTTP──>  │  ├─ Web Panel     │
                                 │  ├─ MCP Server    │         Browser
 training_script2.py             │  └─ SQLite DB     │  <─HTTP─> (web panel)
   intern.log({...})  ──HTTP──>  │                   │
                                 └──────────────────┘
```

All three roles (REST API, Web Panel, MCP Server) run in a single process, sharing one SQLite database. One command to start, one port to expose.

## 3. Data Model

### Project

Top-level grouping for experiments.

| Field | Type | Description |
|-------|------|-------------|
| id | str (auto) | Unique identifier |
| name | str | Human-readable name, e.g. "llama3-postrain" |
| description | str (optional) | Project description |
| created_at | datetime | Creation time |

### Run

A single experiment run, belonging to a project.

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique ID, e.g. "llama3-grpo-epsilon0.2-20260401-143022" |
| project_id | str | Parent project |
| name | str | Human-readable name |
| config | JSON | Hyperparameters dict |
| status | enum | running / finished / crashed |
| tags | list[str] | User-defined tags for filtering |
| started_at | datetime | Run start time |
| finished_at | datetime (nullable) | Run end time |

- Config keys are **not required to be uniform** across runs within a project. Different runs may have different config schemas.
- Status transitions: running → finished (explicit call) or running → crashed (heartbeat timeout).

### MetricMeta

Schema-level metadata for a metric key within a run. Optional but recommended — provides semantic information that helps AI interpret results.

| Field | Type | Description |
|-------|------|-------------|
| run_id | str | Parent run |
| key | str | Metric name, e.g. "reward/mean", "clip_ratio" |
| type | enum | scalar / text_summary |
| direction | enum | higher_better / lower_better / neutral |
| description | str (optional) | Human-readable explanation |
| aggregation | enum | last / min / max / mean |

### MetricPoint

A single numeric data point.

| Field | Type | Description |
|-------|------|-------------|
| run_id | str | Parent run |
| key | str | Metric key |
| step | int | Training step |
| value | float | Metric value |
| timestamp | datetime | Recording time |

### LogEntry

A text log entry (bad cases, warnings, debug output).

| Field | Type | Description |
|-------|------|-------------|
| run_id | str | Parent run |
| step | int (optional) | Associated training step |
| level | enum | info / warning / error |
| content | str | Log text |
| timestamp | datetime | Recording time |

## 4. REST API

### Write endpoints (called by Logger SDK)

```
POST   /api/projects                        # Create project
POST   /api/projects/{project}/runs         # Create run (with config, tags)
POST   /api/runs/{run_id}/metrics/define    # Declare metric meta
POST   /api/runs/{run_id}/metrics           # Batch write metric points
POST   /api/runs/{run_id}/logs              # Write log entries
PATCH  /api/runs/{run_id}                   # Update run status (finish/crash)
```

The Logger SDK batches data internally (flush every 30s or 50 records) and sends a single POST per flush. This is transparent to the user.

### Query endpoints (called by Web Panel)

```
GET    /api/projects                        # List all projects
GET    /api/projects/{project}/runs         # List runs (filterable, sortable)
GET    /api/runs/{run_id}                   # Run details (config, status, metric metas)
GET    /api/runs/{run_id}/metrics/{key}     # Metric time series
GET    /api/runs/{run_id}/logs              # Text logs (paginated, filterable by level)
```

### Authentication

Single API key per deployment. Passed as `Authorization: Bearer <key>` header. No multi-user system — one deployment instance, one key.

## 5. MCP Server

The core value proposition. Designed so AI can go from a vague user request to a structured report in minimal round-trips.

### Tools

#### 5.1 `list_projects`

List all projects with summary info.

**Parameters:** none

**Returns:**
```json
[{ "name": "str", "run_count": "int", "last_active_at": "datetime" }]
```

#### 5.2 `search_runs`

Primary entry point for finding experiments. Supports fuzzy search across run names, tags, and config values.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| project | str | yes | Project name |
| query | str | no | Fuzzy search across run name, tags, config values |
| tags | list[str] | no | Exact tag match (AND with query) |
| status | str | no | Filter by status |
| started_after | datetime | no | Time range start |
| started_before | datetime | no | Time range end |

**Returns:**
```json
[{
  "run_id": "str",
  "name": "str",
  "config": {},
  "status": "str",
  "tags": ["str"],
  "started_at": "datetime",
  "metric_keys": ["str"]
}]
```

The `query` parameter matches against:
1. Run name (highest priority)
2. Tags
3. Config values (string representation)

#### 5.3 `get_run_summary`

Pre-computed summary of one or more runs. This is the most frequently used tool — one call gives AI a complete picture of an experiment.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| run_ids | list[str] | yes | One or more run IDs (batch support) |

**Returns (per run):**
```json
{
  "run_id": "str",
  "config": {},
  "status": "finished",
  "duration": "2h 35m",
  "metrics": {
    "reward/mean": {
      "direction": "higher_better",
      "description": "GRPO mean reward",
      "latest": 0.92,
      "min": 0.11,
      "max": 0.95,
      "mean": 0.73,
      "std": 0.18,
      "trend": "increasing",
      "anomaly_steps": [2400, 3100]
    }
  },
  "log_summary": {
    "total": 142,
    "warnings": 7,
    "errors": 0,
    "recent_warnings": ["step 3100: reward outlier ..."]
  }
}
```

Server-side pre-computation includes:
- **trend**: linear regression over the last N points → increasing / decreasing / stable
- **anomaly_steps**: points where value deviates > 3 std from rolling mean

#### 5.4 `compare_runs`

Side-by-side comparison of multiple runs.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| run_ids | list[str] | yes | Runs to compare |
| metric_keys | list[str] | no | Metrics to compare (default: all shared keys) |

**Returns:**
```json
{
  "config_diff": {
    "epsilon": { "run1": 0.2, "run2": 0.5 }
  },
  "metrics_table": {
    "reward/mean": {
      "run1": { "latest": 0.85, "min": 0.1, "max": 0.9, "mean": 0.7, "trend": "increasing" },
      "run2": { "latest": 0.92, "min": 0.2, "max": 0.95, "mean": 0.75, "trend": "increasing" }
    }
  },
  "ranking": {
    "reward/mean": ["run2", "run1"]
  }
}
```

- `config_diff` only includes fields that differ across the compared runs.
- `ranking` respects the `direction` from MetricMeta (higher_better sorts descending).

#### 5.5 `get_metric_series`

Raw time series for deep-dive analysis.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| run_id | str | yes | Run ID |
| key | str | yes | Metric key |
| start_step | int | no | Range start |
| end_step | int | no | Range end |
| downsample | int | no | Downsample to N points |

**Returns:**
```json
[{ "step": 100, "value": 0.85, "timestamp": "datetime" }]
```

#### 5.6 `get_logs`

Text log retrieval with filtering.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| run_id | str | yes | Run ID |
| level | str | no | Filter by level |
| keyword | str | no | Keyword search in content |
| limit | int | no | Max entries to return |

**Returns:**
```json
[{ "step": 100, "level": "warning", "content": "str", "timestamp": "datetime" }]
```

### Typical AI Query Flow

User: "Summarize yesterday's clip epsilon experiments"

```
1. search_runs(project="llama3-postrain", started_after="2026-03-31", query="epsilon")
   → 8 matching runs

2. get_run_summary(run_ids=["run1", "run2", ..., "run8"])
   → 8 structured summaries with trends and anomalies

3. compare_runs(run_ids=[...], metric_keys=["reward/mean", "clip_ratio"])
   → config diff + metrics table + ranking

4. get_logs(run_id="run3", level="warning")  # only if anomalies detected
   → specific warning messages

→ AI generates report (4 MCP calls total)
```

## 6. Web Panel

Lightweight dashboard for human browsing. Not intended to replace AI-driven analysis.

### Pages

**`/` — Project list**
- Table: project name, run count, last active time

**`/project/{name}` — Run list**
- Table: run name, status, tags, started_at, duration
- Filters: status dropdown, tag filter, time range picker

**`/run/{run_id}` — Run detail**
- Top: config (collapsible JSON), status badge, timing info
- Middle: metric charts (one small chart per metric key)
- Bottom: text logs (reverse chronological, level filter)

### Tech

- **Jinja2** templates (server-side rendering, built into FastAPI)
- **HTMX** for filtering, pagination, partial page updates without JS
- **Chart.js** via CDN for metric curves

Zero build step. No node_modules. No frontend framework.

### Explicitly out of scope

- Real-time WebSocket push (manual refresh or HTMX polling is sufficient)
- Drag-and-drop dashboard layout customization
- Visual run comparison (this is AI's job)
- User management / permissions

## 7. Logger SDK

### Installation

```bash
pip install my-cheap-intern          # SDK only (for training machines)
pip install my-cheap-intern[server]  # SDK + server (for the host machine)
```

### API

```python
import intern

# Initialize a run
run = intern.init(
    project="llama3-postrain",
    name="grpo-epsilon0.2",           # optional, auto-generated if omitted
    config={"lr": 1e-5, "epsilon": 0.2},
    tags=["grpo", "epsilon-sweep"],
    server="http://your-server:8080", # or INTERN_SERVER env var
    api_key="xxx",                    # or INTERN_API_KEY env var
)

# Declare metric metadata (optional, improves AI analysis)
run.define_metric("reward/mean", direction="higher_better",
                  description="GRPO mean reward")

# Log numeric metrics
run.log({"reward/mean": 0.85, "clip_ratio": 0.15, "loss": 1.23}, step=100)

# Log text (bad cases, debug output, etc.)
run.log_text("reward outlier: prompt='xxx', reward=-10.5",
             level="warning", step=100)

# Finish run
run.finish()
```

### Internal behavior

- **Buffered upload**: SDK queues data internally, flushes every 30 seconds or when buffer reaches 50 records.
- **atexit hook**: Auto-flush + finish on process exit.
- **Crash detection**: If process exits without calling `finish()`, server marks run as crashed after heartbeat timeout (5 minutes of no data).
- **Offline tolerance**: SDK does not raise exceptions when server is unreachable. Logs a warning, buffers locally, and retries on reconnection.

### Migration from wandb

The SDK deliberately mirrors wandb's basic API:

```python
# Before                          # After
import wandb                      import intern
wandb.init(project=..., config=.) intern.init(project=..., config=...)
wandb.log({"loss": 1.0})          intern.log({"loss": 1.0})
wandb.finish()                    intern.finish()
```

`define_metric` and `log_text` are additional capabilities, not required for basic usage.

## 8. Deployment

### Option A: pip install (recommended)

```bash
pip install my-cheap-intern[server]
intern-server --port 8080 --api-key "your-key"
```

First launch auto-creates SQLite database at `~/.intern/data.db`.

### Option B: Docker

```bash
docker run -p 8080:8080 -v ~/.intern:/data -e INTERN_API_KEY=xxx my-cheap-intern
```

### Configuration

All via environment variables or CLI flags. No config file needed.

| Variable | Default | Description |
|----------|---------|-------------|
| INTERN_PORT | 8080 | Server port |
| INTERN_API_KEY | (required) | Authentication key |
| INTERN_DATA_DIR | ~/.intern | SQLite file location |
| INTERN_MCP_ENABLED | true | Enable MCP endpoint |

### MCP client configuration

For Claude Code, add to MCP settings:

```json
{
  "mcpServers": {
    "my-cheap-intern": {
      "type": "sse",
      "url": "http://your-server:8080/mcp",
      "headers": { "Authorization": "Bearer your-api-key" }
    }
  }
}
```

## 9. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Target users are Python ML researchers |
| Web framework | FastAPI | Async, performant, mature ecosystem |
| Database | SQLite | Zero-dependency, single file, sufficient for personal/team scale |
| DB access | Raw SQL (no ORM) | Simple schema, ORM adds unnecessary abstraction |
| Frontend | Jinja2 + HTMX + Chart.js | Zero build step, no node_modules |
| MCP | mcp Python SDK | Official SDK, integrates within FastAPI process |
| Logger SDK | Pure Python + requests | Minimal dependencies |
| Dev tooling | uv + venv + pyproject.toml | Modern Python project management |

## 10. Project Structure

```
my-cheap-intern/
├── src/
│   └── intern/
│       ├── __init__.py              # Logger SDK public API
│       ├── sdk/
│       │   ├── client.py            # Run class, buffer, flush logic
│       │   └── api.py               # HTTP communication layer
│       ├── server/
│       │   ├── app.py               # FastAPI application entry point
│       │   ├── routes/
│       │   │   ├── ingest.py        # Write endpoints (SDK calls)
│       │   │   └── query.py         # Query endpoints (Web Panel)
│       │   ├── mcp_server.py        # MCP tools definition
│       │   ├── db.py                # SQLite operations
│       │   ├── analysis.py          # Trend computation, anomaly detection
│       │   ├── templates/           # Jinja2 templates
│       │   └── static/              # CSS, Chart.js
│       └── common/
│           └── models.py            # Shared data structures (Pydantic)
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

SDK and Server share the `intern` package but have separate dependencies:
- `pip install my-cheap-intern` — installs SDK only (requests)
- `pip install my-cheap-intern[server]` — adds FastAPI, uvicorn, jinja2, mcp SDK
