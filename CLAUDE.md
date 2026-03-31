# CLAUDE.md — my-cheap-intern

## 项目简介

my-cheap-intern 是一个 AI-native 的实验追踪工具，面向深度学习研究者。核心思路：自建一个类 wandb 的实验日志服务，但重点在 MCP 接口——让 AI 助手能结构化查询实验数据并自动生成报告，而非让人去面板上手动翻曲线。

项目名寓意：像一个便宜的实习生，帮你整理实验结果。

## 设计文档

完整 spec 在 `docs/2026-04-01-my-cheap-intern-design.md`，包含数据模型、API、MCP tools、SDK、部署方案等全部设计细节。**实现前必读此文件。**

## 架构概览

```
Logger SDK (训练机器) ──HTTP──> FastAPI Server (用户自建) <──MCP──> AI 消费端 (Claude Code 等)
                                  │
                                  ├─ REST API (写入 + 查询)
                                  ├─ Web Panel (Jinja2 + HTMX + Chart.js)
                                  ├─ MCP Server (6 个 tools)
                                  └─ SQLite
```

单进程 All-in-One，一条命令启动，零外部依赖。

## 技术栈

- Python 3.10+, FastAPI, SQLite (raw SQL, no ORM)
- 前端: Jinja2 + HTMX + Chart.js (零构建)
- MCP: mcp Python SDK
- Logger SDK: 纯 Python + requests
- 开发工具: uv + venv + pyproject.toml

## 项目结构

```
my-cheap-intern/
├── src/intern/
│   ├── __init__.py          # SDK 公开接口
│   ├── sdk/                 # Logger SDK (client.py, api.py)
│   ├── server/              # 服务端 (app.py, routes/, mcp_server.py, db.py, analysis.py, templates/, static/)
│   └── common/              # 共享数据结构 (models.py)
├── tests/
├── docs/
├── pyproject.toml
├── Dockerfile
└── README.md
```

SDK 和 Server 同包但分离依赖:
- `pip install my-cheap-intern` → SDK only
- `pip install my-cheap-intern[server]` → 全套

## 开发约定

- 遵循全局 CLAUDE.md 中的代码风格规范（MVP first，不过度封装）
- 不加 try/except、assert、输入校验，除非明确要求
- 不用 ORM，SQLite 直接写 SQL
- 前端不引入任何构建工具或 JS 框架
- commit message 用英文，简洁描述改动

## MCP Tools 速查

| Tool | 用途 |
|------|------|
| `list_projects` | 列出所有 project |
| `search_runs` | 模糊搜索 runs (name/tags/config values) |
| `get_run_summary` | 批量获取 run 摘要 (含趋势/异常检测) |
| `compare_runs` | 对比多个 run (config diff + metrics ranking) |
| `get_metric_series` | 获取原始时间序列 |
| `get_logs` | 获取文本日志 |
