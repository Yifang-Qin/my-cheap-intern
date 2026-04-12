"""intern-cli: client-side utilities for my-cheap-intern."""
import argparse
import json
import re
import shutil
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

MARKER_BEGIN = "<!-- intern:begin -->"
MARKER_END = "<!-- intern:end -->"

CLAUDE_MD_SNIPPET = f"""{MARKER_BEGIN}
## Intern Experiment Tracking

**行为规则**：当用户询问实验、训练、run、指标、结果等相关问题时（例如"今天跑了哪些实验"、"最新结果怎么样"、"对比一下"、"训练炸了吗"），**立即使用 `intern-reader` skill 并调用 intern MCP 工具查询，不要先追问用户要哪个 run**。

- **查实验数据** → 调用 `intern-reader` skill，内含 MCP 工具用法和常见查询模式
- **写 logging 代码** → 调用 `intern-logger` skill，内含 SDK API 参考
- MCP 连接配置在 `.mcp.json`，工具名前缀 `mcp__my-cheap-intern__`
{MARKER_END}
"""
MCP_SERVER_KEY = "my-cheap-intern"


def cmd_init(args):
    cwd = Path.cwd()

    # 1. Copy skills
    target_skills = cwd / ".claude" / "skills"
    target_skills.mkdir(parents=True, exist_ok=True)

    for skill_dir in sorted(SKILLS_DIR.glob("intern-*")):
        dest = target_skills / skill_dir.name
        if dest.exists():
            shutil.rmtree(dest)
            shutil.copytree(skill_dir, dest)
            print(f"  updated {dest.relative_to(cwd)}")
        else:
            shutil.copytree(skill_dir, dest)
            print(f"  created {dest.relative_to(cwd)}")

    # 2. Upsert CLAUDE.md section
    claude_md = cwd / "CLAUDE.md"
    existing = claude_md.read_text() if claude_md.exists() else ""

    if MARKER_BEGIN in existing:
        pattern = re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END)
        updated = re.sub(pattern, CLAUDE_MD_SNIPPET.strip(), existing, flags=re.DOTALL)
        if updated == existing:
            print(f"  skip CLAUDE.md (already up to date)")
        else:
            claude_md.write_text(updated)
            print(f"  updated intern section in CLAUDE.md")
    else:
        with open(claude_md, "a") as f:
            f.write("\n" + CLAUDE_MD_SNIPPET)
        print(f"  appended intern section to CLAUDE.md")

    # 3. Write .mcp.json
    mcp_json = cwd / ".mcp.json"
    mcp_data = json.loads(mcp_json.read_text()) if mcp_json.exists() else {}
    servers = mcp_data.setdefault("mcpServers", {})

    server_url = args.server.rstrip("/")
    auth_value = f"Bearer {args.key}" if args.key else "Bearer ${INTERN_API_KEY}"
    new_config = {
        "type": "http",
        "url": f"{server_url}/mcp/",
        "headers": {"Authorization": auth_value},
    }

    if servers.get(MCP_SERVER_KEY) == new_config:
        print(f"  skip .mcp.json (already up to date)")
    else:
        verb = "updated" if MCP_SERVER_KEY in servers else "wrote"
        servers[MCP_SERVER_KEY] = new_config
        mcp_json.write_text(json.dumps(mcp_data, indent=2) + "\n")
        print(f"  {verb} MCP config in .mcp.json (server: {server_url})")

    print("done. Your AI assistant now knows how to use intern.")


def cmd_uninit(args):
    cwd = Path.cwd()

    # 1. Remove skills
    skills_dir = cwd / ".claude" / "skills"
    removed_any_skill = False
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.glob("intern-*")):
            shutil.rmtree(skill_dir)
            print(f"  removed {skill_dir.relative_to(cwd)}")
            removed_any_skill = True
    if not removed_any_skill:
        print("  skip skills (none found)")

    # 2. Remove CLAUDE.md section
    claude_md = cwd / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if MARKER_BEGIN in content:
            pattern = r"\n?" + re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END) + r"\n?"
            cleaned = re.sub(pattern, "\n", content, flags=re.DOTALL).strip() + "\n"
            claude_md.write_text(cleaned)
            print("  removed intern section from CLAUDE.md")
        else:
            print("  skip CLAUDE.md (no intern section)")
    else:
        print("  skip CLAUDE.md (file not found)")

    # 3. Remove .mcp.json entry
    mcp_json = cwd / ".mcp.json"
    if mcp_json.exists():
        mcp_data = json.loads(mcp_json.read_text())
        servers = mcp_data.get("mcpServers", {})
        if MCP_SERVER_KEY in servers:
            del servers[MCP_SERVER_KEY]
            if servers:
                mcp_json.write_text(json.dumps(mcp_data, indent=2) + "\n")
            else:
                mcp_json.unlink()
                print("  removed .mcp.json (no servers left)")
            print("  removed intern from .mcp.json") if servers else None
        else:
            print("  skip .mcp.json (no intern entry)")
    else:
        print("  skip .mcp.json (file not found)")

    print("done. Intern integration removed from this project.")


def main():
    parser = argparse.ArgumentParser(prog="intern-cli")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Set up Claude Code skills, CLAUDE.md, and MCP config for this project")
    init_parser.add_argument("--server", default="http://localhost:8080", help="Intern server URL (default: http://localhost:8080)")
    init_parser.add_argument("--key", default=None, help="API key. If omitted, uses ${INTERN_API_KEY} env var expansion at runtime")
    init_parser.set_defaults(func=cmd_init)

    uninit_parser = sub.add_parser("uninit", help="Remove intern skills, CLAUDE.md section, and MCP config from this project")
    uninit_parser.set_defaults(func=cmd_uninit)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
