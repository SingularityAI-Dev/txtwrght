# Claude Code prompt: add console + network error capture to txtwrght

Paste everything below into a fresh Claude Code session started in `~/development/txtwrght/txtwrght`.

---

/effort high

Difficulty: medium-high. The change itself is small and localised, but there is one genuine architectural wrinkle (a detached browser that outlives each short-lived CLI command) that a naive `page.on("console")` gets wrong, and one hard constraint (the serialized-page contract and its golden tests) that must not move. Think before typing.

Call the `jcodemunch_guide` tool and strictly follow its instructions; prefer jcodemunch symbol search, outlines, and targeted retrieval over full-file reads for all code exploration in this Python repo.

Use Claude Superpowers as the execution convention: brainstorm the design before writing code, drive the implementation test-first, and run verification-before-completion before you claim anything works.

/goal Add console and network-error capture to the txtwrght engine and expose it through the session CLI, without moving the serialized-page contract. Completion condition, all must hold and be shown with evidence:
1. The existing suite still passes (README claims 92 tests) and the smoke gate still passes 10/10.
2. New tests cover console-message capture, page-error capture, and failed-request capture, and they pass.
3. `tests/test_serializer.py` is UNCHANGED and green: the `[n]` indexed-page format is not touched.
4. A real terminal transcript exists (captured to a file and attached) showing a live `txtwrght` session on a page that emits a `console.error` and a failing `fetch`, then `txtwrght session console` printing both captured entries.
5. The `claude/SKILL.md` and `gemini/GEMINI.md` bindings document the new command.
6. `CHANGELOG.md` and `STATUS.md` are updated.
7. The work is committed on a branch `feat/console-capture` (do NOT commit to the main branch, do NOT open a PR, do NOT push without my go-ahead).

## The task in one line

`txtwrght` drives a real browser but has no way to read the console. A page can throw a `pageerror`, log a `console.error`, or fire a request that 4xx/5xx-fails, and none of it reaches the driver. Add that capture and a `txtwrght session console` command to read it back.

## Repo facts you can rely on (verified 2026-09-02, re-verify before trusting)

- Package root and git repo: `~/development/txtwrght/txtwrght/`. The engine is the Python package `txtwrght` under `src/txtwrght/`. The parent `~/development/txtwrght/` is intentionally un-versioned; never `git init` it.
- Run the CLI as `.venv/bin/python -m txtwrght ...`. The `.venv/bin/txtwrght` console-script shebang is stale (it points at a path that no longer exists). If `-m txtwrght` reports `No module named txtwrght`, repair the editable install with `uv pip install -e . --python .venv/bin/python` (the venv is CPython 3.14; there is no bundled `pip`, use `uv`).
- The console/dialog seam is in `src/txtwrght/browser.py`, where `page.on("dialog", ...)` and `page.on("close", ...)` are attached (around line 105). There is currently NO `page.on("console")` or `page.on("pageerror")` anywhere. That same seam is where popups and adopted new tabs get wired, so whatever you attach here must cover every page the session opens, not just the first one.
- The session model is the wrinkle. `src/txtwrght/session.py` launches a DETACHED Chromium with a remote debugging port, and every `txtwrght session <cmd>` is a SHORT-LIVED Python process that `connect_over_cdp`s, does one thing, and disconnects. A `page.on("console")` handler registered inside one command only lives for that command's few hundred milliseconds. Console output that fires between commands is lost. Design around this: capture during the action/settle window of each command (a click that triggers a failing fetch is exactly when the useful error fires), and persist each captured entry to the session's JSONL trace, which is the store that already spans commands. `txtwrght session console` then reads the entries back from the trace.
- The serialized page text is the prompt contract: `[n]`-indexed elements, `*[n]` for new, tab-depth nesting, pinned by golden tests in `tests/test_serializer.py`. Console output is a SEPARATE stream and a SEPARATE command. Do not fold it into the `[n]` view, and do not touch the serializer. Changing that format is a breaking change and is out of scope here.
- Session subcommands today: `start`, `snapshot`, `act`, `end`, `tabs`, `switch`, `status`. Add `console` in the same style, reading config and the active-session file the same way the others do.
- Bindings are thin glue: `claude/SKILL.md` (Claude) and `gemini/GEMINI.md` (Gemini) document the session CLI. Any real logic goes in `src/txtwrght/`, never in a binding. Update both docs to mention the new command.
- Issues and specs live as local markdown under `.scratch/<feature>/`; there is no git remote for issues.

