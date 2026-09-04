"""Turn a successful run into a plain Playwright script (Phase 5).

An agent run is expensive and non-deterministic. Most of the time the flow it
discovered is neither: sign in, click through, read a value. Distillation takes
the trace of a run that worked and emits a script that repeats it with no model
in the loop at all.

Indices cannot survive this: they are renumbered on every snapshot and mean
nothing tomorrow. What survives is the element identity captured at action time
(id, name, placeholder, aria-label, text, css path), which is exactly what the
trace records. Selectors are resolved from that here, at distill time.

Guardrails, carried over from the hermes-task-distiller pattern:
  - generated scripts land in a staging directory, never registered anywhere
  - values typed into password fields were scrubbed at trace time, so they come
    out as os.environ lookups, never literals
  - --verify replays the script before you trust it
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from txtwrght.logging import get_logger
from txtwrght.trace import SCRUBBED

log = get_logger(__name__)


class DistillError(Exception):
    pass


@dataclass
class Step:
    action: str
    args: dict[str, Any]
    element: dict[str, Any]
    url_before: str
    url_after: str = ""


@dataclass
class Run:
    trace_path: Path
    start_url: str = ""
    final_url: str = ""
    steps: list[Step] = field(default_factory=list)
    task: str = ""
    success: bool | None = None
    driver: str = "agent"


# -- reading --------------------------------------------------------------


def load_run(trace_path: str | Path) -> Run:
    path = Path(trace_path)
    if not path.exists():
        raise DistillError(f"No such trace: {path}")

    run = Run(trace_path=path)
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        raise DistillError(f"Trace is empty: {path}")

    pending: Step | None = None
    for record in records:
        kind = record.get("type")

        if kind == "task_start":
            run.task = record.get("task", "")
        elif kind == "session_start":
            run.driver = "session"
            run.task = record.get("url", "")
        elif kind == "browser_state":
            url = record.get("url", "")
            if not run.start_url:
                run.start_url = url
            run.final_url = url
            if pending is not None:
                pending.url_after = url
                pending = None
        elif kind == "action_result":
            step = Step(
                action=record.get("action", ""),
                args=record.get("input") or {},
                element=record.get("element") or {},
                url_before=run.final_url,
            )
            run.steps.append(step)
            pending = step
        elif kind == "task_end":
            run.success = bool(record.get("success"))

    if not run.steps:
        raise DistillError(
            f"{path} records no actions, so there is nothing to distill."
        )
    return run


# -- selectors ------------------------------------------------------------


def _quote(value: str) -> str:
    return json.dumps(value)


def selector_for(element: dict[str, Any]) -> str:
    """Most stable selector this element's recorded identity supports."""
    tag = element.get("tag", "*")

    if element.get("id"):
        return f"#{element['id']}"
    if element.get("name"):
        return f"{tag}[name={_quote(element['name'])}]"
    if element.get("placeholder"):
        return f"{tag}[placeholder={_quote(element['placeholder'])}]"
    if element.get("aria_label"):
        return f"{tag}[aria-label={_quote(element['aria_label'])}]"
    text = (element.get("text") or "").strip()
    if text and tag in ("button", "a", "label", "summary"):
        return f"{tag}:has-text({_quote(text)})"
    if element.get("role"):
        return f"{tag}[role={_quote(element['role'])}]"
    if element.get("css"):
        return element["css"]
    raise DistillError(
        f"Step on a <{tag}> has no recorded identity to build a selector from. "
        "Re-run the flow with a current txtwrght so the trace captures elements."
    )


def _secret_name(element: dict[str, Any], used: set[str]) -> str:
    base = element.get("name") or element.get("id") or "value"
    name = "TXTWRGHT_SECRET_" + re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").upper()
    candidate, n = name, 2
    while candidate in used:
        candidate, n = f"{name}_{n}", n + 1
    used.add(candidate)
    return candidate


# -- writing --------------------------------------------------------------


