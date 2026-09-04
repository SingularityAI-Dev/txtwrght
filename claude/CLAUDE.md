# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`claude` is the Claude binding for the dom-agent workspace: it makes Claude Code the brain
driving the `txtwrght` browser engine that lives in `../txtwrght/`. Read
`../DEVELOPMENT_PLAN.md` first; this directory implements Phase 3 of that plan.

Status: shipped 17 August 2026. `SKILL.md` is the binding. The session primitives it teaches
live in `../txtwrght/src/txtwrght/session.py` and are covered by `tests/test_session.py` there.

## The design in one paragraph

`txtwrght` (Python, Playwright, headless, text-only DOM, zero screenshots) exposes two modes.
Mode 1 is autonomous: an LLM behind an OpenAI-compatible API runs the observe, think, act
loop internally; that mode needs nothing from this directory beyond `.env` configuration.
Mode 2 is what claude exists for: Claude Code itself is the loop. The engine exposes
per-step session primitives as a CLI:

```bash
txtwrght session start --url <url>     # launch browser, returns session id
txtwrght session snapshot              # indexed text view of the current page
txtwrght session act click <index>
txtwrght session act input <index> "text"
txtwrght session act scroll --down
txtwrght session end
```

Claude Code snapshots, chooses one action, acts, and repeats. There is no second LLM in the
loop: token spend stays in one place and Claude keeps its own judgment, memory, and tool
ecosystem while operating the page.

## What gets built here

- `SKILL.md`: a Claude Code skill teaching the snapshot, decide, act loop, the indexed
  element format (`[n]` prefixes, `*[n]` for new elements, tab-depth nesting), and the rule
  that indices are only valid for the current snapshot.
- Thin glue only. Anything reusable across bindings (Gemini in `../gemini/`, Hermes)
  belongs in the engine, not here. If a change here starts adding logic, push it down into
  `txtwrght` instead.

## History note

Until 16 July 2026 this directory held the `hermes-task-distiller` deliverable (a Hermes
skill/plugin pair). That now lives at `../txtwrght/integrations/hermes-task-distiller/` and
feeds Phase 5 (distilling successful agent traces into deterministic Playwright scripts).
