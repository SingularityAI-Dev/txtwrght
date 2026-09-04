# Changelog

> Last 20 changes. Full history in git.

- 2026-09-04: Rethemed the three animated README diagrams (`docs/assets/{hero-layers,observe-think-act-loop,distill-flow}.svg`) off GitHub's own dark palette onto the palette singlesource.co.za/txtwrght/ uses: warm near-black ground, amber core, sage driven path, clay distillation, one dusty blue as the sole cool hue, IBM Plex Mono in place of the generic mono stack. The same retheme landed in the site's copy of the page (`SingleSourceStudios/singlesource-site@e0ffa4e`), since the site page inlines these same three diagrams and the two must move together. Measuring rather than eyeballing caught two defects: Plex Mono is wider than the stack these were drawn against, so 12px panel text reached the panel edge (dropped to 11.5px); and both `animateMotion` packets with a `begin` delay were parking at the SVG origin fully opaque for the first ~1.2s of every load (now `opacity="0"` at rest). Pushed as `aeebeb9`, then `14e4065` fixed the same origin-flash bug in the site's inline copy.
- 2026-09-04: Added a fourth diagram, `docs/assets/hero-banner.svg`, and put it at the top of `README.md`. Built as SVG rather than a screenshot of the live page, since GitHub strips page CSS from an embedded screenshot and a raster image would not scale, would not survive a future palette change, and could not carry the blinking cursor after the wordmark. Chip boxes, the cursor gap and the widest code line were all measured in a browser against the rendered SVG rather than guessed. Pushed as `14e4065`.
- 2026-09-04: Renamed `hermd` -> `txtwrght` project-wide (package, CLI
  entrypoint, bindings `clau-dom`/`gem-dom` -> `claude`/`gemini`) and flattened
  the workspace/engine split: this repo is now the repo root directly at
  `~/development/txtwrght` (was nested as `her-dom/` under an un-versioned
  `hermd/` wrapper). Reference clones moved to a sibling
  `~/development/txtwrght-refs/`. GitHub repo renamed
  `SingularityAI-Dev/hermd` -> `SingularityAI-Dev/txtwrght`. Global Claude
  Code skill and `/txtwrght` slash command installed to match. 92 tests green
  after the rebuild.
- 2026-08-23: Repo consolidation and README rewrite. `claude` and `gemini`
  (each 1-2 commits, docs only) folded into this repo as `git subtree` merges,
  history preserved; the two standalone GitHub repos are now orphaned and
  pending deletion (needs a `delete_repo`-scoped token). This repo renamed
  `herd` -> `hermd` on GitHub (typo fix) and pushed to
  `SingularityAI-Dev/hermd` (superseded by the `txtwrght` rename above).
  `ARCHITECTURE.md`/`DEVELOPMENT_PLAN.md` at the workspace root updated to
  match. `README.md` rewritten to a full standard-reference format (badges,
  problem framing, three animated SVG diagrams, honest browser-use
  comparison, status table), superseding the shorter version shipped
  2026-08-22.
- 2026-08-22: Two of three post-gate roadmap items closed. `README.md`
  shipped (install, three modes, iframe limitation, attribution chain).
  Second distillation proof: live run against
  the-internet.herokuapp.com/redirector (redirect chain, not another form),
  2 steps, distilled to `distilled/run_20260822_195456.py`, replay verified.
  Third item (second model, non-Claude, through the smoke gate) blocked: no
  Gemini credential available on this machine, see STATUS.md.
- 2026-08-20: Phase 1 exit gate PASSED, 10 of 10 (gate was 8 of 10), 181,851 tokens, 173s total, one trace per task in `smoke/RESULTS.md`. Every capability the fixtures isolate held under a real model (form, login, dropdown, scroll-and-read, shadow DOM, iframe, SPA, popup tab) and both live sites passed: herokuapp login reached /secure in 4 steps, Hacker News front-page extraction in 1. The engine is real by its own definition; all of DEVELOPMENT_PLAN.md phases 0 to 5 are now closed.
- 2026-08-17: Phase 5 distillation + Phase 1 smoke harness. `txtwrght distill <trace>` rebuilds selectors from recorded element identity and emits a plain Playwright script into staging; scrubbed passwords become os.environ lookups; --verify replays. Long successful runs flagged as distill candidates (DISTILL_THRESHOLD). Fixed a real bug the replay exposed: over connect_over_cdp Playwright reports clicks as successful while the browser drops the event, so session clicks silently did nothing on real sites; clicks now verify delivery and fall back to in-page dispatch. settle() re-settles when a navigation commits under it. smoke/ holds the ten-task exit gate (verified against page, frame, URL or the agent's own answer; resumable; one probe call up front). 92 tests green.
- 2026-08-17: Phase 3 session CLI (`txtwrght session start/snapshot/act/tabs/switch/status/end`): Chromium launched detached with a debugging port, every command reconnects over CDP, so the browser outlives the CLI process and the caller is the loop. Tabs tracked by CDP target id, not position. Passwords scrubbed from session traces (they leaked in plaintext before). Extractor now reflects live input values into the view, passwords as ***. claude SKILL.md and gemini GEMINI.md ship the bindings. Proven by driving the-internet.herokuapp.com/login end to end with no model in the loop.
- 2026-08-17: Phase 2 hardening: popups and target=_blank tabs adopted as the active page with a <sys> note, dialogs auto-dismissed (DIALOG_POLICY), settle() after every action (grace pump, load states, DOM-quiet wait), structlog to stderr, describe_element() recording element identity for distillation, Playwright driver can be borrowed. Same-origin iframes confirmed already indexed and actionable. 65 tests green.
- 2026-07-17: LLM in the loop (Phase 1 steps 3-5): llm.py (httpx OpenAI-compatible client, forced AgentOutput tool call, ordered endpoint failover chain, auto-fixer ported from page-agent with 2x parse retry), agent.py (PageAgentCore loop port: max steps, step delay, <sys> observations, reflection history, errors excluded from LLM context), trace.py (JSONL per run, password values scrubbed), txtwrght run CLI. 51 tests green; live-proven on tests/pages/form.html via CLIProxyAPI + claude-sonnet-5 (4 steps, submitted:geez captured in trace).
- 2026-07-17: Engine core landed (0bd5e80): page-agent DOM extractor port (injectable, in-page selector map), serializer with 8 golden tests pinning the prompt contract, BrowserState render, txtwrght snapshot CLI, action tools (click/input/select/scroll incl. shadow DOM and container scroll); 23 tests green; live-verified on news.ycombinator.com.
- 2026-07-17: Repo initialized; naming unified on txtwrght (dist, import, CLI); requirements.txt removed as a pyproject duplicate; .env.example moved in from repos/.
- 2026-07-16: hermes-task-distiller deliverable moved in at integrations/hermes-task-distiller/ (Phase 5 design input, see its INTEGRATION.md).
