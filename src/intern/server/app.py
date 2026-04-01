import os
import json as _json
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


def create_app(db_path: str | None = None, api_key: str = "") -> FastAPI:
    app = FastAPI(title="my-cheap-intern")
    app.state.api_key = api_key

    if db_path:
        from intern.server.db import init_db
        init_db(db_path)

    verify = _make_verify_api_key(api_key)

    from intern.server.routes.ingest import router as ingest_router
    from intern.server.routes.query import router as query_router
    app.include_router(ingest_router, prefix="/api", dependencies=[Depends(verify)])
    app.include_router(query_router, prefix="/api", dependencies=[Depends(verify)])

    # Web panel routes (no auth)
    from intern.server import db as _db
    _pkg_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(_pkg_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(_pkg_dir / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def project_list_page(request: Request):
        projects = _db.list_projects()
        return templates.TemplateResponse(request, "project_list.html",
                                          {"projects": projects})

    @app.get("/project/{name}", response_class=HTMLResponse)
    def run_list_page(request: Request, name: str, status: str | None = None):
        project = _db.get_project_by_name(name)
        runs = _db.list_runs(project["id"], status=status) if project else []
        return templates.TemplateResponse(request, "run_list.html", {
            "project": project, "runs": runs,
            "status_filter": status,
        })

    @app.get("/run/{run_id}", response_class=HTMLResponse)
    def run_detail_page(request: Request, run_id: str, log_level: str | None = None):
        run = _db.get_run(run_id)
        metas = _db.get_metric_metas(run_id)
        metrics_data = {}
        for meta in metas:
            series = _db.get_metric_series(run_id, meta["key"])
            metrics_data[meta["key"]] = series
        logs = _db.get_logs(run_id, level=log_level, limit=100)
        return templates.TemplateResponse(request, "run_detail.html", {
            "run": run, "metas": metas,
            "metrics_data": metrics_data, "logs": logs,
            "config_json": _json.dumps(run["config"], indent=2),
        })

    # Mount MCP server
    from intern.server.mcp_server import mcp_app, set_api_key
    set_api_key(api_key)
    app.mount("/mcp", mcp_app)

    return app


def main():
    import uvicorn
    port = int(os.environ.get("INTERN_PORT", "8080"))
    api_key = os.environ.get("INTERN_API_KEY", "")
    data_dir = os.environ.get("INTERN_DATA_DIR", str(Path.home() / ".intern"))
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db_path = str(Path(data_dir) / "data.db")

    app = create_app(db_path=db_path, api_key=api_key)
    uvicorn.run(app, host="0.0.0.0", port=port)
