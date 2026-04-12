"""Tests for delete cascade: delete_run and delete_project clean up all related data."""

import pytest
from intern.server import db


@pytest.fixture(autouse=True)
def setup_db(db_path):
    db._db_path = db_path


def _create_run_with_data(project_id, run_name):
    """Helper: create a run with metrics and logs, return run_id."""
    run = db.create_run(project_id, run_id=None, name=run_name, config={"lr": 0.01}, tags=["t1"])
    rid = run["id"]
    db.define_metric(rid, "loss", type="scalar", direction="minimize")
    db.insert_metric_points(rid, [
        {"key": "loss", "step": 1, "value": 0.9},
        {"key": "loss", "step": 2, "value": 0.7},
    ])
    db.insert_logs(rid, [
        {"step": 1, "level": "info", "content": "started"},
        {"step": 2, "level": "warning", "content": "slow"},
    ])
    return rid


# --- delete_run ---

def test_delete_run_clears_all_related_data():
    pid = db.create_project("proj-del-run")["id"]
    rid = _create_run_with_data(pid, "run-to-delete")

    db.delete_run(rid)

    assert db.get_run(rid) is None
    assert db.get_metric_series(rid, "loss") == []
    assert db.get_metric_metas(rid) == []
    assert db.get_logs(rid) == []


def test_delete_run_nonexistent_is_idempotent():
    db.delete_run("nonexistent-run-id")


def test_delete_run_does_not_affect_other_runs():
    pid = db.create_project("proj-isolation")["id"]
    rid_keep = _create_run_with_data(pid, "run-keep")
    rid_del = _create_run_with_data(pid, "run-delete")

    db.delete_run(rid_del)

    # kept run is intact
    assert db.get_run(rid_keep) is not None
    assert len(db.get_metric_series(rid_keep, "loss")) == 2
    assert len(db.get_metric_metas(rid_keep)) == 1
    assert len(db.get_logs(rid_keep)) == 2


# --- delete_project ---

def test_delete_project_clears_all_runs_and_data():
    pid = db.create_project("proj-to-delete")["id"]
    rid1 = _create_run_with_data(pid, "run1")
    rid2 = _create_run_with_data(pid, "run2")

    db.delete_project(pid)

    assert db.list_runs(pid) == []
    for rid in (rid1, rid2):
        assert db.get_run(rid) is None
        assert db.get_metric_series(rid, "loss") == []
        assert db.get_metric_metas(rid) == []
        assert db.get_logs(rid) == []


def test_delete_project_nonexistent_is_idempotent():
    db.delete_project("nonexistent-project-id")


def test_delete_project_does_not_affect_other_projects():
    pid_keep = db.create_project("proj-keep")["id"]
    rid_keep = _create_run_with_data(pid_keep, "run-keep")

    pid_del = db.create_project("proj-del")["id"]
    _create_run_with_data(pid_del, "run-del")

    db.delete_project(pid_del)

    # kept project and its run are intact
    assert db.get_run(rid_keep) is not None
    assert len(db.get_metric_series(rid_keep, "loss")) == 2
    assert len(db.get_logs(rid_keep)) == 2
    assert len(db.list_runs(pid_keep)) == 1
