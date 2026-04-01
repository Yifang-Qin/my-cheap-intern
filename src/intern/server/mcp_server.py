import json
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import mcp.types as types

from intern.server import db
from intern.server.analysis import compute_metric_stats, compute_log_summary, compute_duration

server = Server("my-cheap-intern")

_api_key = ""


def set_api_key(key: str):
    global _api_key
    _api_key = key


# --- Tool logic (testable without MCP transport) ---

def handle_tool_call(name: str, arguments: dict) -> str:
    if name == "list_projects":
        result = db.list_projects()

    elif name == "search_runs":
        project = db.get_project_by_name(arguments["project"])
        if not project:
            return json.dumps({"error": f"Project '{arguments['project']}' not found"})
        result = db.search_runs(
            project_id=project["id"],
            query=arguments.get("query"),
            tags=arguments.get("tags"),
            status=arguments.get("status"),
            started_after=arguments.get("started_after"),
            started_before=arguments.get("started_before"),
        )

    elif name == "get_run_summary":
        result = []
        for run_id in arguments["run_ids"]:
            run = db.get_run(run_id)
            if not run:
                continue
            metas = db.get_metric_metas(run_id)
            metrics = {}
            for meta in metas:
                stats = compute_metric_stats(run_id, meta["key"])
                metrics[meta["key"]] = stats
            log_summary = compute_log_summary(run_id)
            duration = compute_duration(run["started_at"], run.get("finished_at"))
            result.append({
                "run_id": run_id,
                "config": run["config"],
                "status": run["status"],
                "duration": duration,
                "metrics": metrics,
                "log_summary": log_summary,
            })

    elif name == "compare_runs":
        run_ids = arguments["run_ids"]
        metric_keys = arguments.get("metric_keys")
        runs = [db.get_run(rid) for rid in run_ids]
        runs = [r for r in runs if r]

        # Config diff: only keys that differ
        all_config_keys = set()
        for r in runs:
            all_config_keys.update(r["config"].keys())
        config_diff = {}
        for key in sorted(all_config_keys):
            values = {r["id"]: r["config"].get(key) for r in runs}
            if len(set(str(v) for v in values.values())) > 1:
                config_diff[key] = values

        # Shared metric keys
        if not metric_keys:
            key_sets = []
            for r in runs:
                metas = db.get_metric_metas(r["id"])
                key_sets.append(set(m["key"] for m in metas))
            metric_keys = sorted(set.intersection(*key_sets)) if key_sets else []

        # Metrics table + ranking
        metrics_table = {}
        ranking = {}
        for key in metric_keys:
            metrics_table[key] = {}
            for r in runs:
                stats = compute_metric_stats(r["id"], key)
                metrics_table[key][r["id"]] = stats
            direction = metrics_table[key].get(runs[0]["id"], {}).get("direction", "neutral")
            sorted_ids = sorted(
                [r["id"] for r in runs],
                key=lambda rid: metrics_table[key].get(rid, {}).get("latest", 0),
                reverse=(direction != "lower_better"),
            )
            ranking[key] = sorted_ids

        result = {"config_diff": config_diff, "metrics_table": metrics_table, "ranking": ranking}

    elif name == "get_metric_series":
        result = db.get_metric_series(
            arguments["run_id"], arguments["key"],
            start_step=arguments.get("start_step"),
            end_step=arguments.get("end_step"),
            downsample=arguments.get("downsample"),
        )

    elif name == "get_logs":
        result = db.get_logs(
            arguments["run_id"],
            level=arguments.get("level"),
            keyword=arguments.get("keyword"),
            limit=arguments.get("limit", 100),
        )

    else:
        result = {"error": f"Unknown tool: {name}"}

    return json.dumps(result, default=str, indent=2)


# --- MCP protocol handlers ---

TOOLS = [
    types.Tool(
        name="list_projects",
        description="List all projects with run count and last active time",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="search_runs",
        description="Search runs by name, tags, config values within a project",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "query": {"type": "string", "description": "Fuzzy search across run name, tags, config"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Exact tag match (AND)"},
                "status": {"type": "string", "enum": ["running", "finished", "crashed"]},
                "started_after": {"type": "string", "description": "ISO datetime filter"},
                "started_before": {"type": "string", "description": "ISO datetime filter"},
            },
            "required": ["project"],
        },
    ),
    types.Tool(
        name="get_run_summary",
        description="Pre-computed summary of runs with trends, anomalies, log stats",
        inputSchema={
            "type": "object",
            "properties": {"run_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["run_ids"],
        },
    ),
    types.Tool(
        name="compare_runs",
        description="Side-by-side comparison: config diff, metrics ranking",
        inputSchema={
            "type": "object",
            "properties": {
                "run_ids": {"type": "array", "items": {"type": "string"}},
                "metric_keys": {"type": "array", "items": {"type": "string"}, "description": "Defaults to all shared keys"},
            },
            "required": ["run_ids"],
        },
    ),
    types.Tool(
        name="get_metric_series",
        description="Raw metric time series data",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "key": {"type": "string"},
                "start_step": {"type": "integer"},
                "end_step": {"type": "integer"},
                "downsample": {"type": "integer", "description": "Downsample to N points"},
            },
            "required": ["run_id", "key"],
        },
    ),
    types.Tool(
        name="get_logs",
        description="Text log entries with filtering by level and keyword",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "level": {"type": "string", "enum": ["info", "warning", "error"]},
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["run_id"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    result_text = handle_tool_call(name, arguments)
    return [types.TextContent(type="text", text=result_text)]


# --- SSE transport + Starlette app ---

sse = SseServerTransport("/messages/")


async def handle_sse(request):
    auth = request.headers.get("authorization", "")
    if _api_key and (not auth.startswith("Bearer ") or auth[7:] != _api_key):
        return Response(status_code=401)
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


mcp_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
    ],
)
