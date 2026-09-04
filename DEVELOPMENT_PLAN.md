# dom-agent Development Plan

Date: 16 July 2026, status updated 23 August 2026. This plan covers the whole
`~/development/dom-agent/` workspace.

Status: Phases 0 to 5 are built and committed, Phase 1 exit gate passed 10/10
on 2026-08-17. See `txtwrght/STATUS.md` for current state and next steps.

Repo note (2026-08-23): `claude` and `gemini` were originally three
separate git repos per Phase 0 below; they were consolidated into `txtwrght`
(pushed to GitHub as `txtwrght`) as subtrees, history preserved, since neither
binding ever grew beyond a commit or two of documentation. `ARCHITECTURE.md`
reflects the current layout; the phase log below is left as the historical
record of what actually happened at the time.

## What this workspace is building

A CLI-first, headless, text-only DOM browser agent: Playwright drives a real browser, the page is serialized to indexed text (no screenshots, no multimodal models), an LLM picks one action per step, and the loop runs until done. The engine is runtime-agnostic; three thin variants bind it to different driving agents:

| Directory | Role | State today |
|---|---|---|
| `txtwrght/` | The engine itself. Python package `txtwrght`, CLI `txtwrght`, LLM via OpenAI-compatible API (Hermes, or anything). One repo, GitHub `SingularityAI-Dev/txtwrght`. | All phases closed, gate passed 10/10, 92 tests. |
| `txtwrght/claude/` | Claude-native binding (Claude Code drives the session CLI). Subtree of the same repo since 2026-08-23. | `SKILL.md` + `CLAUDE.md` shipped, proven driving a real login end to end. |
| `txtwrght/gemini/` | Gemini binding. Same treatment. | `GEMINI.md` shipped, same shape as claude, less exercised. |
| `repos/` | References: `page-agent` (Alibaba, the core tech to port), `space-agent` (Agent Zero, skill/runtime philosophy), `.env.example` (config surface, already drafted), shared `.venv`. | Cloned. |

Core assumption, stated for correction: the product is one Python engine (txtwrght) plus per-runtime bindings, not three independent rewrites. Everything below follows from that. If claude/gemini are meant as full independent implementations instead, Phases 3 and 4 change; nothing in Phases 0 to 2 does.

## The technical bet

`page-agent` already solved the hard parts for the in-page case, MIT-licensed (itself derived from `browser-use`, with attribution). We port its architecture to Playwright rather than reinventing:

- **DOM extraction** (`page-controller/src/dom/dom_tree/index.js`): plain JavaScript, framework-free. It can be injected nearly verbatim via `page.evaluate()`. It builds a FlatDomTree with per-node `isVisible` / `isInteractive` (computed-cursor heuristic plus tag/role/tabindex checks) / `isTopElement` (elementFromPoint, shadow-DOM aware), and assigns a page-global `highlightIndex` to each interactive element.
- **Serialization** (`flatTreeToString`): one line per element, `\t` depth nesting, `[n]` index prefix (`*[n]` when new since last step), filtered attribute whitelist (title, type, checked, name, role, value, placeholder, alt, aria-label, aria-expanded, data-state, id, for, ...), values capped at 20 chars. Header/footer carry URL, title, viewport metrics, pixels above/below.
- **Action contract** (MacroTool): one forced tool call per step returning `{evaluation_previous_goal, memory, next_goal, action: {tool_name: args}}`. Reflection before action, one action per step.
- **Tool set**: `done`, `wait`, `ask_user`, `click_element_by_index`, `input_text`, `select_dropdown_option`, `scroll`, `scroll_horizontally`, optional `execute_javascript`.
- **Loop mechanics**: max 40 steps, indices regenerated every step, URL-change observations injected as `<sys>` notes, remaining-step warnings at 5 and 2, error history excluded from LLM context, LLM retry (2) with an auto-fixer for malformed outputs, fallback action `wait` when action missing.

Key Playwright-specific difference: in page-agent the `selectorMap` holds live element references inside the page. In our design the map also lives in the page (as a JS global set by the injected extractor); the Python side sends `click(index)` back through `page.evaluate()` against that map, falling back to Playwright's own click on the resolved element handle for proper event dispatch. Indices remain valid only within one step, same as upstream.

