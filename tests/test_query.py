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
