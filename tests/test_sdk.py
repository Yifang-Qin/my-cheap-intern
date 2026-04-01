import pytest
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture
def server(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    app = create_app(db_path=db_path, api_key="test-key")
    return TestClient(app)


@pytest.fixture
def server_url(server):
    # TestClient uses a special base_url
    return server


def test_sdk_api_create_project(server):
    from intern.sdk.api import create_project
    with patch("intern.sdk.api.requests") as mock_req:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "123", "name": "proj"}
        mock_req.post.return_value = mock_resp
        result = create_project("http://localhost:8080", "key", "proj")
        assert result["name"] == "proj"
        mock_req.post.assert_called_once()


def test_sdk_client_buffering():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        # Log fewer than 50 items - should not flush
        for i in range(10):
            run.log({"loss": float(i)}, step=i)
        mock_send.assert_not_called()

        # Manually flush
        run.flush()
        mock_send.assert_called_once()
        points = mock_send.call_args[0][3]
        assert len(points) == 10

        # Clean up timer
        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_client_auto_flush_on_50():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        for i in range(55):
            run.log({"loss": float(i)}, step=i)
        # Should have flushed once at 50, leaving 5 in buffer
        assert mock_send.call_count == 1
        assert len(mock_send.call_args[0][3]) == 50

        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_client_finish():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"), \
         patch("intern.sdk.api.update_run") as mock_update:
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log({"loss": 1.0}, step=0)
        run.finish()
        mock_send.assert_called_once()
        mock_update.assert_called_once_with("http://localhost:8080", "key", "run-1", "finished")


def test_sdk_client_log_text():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics"), \
         patch("intern.sdk.api.send_logs") as mock_logs:
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log_text("hello", level="warning", step=5)
        run.flush()
        mock_logs.assert_called_once()
        entries = mock_logs.call_args[0][3]
        assert len(entries) == 1
        assert entries[0]["level"] == "warning"
        assert entries[0]["content"] == "hello"

        run._finished = True
        if run._timer:
            run._timer.cancel()


def test_sdk_module_api():
    import intern
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"), \
         patch("intern.sdk.api.update_run"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = intern.init(project="test", name="run-1", server="http://localhost:8080", api_key="key")
        intern.log({"loss": 1.0}, step=0)
        intern.log_text("hello")
        intern.finish()
        mock_send.assert_called()


def test_sdk_step_auto_increment():
    from intern.sdk.client import Run
    with patch("intern.sdk.api.create_project"), \
         patch("intern.sdk.api.create_run") as mock_create, \
         patch("intern.sdk.api.send_metrics") as mock_send, \
         patch("intern.sdk.api.send_logs"):
        mock_create.return_value = {"id": "run-1", "name": "run-1"}
        run = Run("http://localhost:8080", "key", "proj", name="run-1")
        run.log({"a": 1.0})
        run.log({"a": 2.0})
        run.log({"a": 3.0})
        run.flush()
        points = mock_send.call_args[0][3]
        steps = [p["step"] for p in points]
        assert steps == [0, 1, 2]

        run._finished = True
        if run._timer:
            run._timer.cancel()
