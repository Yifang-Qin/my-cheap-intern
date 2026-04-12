TOKEN = "test-key"


def test_project_list_page(client, sample_project):
    resp = client.get(f"/?token={TOKEN}")
    assert resp.status_code == 200
    assert "test-project" in resp.text


def test_panel_requires_auth(client, sample_project):
    resp = client.get("/")
    assert resp.status_code == 401


def test_panel_cookie_auth(client, sample_project):
    # First request with token sets cookie
    resp = client.get(f"/?token={TOKEN}")
    assert resp.status_code == 200
    # Subsequent request uses cookie (TestClient persists cookies)
    resp = client.get("/")
    assert resp.status_code == 200


def test_run_list_page(client, sample_run):
    resp = client.get(f"/project/test-project?token={TOKEN}")
    assert resp.status_code == 200
    assert "test-run" in resp.text


def test_run_list_page_status_filter(client, sample_run):
    resp = client.get(f"/project/test-project?status=finished&token={TOKEN}")
    assert resp.status_code == 200
    # run is still "running", so it should not appear
    assert "test-run" not in resp.text


def test_run_detail_page(client, sample_run):
    # Add some metrics and logs so the detail page has data to render
    run_id = sample_run["id"]
    client.post(f"/api/runs/{run_id}/metrics/define", json={"key": "loss", "direction": "lower_better"})
    client.post(f"/api/runs/{run_id}/metrics", json=[
        {"key": "loss", "step": 0, "value": 1.0, "timestamp": "2026-01-01T00:00:00Z"},
        {"key": "loss", "step": 1, "value": 0.5, "timestamp": "2026-01-01T00:01:00Z"},
    ])
    client.post(f"/api/runs/{run_id}/logs", json=[
        {"step": 0, "level": "info", "content": "started training", "timestamp": "2026-01-01T00:00:00Z"},
    ])

    resp = client.get(f"/run/{run_id}?token={TOKEN}")
    assert resp.status_code == 200
    assert "test-run" in resp.text
    assert "loss" in resp.text
    assert "0.001" in resp.text  # config lr value
    assert "started training" in resp.text


def test_run_list_search_by_name(client, sample_run):
    resp = client.get(f"/project/test-project?q=test-run&token={TOKEN}")
    assert resp.status_code == 200
    assert "test-run" in resp.text


def test_run_list_search_no_match(client, sample_run):
    resp = client.get(f"/project/test-project?q=nonexistent&token={TOKEN}")
    assert resp.status_code == 200
    assert "test-run" not in resp.text
    assert "No runs found" in resp.text


def test_run_list_search_with_status_filter(client, sample_run):
    # search matches name but status doesn't match -> no results
    resp = client.get(f"/project/test-project?q=test-run&status=finished&token={TOKEN}")
    assert resp.status_code == 200
    assert "No runs found" in resp.text
