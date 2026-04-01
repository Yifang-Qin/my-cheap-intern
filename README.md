# my-cheap-intern

AI-native experiment tracking for ML researchers. Like a cheap intern who reads all your dashboards and summarizes them.

## Quick Start

### Install

```bash
pip install my-cheap-intern          # SDK only (training machines)
pip install my-cheap-intern[server]  # Full server
```

### Start Server

```bash
export INTERN_API_KEY=your-secret-key
intern-server
```

Server runs at `http://localhost:8080`. Web panel at `/`, MCP endpoint at `/mcp/sse`.

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

| Env Variable | Default | Description |
|---|---|---|
| INTERN_PORT | 8080 | Server port |
| INTERN_API_KEY | (required) | Auth key |
| INTERN_DATA_DIR | ~/.intern | Data directory |
