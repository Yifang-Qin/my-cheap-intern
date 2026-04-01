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


def test_auth_wrong_token(db_path):
    from fastapi.testclient import TestClient
    from intern.server.app import create_app
    app = create_app(db_path=db_path, api_key="secret")
    bad_auth = TestClient(app, headers={"Authorization": "Bearer wrong-key"})
    resp = bad_auth.post("/api/projects", json={"name": "x"})
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


def test_write_metrics_then_read_back(client, sample_run):
    """写入 metric points 后通过 db 层验证数据真正落盘"""
    from intern.server import db
    client.post(
        f"/api/runs/{sample_run['id']}/metrics",
        json=[
            {"key": "loss", "step": 1, "value": 2.0},
            {"key": "loss", "step": 2, "value": 1.5},
        ],
    )
    series = db.get_metric_series(sample_run["id"], "loss")
    assert len(series) == 2
    assert series[0]["value"] == 2.0
    assert series[1]["value"] == 1.5


def test_write_logs_then_read_back(client, sample_run):
    """写入 logs 后通过 db 层验证数据真正落盘"""
    from intern.server import db
    client.post(
        f"/api/runs/{sample_run['id']}/logs",
        json=[
            {"level": "info", "content": "Started training", "step": 0},
            {"level": "error", "content": "OOM", "step": 10},
        ],
    )
    logs = db.get_logs(sample_run["id"])
    assert len(logs) == 2
    contents = {log["content"] for log in logs}
    assert "Started training" in contents
    assert "OOM" in contents


def test_update_run_status(client, sample_run):
    resp = client.patch(
        f"/api/runs/{sample_run['id']}",
        json={"status": "finished"},
    )
    assert resp.status_code == 200


def test_update_run_status_sets_finished_at(client, sample_run):
    """通过路由 PATCH 后验证 finished_at 被正确写入"""
    from intern.server import db
    client.patch(
        f"/api/runs/{sample_run['id']}",
        json={"status": "finished"},
    )
    run = db.get_run(sample_run["id"])
    assert run["status"] == "finished"
    assert run["finished_at"] is not None
