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

---

## 实现进度

详细 plan 在 `docs/superpowers/plans/2026-04-01-my-cheap-intern.md`，每个 Phase 对应一个 commit。

**新 session 开始时：读此表找到下一个 `[ ]`，读 plan 中对应 Task 的完整代码，执行，跑通测试，commit，然后把下面的 `[ ]` 改成 `[x]`。**

| Phase | Task | Commit Message | Status |
|-------|------|---------------|--------|
| 1 | 项目脚手架 + 数据模型 | `scaffold: project structure, pyproject.toml, data models` | [x] |
| 2 | 数据库层 (TDD) | `feat: database layer with SQLite schema and CRUD operations` | [x] |
| 3 | FastAPI App + Ingest 路由 (TDD) | `feat: FastAPI app with auth and ingest routes` | [ ] |
| 4 | Query 路由 (TDD) | `feat: query routes for projects, runs, metrics, logs` | [ ] |
| 5 | 分析模块 (TDD) | `feat: analysis module with trend detection, anomaly detection, summaries` | [ ] |
| 6 | MCP Server (TDD) | `feat: MCP server with 6 tools` | [ ] |
| 7 | Logger SDK (TDD) | `feat: logger SDK with buffered upload, auto-flush, module-level API` | [ ] |
| 8 | Web Panel | `feat: web panel with project list, run list, run detail pages` | [ ] |
| 9 | CLI + Dockerfile + README | `feat: Dockerfile and README` | [ ] |
| 10 | 集成冒烟测试 | `test: end-to-end smoke test` | [ ] |

### 每个 Phase 的执行流程

1. 读 plan 中对应 Task 的所有 Step
2. 按 TDD 顺序执行：写测试 → 确认失败 → 写实现 → 确认通过
3. `git add` 相关文件 + `git commit`
4. 更新本文件中对应 Phase 的 `[ ]` → `[x]`
5. Session 结束

### 注意事项

- 每个 Phase 的完整代码都在 plan 文件中，不需要猜测
- Phase 3 会创建 `tests/conftest.py`，后续 Phase 的测试依赖它
- Phase 6 (MCP) 需要修改 `app.py` 添加 mount
- Phase 8 (Web Panel) 也需要修改 `app.py` 添加 panel routes
- Phase 10 不产生新代码，只跑全量测试 + 冒烟脚本
