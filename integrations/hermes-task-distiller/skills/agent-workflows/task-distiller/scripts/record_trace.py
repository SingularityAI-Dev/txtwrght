#!/usr/bin/env python3
"""
record_trace.py -- append a structured record of a just-completed agentic task
to the local distillery trace store, so task-distiller has something concrete
to turn into a script later (rather than reconstructing it from memory).

Usage:
    python3 record_trace.py --title "Sync GitHub issues to Notion" \\
        --goal "Pull open issues from repo X and mirror them as Notion pages" \\
        --steps steps.json \\
        --services github,notion \\
        --outcome "23 issues synced, verified against the Notion DB view" \\
        --tags backlog,sync \\
        --big-task-signal tool_calls=14,duration_s=340,external_calls=9

`--steps` accepts either a path to a JSON file or a literal JSON array on the
command line, e.g.:
    [
      {"n": 1, "tool": "web_extract", "purpose": "fetch open issues from the GitHub API",
       "note": "used cursor pagination"},
      {"n": 2, "tool": "execute_code", "purpose": "reshape issue JSON into Notion blocks"},
      {"n": 3, "tool": "mcp_notion.create_page", "purpose": "create/update one page per issue"}
    ]

Record only tool names, purposes, and non-sensitive notes here -- never secrets,
API keys, or tokens, even ones that were only used transiently.
"""
import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

TRACE_DIR = Path.home() / ".hermes" / "distillery" / "traces"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "task"


def parse_kv_list(raw: str) -> dict:
    out = {}
    if not raw:
        return out
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def load_steps(raw: str):
    p = Path(raw).expanduser()
    text = p.read_text() if p.exists() else raw
    try:
        steps = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Could not parse --steps as a file path or inline JSON array: {e}")
    if not isinstance(steps, list):
        raise SystemExit("--steps must be a JSON array of step objects")
    return steps


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--title", required=True, help="Short human name for the task")
    ap.add_argument("--goal", required=True, help="What the task was trying to accomplish")
    ap.add_argument("--steps", required=True, help="JSON file path or inline JSON array of steps")
    ap.add_argument(
        "--services", default="", help="Comma-separated external services/APIs touched"
    )
    ap.add_argument("--outcome", required=True, help="The verified final result")
    ap.add_argument("--tags", default="", help="Comma-separated free-form tags")
    ap.add_argument(
        "--big-task-signal",
        default="",
        help="Comma-separated key=value stats, e.g. tool_calls=14,duration_s=340",
    )
    args = ap.parse_args()

    record = {
        "id": str(uuid.uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "title": args.title,
        "goal": args.goal,
        "steps": load_steps(args.steps),
        "external_services": [s.strip() for s in args.services.split(",") if s.strip()],
        "verified_outcome": args.outcome,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "signals": parse_kv_list(args.big_task_signal),
    }

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.title)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = TRACE_DIR / f"{slug}-{ts}.json"
    out_path.write_text(json.dumps(record, indent=2))
    print(f"Trace recorded: {out_path}")


if __name__ == "__main__":
    main()
