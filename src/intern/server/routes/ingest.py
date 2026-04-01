from datetime import datetime, timezone
from fastapi import APIRouter
from intern.common.models import (
    CreateProjectRequest, CreateRunRequest, DefineMetricRequest,
    MetricPointIn, LogEntryIn, UpdateRunRequest,
)
from intern.server import db

router = APIRouter()


@router.post("/projects")
def create_project(req: CreateProjectRequest):
    existing = db.get_project_by_name(req.name)
    if existing:
        return existing
    return db.create_project(req.name, req.description)


@router.post("/projects/{project}/runs")
def create_run(project: str, req: CreateRunRequest):
    p = db.get_project_by_name(project)
    if not p:
        p = db.create_project(project)
    return db.create_run(p["id"], req.id, req.name, req.config, req.tags)


@router.post("/runs/{run_id}/metrics/define")
def define_metric(run_id: str, req: DefineMetricRequest):
    db.define_metric(run_id, req.key, req.type, req.direction, req.description, req.aggregation)
    return {"status": "ok"}


@router.post("/runs/{run_id}/metrics")
def write_metrics(run_id: str, points: list[MetricPointIn]):
    now = datetime.now(timezone.utc).isoformat()
    data = [p.model_dump() for p in points]
    for d in data:
        if not d.get("timestamp"):
            d["timestamp"] = now
    db.insert_metric_points(run_id, data)
    return {"status": "ok", "count": len(points)}


@router.post("/runs/{run_id}/logs")
def write_logs(run_id: str, entries: list[LogEntryIn]):
    now = datetime.now(timezone.utc).isoformat()
    data = [e.model_dump() for e in entries]
    for d in data:
        if not d.get("timestamp"):
            d["timestamp"] = now
    db.insert_logs(run_id, data)
    return {"status": "ok", "count": len(entries)}


@router.patch("/runs/{run_id}")
def update_run(run_id: str, req: UpdateRunRequest):
    db.update_run_status(run_id, req.status)
    return {"status": "ok"}
