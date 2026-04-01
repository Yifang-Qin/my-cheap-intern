# Getting Started with my-cheap-intern

A step-by-step guide for ML researchers to replace existing loggers with intern and let your AI assistant manage experiment results.

## Prerequisites

- Python 3.10+
- An experiment project with its own venv
- Claude Code (or another MCP-compatible AI assistant)

## Step 1: Install the SDK

In your **experiment project's** venv:

```bash
pip install -e /path/to/my-cheap-intern
# or, once published:
# pip install my-cheap-intern
```

This only installs the lightweight SDK (`requests` + `pydantic`). It won't pollute your ML dependencies.

## Step 2: Set Up AI Assistant Support

Still in your experiment project root:

```bash
intern-cli init
```

This does two things:
1. Creates `.claude/skills/intern-logger/` and `.claude/skills/intern-reader/` with full API reference
2. Appends a short experiment tracking section to `CLAUDE.md`

Your AI assistant now knows intern's API and can write correct integration code.

## Step 3: Replace Your Logger

Ask your AI assistant (in Claude Code):

> "Replace the wandb/tensorboard/print-based logging in my training script with intern. Keep the same metrics."

The assistant will read the `intern-logger` skill and produce correct code. The typical pattern looks like:

```python
import intern

intern.init(
    project="my-project",
    name="resnet18-baseline",
    config={"lr": 1e-3, "batch_size": 128, "epochs": 50},
    tags=["baseline"],
)

for epoch in range(50):
    train_loss = train_one_epoch(...)
    val_loss, val_acc = evaluate(...)

    intern.log({"train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc}, step=epoch)
    intern.log_text(f"epoch {epoch}: val_acc={val_acc:.4f}")

intern.finish()
```

**Tip**: Set environment variables to avoid hardcoding server details:

```bash
export INTERN_SERVER=http://localhost:8080
export INTERN_API_KEY=my-key
```

Then `intern.init()` picks them up automatically — no need to pass `server=` or `api_key=`.

## Step 4: Start the Server

The server needs the `[server]` extras. You can run it from the intern repo's own venv, or install it alongside your experiment:

```bash
intern-server launch --key=my-key
```

You should see:

```
intern-server | port=8080 data_dir=/home/user/.intern auth=on
  Web Panel:  http://localhost:8080/
  MCP (SSE):  http://localhost:8080/mcp/sse
```

Open `http://localhost:8080` in your browser to see the web panel.

**Note**: The server and training script can run on different machines. Just replace `localhost` with the server's IP.

## Step 5: Connect Your AI Assistant via MCP

Add this to your Claude Code MCP settings (one-time setup):

```json
{
  "mcpServers": {
    "my-cheap-intern": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse",
      "headers": { "Authorization": "Bearer my-key" }
    }
  }
}
```

## Step 6: Ask Your Assistant About Experiments

Once MCP is connected and you have some runs logged, you can ask naturally:

| What you say | What happens |
|---|---|
| "What experiments did I run today?" | Searches runs by date, shows summaries with trends |
| "Compare the baseline and the new method" | Config diff + metrics ranking side by side |
| "Is the latest run overfitting?" | Checks train vs val loss trends, pulls raw curves |
| "What went wrong with the crashed run?" | Finds error logs, checks for NaN issues |
| "Which run has the best val_acc?" | Ranks all finished runs by the metric |

The assistant activates the `intern-reader` skill automatically and knows how to combine the MCP tools.

## Typical Daily Workflow

1. **Morning**: Start the server (`intern-server launch --key=my-key`)
2. **During experiments**: Your training scripts log to intern automatically
3. **Check progress**: Open the web panel, or ask your AI assistant
4. **End of day**: Ask "summarize today's experiments" — the assistant pulls all runs, compares metrics, and highlights the best results
5. **Planning**: Ask "which hyperparameters differ between my top 3 runs?" to guide next steps
