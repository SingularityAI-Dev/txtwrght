# Task Distiller for Hermes Agent

A "master skill + rule" pair for [Hermes Agent](https://hermes-agent.nousresearch.com) (Nous
Research's self-hosted, self-improving agent CLI) that:

1. **Detects** when a big/expensive agentic task runs and completes -- deterministically, via a
   plugin, not by hoping the model notices.
2. **Records** the process as a structured trace.
3. **Writes and verifies** a Python script that reproduces the task.
4. **Registers** that script as a new skill, so the same job runs cheaply next time.

It's built specifically around Hermes's real skill/plugin/`execute_code` architecture (SKILL.md
format, `skill_manage`, `${HERMES_SKILL_DIR}` substitution, the `execute_code` RPC sandbox, and
the plugin `register(ctx)` / `ctx.register_hook()` / `ctx.inject_message()` API), and it treats
`skills.sh` / the Skills Hub as the first place to check before building anything new -- Hermes
can install directly from GitHub identifiers, skills.sh identifiers, or a `/.well-known/skills/
index.json` endpoint.

## What's in here

```
hermes-task-distiller/
├── skills/agent-workflows/task-distiller/   <- the master skill (does the actual work)
│   ├── SKILL.md
│   ├── references/
│   │   ├── big-task-criteria.md             <- what counts as "big", with examples
│   │   ├── finding-existing-skills.md       <- how to check skills.sh/Hub before building
│   │   └── skill-authoring-cheatsheet.md    <- condensed Hermes SKILL.md format reference
│   └── scripts/
│       ├── record_trace.py                  <- step 2: record what happened
│       ├── scaffold_skill.py                 <- step 4: package the verified script as a skill
│       └── find_skills.py                    <- step 1: check the ecosystem first
└── plugins/task-distiller-watcher/           <- the "rule" (deterministic detection)
    ├── plugin.yaml
    └── __init__.py
```

## Why two pieces, not one

Hermes already has a self-curating loop where the agent *can* offer to save an approach as a skill
after a complex task -- but that depends on the model's own judgment in the moment. The **skill**
here formalizes and extends that into a full record -> script -> package -> register procedure.
The **plugin** adds a layer that doesn't depend on the model noticing at all: it counts tool calls,
"expensive" tool hits, and elapsed time for the live session itself, and once a threshold is
crossed, injects a plain nudge into the conversation telling the agent to go run the skill's
procedure. It's a plugin (living in `~/.hermes/plugins/`) rather than the simpler
`~/.hermes/hooks/` folder specifically because the simple hooks folder is **gateway-only**
(Telegram/Discord/Slack/etc.) -- the CLI does not load it. Plugin-registered hooks fire in both
CLI and gateway sessions, which matters since this was built for "Hermes Agent CLI."

## Install

**The skill:**

```bash
mkdir -p ~/.hermes/skills/agent-workflows
cp -r skills/agent-workflows/task-distiller ~/.hermes/skills/agent-workflows/
```

It'll show up in the skills index (and as `/task-distiller`) on your next session -- no restart
needed, since skills are read on demand.

**The plugin:**

```bash
cp -r plugins/task-distiller-watcher ~/.hermes/plugins/
```

Plugins are discovered at startup, so restart Hermes (or run `hermes plugins enable
task-distiller-watcher` first if your version requires explicit enabling -- check `hermes plugins
list` to see its state).

Both pieces work independently. You can install just the skill and invoke it manually whenever you
notice a task got big; the plugin is purely an automatic-detection convenience on top.

## Tuning

Edit `~/.hermes/distillery/config.json` (created with defaults the first time the plugin runs) to
adjust sensitivity -- lower the thresholds for earlier nudges, raise them if it fires too often on
a system that legitimately does long single-purpose work. See `references/big-task-criteria.md`
for the reasoning behind the defaults, and set `HERMES_PLUGINS_DEBUG=1` before starting Hermes if
you want to watch hook-firing detail while you calibrate.

Toggle `task_distiller.auto_create_skill` (skill config, default `false`) if you want the agent to
register distilled skills without asking first -- not recommended for anything that touches
destructive or credentialed operations.

## A note on version drift

Hermes Agent ships fast and its CLI surface, hook payload shapes, and Hub subcommand names have
moved around across releases. Everything here is written defensively (best-effort `.get()` reads,
graceful fallbacks, comments pointing at where to double-check) rather than assuming a frozen API,
but if something doesn't fire or a command name has changed, `hermes --help`, `hermes plugins
list`, and the project's own docs at hermes-agent.nousresearch.com are the source of truth --
adjust the two or three spots flagged in comments (`HERMES_SEARCH_CMD` in `find_skills.py`, the
hook names in `plugin.yaml`/`__init__.py`) accordingly.
