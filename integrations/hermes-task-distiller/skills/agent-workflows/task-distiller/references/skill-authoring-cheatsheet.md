# Hermes SKILL.md Cheat Sheet

A condensed reference so you don't need to re-fetch Hermes's own developer docs
(`docs/developer-guide/creating-skills`) every time you scaffold something. If anything here looks
stale, that page is the source of truth — Hermes moves fast.

## Directory shape

```
~/.hermes/skills/
├── <category>/
│   └── <skill-name>/
│       ├── SKILL.md          # required
│       ├── scripts/          # helper scripts, referenced via ${HERMES_SKILL_DIR}
│       ├── references/       # docs loaded only when needed
│       └── assets/           # templates, icons, etc.
```

`~/.hermes/skills/` is the primary, read-write source of truth. Additional read-only-by-convention
directories can be configured; if the same skill name exists in both, the local copy wins.

## Frontmatter fields

| Field | Purpose |
|---|---|
| `name` | Identifier — becomes the `/name` slash command |
| `description` | **The** triggering signal — be specific about when to use it, a little "pushy" combats under-triggering |
| `version`, `author`, `license` | Metadata |
| `platforms` | Optional OS restriction: `[macos]`, `[linux]`, `[windows]`, or omit for all |
| `metadata.hermes.tags` | Category/keyword tags |
| `metadata.hermes.related_skills` | Cross-links to other skill names |
| `metadata.hermes.requires_toolsets` / `requires_tools` | Hide the skill unless these are active/available |
| `metadata.hermes.fallback_for_toolsets` / `fallback_for_tools` | Hide the skill when these ARE available (workaround pattern) |
| `metadata.hermes.config` | Non-secret settings surfaced via `hermes config migrate`, stored under `skills.config.<key>` in `config.yaml` |
| `metadata.hermes.blueprint` | Presence marks the skill as a schedulable automation — see Blueprints below |
| `required_environment_variables` | Secrets (API keys, tokens) — stored in `~/.hermes/.env`, never shown to the model, auto-passed-through to `execute_code`/`terminal` sandboxes once the skill is loaded |
| `required_credential_files` | File-based creds (OAuth tokens, service account JSON) — relative to `~/.hermes/`, auto-mounted into sandboxes |

## Body sections (Hermes's own convention)

```markdown
# Skill Title
Brief intro.
## When to Use
Trigger conditions.
## Quick Reference
Common commands/APIs at a glance.
## Procedure
Step-by-step instructions.
## Pitfalls
Known failure modes.
## Verification
How to confirm it worked.
```

## Template tokens (substituted wherever they appear in the body)

| Token | Replaced with |
|---|---|
| `${HERMES_SKILL_DIR}` | Absolute path to this skill's directory |
| `${HERMES_SESSION_ID}` | The active session id |

So a script reference like `python3 ${HERMES_SKILL_DIR}/scripts/run.py` becomes a ready-to-run
absolute path with no extra lookup round-trip. (Disabled globally via `skills.template_vars:
false` in `config.yaml`, if you ever need to.)

## Inline shell snippets (opt-in, off by default)

`` !`cmd` `` in the body gets its stdout inlined before the agent reads the skill — useful for
dynamic context like the current date. **Off by default** because any snippet runs on the host
without approval; only relevant for skill sources you already trust, and only if the user has set
`skills.inline_shell: true` in `config.yaml`.

## Blueprints

Add a `metadata.hermes.blueprint` block and an ordinary skill becomes a shareable, runnable
automation:

```yaml
metadata:
  hermes:
    blueprint:
      schedule: "0 9 * * *"   # cron expr, "every 2h", or an ISO timestamp
      deliver: origin          # optional, default origin
      prompt: "Task instruction for each run"   # optional
      no_agent: false           # optional
```

Installing a skill that carries a `blueprint:` block registers it as a **suggested** cron job, not
an active one — scheduling stays opt-in via `/suggestions accept N`. This is the right move for
`task-distiller` output when the underlying task is inherently recurring on a timer (a weekly
report, an hourly poll) rather than only "the next time it happens to come up."

## Registering a skill

Prefer the `skill_manage` tool over writing files directly — it respects `write_approval` staging
(if the user has that config on) and keeps the skill on Hermes's normal create/edit/delete path so
it shows up immediately in the system prompt index, `skills_list`, and as a `/skill-name` shortcut.

## Publishing outward (only once you're confident in it)

```bash
hermes skills publish skills/my-skill --to github --repo owner/repo   # to the Hub
hermes skills tap add owner/repo                                      # to share a custom source
```
