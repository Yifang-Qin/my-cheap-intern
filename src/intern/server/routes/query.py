from fastapi import APIRouter, HTTPException
from intern.server import db

router = APIRouter()


@router.get("/projects")
def list_projects():
    return db.list_projects()


@router.get("/projects/{project}/runs")
def list_runs(project: str, status: str | None = None):
    p = db.get_project_by_name(project)
    if not p:
        return []
    return db.list_runs(p["id"], status=status)


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404)
    metas = db.get_metric_metas(run_id)
    run["metric_metas"] = metas
    return run


@router.get("/runs/{run_id}/metrics/{key}")
def get_metric_series(run_id: str, key: str, start_step: int | None = None,
                      end_step: int | None = None, downsample: int | None = None):
    return db.get_metric_series(run_id, key, start_step, end_step, downsample)


@router.get("/runs/{run_id}/logs")
def get_logs(run_id: str, level: str | None = None, keyword: str | None = None,
             limit: int = 100):
    return db.get_logs(run_id, level=level, keyword=keyword, limit=limit)
