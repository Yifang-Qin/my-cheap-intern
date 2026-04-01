import threading
import atexit
from datetime import datetime, timezone

from intern.sdk import api


class Run:
    def __init__(self, server: str, api_key: str, project: str, name: str | None = None,
                 run_id: str | None = None, config: dict | None = None,
                 tags: list[str] | None = None, buffer_size: int = 1):
        self.server = server
        self.api_key = api_key
        self._step = 0
        self._buffer_size = max(1, buffer_size)
        self._metric_buffer: list[dict] = []
        self._log_buffer: list[dict] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._finished = False

        api.create_project(server, api_key, project)
        result = api.create_run(server, api_key, project, run_id, name, config or {}, tags or [])
        self.run_id = result["id"]
        self.name = result["name"]

        if self._buffer_size > 1:
            self._start_flush_timer()
        atexit.register(self._cleanup)

    def define_metric(self, key: str, **kwargs):
        api.define_metric(self.server, self.api_key, self.run_id, key, **kwargs)

    def log(self, data: dict, step: int | None = None):
        if step is None:
            step = self._step
            self._step += 1
        else:
            self._step = step + 1
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for key, value in data.items():
                self._metric_buffer.append({
                    "key": key, "step": step, "value": float(value), "timestamp": now,
                })
            if len(self._metric_buffer) >= self._buffer_size:
                self._flush_locked()

    def log_text(self, content: str, level: str = "info", step: int | None = None):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._log_buffer.append({
                "step": step, "level": level, "content": content, "timestamp": now,
            })
            if len(self._log_buffer) >= self._buffer_size:
                self._flush_locked()

    def _flush_locked(self):
        if self._metric_buffer:
            points = list(self._metric_buffer)
            self._metric_buffer.clear()
            api.send_metrics(self.server, self.api_key, self.run_id, points)
        if self._log_buffer:
            entries = list(self._log_buffer)
            self._log_buffer.clear()
            api.send_logs(self.server, self.api_key, self.run_id, entries)

    def flush(self):
        with self._lock:
            self._flush_locked()

    def _start_flush_timer(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(30.0, self._timed_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timed_flush(self):
        self.flush()
        if not self._finished:
            self._start_flush_timer()

    def finish(self):
        self._finished = True
        if self._timer:
            self._timer.cancel()
        self.flush()
        api.update_run(self.server, self.api_key, self.run_id, "finished")

    def _cleanup(self):
        if not self._finished:
            self.flush()
            if self._timer:
                self._timer.cancel()
            try:
                api.update_run(self.server, self.api_key, self.run_id, "crashed")
            except Exception:
                pass
