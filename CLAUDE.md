# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`clau-dom` is the Claude binding for the dom-agent workspace: it makes Claude Code the brain
driving the `hermd` browser engine that lives in `../her-dom/`. Read
`../DEVELOPMENT_PLAN.md` first; this directory implements Phase 3 of that plan and stays
empty until Phases 0 to 2 (the engine) are done.

## The design in one paragraph

`hermd` (Python, Playwright, headless, text-only DOM, zero screenshots) exposes two modes.
Mode 1 is autonomous: an LLM behind an OpenAI-compatible API runs the observe, think, act
loop internally; that mode needs nothing from this directory beyond `.env` configuration.
Mode 2 is what clau-dom exists for: Claude Code itself is the loop. The engine exposes
per-step session primitives as a CLI:

```bash
hermd session start --url <url>     # launch browser, returns session id
hermd session snapshot              # indexed text view of the current page
hermd session act click <index>
hermd session act input <index> "text"
hermd session act scroll --down
hermd session end
```

Claude Code snapshots, chooses one action, acts, and repeats. There is no second LLM in the
loop: token spend stays in one place and Claude keeps its own judgment, memory, and tool
ecosystem while operating the page.

## What gets built here

- `SKILL.md`: a Claude Code skill teaching the snapshot, decide, act loop, the indexed
  element format (`[n]` prefixes, `*[n]` for new elements, tab-depth nesting), and the rule
  that indices are only valid for the current snapshot.
- Thin glue only. Anything reusable across bindings (Gemini in `../gem-dom/`, Hermes)
  belongs in the engine, not here. If a change here starts adding logic, push it down into
  `her-dom` instead.

## History note

Until 16 July 2026 this directory held the `hermes-task-distiller` deliverable (a Hermes
skill/plugin pair). That now lives at `../her-dom/integrations/hermes-task-distiller/` and
feeds Phase 5 (distilling successful agent traces into deterministic Playwright scripts).
