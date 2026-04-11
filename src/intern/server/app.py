import os
import json as _json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


def _make_verify_api_key(api_key: str):
    def verify_api_key(request: Request):
        if not api_key:
            return
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return verify_api_key


def _make_verify_panel(api_key: str):
    """Panel auth: accepts ?token= query param or intern_token cookie."""
    def verify_panel(request: Request):
        if not api_key:
            return
        token = request.query_params.get("token") or request.cookies.get("intern_token")
        if token != api_key:
            raise HTTPException(status_code=401, detail="Unauthorized. Append ?token=YOUR_KEY to the URL.")
    return verify_panel


def create_app(db_path: str | None = None, api_key: str = "") -> FastAPI:
    from intern.server.mcp_server import create_session_manager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mgr = create_session_manager()
        async with mgr.run():
            yield

    app = FastAPI(title="my-cheap-intern", lifespan=lifespan)
    app.state.api_key = api_key

    if db_path:
        from intern.server.db import init_db
        init_db(db_path)

    verify = _make_verify_api_key(api_key)

    from intern.server.routes.ingest import router as ingest_router
    from intern.server.routes.query import router as query_router
    app.include_router(ingest_router, prefix="/api", dependencies=[Depends(verify)])
    app.include_router(query_router, prefix="/api", dependencies=[Depends(verify)])

    # Web panel routes (token auth via query param or cookie)
    from intern.server import db as _db
    from fastapi.responses import Response, RedirectResponse
    _pkg_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(_pkg_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(_pkg_dir / "static")), name="static")

    verify_panel = _make_verify_panel(api_key)

    def _set_token_cookie(request: Request, response: Response):
        """If authed via ?token= param, set cookie so subsequent requests don't need it."""
        token = request.query_params.get("token")
        if token and api_key and token == api_key:
            response.set_cookie("intern_token", token, httponly=True, samesite="lax")

    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(verify_panel)])
    def project_list_page(request: Request):
        projects = _db.list_projects()
        response = templates.TemplateResponse(request, "project_list.html",
                                              {"projects": projects})
        _set_token_cookie(request, response)
        return response

    @app.get("/project/{name}", response_class=HTMLResponse, dependencies=[Depends(verify_panel)])
    def run_list_page(request: Request, name: str, status: str | None = None):
        project = _db.get_project_by_name(name)
        runs = _db.list_runs(project["id"], status=status) if project else []
        response = templates.TemplateResponse(request, "run_list.html", {
            "project": project, "runs": runs,
            "status_filter": status,
        })
        _set_token_cookie(request, response)
        return response

    @app.get("/run/{run_id}", response_class=HTMLResponse, dependencies=[Depends(verify_panel)])
    def run_detail_page(request: Request, run_id: str, log_level: str | None = None):
        run = _db.get_run(run_id)
        metas = _db.get_metric_metas(run_id)
        metrics_data = {}
        for meta in metas:
            series = _db.get_metric_series(run_id, meta["key"])
            metrics_data[meta["key"]] = series
        logs = _db.get_logs(run_id, level=log_level, limit=100)
        response = templates.TemplateResponse(request, "run_detail.html", {
            "run": run, "metas": metas,
            "metrics_data": metrics_data, "logs": logs,
            "config_json": _json.dumps(run["config"], indent=2),
        })
        _set_token_cookie(request, response)
        return response

    @app.delete("/panel/runs/{run_id}", dependencies=[Depends(verify_panel)])
    def panel_delete_run(run_id: str):
        run = _db.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        _db.delete_run(run_id)
        return Response(status_code=200)

    @app.delete("/panel/projects/{project}", dependencies=[Depends(verify_panel)])
    def panel_delete_project(project: str):
        p = _db.get_project_by_name(project)
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        _db.delete_project(p["id"])
        return Response(status_code=200)

    # Mount MCP server (Streamable HTTP + legacy SSE)
    from intern.server.mcp_server import mcp_app, set_api_key
    set_api_key(api_key)
    app.mount("/mcp", mcp_app)

    return app


def main():
    import argparse, uvicorn

    parser = argparse.ArgumentParser(prog="intern-server")
    sub = parser.add_subparsers(dest="command")

    launch = sub.add_parser("launch", help="Start the server")
    launch.add_argument("--key", default=None, help="API key (env: INTERN_API_KEY)")
    launch.add_argument("--port", type=int, default=None, help="Port (env: INTERN_PORT, default: 8080)")
    launch.add_argument("--data-dir", default=None, help="Data directory (env: INTERN_DATA_DIR, default: ~/.intern)")
    launch.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")

    args = parser.parse_args()
    if args.command is None:
        args.command = "launch"
        args.key = None
        args.port = None
        args.data_dir = None
        args.host = "0.0.0.0"

    import secrets
    api_key = args.key or os.environ.get("INTERN_API_KEY", "") or secrets.token_urlsafe(16)
    port = args.port or int(os.environ.get("INTERN_PORT", "8080"))
    data_dir = args.data_dir or os.environ.get("INTERN_DATA_DIR", str(Path.home() / ".intern"))

    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db_path = str(Path(data_dir) / "data.db")

    app = create_app(db_path=db_path, api_key=api_key)
    print(f"\nintern-server | port={port} data_dir={data_dir}")
    print(f"  API Key:    {api_key}")
    print(f"  Web Panel:  http://localhost:{port}/?token={api_key}")
    print(f"  MCP (HTTP): http://localhost:{port}/mcp/")
    print(f"  MCP (SSE):  http://localhost:{port}/mcp/sse")
    print()
    uvicorn.run(app, host=args.host, port=port)
