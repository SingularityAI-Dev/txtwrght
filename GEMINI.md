# gem-dom: drive a real page from Gemini CLI

`hermd` runs a headless Chromium and serializes the page to indexed text. No
screenshots, no vision model. You snapshot, choose one action, act, repeat. The
browser stays alive between commands, so each command is one step of your own
reasoning.

Use this when a task needs a live page: a login, a click path, JavaScript
rendering, or state that only exists mid-session. For static public content,
fetch the URL instead: cheaper and faster.

## The loop

```bash
hermd session start --url https://example.com   # opens the page, prints the view
hermd session act click 12                      # acts, prints the new view
hermd session act input 3 "geez"
hermd session end                               # kills the browser, keeps the trace
```

Each `act` prints the page again, so one command is one step. Add `--quiet` to
suppress the view when you do not need to look.

## Reading the view

```
Current Page: [Sign in](https://example.com/login)
Page info: 1280x720px viewport, 1280x2400px total page size, 0.0 pages above, 2.3 pages below, ...

[Start of page]
Sign in
*[1]<input type=text name=username placeholder=Your username id=user />
*[2]<input type=password id=pass value=*** />
	*[3]<button type=submit id=signin>Sign in />
[End of page]
```

- `[n]` is the element index; pass that number to `act`.
- `*[n]` means new since the last snapshot, which is how you see what changed.
- Tab depth is DOM nesting; attribute values are cut at 20 characters.
- `value=` is the element's current content. Passwords show `***` only.
- Text without `[n]` is context, not clickable.

**Indices are renumbered on every snapshot.** Only ever act on numbers from the
most recent output.

## Actions

| Command | Does |
|---|---|
| `hermd session act click <n>` | Click element `n` |
| `hermd session act input <n> "text"` | Type into element `n` |
| `hermd session act select <n> "Option label"` | Pick a dropdown option by visible label |
| `hermd session act scroll [--up] [--pages 0.5] [--index n]` | Scroll window or container |
| `hermd session act press Enter` | Press a key |
| `hermd session act goto <url>` | Navigate |
| `hermd session act wait 2` | Wait for a slow page |
| `hermd session snapshot` | Print the current view again |
| `hermd session tabs` / `switch <i>` | List tabs, drive a different one |
| `hermd session status` / `end` | Inspect, then shut the browser down |

## Rules

1. One action per step: the first action invalidates every other index.
2. Judge by the view printed after acting, not by what you expected.
3. A `target=_blank` click makes the popup the active tab; a `<sys>` note says so.
4. Dialogs are auto-dismissed and can never block the run.
5. Always `end`. The browser is detached and outlives your process until killed.

## The other mode: Gemini as the model behind the loop

Nothing in this directory is needed for that. `hermd run` speaks to any
OpenAI-compatible endpoint, and Gemini exposes one. Point `her-dom/.env` at it:

```bash
LLM_1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_1_API_KEY=<your key>
LLM_1_MODEL=gemini-3.6-flash
```

Then `hermd run "task" --url <url>` runs the observe, think, act loop internally
with Gemini choosing the actions, and writes the same JSONL trace.

The two modes differ in where the judgment lives, not in what the engine does.
Driving it yourself keeps your own memory and tools in the loop and spends no
extra tokens on a second model; `hermd run` is what you want when the loop
should run unattended.

## Traces and distillation

Every session appends to `traces/run-<stamp>-session.jsonl`: page states, the
actions taken, and the identity of each element acted on. `hermd distill
<trace>` turns a successful run into a plain Playwright script, so a flow driven
once by hand replays later with no model at all.

## Setup

```bash
cd ../her-dom && pip install -e .          # or use its .venv directly
hermd session start --url <url>
```

Config lives in `her-dom/.env`. For this mode only the `BROWSER_*`, `SETTLE_*`
and `DIALOG_POLICY` settings matter: no LLM endpoint is used.
