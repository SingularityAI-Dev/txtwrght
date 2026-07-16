---
name: task-distiller
description: >-
  Turns a big, expensive, multi-step agentic task you just ran (or are running) into a small
  deterministic Python script plus a reusable skill, so the same job never has to burn LLM tokens
  again. Trigger this whenever a task involved many tool calls, a long execute_code/terminal
  session, calls to external APIs or services, a delegated subagent, or noticeably high token or
  wall-clock cost — and the same shape of task is likely to come up again. Also use it when the
  user says things like "remember how you did that", "can we automate this", "turn this into a
  script", "make this a skill", "next time just run it", or "don't make me pay for this again".
  Always check whether a matching skill already exists locally or on the wider ecosystem (Skills
  Hub / skills.sh) before rebuilding something from scratch.
version: 0.1.0
author: task-distiller
license: MIT
metadata:
  hermes:
    tags: [agent-workflows, meta, automation, skill-authoring, cost-optimization]
    requires_tools: [skill_manage]
    config:
      - key: task_distiller.auto_create_skill
        description: >-
          If true, register the distilled skill via skill_manage as soon as the script is
          verified, without asking first. If false (default), propose it and wait for
          confirmation before creating anything.
        default: "false"
        prompt: "Auto-create distilled skills without asking first?"
---

# Task Distiller

Some tasks are one-off. Others are a *shape* of work — same steps, different inputs — that will
come back next week wearing a different hat. This skill is for the second kind: it turns "I just
spent a long, expensive turn doing X" into "there's now a script and a skill that does X in one
cheap step." Anthropic's own skill-creator skill does the equivalent for Claude; this is the
Hermes-native version, tuned to Hermes's actual skill/plugin/execute_code plumbing.

A companion plugin, `task-distiller-watcher` (see the top-level README this skill shipped with),
does the *detection* half deterministically — counting tool calls and elapsed time itself rather
than waiting for the model to notice — and nudges you here mid-session. You can also just invoke
this skill directly the moment you notice a task got big.

## When to Use

- Right after finishing a task that took a lot of tool calls, a long `execute_code`/`terminal`
  session, several external API/service calls, or a delegated subagent — and it's the kind of
  thing that will recur with different inputs (sync X to Y, generate a weekly report, process a
  batch of files, poll a service and act on results, etc).
- The user asks to "automate," "make a skill of," "remember how you did," or "run this again
  later" for something you just did.
- You're mid-task and it's *already* clearly heading toward "big" — it's fine to plan for
  distillation before you're even done, so the trace records itself as you go instead of being
  reconstructed from memory afterward.

Do **not** use this for tasks that are inherently one-off or deeply contextual: fixing this one
bug in this one function, writing this one specific email, answering a question that depended
entirely on today's context. If the "script" you'd write would just be `print("the answer the user
wanted this one time")`, it's not a distillation candidate — see Pitfalls.

## Quick Reference

| Step | What you do | Tool |
|---|---|---|
| 1. Check for overlap | Search local + Hub/skills.sh before building anything new | `scripts/find_skills.py`, `skill_view`, `hermes skills` |
| 2. Record | Write a structured trace of what actually happened | `scripts/record_trace.py` |
| 3. Reproduce | Write + verify a Python script that does the same thing | `execute_code` or `terminal` |
| 4. Package | Scaffold a skill directory around the verified script | `scripts/scaffold_skill.py` |
| 5. Register | Create the skill for real | `skill_manage` |
| 6. Report | Tell the user what got distilled and how to invoke it | — |

## Procedure

### 1. Check the ecosystem before rebuilding anything

Don't reinvent what's already maintained. Run
`python3 ${HERMES_SKILL_DIR}/scripts/find_skills.py "<a few keywords for the task>"` — it checks
Hermes's own Skills Hub first, falls back to `npx skills find` (the skills.sh CLI), and reminds
you what "good" looks like (install count, source reputation, stars). See
`references/finding-existing-skills.md` for the full quality bar. If something already fits,
install it (`hermes skills install <owner/repo>`, or an explicit `hermes skills tap add` for a
custom source) instead of distilling from scratch — that's a better outcome for the user than a
bespoke script only you know about.

If the fit is partial, note what's missing and consider whether your distilled skill should
*wrap* the existing one rather than duplicate it.

### 2. Record what actually happened

