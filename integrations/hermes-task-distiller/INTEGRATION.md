# Why this lives in txtwrght

This directory is the Hermes "task-distiller" deliverable: a master skill plus watcher plugin
that turns big, expensive agentic runs into verified Python scripts registered as skills. It
originally sat in `claude/` as a zip; it was moved here on 16 July 2026 because it is
Hermes-side tooling and because it is the direct design input for Phase 5 of
`../../DEVELOPMENT_PLAN.md` (the distillation loop):

- `txtwrght distill <trace.jsonl>` will follow this skill's record, reproduce, verify, stage,
  register pipeline, generating deterministic Playwright scripts from successful agent traces.
- The watcher plugin's threshold pattern (tool calls, external hits, wall clock) maps to
  flagging any `txtwrght` run over N steps as a distillation candidate.
- Its guardrails carry over unchanged: staging before live, no secrets in generated scripts,
  destructive steps never auto-registered.

Layout:

- The extracted tree here is the source of truth. Edit these files directly.
- `dist.zip` is the original packaged distribution, kept for provenance. Regenerate after
  edits with: `cd .. && zip -r hermes-task-distiller/dist.zip hermes-task-distiller -x "hermes-task-distiller/dist.zip"`.
- Install instructions for a live Hermes are in `README.md`.
