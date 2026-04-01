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

This project uses [my-cheap-intern](https://github.com/Yifang-Qin/my-cheap-intern) for experiment logging.

- SDK: `import intern` → `intern.init()` / `intern.log()` / `intern.finish()`
- Server: set `INTERN_SERVER` and `INTERN_API_KEY` env vars, or pass them to `intern.init()`
- Claude Code skills `intern-logger` and `intern-reader` are installed in `.claude/skills/` — they contain full API reference and MCP query patterns.
- MCP connection is configured in `.mcp.json` — your AI assistant can query experiments directly.
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
        "url": f"{server_url}/mcp/sse",
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


def main():
    parser = argparse.ArgumentParser(prog="intern-cli")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Set up Claude Code skills, CLAUDE.md, and MCP config for this project")
    init_parser.add_argument("--server", default="http://localhost:8080", help="Intern server URL (default: http://localhost:8080)")
    init_parser.add_argument("--key", default=None, help="API key. If omitted, uses ${INTERN_API_KEY} env var expansion at runtime")
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
