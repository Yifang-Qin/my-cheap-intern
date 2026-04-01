"""intern-cli: client-side utilities for my-cheap-intern."""
import argparse
import shutil
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

CLAUDE_MD_SNIPPET = """\

## Experiment Tracking

This project uses [my-cheap-intern](https://github.com/Yifang-Qin/my-cheap-intern) for experiment logging.

- SDK: `import intern` → `intern.init()` / `intern.log()` / `intern.finish()`
- Server: set `INTERN_SERVER` and `INTERN_API_KEY` env vars, or pass them to `intern.init()`
- Claude Code skills `intern-logger` and `intern-reader` are installed in `.claude/skills/` — they contain full API reference and MCP query patterns.
"""

MARKER = "## Experiment Tracking"


def cmd_init(args):
    cwd = Path.cwd()

    # 1. Copy skills
    target_skills = cwd / ".claude" / "skills"
    target_skills.mkdir(parents=True, exist_ok=True)

    copied = []
    for skill_dir in sorted(SKILLS_DIR.glob("intern-*")):
        dest = target_skills / skill_dir.name
        if dest.exists():
            print(f"  skip {dest.relative_to(cwd)} (already exists)")
        else:
            shutil.copytree(skill_dir, dest)
            copied.append(skill_dir.name)
            print(f"  created {dest.relative_to(cwd)}")

    # 2. Append to CLAUDE.md
    claude_md = cwd / "CLAUDE.md"
    existing = claude_md.read_text() if claude_md.exists() else ""

    if MARKER in existing:
        print(f"  skip CLAUDE.md (already contains '{MARKER}')")
    else:
        with open(claude_md, "a") as f:
            f.write(CLAUDE_MD_SNIPPET)
        print(f"  appended experiment tracking section to CLAUDE.md")

    print("done. Your AI assistant now knows how to use intern.")


def main():
    parser = argparse.ArgumentParser(prog="intern-cli")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Set up Claude Code skills and CLAUDE.md for this project")
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
