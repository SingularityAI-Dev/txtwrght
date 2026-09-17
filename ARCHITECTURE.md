# txtwrght Architecture

One engine, thin bindings. This page is the source of truth for the split; the
build plan lives in `DEVELOPMENT_PLAN.md`.

## The split

```
txtwrght/                   <- one git repo, github.com/SingularityAI-Dev/txtwrght
├── src/txtwrght/           <- THE ENGINE. Python package `txtwrght`.
│   └── dom/                <- injected JavaScript (extractor, actions, settle)
│                              plus the Python serializer and loader
├── claude/                 <- Claude Code binding. Thin glue only.
└── tests/                  <- Python suite (Chromium) and tests/js (happy-dom)
```

<p align="center">
  <a href="docs/architecture/txtwrght.architecture.html">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/architecture/architecture-dark.png"/>
      <img src="docs/architecture/architecture-light.png" alt="txtwrght architecture: Claude Code drives the session CLI and the agent loop asks an LLM endpoint for one action; both act through Browser + tools, which calls the three in-page payloads extractor.js, actions.js and settle.js in Chromium. The serializer turns the flat tree into indexed text; runs record to trace.jsonl, which txtwrght distill turns into a staged Playwright script that replays against Chromium." width="100%"/>
    </picture>
  </a>
</p>

<sub>Interactive version: [`txtwrght.architecture.html`](docs/architecture/txtwrght.architecture.html), generated with archify from [`txtwrght.architecture.json`](docs/architecture/txtwrght.architecture.json).</sub>

Reference clones (page-agent, space-agent) live outside the repo in
`~/development/txtwrght-refs/`.

`txtwrght` owns everything with logic in it: Playwright lifecycle, DOM extraction
(injected JavaScript ported from page-agent/browser-use, MIT), serialization to
indexed text, the action tools, the agent loop, tracing, and the session CLI.
Runtime-agnostic: any OpenAI-compatible endpoint drives Mode 1.

Bindings contain no engine logic. `claude/` teaches Claude Code to drive the
engine's per-step session CLI (a `SKILL.md`). If a change to a binding starts growing logic,
push it down into `txtwrght`'s `src/txtwrght/`.

## The two modes

1. **Autonomous**: `txtwrght run "task" --url ...`: the engine's internal loop
   calls an LLM over an OpenAI-compatible API, one action per step, max 40 steps.
2. **Driven**: `txtwrght session start/snapshot/act/end`: an outer agent (Claude
   Code, Hermes) is the loop. No second LLM; the driving agent keeps
   its own judgment, memory, and tools.

Both modes run the same loop; only who decides changes:

<p align="center">
  <a href="docs/architecture/observe-act-loop.html">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/architecture/loop-dark.png"/>
      <img src="docs/architecture/loop-light.png" alt="Observe, think, act: snapshot() evaluates extractor.js in the page, the serializer turns its flat tree into indexed text, a model or outer agent decides one action, tools.py runs it through actions.js, settle.js waits for the DOM to go quiet, and the loop re-indexes. done or fail ends it." width="100%"/>
    </picture>
  </a>
</p>

<sub>Interactive version: [`observe-act-loop.html`](docs/architecture/observe-act-loop.html), generated with archify from [`observe-act-loop.workflow.json`](docs/architecture/observe-act-loop.workflow.json).</sub>

3. **Distilled**: `txtwrght distill <trace.jsonl>`: a run that worked becomes a
   plain Playwright script with no model in it at all. This is the composition
   that makes the workspace more than a browser-use clone: pay a model once to
   discover a flow, replay it for free afterwards. Selectors are rebuilt from
   the element identity the trace recorded at action time, since indices mean
   nothing after the run that produced them.

<p align="center">
  <a href="docs/architecture/distill.html">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/architecture/distill-dark.png"/>
      <img src="docs/architecture/distill-light.png" alt="Distill: actions.js records element identity at action time into trace.jsonl; txtwrght distill parses the run, rebuilds selectors from id, name, aria-label and css path, writes a plain Playwright script, and --verify replays it with secrets read from os.environ and no model." width="100%"/>
    </picture>
  </a>
</p>

<sub>Interactive version: [`distill.html`](docs/architecture/distill.html), generated with archify from [`distill.dataflow.json`](docs/architecture/distill.dataflow.json).</sub>

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
engine and the `claude/` binding. The reference clones in `txtwrght-refs/`
carry upstream remotes; never commit into them.
