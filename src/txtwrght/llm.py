"""OpenAI-compatible LLM client with forced AgentOutput tool call.

Port of page-agent's packages/llms/src/OpenAIClient.ts and
packages/core/src/utils/autoFixer.ts. One forced tool call per step returning
{evaluation_previous_goal, memory, next_goal, action: {tool_name: args}}.

Endpoints form an ordered failover chain (Config.llm_endpoints): transport and
HTTP errors move to the next endpoint; malformed output is parse-retried twice
per endpoint before failing over.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from txtwrght.config import LLMEndpoint

PARSE_RETRIES = 2

# The LLM-visible action contract. Descriptions and schemas mirror page-agent's
# tools/index.ts; execution lives in tools.py / agent.py.
AGENT_TOOLS: dict[str, dict[str, Any]] = {
    "done": {
        "description": (
            "Complete task. Text is your final response to the user - keep it "
            "concise unless the user explicitly asks for detail."
        ),
        "properties": {
            "text": {"type": "string"},
            "success": {"type": "boolean", "default": True},
        },
        "required": ["text"],
        "defaults": {"success": True},
    },
    "wait": {
        "description": (
            "Wait for x seconds. Can be used to wait until the page or data is "
            "fully loaded."
        ),
        "properties": {
            "seconds": {"type": "number", "minimum": 1, "maximum": 10, "default": 1},
        },
        "required": ["seconds"],
        "defaults": {"seconds": 1},
    },
    "click_element_by_index": {
        "description": "Click element by index",
        "properties": {"index": {"type": "integer", "minimum": 0}},
        "required": ["index"],
        "defaults": {},
    },
    "input_text": {
        "description": "Click and type text into an interactive input element",
        "properties": {
            "index": {"type": "integer", "minimum": 0},
            "text": {"type": "string"},
        },
        "required": ["index", "text"],
        "defaults": {},
    },
    "select_dropdown_option": {
        "description": (
            "Select dropdown option for interactive element index by the text of "
            "the option you want to select"
        ),
        "properties": {
            "index": {"type": "integer", "minimum": 0},
            "text": {"type": "string"},
        },
        "required": ["index", "text"],
        "defaults": {},
    },
    "scroll": {
        "description": (
            "Scroll vertically. Without index: scrolls the document. With index: "
            "scrolls the container at that index (or its nearest scrollable "
            "ancestor). Use index of a data-scrollable element to scroll a "
            "specific area."
        ),
        "properties": {
            "down": {"type": "boolean", "default": True},
            "num_pages": {"type": "number", "minimum": 0, "maximum": 10},
            "pixels": {"type": "integer", "minimum": 0},
            "index": {"type": "integer", "minimum": 0},
        },
        "required": [],
        "defaults": {"down": True, "num_pages": 1.0},
    },
    "scroll_horizontally": {
        "description": (
            "Scroll horizontally. Without index: scrolls the document. With "
            "index: scrolls the container at that index (or its nearest "
            "scrollable ancestor)."
        ),
        "properties": {
            "right": {"type": "boolean", "default": True},
            "pixels": {"type": "integer", "minimum": 0},
            "index": {"type": "integer", "minimum": 0},
        },
        "required": [],
        "defaults": {"right": True},
    },
}


class LLMError(Exception):
    """All endpoints in the chain failed."""


class ParseError(Exception):
    """The model output could not be normalized into a valid AgentOutput."""


@dataclass
class LLMResult:
    action: dict[str, Any]
    evaluation_previous_goal: str = ""
    memory: str = ""
    next_goal: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw_response: Any = None


def agent_output_tool(tools: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The single forced OpenAI tool: schema = union of tool arg schemas under `action`."""
    tools = tools or AGENT_TOOLS
    action_schemas = [
        {
            "type": "object",
            "description": spec["description"],
            "properties": {
                name: {
                    "type": "object",
                    "properties": spec["properties"],
                    "required": spec["required"],
                    "additionalProperties": False,
                }
            },
            "required": [name],
            "additionalProperties": False,
        }
        for name, spec in tools.items()
    ]
    return {
        "type": "function",
        "function": {
            "name": "AgentOutput",
            "description": "You MUST call this tool every step!",
            "parameters": {
                "type": "object",
                "properties": {
                    "evaluation_previous_goal": {"type": "string"},
                    "memory": {"type": "string"},
                    "next_goal": {"type": "string"},
                    "action": {"anyOf": action_schemas},
                },
                "required": ["action"],
            },
        },
    }


