# my-cheap-intern 上手指南

面向 ML 研究者的分步指南：用 intern 替换现有 logger，让 AI 助手帮你管理实验结果。

## 前置条件

- Python 3.10+
- 一个有独立 venv 的实验项目
- Claude Code（或其他支持 MCP 的 AI 助手）

## 第一步：安装 SDK

在你**实验项目**的 venv 里：

```bash
pip install my-cheap-intern
```

SDK 只依赖 `requests` + `pydantic`，不会影响你的 ML 环境。

## 第二步：配置 AI 助手支持

在实验项目根目录执行：

```bash
intern-cli init --key=my-key
```

这条命令会：
1. 在 `.claude/skills/` 下创建 `intern-logger` 和 `intern-reader` 两个 skill，包含完整 API 参考
2. 在 `CLAUDE.md` 末尾追加一段实验追踪的背景描述
3. 在 `.mcp.json` 中写入 MCP 连接配置，AI 助手可以直接查询实验数据

如果 server 在远程机器，加 `--server=http://gpu-box:8080`。

## 第三步：让 AI 助手替你重构日志代码

在 Claude Code 里说：

> "把训练脚本里的 wandb / tensorboard / print 日志替换成 intern，保持记录相同的 metrics"

助手会读取 `intern-logger` skill，生成正确的集成代码。典型写法：

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

## 第四步：启动后端服务

在你想托管面板的机器上：

```bash
pip install my-cheap-intern[server]
intern-server launch --key=my-key
```

浏览器打开 `http://localhost:8080` 可以看到 Web 面板。Server 和训练脚本可以在不同机器上，把 `localhost` 换成 server 的 IP 即可。

## 第五步：让 AI 助手查询实验

MCP 接入后，有了一些 run 数据，就可以自然语言提问：

| 你说 | 助手会做什么 |
|------|------------|
| "今天跑了哪些实验？" | 按日期搜索 runs，展示摘要和趋势 |
| "对比 baseline 和新方法" | 展示 config diff + metrics 排名 |
| "最新的 run 是不是过拟合了？" | 检查 train/val loss 趋势，拉取原始曲线 |
| "哪个 run 的 val_acc 最好？" | 对所有已完成的 run 按该 metric 排名 |

## 日常工作流

1. **开始工作**：启动 server（`intern-server launch --key=my-key`）
2. **实验过程中**：训练脚本自动向 intern 写入日志
3. **查看进度**：打开 Web 面板，或者直接问 AI 助手
4. **一天结束**：对助手说"总结今天的实验"——它会拉取所有 run、对比 metrics、高亮最佳结果
