# tests/test_mcp_streamable_http.py
"""Streamable HTTP transport tests — verify /mcp/ endpoint works with type: http."""
import threading
import time
import os
import pytest
import httpx

import uvicorn
from intern.server.app import create_app
from intern.server.db import init_db

MCP_INIT_BODY = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}
MCP_TOOLS_LIST_BODY = {"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}
HEADERS_AUTH = {
    "Authorization": "Bearer secret-http",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(scope="module")
def http_server():
    db_path = "/tmp/intern_mcp_http.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    app = create_app(db_path=db_path, api_key="secret-http")
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19882, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(1)
    yield "http://127.0.0.1:19882"
    srv.should_exit = True


class TestStreamableHttp:
    def test_initialize(self, http_server):
        """POST /mcp/ with initialize should return valid MCP response."""
        resp = httpx.post(f"{http_server}/mcp/", headers=HEADERS_AUTH, json=MCP_INIT_BODY, timeout=5)
        assert resp.status_code == 200
        assert "protocolVersion" in resp.text
        assert "my-cheap-intern" in resp.text

    def test_tools_list(self, http_server):
        """POST /mcp/ with tools/list should return 6 tools."""
        resp = httpx.post(f"{http_server}/mcp/", headers=HEADERS_AUTH, json=MCP_TOOLS_LIST_BODY, timeout=5)
        assert resp.status_code == 200
        assert "list_projects" in resp.text
        assert "search_runs" in resp.text
        assert "get_run_summary" in resp.text
        assert "compare_runs" in resp.text
        assert "get_metric_series" in resp.text
        assert "get_logs" in resp.text

    def test_no_auth_returns_401(self, http_server):
        """POST /mcp/ without auth should return 401."""
        resp = httpx.post(
            f"{http_server}/mcp/",
            headers={"Content-Type": "application/json"},
            json=MCP_INIT_BODY,
            timeout=5,
        )
        assert resp.status_code == 401

    def test_wrong_auth_returns_401(self, http_server):
        """POST /mcp/ with wrong token should return 401."""
        bad_headers = {**HEADERS_AUTH, "Authorization": "Bearer wrong"}
        resp = httpx.post(f"{http_server}/mcp/", headers=bad_headers, json=MCP_INIT_BODY, timeout=5)
        assert resp.status_code == 401

    def test_sse_get_still_works(self, http_server):
        """GET /mcp/sse should still return SSE stream (legacy transport)."""
        with httpx.stream("GET", f"{http_server}/mcp/sse",
                          headers={"Authorization": "Bearer secret-http"},
                          timeout=5) as resp:
            assert resp.status_code == 200
            # Read first chunk — should contain the endpoint event
            for chunk in resp.iter_text():
                assert "endpoint" in chunk
                break
