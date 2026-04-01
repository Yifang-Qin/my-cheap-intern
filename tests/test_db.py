import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from intern.server.db import (
    init_db, create_project, get_project_by_name, list_projects,
    create_run, get_run, list_runs, update_run_status, search_runs,
    define_metric, insert_metric_points, get_metric_series, get_metric_metas,
    insert_logs, get_logs, STALE_TIMEOUT,
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


def test_search_runs_status_filter(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "run-1", {}, [])
    create_run(p["id"], "r2", "run-2", {}, [])
    update_run_status("r1", "finished")

    results = search_runs(p["id"], status="finished")
    assert len(results) == 1
    assert results[0]["id"] == "r1"

    results = search_runs(p["id"], status="running")
    assert len(results) == 1
    assert results[0]["id"] == "r2"


def test_search_runs_time_filter(db):
    p = create_project("proj")
    create_run(p["id"], "r1", "old-run", {}, [])
    create_run(p["id"], "r2", "new-run", {}, [])

    # 两个 run 都是刚创建的，用一个未来时间做 started_before 应该都命中
    results = search_runs(p["id"], started_before="2099-01-01T00:00:00")
    assert len(results) == 2

    # 用一个未来时间做 started_after 应该都不命中
    results = search_runs(p["id"], started_after="2099-01-01T00:00:00")
    assert len(results) == 0


def test_get_run_nonexistent(db):
    assert get_run("no-such-id") is None


def test_update_run_sets_finished_at(db):
    p = create_project("proj")
    r = create_run(p["id"], "r1", "run", {}, [])
    assert r["finished_at"] is None

    update_run_status("r1", "finished")
    updated = get_run("r1")
    assert updated["status"] == "finished"
    assert updated["finished_at"] is not None

    # crashed 也应该写 finished_at
    create_run(p["id"], "r2", "run-2", {}, [])
    update_run_status("r2", "crashed")
    crashed = get_run("r2")
    assert crashed["finished_at"] is not None


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


# --- Stale run detection (lazy crash check) ---

def test_stale_run_marked_crashed_on_get(db):
    """A running run with no recent activity is auto-marked as crashed."""
    p = create_project("proj")
    r = create_run(p["id"], "r1", "run", {}, [])
    old_ts = (datetime.now(timezone.utc) - STALE_TIMEOUT - timedelta(minutes=1)).isoformat()
    insert_metric_points("r1", [{"key": "loss", "step": 0, "value": 1.0, "timestamp": old_ts}])

    fetched = get_run("r1")
    assert fetched["status"] == "crashed"
    assert fetched["finished_at"] is not None


def test_active_run_stays_running(db):
    """A running run with recent activity is NOT marked as crashed."""
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    fresh_ts = datetime.now(timezone.utc).isoformat()
    insert_metric_points("r1", [{"key": "loss", "step": 0, "value": 1.0, "timestamp": fresh_ts}])

    fetched = get_run("r1")
    assert fetched["status"] == "running"


def test_stale_run_detected_in_list_runs(db):
    """list_runs also detects stale running runs."""
    p = create_project("proj")
    create_run(p["id"], "r1", "run-1", {}, [])
    create_run(p["id"], "r2", "run-2", {}, [])
    old_ts = (datetime.now(timezone.utc) - STALE_TIMEOUT - timedelta(minutes=1)).isoformat()
    insert_metric_points("r1", [{"key": "loss", "step": 0, "value": 1.0, "timestamp": old_ts}])
    fresh_ts = datetime.now(timezone.utc).isoformat()
    insert_metric_points("r2", [{"key": "loss", "step": 0, "value": 1.0, "timestamp": fresh_ts}])

    runs = list_runs(p["id"])
    by_id = {r["id"]: r for r in runs}
    assert by_id["r1"]["status"] == "crashed"
    assert by_id["r2"]["status"] == "running"


def test_stale_run_no_data_uses_started_at(db):
    """A running run with no metrics/logs falls back to started_at for staleness."""
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    # started_at is now(), which is fresh — should stay running
    fetched = get_run("r1")
    assert fetched["status"] == "running"


def test_finished_run_not_rechecked(db):
    """A finished run is never re-evaluated for staleness."""
    p = create_project("proj")
    create_run(p["id"], "r1", "run", {}, [])
    update_run_status("r1", "finished")
    old_ts = (datetime.now(timezone.utc) - STALE_TIMEOUT - timedelta(minutes=10)).isoformat()
    insert_metric_points("r1", [{"key": "loss", "step": 0, "value": 1.0, "timestamp": old_ts}])

    fetched = get_run("r1")
    assert fetched["status"] == "finished"
