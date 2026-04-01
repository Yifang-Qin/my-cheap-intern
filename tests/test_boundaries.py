# tests/test_boundaries.py
"""Data boundary tests — edge cases for API and MCP tools."""
import pytest
import json
from intern.server.db import init_db, list_projects, create_project, create_run, \
    insert_metric_points, insert_logs, get_metric_series, search_runs, get_run
from intern.server.mcp_server import handle_tool_call


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    init_db(str(tmp_path / "boundary.db"))


class TestEmptyState:
    """API behavior when there's no data."""

    def test_list_projects_empty(self):
        assert list_projects() == []

    def test_search_runs_empty_project(self):
        proj = create_project("empty-proj")
        results = search_runs(proj["id"])
        assert results == []

    def test_mcp_list_projects_empty(self):
        result = json.loads(handle_tool_call("list_projects", {}))
        assert result == []

    def test_mcp_get_run_summary_empty_list(self):
        result = json.loads(handle_tool_call("get_run_summary", {"run_ids": []}))
        assert result == []

    def test_mcp_get_metric_series_nonexistent_run(self):
        result = handle_tool_call("get_metric_series", {"run_id": "nonexistent", "key": "loss"})
        # Should return empty or error message, not crash
        assert result is not None


class TestLargeData:
    """Behavior with large volumes of data."""

    def test_10k_metric_points(self):
        proj = create_project("big")
        run = create_run(proj["id"], None, name="big-run", config={}, tags=[])
        points = [{"key": "loss", "step": i, "value": 1.0 / (i + 1),
                   "timestamp": "2026-01-01T00:00:00+00:00"} for i in range(10000)]
        insert_metric_points(run["id"], points)
        series = get_metric_series(run["id"], "loss")
        assert len(series) == 10000

    def test_mcp_downsample_large_series(self):
        proj = create_project("big2")
        run = create_run(proj["id"], None, name="big-run-2", config={}, tags=[])
        points = [{"key": "acc", "step": i, "value": float(i),
                   "timestamp": "2026-01-01T00:00:00+00:00"} for i in range(5000)]
        insert_metric_points(run["id"], points)
        result = json.loads(handle_tool_call("get_metric_series", {
            "run_id": run["id"], "key": "acc", "downsample": 100,
        }))
        assert len(result) == 100


class TestSpecialCharacters:
    """Unicode, long strings, special chars in names/tags/config."""

    def test_unicode_project_name(self):
        create_project("实验-αβγ-テスト")
        projects = list_projects()
        assert any(p["name"] == "实验-αβγ-テスト" for p in projects)

    def test_unicode_run_name_and_tags(self):
        proj = create_project("unicode")
        run = create_run(proj["id"], None, name="训练-🚀", config={"模型": "Transformer"},
                         tags=["中文标签", "émoji-🎯"])
        fetched = get_run(run["id"])
        assert fetched["name"] == "训练-🚀"
        assert "中文标签" in fetched["tags"]

    def test_long_config_value(self):
        proj = create_project("longcfg")
        long_val = "x" * 10000
        run = create_run(proj["id"], None, name="run", config={"desc": long_val}, tags=[])
        fetched = get_run(run["id"])
        assert fetched["config"]["desc"] == long_val

    def test_mcp_search_unicode_query(self):
        create_project("搜索测试")
        proj = create_project("搜索测试")
        create_run(proj["id"], None, name="实验一", config={}, tags=["标签"])
        result = json.loads(handle_tool_call("search_runs", {
            "project": "搜索测试", "query": "实验",
        }))
        assert len(result) >= 1


class TestZeroMetricRun:
    """Run with no metrics at all."""

    def test_mcp_summary_no_metrics(self):
        proj = create_project("nometric")
        run = create_run(proj["id"], None, name="empty-run", config={}, tags=[])
        result = json.loads(handle_tool_call("get_run_summary", {"run_ids": [run["id"]]}))
        assert len(result) == 1
        # Should have empty metrics section, not crash

    def test_mcp_compare_no_metrics(self):
        proj = create_project("nometric2")
        r1 = create_run(proj["id"], None, name="r1", config={"a": 1}, tags=[])
        r2 = create_run(proj["id"], None, name="r2", config={"a": 2}, tags=[])
        result = json.loads(handle_tool_call("compare_runs", {
            "run_ids": [r1["id"], r2["id"]],
        }))
        assert result is not None
