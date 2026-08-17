# Status

> Updated: 2026-08-17

## Where we are

Every phase of `../DEVELOPMENT_PLAN.md` is built except its one live gate.

- **Phase 0, 1 (build), 2, 3, 4, 5: done.** 92 tests green.
- **Phase 1 exit gate: blocked on an LLM endpoint, not on code.** The harness is
  written and dry-run clean; both configured endpoints are logged out.

The engine runs tasks end to end (`hermd run`), exposes per-step primitives for
a driving agent (`hermd session ...`), and turns a recorded run into a plain
Playwright script (`hermd distill`). Every run writes a JSONL trace.

## The one thing waiting on a human

Both LLM endpoints need a login. Endpoint 1 answers
`OAuth access token has been revoked`, endpoint 2 is not running:

```bash
cliproxyapi -claude-login          # browser OAuth, primary endpoint
hermes auth add nous               # optional fallback endpoint
```

Then the gate runs unattended:

```bash
.venv/bin/python smoke/run_smoke.py        # 10 tasks, resumable, gate is 8/10
```

It writes `smoke/RESULTS.md` (pass rate, per-task verifier, trace paths) and
`smoke/results.json`. A killed run resumes; passed tasks are skipped.

## Recent

- Phase 5: `hermd distill` rebuilds selectors from the element identity recorded
  at action time, stages the script, `--verify` replays it. Scrubbed passwords
  come out as `os.environ` lookups. Proven on the herokuapp login flow: driven by
  hand, distilled, replayed against the live site.
- The replay caught a real bug: over `connect_over_cdp` Playwright reports a
  click as successful while the browser drops the event, so session clicks
  silently did nothing on real sites. Clicks now verify delivery.
- Phase 3: `hermd session` keeps a detached Chromium alive between commands, so
  Claude Code (or anything else) can be the loop with no second model.
- Phase 2: popups, dialogs, settle with a DOM-quiet wait, structured logs.
  Same-origin iframes turned out to already work; now covered by tests.

## Next, after the gate

- Whatever the pass rate exposes. Failures are recorded per task with the
  agent's own answer and the verifier's verdict, so they are diagnosable.
- Cross-origin iframes remain out of scope (same-origin only, by design).

## Handover

`HANDOVER.md` is the canonical long-form context. `NEXT_SESSION_PROMPT.md` is
historical.
