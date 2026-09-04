# gemini

Gemini binding for the dom-agent workspace: teaches Gemini CLI to drive the
`txtwrght` browser engine in `../txtwrght/` through its per-step session CLI.

Status: shipped 17 August 2026 (Phase 4). `GEMINI.md` is the binding.

Two modes, both thin over the engine:

1. **Gemini as the model behind the loop.** Nothing here is needed. Point
   `txtwrght/.env` at Gemini's OpenAI-compatible endpoint and use `txtwrght run`.
2. **Gemini CLI as the loop.** `GEMINI.md` teaches the snapshot, decide, act
   pattern against `txtwrght session`, with no second model in the loop.

Anything reusable across bindings belongs in the engine, not here. See
`../ARCHITECTURE.md` and `../DEVELOPMENT_PLAN.md`.
