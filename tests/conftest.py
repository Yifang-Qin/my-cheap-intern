import pytest
from fastapi.testclient import TestClient
from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def client(db_path):
    app = create_app(db_path=db_path, api_key="test-key")
    return TestClient(app, headers={"Authorization": "Bearer test-key"})


@pytest.fixture
def sample_project(client):
    resp = client.post("/api/projects", json={"name": "test-project", "description": "Test"})
    return resp.json()


@pytest.fixture
def sample_run(client, sample_project):
    resp = client.post(
        f"/api/projects/{sample_project['name']}/runs",
        json={"name": "test-run", "config": {"lr": 0.001}, "tags": ["test"]},
    )
    return resp.json()