## Phase 0: Workspace hygiene (half a day) — DONE 17 July 2026

1. DONE: `git init` each of `txtwrght`, `claude`, `gemini` (separate repos, parent stays un-versioned, same rule as the Vaults). All three have initial commits.
2. DONE: `repos/.env.example` moved to `txtwrght/.env.example`. `requirements.txt` removed (exact duplicate of pyproject dependencies). Naming unified on `txtwrght` (pyproject name, import name, CLI); folder stays `txtwrght`.
3. DONE (16 July 2026): `hermes-task-distiller` moved to `txtwrght/integrations/hermes-task-distiller/` as an extracted source tree (original zip kept as `dist.zip`, rationale in its `INTEGRATION.md`); `claude/CLAUDE.md` rewritten to describe the Phase 3 Claude binding.
4. DONE: `ARCHITECTURE.md` at workspace root names the engine/binding split.

Verify: three clean git repos, workspace root explains itself to a fresh session. PASSED.

## Phase 1: Engine core in txtwrght (the bulk of the work)

Package layout:

```
txtwrght/
├── src/txtwrght/
│   ├── __main__.py          # click CLI: txtwrght run "task" --url ..., txtwrght snapshot --url ...
│   ├── config.py            # env + .env via python-dotenv (LLM_*, BROWSER_*, MAX_STEPS, STEP_DELAY)
│   ├── browser.py           # Playwright lifecycle: launch, page, navigation, settle logic
│   ├── dom/
│   │   ├── extractor.js     # ported/adapted page-agent dom_tree (MIT attribution in LICENSE)
│   │   ├── serializer.py    # FlatDomTree JSON -> indexed text (port of flatTreeToString)
│   │   └── state.py         # BrowserState: url, title, header, content, footer, selector map handle
│   ├── llm.py               # httpx OpenAI-compatible client, forced MacroTool call, retry + auto-fixer
│   ├── tools.py             # action registry -> Playwright/page.evaluate implementations
│   ├── agent.py             # the step loop: observe -> think -> act, history, observations, done/fail
│   └── trace.py             # JSONL run trace: every state, LLM output, action result (Phase 5 fuel)
└── tests/
    ├── pages/               # small static HTML fixtures (form, dropdown, scroll, shadow DOM, SPA nav)
    └── test_*.py            # pytest; extractor/serializer tests run against fixtures via Playwright
```

Build order, each step verified before the next (test-driven where the contract is clear):

1. **Extractor + serializer first, no LLM.** DONE 17 July 2026, commit 0bd5e80 in txtwrght. `txtwrght snapshot --url <page>` prints the indexed text view. Verified against 4 local fixtures (form, scroll, shadow DOM, SPA) and live against news.ycombinator.com (514 lines, all links/nav/upvotes indexed). Serializer format pinned by 8 golden tests. Remaining from the original verify bar: 2 more real sites (a login form, an SPA) — fold into the Phase 1 exit smoke suite.
2. **Tools against fixtures, no LLM.** DONE 17 July 2026, same commit. click/input_text/select_dropdown_option/scroll (window + container) + shadow-DOM click, asserted on resulting DOM state. 23 tests passing total.
3. **LLM client.** Forced tool call named `AgentOutput`, schema = union of tool arg schemas under `action`, port the auto-fixer cases (JSON-in-content, action-name-as-toolname, double-stringified args, primitive coercion, missing action falls back to `wait`). Verify: unit tests over recorded malformed outputs, plus one live call.
4. **Agent loop.** Port PageAgentCore semantics: max steps (default 40), step delay, URL-change and step-budget `<sys>` observations, per-step history with reflection fields, error events kept in trace but excluded from LLM context. Verify: `txtwrght run "fill the form and submit" --url tests/pages/form.html` completes headless with a real model.
5. **Trace from day one.** Every run writes a JSONL trace (states, LLM outputs, action results, timing, token counts). This is the "measure, do not assume" artifact and the input to Phase 5.

Exit criteria for Phase 1: a 10-task live smoke suite (mix of fixtures and real sites) with recorded traces and a pass rate, not a demo anecdote. Target 8/10 before calling the engine real.

