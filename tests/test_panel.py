def test_project_list_page(client, sample_project):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "test-project" in resp.text


def test_run_list_page(client, sample_run):
    resp = client.get("/project/test-project")
    assert resp.status_code == 200
    assert "test-run" in resp.text


def test_run_list_page_status_filter(client, sample_run):
    resp = client.get("/project/test-project?status=finished")
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

    resp = client.get(f"/run/{run_id}")
    assert resp.status_code == 200
    assert "test-run" in resp.text
    assert "loss" in resp.text
    assert "0.001" in resp.text  # config lr value
    assert "started training" in resp.text
