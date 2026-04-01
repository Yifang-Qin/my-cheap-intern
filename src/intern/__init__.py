import os
from intern.sdk.client import Run

_current_run: Run | None = None


def init(project: str, name: str | None = None, config: dict | None = None,
         tags: list[str] | None = None, server: str | None = None,
         api_key: str | None = None, run_id: str | None = None,
         buffer_size: int = 1) -> Run:
    global _current_run
    server = server or os.environ.get("INTERN_SERVER", "http://localhost:8080")
    api_key = api_key or os.environ.get("INTERN_API_KEY", "")
    _current_run = Run(server=server, api_key=api_key, project=project,
                       name=name, run_id=run_id, config=config, tags=tags,
                       buffer_size=buffer_size)
    return _current_run


def log(data: dict, step: int | None = None):
    _current_run.log(data, step=step)


def log_text(content: str, level: str = "info", step: int | None = None):
    _current_run.log_text(content, level=level, step=step)


def finish():
    global _current_run
    _current_run.finish()
    _current_run = None
