# Status

> Updated: 2026-08-20

## Where we are

Every phase of `../DEVELOPMENT_PLAN.md` is closed, gate included. The Phase 1
exit gate passed **10 of 10** on 2026-08-17 (bar was 8 of 10), so the engine is
real by the standard the plan set: a recorded pass rate, not a demo.

hermd runs tasks end to end (`hermd run`), exposes per-step primitives so an
outer agent can be the loop (`hermd session ...`), and turns a recorded run into
a plain Playwright script with no model in it (`hermd distill`). 92 tests green.

## Recent

- Gate: 10/10, 181,851 tokens, 173s. Fixtures covered form fill, login,
  dropdown, scroll-and-read, shadow DOM, same-origin iframe, SPA nav and popup
  tabs; live sites covered a real login (4 steps to /secure) and Hacker News
  extraction (1 step). Per-task verifiers, traces and numbers in `smoke/RESULTS.md`.
- Phase 5: `hermd distill` rebuilds selectors from element identity recorded at
  action time, stages the script, `--verify` replays it, scrubbed passwords come
  out as `os.environ` lookups. Proven on the herokuapp flow end to end.
- Phase 3: `hermd session` keeps a detached Chromium alive between commands, so
  Claude Code drove a real login with no second model involved.
- Phase 2: popups, dialogs, settle with a DOM-quiet wait, structured logs.
  Same-origin iframes turned out to already work; now covered by tests.
- Two real bugs the proof work caught: passwords written to session traces in
  plaintext, and clicks over `connect_over_cdp` reported as delivered while the
  browser dropped them. Both fixed, both regression-tested.

## Next

- Open-source readiness: DONE 22 August 2026. `README.md` shipped; attribution
  chain checked against `LICENSE` and both upstream repos, nothing to fix.
- Distillation second proof: DONE 22 August 2026. Live run against
  `the-internet.herokuapp.com/redirector` (a real redirect chain, `/redirect`
  303s to `/status_codes`), 2 steps, distilled and replay-verified. Two live
  proofs now (login flow, redirect chain).
- Cross-origin iframes: documented in the README as an explicit limit rather
  than a bug a user finds by accident.
- `hermd run` has never been driven by anything but claude-sonnet-5 through
  CLIProxyAPI. A second model on the same gate would tell us whether the
  serialized-page contract or the prompt is doing the work. **Deferred by
  choice, 23 August 2026**: no Gemini credential exists on this machine
  (CLIProxyAPI's `gemini-api-key` block is commented out, no `GEMINI_API_KEY`
  in the shell profile), and Rainier chose not to wire one up for this.
  Nothing blocking a pickup later beyond that same credential decision.
