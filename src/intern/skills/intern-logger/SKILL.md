---
name: intern-logger
description: >
  SDK reference for my-cheap-intern experiment tracking.
  TRIGGER when: writing or modifying training code that needs experiment logging,
  integrating intern SDK, replacing wandb/tensorboard,
  or user asks to add metrics/logging to a training script —
  e.g. "加上实验记录", "把训练指标记下来", "add logging", "track this experiment".
---

# my-cheap-intern Logger SDK

Lightweight experiment tracking SDK. Install: `pip install -e /path/to/my-cheap-intern`

Dependencies: `requests`, `pydantic` only. No heavy ML framework dependency.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `INTERN_SERVER` | `http://localhost:8080` | Server URL |
| `INTERN_API_KEY` | *(required)* | Auth token (printed at server startup) |

These are fallbacks — explicit arguments in `init()` take precedence.

## Module-Level API (`import intern`)

```python
intern.init(
    project: str,               # project name (auto-created if new)
    name: str | None = None,    # run name (auto-generated if omitted)
    config: dict | None = None, # hyperparameters dict
    tags: list[str] | None = None,
    server: str | None = None,  # overrides INTERN_SERVER
    api_key: str | None = None, # overrides INTERN_API_KEY
    run_id: str | None = None,  # resume existing run
) -> Run

intern.log(data: dict, step: int | None = None)
# data: {"metric_name": float_value, ...}
# step auto-increments if omitted

intern.log_text(content: str, level: str = "info", step: int | None = None)
# level: "info" | "warning" | "error"

intern.finish()
# marks run complete, flushes all buffered data
```

## Run Instance Methods

```python
run = intern.init(...)

run.define_metric(key: str, direction="neutral", type="scalar", description="", aggregation="last")
# direction: "neutral" | "higher_better" | "lower_better"

run.log(data: dict, step: int | None = None)
run.log_text(content: str, level: str = "info", step: int | None = None)
run.flush()   # force flush buffers
run.finish()  # flush + mark complete
```

## Buffering Behavior

- Metrics and logs are buffered in memory
- Auto-flush triggers: buffer reaches 50 items OR every 30 seconds
- `finish()` flushes all remaining data
- `atexit` handler ensures flush on process exit
- Thread-safe

## Minimal Integration Example

```python
import intern

intern.init(
    project="my-project",
    name="resnet18_cifar10_lr1e-3",
    config={"lr": 1e-3, "batch_size": 128, "epochs": 50, "model": "resnet18"},
    tags=["baseline"],
    server="http://localhost:8080",
    api_key="my-key",
)

for epoch in range(50):
    train_loss = train_one_epoch(model, train_loader, optimizer)
    val_loss, val_acc = evaluate(model, val_loader)

    intern.log({"train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc}, step=epoch)
    intern.log_text(f"epoch {epoch}: val_acc={val_acc:.4f}")

intern.finish()
```

## Key Notes

- `intern.init()` must be called before `log()` / `log_text()` / `finish()`
- One active run per process (module-level API). For multiple concurrent runs, use `Run` instances directly
- Server must be running (`intern-server launch --key=xxx`) before SDK can log
- If server is unreachable, SDK silently drops data (no exceptions thrown in training loop)
