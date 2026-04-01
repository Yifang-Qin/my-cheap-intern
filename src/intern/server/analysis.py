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
        threshold = abs(y_mean) * 0.01
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
        deviation = abs(values[i] - mean)
        if (std > 0 and deviation > 3 * std) or (std == 0 and deviation > 0):
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
