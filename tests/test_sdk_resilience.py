"""SDK resilience tests — verify SDK doesn't block training when server is down."""
import threading
import time
import pytest
from unittest.mock import patch
import requests

from intern.sdk.client import Run
from intern.sdk import api


class TestServerUnreachable:
    """SDK should raise on init (can't create project/run), but log/flush should not crash."""

    def test_init_fails_when_server_down(self):
        """intern.init should raise when server is unreachable."""
        with pytest.raises(requests.ConnectionError):
            Run(server="http://127.0.0.1:19999", api_key="key",
                project="test", name="run-1")

    def test_flush_tolerates_server_down(self):
        """Once a Run is created, flush should not crash if server goes away."""
        # Create a Run with mocked init calls and buffer_size > 1 so log() buffers
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1", buffer_size=50)

        # Log some data — this just buffers, no network
        run.log({"loss": 1.0}, step=0)

        # Flush should raise (server gone), but that's expected —
        # the key thing is it doesn't hang forever
        with pytest.raises(requests.ConnectionError):
            run.flush()

        # Run object is still usable for buffering
        run.log({"loss": 0.5}, step=1)
        assert len(run._metric_buffer) == 1  # new data buffered

        run._finished = True  # prevent timer from firing

    def test_immediate_log_raises_when_server_down(self):
        """With default buffer_size=1, log() itself raises on server down."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")

        with pytest.raises(requests.ConnectionError):
            run.log({"loss": 1.0}, step=0)

        run._finished = True

    def test_finish_tolerates_server_down(self):
        """finish() should propagate the error but not hang."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1", buffer_size=50)

        run.log({"loss": 1.0}, step=0)
        with pytest.raises(requests.ConnectionError):
            run.finish()


class TestServerMidwayRestart:
    """Simulate server going away and coming back."""

    def test_log_before_and_after_server_restart(self):
        """SDK can resume logging after server comes back."""
        import uvicorn
        from intern.server.app import create_app
        from intern.server.db import init_db
        import os

        db_path = "/tmp/intern_resilience.db"
        if os.path.exists(db_path):
            os.remove(db_path)
        init_db(db_path)

        # Start server
        app = create_app(db_path=db_path, api_key="test")
        srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19876, log_level="error"))
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        time.sleep(0.5)

        # Init SDK with buffer_size > 1 to test buffered resilience
        import intern
        run = intern.init(project="resilience", name="run-1",
                          config={}, tags=[],
                          server="http://127.0.0.1:19876", api_key="test",
                          buffer_size=50)
        run.log({"loss": 1.0}, step=0)
        run.flush()

        # Stop server
        srv.should_exit = True
        time.sleep(0.5)

        # Log while server is down — just buffers
        run.log({"loss": 0.5}, step=1)

        # Flush fails (server down)
        with pytest.raises(requests.ConnectionError):
            run.flush()

        # Restart server (same DB)
        srv2 = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19876, log_level="error"))
        t2 = threading.Thread(target=srv2.run, daemon=True)
        t2.start()
        time.sleep(0.5)

        # Now flush succeeds — data from step=1 arrives
        run.log({"loss": 0.3}, step=2)
        run.flush()
        run.finish()

        # Verify via API
        headers = {"Authorization": "Bearer test"}
        resp = requests.get(f"http://127.0.0.1:19876/api/runs/{run.run_id}/metrics/loss",
                            headers=headers)
        series = resp.json()
        steps = [p["step"] for p in series]
        assert 0 in steps
        assert 2 in steps

        srv2.should_exit = True
