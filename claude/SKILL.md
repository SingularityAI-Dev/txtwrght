---
name: claude
description: Drive a real browser as a text-only DOM, one step at a time, with Claude Code itself as the loop. Use when a task needs a live web page - filling a form, signing in, extracting data behind navigation, checking a deployed site, reproducing a UI bug - and a plain HTTP fetch is not enough because the page needs JavaScript, clicks, or session state. Not for reading static pages or documentation, where fetching the URL is cheaper.
---

# claude: you are the loop

`txtwrght` drives a headless Chromium and serializes the page to indexed text. No
screenshots, no second model. You snapshot, choose one action, act, and repeat.

The browser lives between commands, so each command is one step of your own
reasoning. Nothing hands control to another agent.

## The loop

```bash
txtwrght session start --url https://example.com   # opens the page, prints the view
txtwrght session act click 12                      # acts, prints the new view
txtwrght session act input 3 "geez"
txtwrght session end                               # kills the browser, keeps the trace
```

Every `act` prints the page again afterwards, so the normal loop is one command
per step. Add `--quiet` when you do not need to look.

## Reading the view

```
Current Page: [Sign in](https://example.com/login)
Page info: 1280x720px viewport, 1280x2400px total page size, 0.0 pages above, 2.3 pages below, ...

Interactive elements from top layer of the current page (full page):

[Start of page]
Sign in
*[0]<label for=user>Username />
*[1]<input type=text name=username placeholder=Your username id=user />
*[2]<input type=password placeholder=Your password id=pass value=*** />
	*[3]<button type=submit id=signin>Sign in />
[End of page]
```

- `[n]` is the element index. Pass that number to `act`.
- `*[n]` means the element is new since the previous snapshot. Useful for
  spotting what a click actually changed.
- Tab depth is DOM nesting.
- Attribute values are cut at 20 characters.
- `value=` shows what an input currently holds. Password fields show `***` only:
  their contents never enter your context or the trace.
- Text with no `[n]` is context, not clickable.

**Indices die with the snapshot.** They are renumbered every time the page is
serialized. Never reuse an index from an earlier view; act on the numbers in the
most recent output only.

## Actions

| Command | Does |
|---|---|
| `txtwrght session act click <n>` | Click element `n` |
| `txtwrght session act input <n> "text"` | Type into element `n` |
| `txtwrght session act select <n> "Option label"` | Choose a dropdown option by its visible label |
| `txtwrght session act scroll [--up] [--pages 0.5] [--pixels 400] [--index n]` | Scroll the window, or the container at `n` |
| `txtwrght session act scroll_horizontally [--left]` | Scroll sideways |
| `txtwrght session act press Enter` | Press a key |
| `txtwrght session act goto <url>` | Navigate |
| `txtwrght session act wait 2` | Wait, for pages that answer slowly |

Inspecting and steering:

| Command | Does |
|---|---|
| `txtwrght session snapshot` | Print the current view again |
| `txtwrght session tabs` | List open tabs, `*` marks the active one |
| `txtwrght session switch <i>` | Drive a different tab (`-1` is the newest) |
| `txtwrght session status` | pid, port, steps taken, trace path |
| `txtwrght session end` | Kill the browser, keep the trace |

## Rules that keep runs cheap and honest

1. **One action per step.** Snapshot, decide, act. Do not queue several clicks
   against one view: the first one invalidates the rest.
2. **Read the result, not your expectation.** The view printed after an action is
   what actually happened. If nothing changed, say so and choose differently
   rather than repeating the same click.
3. **A new tab takes over.** Clicking a `target=_blank` link makes the popup the
   active tab, and a `<sys>` note says so. Use `switch` to go back.
4. **Dialogs are already handled.** `alert`, `confirm` and `prompt` are dismissed
   automatically so they can never block the run. Set `DIALOG_POLICY=accept` in
   `.env` when a flow needs them accepted.
5. **Slow pages need `wait`, not guessing.** The engine waits for load and for
   the DOM to go quiet, but a page that answers after a timer still needs
   `act wait 1` before you judge it.
6. **Always `end`.** The browser is a detached process; it outlives your session
   until killed. `txtwrght session status` tells you if one is already running.

## Secrets

Type credentials with `input` as normal. Anything typed into a `password` field
is masked in the view and scrubbed from the trace. Never paste a secret into a
task description, a URL, or a commit: those are not scrubbed.

## Where the trace goes

Every session appends to `traces/run-<stamp>-session.jsonl`: each page state,
each action, and the identity (`id`, `name`, css path, text) of the element you
acted on. That file is what Phase 5 distillation turns into a plain Playwright
script, so a flow you drove once by hand can be replayed later with no model in
the loop at all.

## When not to use this

If the content is static and public, fetch the URL instead: cheaper and faster.
Reach for a browser when the page needs JavaScript, a login, a click path, or
state that only exists mid-session.

## Setup

```bash
cd ../txtwrght && .venv/bin/python -m txtwrght session start --url <url>
```

Or install once (`pip install -e ../txtwrght`) and call `txtwrght` directly. Config
lives in `txtwrght/.env`; only the `BROWSER_*`, `SETTLE_*` and `DIALOG_POLICY`
settings matter here, since this mode uses no LLM endpoint at all.
