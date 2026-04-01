import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends


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
