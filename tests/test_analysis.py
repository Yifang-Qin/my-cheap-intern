import pytest
from intern.server.analysis import compute_trend, detect_anomalies, compute_metric_stats, compute_log_summary, compute_duration
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


def test_compute_metric_stats_custom_windows(db):
    p = create_project("proj2")
    create_run(p["id"], "r2", "run", {}, [])
    define_metric("r2", "acc", direction="higher_better", description="Accuracy")
    # first 40 points flat, last 10 points increasing
    points = [{"key": "acc", "step": i, "value": 0.5, "timestamp": "2026-01-01T00:00:00"}
              for i in range(40)]
    points += [{"key": "acc", "step": 40 + i, "value": 0.5 + i * 0.05, "timestamp": "2026-01-01T00:00:00"}
               for i in range(10)]
    insert_metric_points("r2", points)

    # default auto window = max(20, 50//2) = 25, covers flat+rising → may be stable
    stats_auto = compute_metric_stats("r2", "acc")
    # trend_window=10 → only last 10 rising points → should be increasing
    stats_recent = compute_metric_stats("r2", "acc", trend_window=10)
    assert stats_recent["trend"] == "increasing"


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


def test_compute_duration_running():
    assert compute_duration("2026-01-01T00:00:00", None) == "running"


def test_compute_duration_minutes():
    assert compute_duration("2026-01-01T00:00:00", "2026-01-01T00:45:00") == "45m"


def test_compute_duration_hours():
    assert compute_duration("2026-01-01T00:00:00", "2026-01-01T02:30:00") == "2h 30m"
