# Finding Existing Skills Before You Build One

The open agent-skills ecosystem is large and growing — checking it first is usually faster than
writing something from scratch, and gives the user a maintained, community-vetted result instead
of a bespoke script only this Hermes instance knows about. Hermes can consume skills from several
sources natively: direct GitHub identifiers (`owner/repo` or `owner/repo/skill-name`), skills.sh
identifiers, and well-known `/.well-known/skills/index.json` endpoints. This doc covers the
practical workflow; `scripts/find_skills.py` automates most of it.

## Step 1 — Check the leaderboard / Hub for an obvious fit

Before running any search, think about whether this is a common-enough domain that a well-known
skill probably already exists — deployment workflows, document formats, common dev/design/testing
tasks, popular SaaS integrations. The [skills.sh leaderboard](https://skills.sh) surfaces the most
installed, battle-tested options; official sources like `anthropics/skills`, `vercel-labs/*`, and
`microsoft/azure-skills` are a good first stop for broad categories.

## Step 2 — Search

```bash
python3 ${HERMES_SKILL_DIR}/scripts/find_skills.py "<keywords>"
```

This tries the native Hermes Hub search first, then falls back to `npx skills find <query>` (the
skills.sh CLI) if that comes up empty or isn't available. Use specific keywords — "react
performance" beats "performance"; "changelog generator" beats "docs."

## Step 3 — Verify quality before recommending or installing anything

Don't act on a search hit alone. Check:

1. **Install count** — prefer 1K+ installs; treat anything under ~100 with real skepticism.
2. **Source reputation** — official orgs (`vercel-labs`, `anthropics`, `microsoft`, `openai`,
   `huggingface`) carry more trust than an unknown individual account.
3. **GitHub stars** — a source repo with under ~100 stars is worth a closer look before trusting
   it, especially for anything that will run shell commands or handle credentials.

Hermes's own hub applies a security scan to hub-installed skills (checking for data exfiltration
patterns, prompt injection, destructive commands, and shell injection) with trust tiers of
`builtin` / `official` / `trusted` (openai/skills, anthropics/skills, huggingface/skills) /
`community` (non-dangerous findings can be overridden with `--force`; `dangerous` verdicts stay
blocked). That scan is a floor, not a substitute for your own judgment on anything sensitive.

## Step 4 — Install or fall back to distillation

If something fits:

```bash
hermes skills install <owner/repo>              # or owner/repo/skill-name for a single skill
hermes skills tap add <owner/repo>              # to add a whole custom source for repeated use
```

(`npx skills add <owner/repo>` also works generically across the wider skills.sh-compatible agent
ecosystem, if you'd rather install it that way.)

If nothing fits, or the fit is only partial, that's exactly when `task-distiller`'s own
record → script → scaffold → register flow (back in the main `SKILL.md`) takes over. Note in the
new skill's description what you checked and didn't find, so a future search — yours or anyone
else's — doesn't repeat the same dead end.
