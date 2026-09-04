# Status

> Updated: 2026-08-23

## Where we are

Every phase of `../DEVELOPMENT_PLAN.md` is closed, gate included. The Phase 1
exit gate passed **10 of 10** on 2026-08-17 (bar was 8 of 10), so the engine is
real by the standard the plan set: a recorded pass rate, not a demo. One repo
now: `claude` and `gemini` are subtrees of this repo, not siblings, pushed
to GitHub as `SingularityAI-Dev/txtwrght`.

txtwrght runs tasks end to end (`txtwrght run`), exposes per-step primitives so an
outer agent can be the loop (`txtwrght session ...`), and turns a recorded run into
a plain Playwright script with no model in it (`txtwrght distill`). 92 tests green.
`README.md` is now a full standard-reference doc with three animated SVG
diagrams (hero layers, observe-think-act loop, distill flow).

## Recent

- Repo consolidation, 2026-08-23: `claude`/`gemini` folded in as
  `git subtree` merges (history kept), repo renamed `herd` -> `txtwrght` on
  GitHub, `ARCHITECTURE.md`/`DEVELOPMENT_PLAN.md` updated to match. The two
  standalone GitHub repos are orphaned pending deletion (blocked on a
  `delete_repo`-scoped token, see Next).
- README rewrite, 2026-08-23: full standard-reference format matching the
  logic-md README, badges, problem framing, three animated diagrams, an
  honest comparison against browser-use, status table.
- Gate: 10/10, 181,851 tokens, 173s. Fixtures covered form fill, login,
  dropdown, scroll-and-read, shadow DOM, same-origin iframe, SPA nav and popup
  tabs; live sites covered a real login (4 steps to /secure) and Hacker News
  extraction (1 step). Per-task verifiers, traces and numbers in `smoke/RESULTS.md`.
- Phase 5: `txtwrght distill` rebuilds selectors from element identity recorded at
  action time, stages the script, `--verify` replays it, scrubbed passwords come
  out as `os.environ` lookups. Proven on the herokuapp flow end to end.
- Phase 3: `txtwrght session` keeps a detached Chromium alive between commands, so
  Claude Code drove a real login with no second model involved.
- Phase 2: popups, dialogs, settle with a DOM-quiet wait, structured logs.
  Same-origin iframes turned out to already work; now covered by tests.
- Two real bugs the proof work caught: passwords written to session traces in
  plaintext, and clicks over `connect_over_cdp` reported as delivered while the
  browser dropped them. Both fixed, both regression-tested.

## Next

- Delete the two orphaned GitHub repos, `SingularityAI-Dev/claude` and
  `/gemini`. Blocked on Rainier running
  `gh auth refresh -h github.com -s delete_repo` (this session's token lacks
  `delete_repo`).
- `txtwrght run` has never been driven by anything but claude-sonnet-5 through
  CLIProxyAPI. A second model on the same gate would tell us whether the
  serialized-page contract or the prompt is doing the work. **Deferred by
  choice, 23 August 2026**: no Gemini credential exists on this machine
  (CLIProxyAPI's `gemini-api-key` block is commented out, no `GEMINI_API_KEY`
  in the shell profile), and Rainier chose not to wire one up for this.
  Nothing blocking a pickup later beyond that same credential decision.
