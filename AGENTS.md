# dom-agent

CLI-first, headless, text-only DOM browser agent. One Python engine (`txtwrght`) plus per-runtime bindings (`claude`, `gemini`). See `ARCHITECTURE.md` for the engine/binding split.

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature>/` in this repo (no git remote). See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.
