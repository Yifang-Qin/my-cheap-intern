---
name: intern-reader
description: "Guide for querying experiment data via my-cheap-intern MCP tools. Use when analyzing experiments, comparing runs, summarizing results, or investigating training issues."
---

# my-cheap-intern Experiment Reader

Query experiment data through 6 MCP tools. Requires MCP connection to the intern server.

## MCP Tools Reference

### list_projects
List all projects with run count and last active time.

No parameters.

### search_runs
Search runs within a project.

| Param | Type | Required | Description |
|---|---|---|---|
| `project` | string | yes | Project name |
| `query` | string | no | Fuzzy search across run name, tags, config values |
| `tags` | string[] | no | Exact tag match (AND logic) |
| `status` | enum | no | `"running"` / `"finished"` / `"crashed"` |
| `started_after` | string | no | ISO datetime |
| `started_before` | string | no | ISO datetime |

### get_run_summary
Pre-computed summary with trends, anomalies, log stats.

| Param | Type | Required | Description |
|---|---|---|---|
| `run_ids` | string[] | yes | One or more run IDs |

Returns per run: config, status, duration, metrics (last/min/max/mean + trend direction), log_summary.

### compare_runs
Side-by-side comparison: config diff + metrics ranking.

| Param | Type | Required | Description |
|---|---|---|---|
| `run_ids` | string[] | yes | Two or more run IDs |
| `metric_keys` | string[] | no | Defaults to all shared metric keys |

Returns: config_diff (only differing keys), metrics_table, ranking.

### get_metric_series
Raw time series data for one metric.

| Param | Type | Required | Description |
|---|---|---|---|
| `run_id` | string | yes | Single run ID |
| `key` | string | yes | Metric key name |
| `start_step` | int | no | Filter by step range |
| `end_step` | int | no | Filter by step range |
| `downsample` | int | no | Downsample to N points |

### get_logs
Text log entries with filtering.

| Param | Type | Required | Description |
|---|---|---|---|
| `run_id` | string | yes | Single run ID |
| `level` | enum | no | `"info"` / `"warning"` / `"error"` |
| `keyword` | string | no | Substring search |
| `limit` | int | no | Default 100 |

## Common Query Patterns

**"Show me today's experiments"**
1. `list_projects` to find the project name
2. `search_runs(project=..., started_after="2026-04-01T00:00:00")` to get today's runs
3. `get_run_summary(run_ids=[...])` for overview with trends

**"Compare two runs"**
1. `compare_runs(run_ids=[id1, id2])` for config diff and metrics ranking
2. If deeper look needed: `get_metric_series` for specific curves

**"Is this run overfitting?"**
1. `get_run_summary(run_ids=[id])` — check if train_loss trend is "decreasing" but val_loss trend is "increasing"
2. `get_metric_series(run_id=id, key="train_loss")` and `get_metric_series(run_id=id, key="val_loss")` for the raw curves

**"What went wrong with this crashed run?"**
1. `get_run_summary(run_ids=[id])` — check status and duration
2. `get_logs(run_id=id, level="error")` — find error messages
3. `get_logs(run_id=id, keyword="nan")` — check for NaN issues

**"Find the best run for a given metric"**
1. `search_runs(project=..., status="finished")` — get all finished runs
2. `compare_runs(run_ids=[...], metric_keys=["val_acc"])` — ranking will show the best
