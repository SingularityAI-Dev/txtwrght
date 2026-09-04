# dom-agent Architecture

One engine, thin bindings. This page is the source of truth for the split; the
build plan lives in `DEVELOPMENT_PLAN.md`.

## The split

```
dom-agent/                  <- workspace root, intentionally un-versioned
├── txtwrght/                <- THE ENGINE. Python package `txtwrght`. One git repo,
│                               pushed to github.com/SingularityAI-Dev/txtwrght.
│   ├── claude/           <- Claude binding. Thin glue only. Subtree, not a
│   │                          separate repo (folded in 2026-08-23, history
│   │                          preserved via `git subtree`).
│   └── gemini/            <- Gemini binding. Thin glue only. Same treatment.
└── repos/                  <- read-only reference clones (page-agent, space-agent)
```

Consolidated to one repo on 2026-08-23. `claude` and `gemini` were each a
commit or two of documentation, no code, and never needed independent
versioning; three repos for that much content was ceremony the content didn't
earn. Their histories were folded in with `git subtree`, not squashed or
discarded.

`txtwrght` owns everything with logic in it: Playwright lifecycle, DOM extraction
(injected JavaScript ported from page-agent/browser-use, MIT), serialization to
indexed text, the action tools, the agent loop, tracing, and the session CLI.
Runtime-agnostic: any OpenAI-compatible endpoint drives Mode 1.

Bindings contain no engine logic. `claude/` teaches Claude Code to drive the
engine's per-step session CLI (a `SKILL.md`); `gemini/` does the same for Gemini
(a `GEMINI.md` / CLI extension). If a change to a binding starts growing logic,
push it down into `txtwrght`'s `src/txtwrght/`.

## The two modes

1. **Autonomous**: `txtwrght run "task" --url ...` — the engine's internal loop
   calls an LLM over an OpenAI-compatible API, one action per step, max 40 steps.
2. **Driven**: `txtwrght session start/snapshot/act/end` — an outer agent (Claude
   Code, Gemini CLI, Hermes) is the loop. No second LLM; the driving agent keeps
   its own judgment, memory, and tools.

3. **Distilled**: `txtwrght distill <trace.jsonl>` — a run that worked becomes a
   plain Playwright script with no model in it at all. This is the composition
   that makes the workspace more than a browser-use clone: pay a model once to
   discover a flow, replay it for free afterwards. Selectors are rebuilt from
   the element identity the trace recorded at action time, since indices mean
   nothing after the run that produced them.

## The contract worth protecting

The serialized page text is the prompt contract: `[n]` indexed elements, `*[n]`
for new-since-last-snapshot, tab-depth nesting, whitelisted attributes capped at
20 chars, plain text lines for visible non-interactive content. Golden tests in
`txtwrght/tests/test_serializer.py` pin it; changing that format is a breaking
change and must be deliberate.

Indices are only valid for the current snapshot. Every action invalidates them;
snapshot again before acting again.

## Versioning rules

`txtwrght` (repo name on GitHub: `txtwrght`) is the one git repository for the
engine and both bindings; `claude/` and `gemini/` live inside it as
subtrees. The workspace parent (`dom-agent/`) stays un-versioned (same rule as
the Vaults). `repos/` is reference material with upstream remotes; never
commit into it.
