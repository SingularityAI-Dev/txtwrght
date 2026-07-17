# Next session kickoff prompt (her-dom / hermd)

Run this from a Claude Code session started inside `~/development/dom-agent/her-dom`. It is a one-shot build (Phase 1 steps 3 to 5), so it uses `/goal` alone — no `/loop`, which is for recurring/polling work.

---

/goal Land the LLM-in-the-loop slice of the hermd engine: `llm.py`, `agent.py`, `trace.py`, and the `hermd run` CLI subcommand, ending with a live proof run. This is Phase 1 steps 3 to 5 of `../DEVELOPMENT_PLAN.md`.

Read first, in this order: `HANDOVER.md`, `STATUS.md`, `../DEVELOPMENT_PLAN.md`, then the existing engine (`src/hermd/`). For code retrieval across this repo and the `../repos/page-agent` reference, call the `jcodemunch_guide` tool and strictly follow its instructions; prefer symbol search and outlines over full-file reads. Use Claude Superpowers conventions for execution.

Port from the already-cloned reference (do not reinvent):
- `../repos/page-agent/packages/core/src/utils/autoFixer.ts` — the malformed-output cases.
- `../repos/page-agent/packages/core/src/PageAgentCore.ts` — the agent loop semantics.
- `../repos/page-agent/packages/core/src/tools/index.ts` and `types.ts` — the `AgentOutput` contract `{evaluation_previous_goal, memory, next_goal, action:{tool_name:args}}`.
- `../repos/page-agent/packages/llms/src/OpenAIClient.ts` — OpenAI-compatible forced tool call.

Build order, each verified before the next:
1. `llm.py`: httpx OpenAI-compatible client, one forced `AgentOutput` tool call (schema = union of tool arg schemas under `action`), parse-retry twice per endpoint. Endpoints form an ordered failover chain from `.env` (already written and live-verified): `LLM_1_*` (CLIProxyAPI on 127.0.0.1:8317, Claude subscription, primary), `LLM_2_*` (Hermes proxy on 127.0.0.1:8645, Nous Portal upstream), `LLM_3_*` (spare, unset). `API_KEY` is optional per endpoint: blank means omit the Authorization header entirely. On transport/auth failure fall through to the next endpoint with a `BASE_URL`, skip unset ones. Extend `Config.from_env()` to load the chain (vars exist in `.env.example` but aren't loaded yet). Use TDD for the auto-fixer — write the recorded malformed-output cases as failing unit tests first (JSON-in-content, action-name-as-toolname, double-stringified args, primitive coercion, missing-action-falls-back-to-`wait`), then make them pass; unit-test the failover order with mocked clients too. Verify with a mocked client; defer the one live call to step 4.
2. `agent.py`: the step loop — max 40 steps (from config), step delay, URL-change and step-budget `<sys>` observations, per-step history with the reflection fields, error events recorded in trace but excluded from LLM context. Indices regenerate every step.
3. `trace.py`: JSONL trace written from the first run — every BrowserState, LLM output, action result, timing, token counts. Scrub values typed into `password`-type inputs.
4. Wire `hermd run "task" --url ...` in `__main__.py`.

Do not touch the serializer output format; its 8 golden tests are the prompt contract. Commit `STATUS.md` and `CHANGELOG.md` (currently untracked) with your first code commit, and keep both current as you go. Commit inside `her-dom` only.

Stop condition (all must hold, show the evidence, do not assume):
- All existing 23 tests still green, plus new passing unit tests for the auto-fixer cases and the loop mechanics (mocked client). Auto-fixer tests pass without network.
- `hermd run "Fill in username geez, accept the terms, and submit the form" --url tests/pages/form.html` completes headless against a real model, the page's `#status` div reads `submitted:geez` afterwards, and a JSONL trace is written with password-input values scrubbed. `.env` is already configured and endpoint 1 (CLIProxyAPI, 127.0.0.1:8317, brew service) was live-verified on 2026-07-17. Endpoint 2 (Hermes proxy, 127.0.0.1:8645) only responds while `hermes proxy start` is running. If neither endpoint is reachable at this gate, stop and ask Rainier rather than faking the run.
- `STATUS.md` and `CHANGELOG.md` updated and committed.

Out of scope this session: the 10-task Phase 1 exit smoke suite (that is the next slice, gated on API spend), and any clau-dom / gem-dom binding work.