def to_script(run: Run, name: str) -> tuple[str, list[str]]:
    """Return (script source, required secret env var names)."""
    body: list[str] = []
    secrets: list[str] = []
    used: set[str] = set()
    frame_seen = False

    for step in run.steps:
        element = step.element
        if element.get("frame_url") and not frame_seen:
            frame_seen = True
            body.append(
                "    # NOTE: the run acted inside an iframe. Selectors below "
                "target the main frame;"
            )
            body.append(
                "    # wrap them in page.frame_locator(...) if the replay cannot "
                "find them."
            )

        if step.action in ("click", "click_element_by_index"):
            body.append(f"    page.click({_quote(selector_for(element))})")
        elif step.action in ("input", "input_text"):
            text = step.args.get("text", "")
            selector = _quote(selector_for(element))
            if text == SCRUBBED:
                var = _secret_name(element, used)
                secrets.append(var)
                body.append(f"    page.fill({selector}, os.environ[{_quote(var)}])")
            else:
                body.append(f"    page.fill({selector}, {_quote(text)})")
        elif step.action in ("select", "select_dropdown_option"):
            body.append(
                f"    page.select_option({_quote(selector_for(element))}, "
                f"label={_quote(step.args.get('text', ''))})"
            )
        elif step.action == "press":
            body.append(f"    page.keyboard.press({_quote(step.args.get('key', 'Enter'))})")
        elif step.action == "goto":
            body.append(
                f"    page.goto({_quote(step.args.get('url', ''))}, "
                'wait_until="domcontentloaded")'
            )
        elif step.action == "scroll":
            pixels = step.args.get("pixels")
            distance = pixels if pixels else int(720 * float(step.args.get("num_pages", 1)))
            sign = 1 if step.args.get("down", True) else -1
            body.append(f"    page.mouse.wheel(0, {sign * distance})")
        elif step.action == "scroll_horizontally":
            pixels = step.args.get("pixels") or 640
            sign = 1 if step.args.get("right", True) else -1
            body.append(f"    page.mouse.wheel({sign * pixels}, 0)")
        elif step.action == "wait":
            body.append(f"    page.wait_for_timeout({float(step.args.get('seconds', 1)) * 1000:.0f})")
        else:
            body.append(f"    # skipped unsupported action: {step.action}")
            continue

        if step.url_after and step.url_after != step.url_before:
            body.append(
                f"    page.wait_for_url({_quote(step.url_after)}, timeout=15000)"
            )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    secret_note = (
        "\n".join(f"#   {var}" for var in secrets)
        if secrets
        else "#   (none)"
    )

    source = f'''"""Distilled from {run.trace_path.name} on {stamp}.

Generated by `txtwrght distill`. This is a plain Playwright script: no model, no
agent loop. Read it before you trust it, and keep it in staging until a replay
has passed.

Task as originally given:
    {run.task or "(not recorded)"}

Required environment variables:
{secret_note}
"""

import os
import sys

from playwright.sync_api import sync_playwright

START_URL = {_quote(run.start_url)}
FINAL_URL = {_quote(run.final_url)}


def run(page) -> None:
    page.goto(START_URL, wait_until="domcontentloaded")
{chr(10).join(body) if body else "    pass"}


def main(headless: bool = True) -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_context(viewport={{"width": 1280, "height": 720}}).new_page()
        page.on("dialog", lambda dialog: dialog.dismiss())
        try:
            run(page)
            if page.url != FINAL_URL:
                print(f"replay ended on {{page.url}}, the run ended on {{FINAL_URL}}")
            print("ok")
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main(headless="--headed" not in sys.argv))
'''
    return source, secrets


# -- top level ------------------------------------------------------------


def distill(
    trace_path: str | Path,
    out_dir: str | Path = "distilled",
    name: str | None = None,
    verify: bool = False,
) -> dict[str, Any]:
    run = load_run(trace_path)
    script_name = name or f"{Path(trace_path).stem.replace('-', '_')}.py"
    if not script_name.endswith(".py"):
        script_name += ".py"

    source, secrets = to_script(run, script_name)
    staging = Path(out_dir)
    staging.mkdir(parents=True, exist_ok=True)
    destination = staging / script_name
    destination.write_text(source)
    log.info("distilled", trace=str(trace_path), script=str(destination))

    result: dict[str, Any] = {
        "script": str(destination),
        "steps": len(run.steps),
        "secrets": secrets,
        "verified": None,
        "output": "",
    }
    if verify:
        if secrets:
            result["output"] = (
                "not replayed: the script needs "
                + ", ".join(secrets)
                + " in the environment, and this run's values were scrubbed."
            )
        else:
            completed = subprocess.run(
                [sys.executable, str(destination)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            result["verified"] = completed.returncode == 0
            result["output"] = (completed.stdout + completed.stderr).strip()
    return result


def is_candidate(steps: int, threshold: int) -> bool:
    """A run long enough to be worth replaying deterministically."""
    return steps >= threshold
