"""
task-distiller-watcher -- Hermes plugin.

Deterministically watches tool-call volume, external/expensive tool usage, and wall-clock
duration for the *current* session, and once a configurable threshold is crossed, injects a
nudge into the conversation pointing the agent at the task-distiller skill. This does not
depend on the model noticing on its own -- and because it's a plugin (not a
~/.hermes/hooks/ gateway hook), it fires in CLI sessions too, not just the messaging gateway.

Install:
    cp -r task-distiller-watcher ~/.hermes/plugins/
    (restart Hermes; run `hermes plugins enable task-distiller-watcher` first if your
    version requires explicit enabling -- check `hermes plugins list`)

Tune thresholds in ~/.hermes/distillery/config.json (created with defaults on first run).

Set HERMES_PLUGINS_DEBUG=1 before starting Hermes to see hook-firing detail in stderr /
~/.hermes/logs/agent.log while you calibrate thresholds. The exact keyword arguments Hermes
passes into each hook can vary across versions, so this plugin only relies on what it can
defensively read via .get(), and otherwise tracks everything itself (tool-call counts,
timestamps) rather than assuming one particular payload shape. If your version's hook
kwargs differ from what's guessed here, the counting logic (which doesn't depend on any of
that) still works fine on its own.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

CONFIG_PATH = Path.home() / ".hermes" / "distillery" / "config.json"
CANDIDATES_LOG = Path.home() / ".hermes" / "distillery" / "candidates.jsonl"

DEFAULT_CONFIG = {
    "enabled": True,
    "tool_call_threshold": 8,
    "external_hit_threshold": 3,
    "duration_s_threshold": 180,
    # Rough name-matching for "this touched something outside plain reasoning" --
    # tune this list for your own tool/plugin/MCP server names.
    "expensive_tool_markers": [
        "execute_code",
        "terminal",
        "delegate_task",
        "web_search",
        "web_extract",
        "browser_",
        "mcp_",
        "email",
        "notion",
        "github",
        "slack",
        "calendar",
    ],
}

# In-process, per-session state. A CLI session is one process lifetime, so this is reliable
# there; a long-lived gateway process serving many sessions is naturally keyed per session id.
_session_state: dict = {}


def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(json.loads(CONFIG_PATH.read_text()))
            return cfg
    except Exception:
        pass
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def _session_key(kwargs: dict) -> str:
    # Best-effort: different hook payloads may expose the session id under different keys
    # depending on your Hermes version.
    for k in ("session_id", "session", "sid"):
        if kwargs.get(k):
            return str(kwargs[k])
    return "default"


def _tool_name(args: tuple, kwargs: dict) -> str:
    for k in ("tool_name", "name", "tool"):
        if kwargs.get(k):
            return str(kwargs[k])
    for a in args:
        if isinstance(a, str):
            return a
        if isinstance(a, dict) and a.get("name"):
            return str(a["name"])
    return "unknown_tool"


def _log_candidate(record: dict) -> None:
    try:
        CANDIDATES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CANDIDATES_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def register(ctx) -> None:
    config = _load_config()
    if not config.get("enabled", True):
        return

    def on_session_start(*args, **kwargs) -> None:
        key = _session_key(kwargs)
        _session_state[key] = {
            "start": time.time(),
            "tool_calls": 0,
            "external_hits": 0,
            "flagged": False,
            "tools_seen": [],
        }

    def post_tool_call(*args, **kwargs) -> None:
        key = _session_key(kwargs)
        state = _session_state.setdefault(
            key,
            {"start": time.time(), "tool_calls": 0, "external_hits": 0, "flagged": False, "tools_seen": []},
        )
        name = _tool_name(args, kwargs)
        state["tool_calls"] += 1
        state["tools_seen"].append(name)
        if any(marker in name for marker in config["expensive_tool_markers"]):
            state["external_hits"] += 1

        if state["flagged"]:
            return

        elapsed = time.time() - state["start"]
        crossed = (
            state["tool_calls"] >= config["tool_call_threshold"]
            or state["external_hits"] >= config["external_hit_threshold"]
            or elapsed >= config["duration_s_threshold"]
        )
        if not crossed:
            return

        state["flagged"] = True
        _log_candidate(
            {
                "session": key,
                "flagged_at": time.time(),
                "tool_calls": state["tool_calls"],
                "external_hits": state["external_hits"],
                "elapsed_s": round(elapsed, 1),
                "tools_seen": state["tools_seen"][-25:],
            }
        )

        nudge = (
            f"[task-distiller-watcher] This task has now made {state['tool_calls']} tool calls "
            f"(including {state['external_hits']} that look like external/API/service calls) over "
            f"about {int(elapsed)}s. That's a strong candidate for distillation. Once the current "
            f"task is verified complete, consult the task-distiller skill and, unless this was a "
            f"one-off/contextual task that's unlikely to recur, record the process, write a Python "
            f"script that reproduces it, verify the script, and register it as a new skill."
        )
        try:
            ctx.inject_message(nudge, role="user")
        except Exception:
            # Older/newer ctx APIs may differ -- fall back to a log entry so the signal isn't
            # silently lost even if injection isn't available in your version.
            _log_candidate(
                {"session": key, "note": "inject_message failed; nudge not delivered", "nudge": nudge}
            )

    def on_session_end(*args, **kwargs) -> None:
        key = _session_key(kwargs)
        _session_state.pop(key, None)

    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("post_tool_call", post_tool_call)
    ctx.register_hook("on_session_end", on_session_end)
