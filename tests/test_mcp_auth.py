# tests/test_mcp_auth.py
"""MCP auth tests — verify SSE endpoint rejects bad/missing credentials."""
import threading
import time
import os
import pytest
import httpx
import asyncio

import uvicorn
from intern.server.app import create_app
from intern.server.db import init_db


@pytest.fixture(scope="module")
def auth_server():
    db_path = "/tmp/intern_mcp_auth.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    app = create_app(db_path=db_path, api_key="secret123")
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19878, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:19878"
    srv.should_exit = True


class TestMcpAuth:
    def test_sse_no_token_returns_401(self, auth_server):
        """SSE endpoint without auth header should return 401."""
        resp = httpx.get(f"{auth_server}/mcp/sse", timeout=5)
        assert resp.status_code == 401

    def test_sse_wrong_token_returns_401(self, auth_server):
        """SSE endpoint with wrong token should return 401."""
        resp = httpx.get(f"{auth_server}/mcp/sse",
                         headers={"Authorization": "Bearer wrongtoken"},
                         timeout=5)
        assert resp.status_code == 401

    def test_sse_correct_token_connects(self, auth_server):
        """SSE endpoint with correct token should accept connection (status 200)."""
        async def check():
            from mcp.client.session import ClientSession
            from mcp.client.sse import sse_client
            headers = {"Authorization": "Bearer secret123"}
            async with sse_client(f"{auth_server}/mcp/sse", headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert len(tools.tools) == 6
            return True

        result = asyncio.run(check())
        assert result is True