## Requirements

1. In `browser.py`, at the same seam as the dialog/close handlers and for every adopted page, attach listeners for: `console` (message type + text), `pageerror` (uncaught exceptions), and failed network requests (`requestfailed`, plus responses with status >= 400). Keep each captured entry small and structured: type, text/summary, url where relevant, status where relevant, and a step/timestamp marker.
2. Buffer captured entries and persist each to the session JSONL trace as its own record type (for example `{"type": "console", ...}`), so it survives across the short-lived CLI invocations. Bound the in-memory buffer the way the step budget is bounded; do not let it grow without limit.
3. Capture during the initial page load in `session start` and during each `act`'s settle window, so an action that provokes a console error or a failed request has that error recorded against it.
4. Add `txtwrght session console` to read the entries back from the trace. Support at least `--errors-only` (drop plain `console.log`, keep error/warning/pageerror/failed-request) and a `--limit N`. Match the output style of the existing session commands.
5. Secrets: console text and request URLs are free-form and can contain tokens. Do not persist an entry whose text or URL matches an obvious secret shape (bearer tokens, `api_key=`, long hex/base64 runs); redact it to a placeholder. Note in a comment that password-field values already never reach the console because the serializer masks them.
6. Do not change the serialized-page format or `test_serializer.py`. Do not change the autonomous `txtwrght run` loop's behaviour beyond it now recording console entries to the trace.

## How to work

- Start by reading, via jcodemunch: `ARCHITECTURE.md`, `README.md`, `src/txtwrght/browser.py`, `src/txtwrght/session.py`, `src/txtwrght/tools.py` (for how an action settles), and the trace-writing code, plus `tests/` layout and `tests/test_serializer.py`. Understand the settle/adopt flow before you touch it.
- Brainstorm the capture-and-persist design against the detached-session constraint above, then confirm the approach makes sense before implementing.
- Test-first. Write a hermetic fixture page rather than depending on the network: a `data:text/html` document whose inline script runs `console.error('boom')`, throws once, and `fetch()`es a URL that fails. Assert that after a `start` (or `act`) the trace contains the console error, the pageerror, and the failed request, and that `session console --errors-only` prints them. Keep a test that asserts the serialized view is byte-identical with and without the console feature on, so a regression into the contract fails loudly.
- Measure, do not assume. Before declaring done, run a real session end to end:
  ```
  .venv/bin/python -m txtwrght session start --url "data:text/html,<script>console.error('boom');fetch('https://example.invalid/nope');throw new Error('kaboom')</script>" | tee /tmp/txtwrght-console-evidence.txt
  .venv/bin/python -m txtwrght session console --errors-only | tee -a /tmp/txtwrght-console-evidence.txt
  .venv/bin/python -m txtwrght session end
  ```
  The transcript must show the captured `console.error`, the thrown error, and the failed request. Attach `/tmp/txtwrght-console-evidence.txt`. A green unit test is not sufficient evidence on its own; the live transcript is the proof.
- Run the full suite and the smoke gate and paste the real counts. If the suite count differs from 92, report the actual number rather than asserting the badge.

## Guardrails

- Branch `feat/console-capture` off the current HEAD. Commit there with a clear message. Do not commit to main, do not push, do not open a PR until I have seen the diff and the evidence and said go.
- Surgical scope: console capture, its persistence, the `session console` command, its tests, and the two binding docs plus CHANGELOG/STATUS. Do not refactor adjacent code, do not touch the serializer, do not restyle unrelated files.
- No em-dashes in anything you author.
- If the detached-session constraint forces a design tradeoff (for example, console that fires while no command is connected is genuinely unrecoverable without a persistent sidecar), state that limitation plainly in the SKILL.md and the CHANGELOG rather than pretending full coverage.

When the completion condition is met, stop and report: what you added, the real test and smoke counts, the path to the evidence transcript, and the one thing you would build next (a persistent capture sidecar, if you judged it out of scope). Then wait for my go-ahead on push.
