# my-cheap-intern

AI-native experiment tracking for ML researchers. Like a cheap intern who reads all your dashboards and summarizes them.

**New here?** Read the [Getting Started Guide](manual/getting-started.md) ([中文版](manual/getting-started-zh.md)) for a step-by-step walkthrough.

## Quick Start

### Install

**From local source** (recommended during development):

```bash
# In your experiment project's venv, install SDK only
pip install -e /path/to/my-cheap-intern

# On the server machine, install with server dependencies
pip install -e /path/to/my-cheap-intern[server]
```

The `-e` (editable) flag means changes to intern source take effect immediately without reinstalling.

**From PyPI** (once published):

```bash
pip install my-cheap-intern          # SDK only
pip install my-cheap-intern[server]  # Full server
```

### Start Server

```bash
# One-liner
intern-server launch --key=your-secret-key

# Custom port and data directory
intern-server launch --key=your-secret-key --port=9000 --data-dir=./my-experiments

# Or use environment variables
export INTERN_API_KEY=your-secret-key
export INTERN_PORT=8080            # optional, default 8080
export INTERN_DATA_DIR=~/.intern   # optional, default ~/.intern
intern-server
```

CLI flags take precedence over environment variables. Server prints endpoints on startup:

```
intern-server | port=8080 data_dir=/home/user/.intern auth=on
  Web Panel:  http://localhost:8080/
  MCP (SSE):  http://localhost:8080/mcp/sse
```

### Log Experiments

```python
import intern

run = intern.init(
    project="my-project",
    name="experiment-1",
    config={"lr": 1e-5, "epochs": 10},
    tags=["baseline"],
    server="http://your-server:8080",
    api_key="your-secret-key",
)

run.define_metric("loss", direction="lower_better")

for step in range(100):
    intern.log({"loss": compute_loss()}, step=step)

intern.finish()
```

### Connect AI Assistant (MCP)

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "my-cheap-intern": {
      "type": "sse",
      "url": "http://your-server:8080/mcp/sse",
      "headers": { "Authorization": "Bearer your-api-key" }
    }
  }
}
```

## Configuration

| CLI Flag | Env Variable | Default | Description |
|---|---|---|---|
| `--key` | `INTERN_API_KEY` | *(empty, no auth)* | API key for authentication |
| `--port` | `INTERN_PORT` | `8080` | Server port |
| `--data-dir` | `INTERN_DATA_DIR` | `~/.intern` | SQLite database directory |
| `--host` | — | `0.0.0.0` | Bind address |

## AI Assistant Integration

my-cheap-intern ships with Claude Code skills that teach your AI assistant how to use the SDK and query experiments. This is useful during vibe coding — the assistant won't know intern's API otherwise.

### Option 1: `intern-cli init` (recommended)

Run in your experiment project root:

```bash
intern-cli init
```

This creates `.claude/skills/intern-logger/` and `.claude/skills/intern-reader/`, and appends a short section to `CLAUDE.md`. Safe to run multiple times — it skips existing files.

Two skills are provided:
- **intern-logger** — SDK API reference. Activates when the assistant sees "logger", "experiment tracking", "intern", etc.
- **intern-reader** — MCP query guide. Activates when the assistant sees "experiment results", "compare runs", etc.

### Option 2: CLAUDE.md Snippet

If you prefer not to install skills, add this to your project's `CLAUDE.md`:

```markdown
## Experiment Tracking

This project uses my-cheap-intern for experiment logging.
Server: http://localhost:8080 | API key: (your key here)

SDK usage: `import intern` then `intern.init(project, name, config, tags, server, api_key)`,
`intern.log({"metric": value}, step=N)`, `intern.log_text("message")`, `intern.finish()`.

For detailed SDK API, read the skill file at .claude/skills/intern-logger/SKILL.md (installed by `intern-cli init`)
For MCP query patterns, read .claude/skills/intern-reader/SKILL.md (installed by `intern-cli init`)
```
