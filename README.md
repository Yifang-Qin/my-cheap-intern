# my-cheap-intern

AI-native experiment tracking for ML researchers. Like a cheap intern who reads all your dashboards and summarizes them.

**New here?** Read the [Getting Started Guide](manual/getting-started.md) ([中文版](manual/getting-started-zh.md)) for a step-by-step walkthrough.

## Quick Start

### 1. Install

```bash
pip install my-cheap-intern          # SDK only (in your experiment venv)
pip install my-cheap-intern[server]  # Full server (on the server machine)
```

### 2. Start Server

```bash
intern-server launch --key=your-secret-key
```

Open `http://localhost:8080` to see the web panel.

### 3. Log Experiments

```python
import intern

intern.init(
    project="my-project",
    name="experiment-1",
    config={"lr": 1e-5, "epochs": 10},
    tags=["baseline"],
)

for step in range(100):
    intern.log({"loss": compute_loss()}, step=step)

intern.finish()
```

Set `INTERN_SERVER` and `INTERN_API_KEY` environment variables so you don't need to pass `server=` and `api_key=` every time.

### 4. Connect AI Assistant

In your experiment project root:

```bash
intern-cli init --key=your-secret-key
```

This installs Claude Code skills (`intern-logger`, `intern-reader`) and writes MCP config so your AI assistant can query experiments. Safe to run multiple times.

## Advanced Configuration

| CLI Flag | Env Variable | Default | Description |
|---|---|---|---|
| `--key` | `INTERN_API_KEY` | *(empty, no auth)* | API key for authentication |
| `--port` | `INTERN_PORT` | `8080` | Server port |
| `--data-dir` | `INTERN_DATA_DIR` | `~/.intern` | SQLite database directory |
| `--host` | — | `0.0.0.0` | Bind address |

CLI flags take precedence over environment variables.
