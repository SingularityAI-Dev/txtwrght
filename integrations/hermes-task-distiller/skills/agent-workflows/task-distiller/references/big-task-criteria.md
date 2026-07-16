# What Counts as a "Big Task"

Kept out of `SKILL.md` per progressive disclosure — read this when you actually need to judge a
borderline case, or when tuning the watcher plugin's thresholds.

## Signals worth weighing

None of these alone is decisive; weigh them together.

- **Tool-call count.** A task that needed 8+ tool calls to finish is doing real multi-step work.
  Under ~4-5, it's usually not worth the overhead of a script + skill.
- **External/expensive tool usage.** Calls to `execute_code`, `terminal`, `delegate_task`,
  `web_search`/`web_extract`, browser automation, or any `mcp_*`-prefixed tool are a stronger
  signal than plain reasoning turns — they mean the task actually reached outside the model.
- **Wall-clock duration.** A task that ran for several minutes (roughly 3+) usually did enough
  sequential work that a script would meaningfully save time next time, independent of token cost.
- **Repetition potential.** The strongest signal of all, and the one no plugin can measure for
  you: will this specific *shape* of task come up again with different inputs? A one-off is a
  one-off no matter how expensive it was.
- **Explicit user signal.** "Can you automate this," "make this a skill," "remember how you did
  this" overrides any heuristic — treat it as an immediate trigger regardless of size.

## Examples

**Good distillation candidates:**
- "Pull this week's closed GitHub issues and post a summary to Slack" — recurs weekly, same steps,
  different data each time.
- "Take this CSV, clean it, and load it into the reporting database" — recurs whenever a new CSV
  shows up, same transform each time.
- "Poll this API every hour and alert if a value crosses a threshold" — obviously recurring, and a
  natural fit for a [blueprint](skill-authoring-cheatsheet.md#blueprints) rather than only an
  on-demand skill.

**Poor distillation candidates (even if they were expensive):**
- "Debug why *this* deployment is failing" — the fix was specific to this incident.
- "Draft a reply to *this* email from *this* person" — the content was the point, not the process.
- A long research task whose value was the specific synthesis/judgment calls made along the way,
  not a repeatable procedure — a script can't replace the reasoning; don't try to force one.

## Relationship to the watcher plugin's thresholds

The `task-distiller-watcher` plugin (installed separately — see the top-level README) tracks
tool-call count, "expensive tool" hits, and elapsed time *itself*, per session, and nudges you
here once configured thresholds are crossed. Its defaults live in
`~/.hermes/distillery/config.json`:

```json
{
  "enabled": true,
  "tool_call_threshold": 8,
  "external_hit_threshold": 3,
  "duration_s_threshold": 180,
  "expensive_tool_markers": ["execute_code", "terminal", "delegate_task", "web_search", "web_extract", "browser_", "mcp_", "email", "notion", "github", "slack", "calendar"]
}
```

Edit that file directly to tune sensitivity — lower the thresholds if you want earlier nudges on a
system that mostly does small tasks, raise them if the nudge fires too often on a system that
routinely does legitimately long single-purpose work.