Write down the task as a structured trace, not just prose in the transcript — that's what makes
step 3 possible later, even in a different session. Use
`python3 ${HERMES_SKILL_DIR}/scripts/record_trace.py` with the task's title, goal, an ordered list
of steps (tool + purpose, no secrets), which external services were touched, and the verified
final outcome. This writes to `~/.hermes/distillery/traces/`. See
`references/big-task-criteria.md` for what's worth recording vs. skippable noise.

### 3. Synthesize and verify a reproducing script

- If every step is something `execute_code` can already reach via `hermes_tools` (web search/
  extract, file tools, etc.), write it as an `execute_code`-style script — it drops straight into
  the eventual skill's `scripts/` folder and needs no new dependency story.
- If the task called external APIs directly (not wrapped as a Hermes tool), write a small
  standalone Python script instead. Parameterize whatever varies run-to-run as CLI args or env
  vars. Never inline API keys or tokens — route them through `required_environment_variables` in
  the eventual SKILL.md instead (see `references/skill-authoring-cheatsheet.md`).
- **Actually run it** against the same or a fresh comparable input via `terminal`/`execute_code`
  and check the output matches the shape of the original verified outcome. A script you haven't
  run is a guess, not a distillation. If it only half-works, that's real information — the task
  may be less mechanical than it looked; see Pitfalls before forcing it into a skill anyway.

### 4. Scaffold the skill around the verified script

Run:

```
python3 ${HERMES_SKILL_DIR}/scripts/scaffold_skill.py \
  --name <kebab-case-name> \
  --category <productivity|devops|research|...> \
  --description "<when-to-use, written the way you'd want a future you to trigger on it>" \
  --script /path/to/verified_script.py \
  --trace ~/.hermes/distillery/traces/<the-trace-you-just-wrote>.json
```

By default this **stages** the skill under `~/.hermes/distillery/staged-skills/` rather than
writing straight into the live library — review the generated `SKILL.md` before it goes live.
If the task is something that should run on a schedule rather than only on demand, add
`--blueprint-schedule "<cron expr>"` so the scaffolded skill becomes a
[blueprint](references/skill-authoring-cheatsheet.md#blueprints) instead of a purely on-demand
skill.

### 5. Register it for real

Use the `skill_manage` tool to create the skill from the staged directory's contents, rather than
writing files into `~/.hermes/skills/` by hand — that keeps it on the normal path (shows up in the
system prompt index immediately, respects `write_approval` staging if the user has that config
on). If `task_distiller.auto_create_skill` is off (the default), describe what you're about to
register and get a go-ahead first.

### 6. Tell the user what happened

State plainly: what got distilled, where the skill now lives, what it's named (so they know what
to say to invoke it, or its `/skill-name` shortcut), and — if relevant — that it also matches a
`blueprint:` schedule they can accept via `/suggestions`. This is not a silent background
operation; the user should know their skill library grew.

## Pitfalls

- **Contextual ≠ repeatable.** A task that was hard because of *this specific context* (this bug,
  this conversation, this person's exact phrasing) doesn't generalize into a script no matter how
  many tool calls it took. Distill the *shape*, not the instance.
- **Don't launder secrets into the script.** `execute_code` scripts already can't read anything
  with `KEY`/`TOKEN`/`SECRET`/`PASSWORD`/`CREDENTIAL`/`AUTH` in the env var name — lean into that
  rather than working around it. Declare `required_environment_variables` (or
  `required_credential_files` for OAuth-style file creds) in the scaffolded SKILL.md instead.
- **Destructive or irreversible steps need a human in the loop, always** — don't set
  `task_distiller.auto_create_skill: true`, and don't let the generated script run destructive
  terminal/file/delete operations unattended just because the original task did them once
  successfully.
- **Hub security scanning doesn't cover locally-created skills.** The exfiltration/injection/
  destructive-command scanner in `references/skill-authoring-cheatsheet.md` runs on hub installs,
  not on skills you register via `skill_manage`. Read your own generated script critically before
  calling it done — especially before ever running `hermes skills publish` on it.
- **Don't flag noise.** Long doesn't always mean valuable. If the companion watcher plugin nudges
  you on something that was actually a one-off, just say so and move on — there's no obligation to
  distill everything that crosses a tool-call threshold.

## Verification

After registering the skill, confirm it actually works cheaply: invoke it on a fresh, analogous
input and check that the agent runs the bundled script (via `terminal`/`execute_code`) rather than
re-deriving the whole plan through LLM reasoning, that the script exits cleanly, and that the
output matches the shape of the original verified outcome. Also confirm
`~/.hermes/skills/<category>/<name>/` exists with `SKILL.md`, `scripts/`, and `references/trace.json`
in place.
