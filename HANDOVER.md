# Handover: hermd (her-dom engine)

> Written 2026-07-17. Read alongside `STATUS.md` (living state), `CHANGELOG.md`, and `../DEVELOPMENT_PLAN.md` (the master plan). This handover carries the context a fresh session needs to land Phase 1 steps 3 to 5 without re-deriving decisions. This is the single canonical handover; the session's brain.md at `~/.claude/projects/-Users-rainierpotgieter-development-dom-agent-her-dom/memory/brain.md` auto-loads and points at the same state.

## One-paragraph summary

`hermd` is a CLI-first, headless, text-only DOM browser agent. Playwright drives a real browser, the page is serialized to indexed text (no screenshots, no multimodal models), an LLM picks one action per step, loop runs until done. It is a Playwright port of Alibaba's MIT-licensed `page-agent` (itself derived from `browser-use`). The engine core is landed and verified with no LLM in it yet. The next slice adds the LLM: client, agent loop, and run trace, ending at a live smoke suite.

## Where the code is

- Engine core committed at `0bd5e80`: `src/hermd/` holds `browser.py` (Playwright lifecycle), `dom/extractor.js` (page-agent DOM port, injected via `page.evaluate`), `dom/serializer.py` (FlatDomTree JSON to indexed text, format pinned by 8 golden tests), `dom/state.py` (BrowserState), `tools.py` (click / input_text / select_dropdown_option / scroll incl. container + shadow DOM), `config.py`, `__main__.py` (`hermd snapshot` only so far).
- 23 tests green against fixtures `tests/pages/{form,scroll,shadow,spa}.html`. Live-verified on news.ycombinator.com (514 lines, all interactive elements indexed).
- Selector map lives **in-page** as `window.__hermd_selector_map`; refs are stripped at the JSON boundary; `isNew` tracked via a persistent in-page WeakSet. Indices are valid only within one step.

## What is NOT built yet (the next session's job — Phase 1 steps 3 to 5)

1. **`llm.py`** — httpx OpenAI-compatible client. One forced tool call named `AgentOutput`; its schema is the union of tool arg schemas nested under an `action` field. Port page-agent's auto-fixer for malformed model output: JSON-in-content, action-name-used-as-toolname, double-stringified args, primitive coercion, and missing-action-falls-back-to-`wait`. Retry twice on parse failure.
2. **`agent.py`** — the step loop. Port `PageAgentCore` semantics: max 40 steps (configurable), step delay, URL-change and step-budget observations injected as `<sys>` notes, per-step history carrying the reflection fields (`evaluation_previous_goal`, `memory`, `next_goal`), error events recorded in the trace but **excluded** from LLM context.
3. **`trace.py`** — JSONL run trace from day one: every BrowserState, LLM output, action result, timing, token counts. This is the "measure, do not assume" artifact and the fuel for Phase 5 distillation. Not optional, not a follow-up.
4. **`hermd run`** — wire the CLI subcommand: `hermd run "task" --url ...`.

## Reference source to port from (already cloned)

- `../repos/page-agent/packages/core/src/PageAgentCore.ts` — the agent loop to mirror.
- `../repos/page-agent/packages/core/src/utils/autoFixer.ts` — the exact malformed-output cases to port as unit tests.
- `../repos/page-agent/packages/core/src/tools/index.ts` — MacroTool / AgentOutput schema shape.
- `../repos/page-agent/packages/core/src/types.ts` — the `{evaluation_previous_goal, memory, next_goal, action}` output contract.
- `../repos/page-agent/packages/llms/src/OpenAIClient.ts` — OpenAI-compatible client, forced tool call.

## Decisions already made (do not relitigate)

- **Engine + thin bindings**, not three rewrites. `clau-dom` (Claude) and `gem-dom` (Gemini) bind to this one engine later (Phases 3 to 4). Structural, stated for correction in the plan; treat as settled unless Rainier says otherwise.
- **Naming unified on `hermd`** (distribution, import, CLI). Folder/repo stays `her-dom`.
- **Config is env-only** via `.env` (`python-dotenv`). See `.env.example`: `LLM_{1,2,3}_{BASE_URL,API_KEY,MODEL}`, `BROWSER_*`, `MAX_STEPS`, `STEP_DELAY`. Note: `config.py` currently loads only the browser vars; the LLM vars need adding to `Config.from_env()` in step 3.
- **LLM endpoints (decided and verified 2026-07-17):** ordered failover chain, OpenAI-compatible, all localhost, no cloud keys. `.env` is already written and endpoint 1 live-proven (test completion returned through the Claude subscription). Chain: 1. **CLIProxyAPI** at `http://127.0.0.1:8317/v1` (brew service, always on, Claude subscription via the claude-rain.singlesource login; key is the local `sk-local-*` from `/opt/homebrew/etc/cliproxyapi.conf`), model `claude-sonnet-5`. 2. **Hermes proxy** at `http://127.0.0.1:8645/v1` (Nous Portal upstream, `hermes proxy start` to run, any bearer token accepted), model `anthropic/claude-sonnet-5`. Droid was dropped from the chain: `droid daemon` speaks websocket/IPC, not OpenAI HTTP, and rides the same Claude subscription as endpoint 1 anyway. Client walks the chain on transport/auth failure; per-endpoint parse retry (2x) runs before failing over; endpoints without a `BASE_URL` are skipped; blank `API_KEY` = omit Authorization header.
- **Serializer format is the prompt contract.** The 8 golden tests pin it. Do not let a refactor silently change what the LLM sees. Known upstream quirk kept deliberately: elements with no whitelisted attributes get a padding space, so scrollable-only elements render a double space before `/>`.
- **Index clicking**: resolve element handles from the in-page map, fall back to in-page `el.click()` (what page-agent does) if the handle round-trip proves flaky.
- **Highlight overlay code kept** in the extractor but `doHighlightElements` is always false (headless, zero screenshots).
- **`viewportExpansion: -1`** (full page) is the default; `isTopElement` short-circuits true in that mode.

## Verify gates (evidence, not vibes)

- Auto-fixer: unit tests over recorded malformed outputs (TDD — the contract is clear, write the failing cases first).
- LLM client: unit tests plus one live call.
- Agent loop: `hermd run "fill the form and submit" --url tests/pages/form.html` completes headless with a real model, trace written.
- Phase 1 exit: a 10-task live smoke suite (fixtures + real sites), recorded traces, target 8/10 pass rate. This is a follow-on to the three steps above, gated on API spend.

## Open questions / prerequisites for the next session

- **Live model access: solved.** `.env` exists with working values; endpoint 1 answered a live test completion on 2026-07-17. Nothing needed from Rainier. If endpoint 1 is down at the live gate, either fall through to endpoint 2 (needs `hermes proxy start` running) or stop and report; never mock the live run.
- **Remaining step-1 verify debt**: 2 more real sites (a login form, an SPA) were deferred into the Phase 1 exit smoke suite. Fold in, don't forget.

## Housekeeping

- `STATUS.md` and `CHANGELOG.md` are currently untracked — commit them with the next code change.
- Three sub-repos are separate git repos; parent `dom-agent` stays un-versioned (same rule as the Vaults). Commit inside `her-dom` only.
