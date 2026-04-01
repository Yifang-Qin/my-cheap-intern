import requests


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


_TIMEOUT = (3, 10)  # (connect, read) seconds


def create_project(server: str, api_key: str, name: str, description: str = "") -> dict:
    resp = requests.post(f"{server}/api/projects",
                         json={"name": name, "description": description},
                         headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def create_run(server: str, api_key: str, project: str, run_id: str | None,
               name: str | None, config: dict, tags: list[str]) -> dict:
    resp = requests.post(f"{server}/api/projects/{project}/runs",
                         json={"id": run_id, "name": name, "config": config, "tags": tags},
                         headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def define_metric(server: str, api_key: str, run_id: str, key: str, **kwargs):
    resp = requests.post(f"{server}/api/runs/{run_id}/metrics/define",
                         json={"key": key, **kwargs},
                         headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()


def send_metrics(server: str, api_key: str, run_id: str, points: list[dict]):
    resp = requests.post(f"{server}/api/runs/{run_id}/metrics",
                         json=points,
                         headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()


def send_logs(server: str, api_key: str, run_id: str, entries: list[dict]):
    resp = requests.post(f"{server}/api/runs/{run_id}/logs",
                         json=entries,
                         headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()


def update_run(server: str, api_key: str, run_id: str, status: str):
    resp = requests.patch(f"{server}/api/runs/{run_id}",
                          json={"status": status},
                          headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()
