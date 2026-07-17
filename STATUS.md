# Status

> Updated: 2026-07-17

## Where we are
hermd runs tasks end to end: Playwright drives the page, the DOM is serialized to indexed text, an LLM picks one action per step through a forced AgentOutput tool call, every run writes a JSONL trace. Phase 0 and all of Phase 1 steps 1 to 5 of ../DEVELOPMENT_PLAN.md are done. First live run: form fixture filled and submitted in 4 steps by claude-sonnet-5 through the local CLIProxyAPI, submitted:geez verified from the trace's final browser state.

## Recent
- LLM slice landed: llm.py (failover chain, auto-fixer, parse retry), agent.py (loop port), trace.py (JSONL + password scrubbing), hermd run CLI. 51 tests green, live-proven.
- Engine core commit 0bd5e80: extractor.js injected via page.evaluate, selector map lives in-page (window.__hermd_selector_map), refs stripped at the JSON boundary, isNew via persistent WeakSet; serializer format pinned by golden tests.
- LLM endpoints resolved: 1. CLIProxyAPI 127.0.0.1:8317 (Claude subscription, always on), 2. Hermes proxy 127.0.0.1:8645 (Nous upstream, start manually). Values live in .env.

## Next
- Phase 1 exit gate: 10-task live smoke suite (fixtures + real sites incl. a login form and an SPA), recorded traces, target 8/10. Gated on API spend.
- Phase 2 hardening: navigation waits after actions, new-tab/popup handling, iframe stance (main-frame v1), structlog wiring.
- Phase 3 clau-dom binding: per-step session CLI (hermd session start/snapshot/act) + SKILL.md.

## Handover
Full context for the next session lives in HANDOVER.md (canonical) and NEXT_SESSION_PROMPT.md (now historical: its goal completed 2026-07-17). A duplicate handover in docs/ was merged into HANDOVER.md and removed on 2026-07-17.
