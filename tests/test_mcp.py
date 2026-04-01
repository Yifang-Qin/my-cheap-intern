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