def _safe_json_parse(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value.strip())
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def _json_from_string(text: str) -> Any:
    match = re.search(r"({[\s\S]*})", text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


REFLECTION_KEYS = ("evaluation_previous_goal", "memory", "next_goal", "thinking")


def normalize_response(
    response: dict[str, Any], tools: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Normalize an LLM chat-completion response into a MacroTool input dict.

    Fixes, in autoFixer.ts order: action name used as tool name, JSON in content
    instead of tool_calls (with wrapper unwrapping), double-stringified
    arguments, primitive action input, missing action -> wait.
    """
    tools = tools or AGENT_TOOLS

    choices = response.get("choices") or []
    if not choices:
        raise ParseError("No choices in response")
    message = choices[0].get("message")
    if not message:
        raise ParseError("No message in choice")

    tool_calls = message.get("tool_calls") or []
    tool_call = tool_calls[0] if tool_calls else None
    function = (tool_call or {}).get("function") or {}

    if function.get("arguments"):
        resolved = _safe_json_parse(function["arguments"])
        name = function.get("name")
        if name and name != "AgentOutput":
            # Model used the action name as the tool call name.
            resolved = {"action": {name: _safe_json_parse(resolved)}}
    elif message.get("content"):
        parsed = _json_from_string(message["content"].strip())
        if parsed is None:
            raise ParseError(
                "No tool_call and the message content does not contain valid JSON"
            )
        resolved = parsed
        if isinstance(resolved, dict) and resolved.get("name") == "AgentOutput":
            resolved = _safe_json_parse(resolved.get("arguments"))
        if isinstance(resolved, dict) and resolved.get("type") == "function":
            resolved = _safe_json_parse(
                (resolved.get("function") or {}).get("arguments")
            )
        if isinstance(resolved, dict) and not any(
            k in resolved for k in ("action", *REFLECTION_KEYS)
        ):
            resolved = {"action": resolved}
    else:
        raise ParseError("No tool_call nor message content is present")

    resolved = _safe_json_parse(resolved)
    if not isinstance(resolved, dict):
        raise ParseError(f"Arguments did not resolve to an object: {resolved!r}")
    if resolved.get("action"):
        resolved["action"] = _safe_json_parse(resolved["action"])

    if resolved.get("action"):
        resolved["action"] = _validate_action(resolved["action"], tools)
    else:
        resolved["action"] = {"wait": {"seconds": 1}}

    return resolved


def _validate_action(
    action: Any, tools: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if not isinstance(action, dict) or not action:
        raise ParseError(f"Action is not an object: {action!r}")

    tool_name = next(iter(action))
    spec = tools.get(tool_name)
    if spec is None:
        available = ", ".join(tools)
        raise ParseError(f'Unknown action "{tool_name}". Available: {available}')

    value = action[tool_name]

    # Coerce primitive input for single-required-field tools:
    # {"click_element_by_index": 2} -> {"click_element_by_index": {"index": 2}}
    if not isinstance(value, dict) and value is not None:
        if len(spec["required"]) == 1:
            value = {spec["required"][0]: value}
        else:
            raise ParseError(
                f'Invalid input for action "{tool_name}": expected an object, '
                f"got {value!r}"
            )
    value = dict(spec["defaults"], **(value or {}))

    missing = [k for k in spec["required"] if k not in value]
    if missing:
        raise ParseError(
            f'Invalid input for action "{tool_name}": missing required '
            f"field(s) {', '.join(missing)}"
        )

    return {tool_name: value}


class LLMClient:
    def __init__(
        self,
        endpoints: list[LLMEndpoint],
        tools: dict[str, dict[str, Any]] | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120.0,
    ):
        if not endpoints:
            raise LLMError(
                "No LLM endpoints configured. Set LLM_1_BASE_URL (and friends) "
                "in .env; see .env.example."
            )
        self.endpoints = endpoints
        self.tools = tools or AGENT_TOOLS
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def invoke(self, messages: list[dict[str, Any]]) -> LLMResult:
        """Walk the endpoint chain; parse-retry per endpoint; failover on error."""
        failures: list[str] = []

        for endpoint in self.endpoints:
            headers = {"Content-Type": "application/json"}
            if endpoint.api_key:
                headers["Authorization"] = f"Bearer {endpoint.api_key}"
            body = {
                "model": endpoint.model,
                "messages": messages,
                "tools": [agent_output_tool(self.tools)],
                "parallel_tool_calls": False,
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "AgentOutput"},
                },
            }

            for _attempt in range(1 + PARSE_RETRIES):
                try:
                    response = self._client.post(
                        f"{endpoint.base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                except httpx.HTTPError as error:
                    failures.append(f"{endpoint.base_url}: transport error {error}")
                    break  # next endpoint

                if response.status_code != 200:
                    detail = response.text[:200]
                    failures.append(
                        f"{endpoint.base_url}: HTTP {response.status_code} {detail}"
                    )
                    break  # auth/rate-limit/server error: next endpoint

                try:
                    data = response.json()
                except ValueError:
                    failures.append(f"{endpoint.base_url}: response not JSON")
                    break

                finish_reason = (data.get("choices") or [{}])[0].get("finish_reason")
                if finish_reason in ("length", "content_filter"):
                    failures.append(
                        f"{endpoint.base_url}: finish_reason={finish_reason}"
                    )
                    break

                try:
                    parsed = normalize_response(data, self.tools)
                except ParseError as error:
                    failures.append(f"{endpoint.base_url}: parse error: {error}")
                    continue  # parse retry on the same endpoint

                usage = data.get("usage") or {}
                return LLMResult(
                    action=parsed["action"],
                    evaluation_previous_goal=parsed.get(
                        "evaluation_previous_goal", ""
                    ),
                    memory=parsed.get("memory", ""),
                    next_goal=parsed.get("next_goal", ""),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    model=endpoint.model,
                    raw_response=data,
                )

        raise LLMError(
            "All LLM endpoints failed:\n" + "\n".join(f"- {f}" for f in failures)
        )
