"""Phase 1 exit gate: run the smoke suite, record traces, report a pass rate.

Not a demo. Every task runs the real agent loop against a real browser, is
verified against the page (or the agent's own answer) rather than against
vibes, and leaves a JSONL trace behind. The gate is 8 of 10.

    python smoke/run_smoke.py                 # run everything not yet passed
    python smoke/run_smoke.py --only form-fill,real-login
    python smoke/run_smoke.py --fixtures      # skip the live sites (no network)
    python smoke/run_smoke.py --fresh         # ignore earlier results

Results are written after every task, so a killed run resumes where it stopped
instead of starting over.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hermd.agent import Agent  # noqa: E402
from hermd.browser import Browser  # noqa: E402
from hermd.config import Config  # noqa: E402
from hermd.llm import LLMClient, LLMError  # noqa: E402
from hermd.trace import Trace  # noqa: E402

TASKS = Path(__file__).parent / "tasks.yaml"
PAGES = ROOT / "tests" / "pages"
RESULTS = Path(__file__).parent / "results.json"
REPORT = Path(__file__).parent / "RESULTS.md"
GATE = 8


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def serve_fixtures() -> tuple[ThreadingHTTPServer, str]:
    """Fixtures are served over http: file:// is an opaque origin, so frames
    would be unreachable and the iframe task would fail for the wrong reason."""
    handler = functools.partial(_QuietHandler, directory=str(PAGES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def verify(spec: dict, browser: Browser, answer: str) -> tuple[bool, str]:
    page = browser.page
    if "js" in spec:
        try:
            return bool(page.evaluate(f"() => ({spec['js']})")), "page state"
        except Exception as error:
            return False, f"verifier failed to run: {error}"
    if "frame_js" in spec:
        frames = [f for f in page.frames if f is not page.main_frame]
        if not frames:
            return False, "no child frame on the final page"
        try:
            return bool(frames[0].evaluate(f"() => ({spec['frame_js']})")), "frame state"
        except Exception as error:
            return False, f"verifier failed to run: {error}"
    if "url_contains" in spec:
        return spec["url_contains"] in page.url, f"final url {page.url}"
    if "answer_contains" in spec:
        return spec["answer_contains"].lower() in (answer or "").lower(), "agent answer"
    if "answer_min_length" in spec:
        return len((answer or "").strip()) >= int(spec["answer_min_length"]), "agent answer"
    return False, "no verifier defined"


def run_task(task: dict, base: str, config: Config) -> dict:
    url = task["url"] if task["kind"] == "live" else f"{base}/{task['url']}"
    started = time.time()

    task_config = Config(**{**config.__dict__, "max_steps": task.get("max_steps", 15)})
    trace = Trace()
    llm = LLMClient(task_config.llm_endpoints)

    passed, detail, result = False, "", None
    try:
        with Browser(task_config) as browser:
            browser.goto(url)
            agent = Agent(task["task"], browser, llm, config=task_config, trace=trace)
            result = agent.run()
            passed, detail = verify(task["verify"], browser, result.data)
    except Exception as error:  # a crashed task is a failed task, not a stopped run
        detail = f"run raised: {error}"
    finally:
        llm.close()
        trace.close()

    return {
        "id": task["id"],
        "kind": task["kind"],
        "passed": passed,
        "detail": detail,
        "steps": result.steps if result else 0,
        "agent_success": result.success if result else False,
        "answer": (result.data if result else "")[:300],
        "tokens": result.usage.get("total_tokens", 0) if result else 0,
        "seconds": round(time.time() - started, 1),
        "trace": str(trace.path),
    }


def write_report(results: dict[str, dict]) -> None:
    ordered = list(results.values())
    passed = sum(1 for r in ordered if r["passed"])
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Smoke suite results",
        "",
        f"Run {stamp}. **{passed} of {len(ordered)} passed** "
        f"(gate is {GATE} of 10).",
        "",
        "| Task | Kind | Result | Steps | Tokens | Seconds | Checked against |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ordered:
        lines.append(
            f"| {r['id']} | {r['kind']} | {'pass' if r['passed'] else 'FAIL'} | "
            f"{r['steps']} | {r['tokens']} | {r['seconds']} | {r['detail']} |"
        )
    lines += ["", "## Traces", ""]
    lines += [f"- `{r['id']}`: `{r['trace']}`" for r in ordered]
    failures = [r for r in ordered if not r["passed"]]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines += [
                f"### {r['id']}",
                "",
                f"- agent reported success: {r['agent_success']}",
                f"- answer: {r['answer'] or '(none)'}",
                f"- verifier: {r['detail']}",
                "",
            ]
    REPORT.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="Comma-separated task ids.")
    parser.add_argument("--fixtures", action="store_true", help="Skip live sites.")
    parser.add_argument("--fresh", action="store_true", help="Ignore earlier results.")
    args = parser.parse_args()

    tasks = yaml.safe_load(TASKS.read_text())
    if args.only:
        wanted = {t.strip() for t in args.only.split(",")}
        tasks = [t for t in tasks if t["id"] in wanted]
    if args.fixtures:
        tasks = [t for t in tasks if t["kind"] == "fixture"]

    results: dict[str, dict] = {}
    if RESULTS.exists() and not args.fresh:
        results = json.loads(RESULTS.read_text())

    config = Config.from_env()
    if not config.llm_endpoints:
        print("No LLM endpoint configured. See .env.example.")
        return 2
    # One probe call up front. Without it a dead endpoint burns the whole suite
    # producing ten identical authentication failures.
    probe = LLMClient(config.llm_endpoints)
    try:
        probe.invoke(
            [
                {"role": "system", "content": "Reply by calling the tool."},
                {"role": "user", "content": "Call done with the text ok."},
            ]
        )
    except LLMError as error:
        print(f"LLM chain unusable, nothing was run:\n{error}")
        return 2
    except Exception:
        pass  # a malformed answer still proves the endpoint is alive
    finally:
        probe.close()

    server, base = serve_fixtures()
    try:
        for task in tasks:
            previous = results.get(task["id"])
            if previous and previous["passed"] and not args.fresh:
                print(f"  {task['id']}: already passed, skipping")
                continue

            print(f"  {task['id']}: running...", flush=True)
            result = run_task(task, base, config)
            results[task["id"]] = result
            RESULTS.write_text(json.dumps(results, indent=2))
            write_report(results)
            print(
                f"  {task['id']}: {'pass' if result['passed'] else 'FAIL'} "
                f"({result['steps']} steps, {result['seconds']}s) {result['detail']}"
            )
    finally:
        server.shutdown()
        server.server_close()

    passed = sum(1 for r in results.values() if r["passed"])
    print(f"\n{passed}/{len(results)} passed. Report: {REPORT}")
    return 0 if passed >= GATE else 1


if __name__ == "__main__":
    sys.exit(main())
