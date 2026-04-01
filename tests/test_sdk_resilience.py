"""SDK resilience tests — verify SDK never blocks training when server is down."""
import threading
import time
import warnings
import pytest
from unittest.mock import patch

from intern.sdk.client import Run
from intern.sdk import api


class TestServerUnreachable:
    """When server is unreachable at init, SDK enters offline mode silently."""

    def test_init_offline_when_server_down(self):
        """intern.init should not raise, just warn and go offline."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        assert run._offline is True
        assert len(w) == 1
        assert "offline" in str(w[0].message).lower()

    def test_log_noop_when_offline(self):
        """log() should silently do nothing when offline."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        # These should not raise
        run.log({"loss": 1.0}, step=0)
        run.log({"loss": 0.5}, step=1)
        run.log_text("hello")
        assert run._metric_buffer == []
        assert run._log_buffer == []

    def test_flush_noop_when_offline(self):
        """flush() should silently do nothing when offline."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        run.flush()  # should not raise

    def test_finish_noop_when_offline(self):
        """finish() should silently do nothing when offline."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        run.finish()  # should not raise

    def test_define_metric_noop_when_offline(self):
        """define_metric() should silently do nothing when offline."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        run.define_metric("loss")  # should not raise

    def test_step_counter_still_works_offline(self):
        """Step counter should still increment even when offline."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")
        run.log({"loss": 1.0})
        run.log({"loss": 0.5})
        assert run._step == 2


class TestMidwayFailure:
    """When server goes down mid-run, SDK enters offline mode on first failure."""

    def test_flush_goes_offline_on_network_error(self):
        """If flush fails, SDK goes offline and subsequent calls are no-ops."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1", buffer_size=50)

        assert run._offline is False
        run.log({"loss": 1.0}, step=0)
        assert len(run._metric_buffer) == 1

        # Flush hits unreachable server — should warn, not raise
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run.flush()
        assert run._offline is True
        assert len(w) == 1

        # Subsequent log is a no-op
        run.log({"loss": 0.5}, step=1)
        assert run._metric_buffer == []

        run._finished = True

    def test_immediate_log_goes_offline_on_error(self):
        """With buffer_size=1, log() triggers flush which goes offline."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run.log({"loss": 1.0}, step=0)
        assert run._offline is True

        # Second log is silent no-op
        run.log({"loss": 0.5}, step=1)
        run._finished = True

    def test_finish_goes_offline_on_error(self):
        """finish() should not raise even if server is gone."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1", buffer_size=50)

        run.log({"loss": 1.0}, step=0)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run.finish()
        assert run._offline is True
        assert run._finished is True

    def test_define_metric_goes_offline_on_error(self):
        """define_metric() should not raise if server is gone."""
        with patch.object(api, "create_project", return_value={}), \
             patch.object(api, "create_run", return_value={"id": "r1", "name": "run-1"}):
            run = Run(server="http://127.0.0.1:19999", api_key="key",
                      project="test", name="run-1")

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            run.define_metric("loss")
        assert run._offline is True
        run._finished = True


class TestServerMidwayRestart:
    """Integration test: init succeeds, server dies, SDK goes offline gracefully."""

    def test_log_before_and_after_server_down(self):
        import uvicorn
        from intern.server.app import create_app
        from intern.server.db import init_db
        import os
        import requests

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

        # Init SDK — succeeds
        import intern
        run = intern.init(project="resilience", name="run-1",
                          config={}, tags=[],
                          server="http://127.0.0.1:19876", api_key="test",
                          buffer_size=50)
        run.log({"loss": 1.0}, step=0)
        run.flush()
        assert run._offline is False

        # Stop server
        srv.should_exit = True
        time.sleep(0.5)

        # Log while server is down — just buffers
        run.log({"loss": 0.5}, step=1)

        # Flush goes offline silently
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run.flush()
        assert run._offline is True

        # Subsequent operations are no-ops
        run.log({"loss": 0.3}, step=2)
        run.finish()

        # Verify step 0 data was persisted before server died
        # Restart server to check
        srv2 = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19876, log_level="error"))
        t2 = threading.Thread(target=srv2.run, daemon=True)
        t2.start()
        time.sleep(0.5)

        headers = {"Authorization": "Bearer test"}
        resp = requests.get(f"http://127.0.0.1:19876/api/runs/{run.run_id}/metrics/loss",
                            headers=headers)
        series = resp.json()
        steps = [p["step"] for p in series]
        assert 0 in steps
        # step 1 and 2 were lost (server was down, then offline) — expected
        assert 2 not in steps

        srv2.should_exit = True
