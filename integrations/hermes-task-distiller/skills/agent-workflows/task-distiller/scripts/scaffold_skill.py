#!/usr/bin/env python3
"""
scaffold_skill.py -- turn a verified script + its trace record into a ready-to-review
Hermes skill directory.

By default this writes to a STAGING area, not the live skill library:
    ~/.hermes/distillery/staged-skills/<category>/<name>/

Review the generated SKILL.md, then either ask the agent to create it for real via
the `skill_manage` tool (preferred -- respects write_approval staging), or pass
--commit to this script to copy it straight into the live library:
    ~/.hermes/skills/<category>/<name>/

Usage:
    python3 scaffold_skill.py \\
        --name sync-github-issues-to-notion \\
        --category productivity \\
        --description "Mirrors open GitHub issues into a Notion database. Use when \\
asked to sync or mirror GitHub issues into Notion." \\
        --script /path/to/verified_script.py \\
        --trace ~/.hermes/distillery/traces/sync-github-issues-...json \\
        [--author "Your Name"] [--blueprint-schedule "0 * * * *"] [--commit]
"""
import argparse
import json
import shutil
import textwrap
from pathlib import Path

SKILLS_ROOT = Path.home() / ".hermes" / "skills"
STAGING_ROOT = Path.home() / ".hermes" / "distillery" / "staged-skills"

SKILL_TEMPLATE = """---
name: {name}
description: {description}
version: 0.1.0
author: {author}
license: MIT
metadata:
  hermes:
    tags: [{category}, distilled, automation]
{blueprint_block}---

# {title}

This skill was distilled from a real agent run on {recorded_date} rather than hand-written.
See `references/trace.json` for the original recorded process this was built from.

## When to Use

{description}

## Quick Reference

Run the bundled script instead of re-deriving the steps with the LLM:

    python3 ${{HERMES_SKILL_DIR}}/scripts/{script_name} [args]

## Procedure

1. Confirm the current request matches this skill's shape (same kind of task, possibly
   different inputs/parameters than last time).
2. Run `${{HERMES_SKILL_DIR}}/scripts/{script_name}` via `terminal` (or `execute_code` if
   it only calls things already reachable through `hermes_tools`) with whatever inputs
   this run needs.
3. Report the script's output back to the user. Do not re-run the original multi-step
   plan through LLM reasoning -- that defeats the point of having distilled it.

## Pitfalls

- If the inputs for this run are meaningfully different in *kind* (not just in value) from
  what's recorded in `references/trace.json`, the script may not generalize -- fall back to
  doing the task directly and consider whether this skill needs revising.
- Check any `required_environment_variables` below are actually set before running.

## Verification

Confirm the script exits 0 and its output matches the shape of the verified outcome recorded
in `references/trace.json`.
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--name", required=True, help="kebab-case skill name")
    ap.add_argument(
        "--category", required=True, help="category subfolder, e.g. productivity, devops, research"
    )
    ap.add_argument("--description", required=True)
    ap.add_argument("--script", required=True, help="path to the verified, working Python script")
    ap.add_argument("--trace", required=True, help="path to the JSON trace from record_trace.py")
    ap.add_argument("--author", default="task-distiller")
    ap.add_argument(
        "--blueprint-schedule",
        default="",
        help="cron expression; if set, the scaffolded skill becomes a schedulable blueprint",
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="write directly into ~/.hermes/skills/ instead of staging",
    )
    args = ap.parse_args()

    script_path = Path(args.script).expanduser()
    trace_path = Path(args.trace).expanduser()
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")
    if not trace_path.exists():
        raise SystemExit(f"Trace not found: {trace_path}")

    trace = json.loads(trace_path.read_text())
    root = SKILLS_ROOT if args.commit else STAGING_ROOT
    skill_dir = root / args.category / args.name
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)

    shutil.copy2(script_path, skill_dir / "scripts" / script_path.name)
    (skill_dir / "references" / "trace.json").write_text(json.dumps(trace, indent=2))

    blueprint_block = ""
    if args.blueprint_schedule:
        block = textwrap.dedent(
            f"""\
            blueprint:
              schedule: "{args.blueprint_schedule}"
              deliver: origin
            """
        )
        blueprint_block = "    " + block.replace("\n", "\n    ").rstrip() + "\n"

    skill_md = SKILL_TEMPLATE.format(
        name=args.name,
        description=args.description,
        author=args.author,
        category=args.category,
        blueprint_block=blueprint_block,
        title=args.name.replace("-", " ").title(),
        recorded_date=trace.get("recorded_at", "an earlier session"),
        script_name=script_path.name,
    )
    (skill_dir / "SKILL.md").write_text(skill_md)

    print(f"Scaffolded skill at: {skill_dir}")
    if not args.commit:
        print("This is STAGED, not live. Review it, then either:")
        print("  - ask the agent to create it for real via the skill_manage tool, or")
        print(
            f"  - rerun this command with --commit to copy it straight into "
            f"~/.hermes/skills/{args.category}/{args.name}/"
        )


if __name__ == "__main__":
    main()
