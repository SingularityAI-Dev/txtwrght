# hermd

CLI-first, headless, text-only DOM browser agent. Playwright drives a real
browser; the page is serialized to indexed text (no screenshots, no
multimodal model); an LLM (or an outer agent) picks one action per step.

This is the engine. It is runtime-agnostic: `hermd run` drives itself against
any OpenAI-compatible LLM endpoint. Two thin bindings sit on top of it in the
parent workspace (`../clau-dom`, `../gem-dom`) for driving it from Claude Code
or Gemini CLI instead of a second model. See `../ARCHITECTURE.md` for the full
engine/binding split and `../DEVELOPMENT_PLAN.md` for how it got built.

Status: all build phases closed, Phase 1 exit gate passed 10/10. Details in
`STATUS.md`.

## Install

```
cd her-dom
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env   # fill in an LLM endpoint
```

## The three modes

**Autonomous** — the engine's own loop calls an LLM, one action per step,
until done or `MAX_STEPS`:

```
hermd run "log in with username tomsmith and password SuperSecretPassword!" \
  --url https://the-internet.herokuapp.com/login
```

**Driven** — an outer agent (Claude Code, Gemini CLI, anything) is the loop.
No second model; the browser stays alive between commands:

```
hermd session start --url https://example.com
hermd session snapshot
hermd session act click 5
hermd session end
```

**Distilled** — turn a recorded run into a plain Playwright script with no
model in it at all, once a flow is proven to work:

```
hermd distill traces/run-<id>.jsonl --verify
```

Selectors are rebuilt from element identity recorded at action time, not from
indices, since indices are only valid for the snapshot that produced them.
Passwords are scrubbed at trace time and come back as `os.environ` lookups in
the generated script.

## What it does not do

Cross-origin iframes are out of scope. The extractor descends into
same-origin `contentDocument` (covered by tests) but does not attempt to
bridge cross-origin frame boundaries, which browsers block by design without
a cooperating postMessage protocol on both sides. A task that needs to act
inside a cross-origin frame will not see into it.

## Third-party attribution

The DOM extractor (`src/hermd/dom/extractor.js`) and serializer
(`src/hermd/dom/serializer.py`) are ported from
[page-agent](https://github.com/alibaba/page-agent) (MIT), itself derived
from [browser-use](https://github.com/browser-use/browser-use) (MIT,
Copyright (c) 2024 Gregor Zunic). Full notice chain in `LICENSE`.

## Tests

```
pytest
```

92 tests as of the last exit gate: extractor/serializer golden tests, tool
behavior against local fixtures, distillation replay, and the smoke suite
under `smoke/` (`python smoke/run_smoke.py`) for the live 10-task gate.
