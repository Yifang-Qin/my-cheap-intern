"""Concurrent write tests — verify SQLite handles multiple SDK writers."""
import threading
import time
import os
import requests
import uvicorn
import pytest

from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture(scope="module")
def concurrent_server():
    """Start a real server for concurrent tests."""
    db_path = "/tmp/intern_concurrent.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    app = create_app(db_path=db_path, api_key="conc")
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19877, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:19877"
    srv.should_exit = True


def _run_writer(server_url: str, project: str, run_name: str, n_steps: int, errors: list):
    """Worker that creates a run and writes metrics."""
    try:
        from intern.sdk.client import Run
        run = Run(server=server_url, api_key="conc", project=project,
                  name=run_name, config={"worker": run_name}, tags=["concurrent"])
        for i in range(n_steps):
            run.log({"loss": float(n_steps - i)}, step=i)
        run.finish()
    except Exception as e:
        errors.append((run_name, e))


class TestConcurrentWrites:
    def test_5_writers_same_project(self, concurrent_server):
        """5 concurrent SDK writers to the same project should all succeed."""
        errors = []
        threads = []
        n_writers = 5
        n_steps = 20

        for i in range(n_writers):
            t = threading.Thread(target=_run_writer,
                                 args=(concurrent_server, "conc-project", f"writer-{i}", n_steps, errors))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Writer errors: {errors}"

        # Verify all runs exist
        headers = {"Authorization": "Bearer conc"}
        runs = requests.get(f"{concurrent_server}/api/projects/conc-project/runs",
                            headers=headers).json()
        assert len(runs) == n_writers

        # Verify each run has correct number of metric points
        for run in runs:
            series = requests.get(f"{concurrent_server}/api/runs/{run['id']}/metrics/loss",
                                  headers=headers).json()
            assert len(series) == n_steps, f"Run {run['id']} has {len(series)} points, expected {n_steps}"

    def test_3_writers_different_projects(self, concurrent_server):
        """3 concurrent writers to different projects."""
        errors = []
        threads = []

        for i in range(3):
            t = threading.Thread(target=_run_writer,
                                 args=(concurrent_server, f"proj-{i}", f"run-{i}", 10, errors))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Writer errors: {errors}"

        headers = {"Authorization": "Bearer conc"}
        projects = requests.get(f"{concurrent_server}/api/projects", headers=headers).json()
        proj_names = {p["name"] for p in projects}
        assert {"proj-0", "proj-1", "proj-2"}.issubset(proj_names)