Status 17 August 2026: the harness is built and dry-run clean (`txtwrght/smoke/`,
tasks in `tasks.yaml`, runner `run_smoke.py`, resumable, verifiers check the
page, a frame, the final URL or the agent's own answer). It has not been run:
both configured LLM endpoints are logged out, so the gate is waiting on
`cliproxyapi -claude-login`, not on code.

## Phase 2: Hardening (interleaved with Phase 1 exit) — DONE 17 August 2026

- Navigation robustness: waits for load/network-idle after actions that navigate, new-tab/popup handling (Playwright context events), dialog auto-dismiss policy.
- Iframes: RESOLVED 17 August 2026, better than planned. The ported extractor already descends into same-origin `contentDocument`, and element handles resolved from the in-page map click and fill correctly inside frames. Covered by tests over http; `file://` documents are opaque origins in Chromium, so frames do not apply there. Cross-origin frames remain out of scope.
- Secrets discipline: config through env only, traces scrub values typed into `password`-type inputs.
- Structured logging via structlog (already a declared dependency), `--verbose` streaming of reflection fields so a human can watch the agent think.

## Phase 3: claude, the Claude binding — DONE 17 August 2026

Two distinct modes, both thin over the engine:

1. **Claude-as-API-brain**: nothing to build; `txtwrght` already speaks to any OpenAI-compatible endpoint or an Anthropic proxy per `.env.example`.
2. **Claude-Code-as-driver** (the interesting one): Claude Code is the loop, not a model behind an API. Expose the engine's primitives as a per-step CLI: `txtwrght session start --url ...`, `txtwrght session snapshot`, `txtwrght session act click 5`, `txtwrght session act input 3 "text"`. A Claude Code skill (SKILL.md in `claude/`) teaches the pattern: snapshot, choose action, act, repeat. No second LLM in the loop, so token cost stays in one place and the driving agent keeps its own judgment, memory, and tool ecosystem.

Verify: Claude Code completes one of the Phase 1 smoke tasks end-to-end through the session CLI, trace recorded.

## Phase 4: gemini, the Gemini binding — DONE 17 August 2026

Same shape as Phase 3: mode 1 is pure config (Gemini's OpenAI-compatible endpoint), mode 2 is a Gemini CLI extension/GEMINI.md teaching the same session primitives. Lowest priority; do not start before Phase 3 works.

## Phase 5: Distillation loop (why task-distiller is in this workspace) — DONE 17 August 2026

The composition that makes this more than another browser-use clone: expensive DOM-agent runs get distilled into deterministic Playwright scripts. The `hermes-task-distiller` already defines the pattern (trace, reproduce as script, verify, register as skill). Adapt it:

- `txtwrght distill <trace.jsonl>`: generate a plain Playwright script from a successful trace (selectors resolved at distill time from recorded DOM states, not indices), verify by replay, stage for review.
- The Hermes plugin's threshold-watcher pattern maps to: flag any `txtwrght` run over N steps as a distillation candidate in the trace footer.
- Same guardrails carry over: staging before live, no secrets in generated scripts, destructive steps never auto-registered.

This phase is deliberately last: it needs real traces to exist first.

## Risks and open questions

- **Engine-plus-bindings assumption** (stated above) is the one structural call made without confirmation. Cheap to redirect now, expensive after Phase 3.
- **Index-based clicking through `page.evaluate` vs Playwright element handles**: plan is handles resolved from the in-page map (real input events, auto-waiting); if the handle round-trip proves flaky the fallback is in-page `el.click()`, which is what page-agent itself does.
- **Serializer drift**: the serialization format is the prompt contract. Pin the fixture-based golden tests early so refactors cannot silently change what the LLM sees.
- **License hygiene**: extractor port carries page-agent's MIT notice and the browser-use acknowledgment chain, same as page-agent does.
- **Naming**: RESOLVED 17 July 2026. Unified on `txtwrght` (distribution name, import name, CLI); the folder/repo stays `txtwrght`.

## Suggested first session

Phase 0 complete plus Phase 1 steps 1 and 2: extractor injected, `txtwrght snapshot` working against fixtures and one real site, tools tested against fixtures. That is a self-contained, verifiable slice with zero LLM spend.
