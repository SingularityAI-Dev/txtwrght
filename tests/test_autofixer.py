"""Auto-fixer unit tests: recorded malformed LLM outputs -> normalized MacroTool input.

Cases ported from page-agent packages/core/src/utils/autoFixer.ts. No network.
"""

import json

import pytest

from hermd.llm import ParseError, normalize_response


def response_with_tool_call(name: str, arguments: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


def response_with_content(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ]
    }


WELL_FORMED = {
    "evaluation_previous_goal": "Success",
    "memory": "On the form page",
    "next_goal": "Click submit",
    "action": {"click_element_by_index": {"index": 5}},
}


def test_well_formed_passthrough():
    resp = response_with_tool_call("AgentOutput", json.dumps(WELL_FORMED))
    out = normalize_response(resp)
    assert out == WELL_FORMED


def test_json_in_content_instead_of_tool_call():
    resp = response_with_content(
        "Here is my plan:\n" + json.dumps(WELL_FORMED) + "\nDone."
    )
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 5}}
    assert out["next_goal"] == "Click submit"


def test_content_with_agentoutput_wrapper():
    wrapped = {"name": "AgentOutput", "arguments": json.dumps(WELL_FORMED)}
    resp = response_with_content(json.dumps(wrapped))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 5}}


def test_content_with_function_wrapper():
    wrapped = {
        "type": "function",
        "function": {"name": "AgentOutput", "arguments": json.dumps(WELL_FORMED)},
    }
    resp = response_with_content(json.dumps(wrapped))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 5}}


def test_content_action_level_only():
    resp = response_with_content(json.dumps({"click_element_by_index": {"index": 3}}))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 3}}


def test_action_name_used_as_tool_name():
    resp = response_with_tool_call(
        "click_element_by_index", json.dumps({"index": 7})
    )
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 7}}


def test_double_stringified_arguments():
    resp = response_with_tool_call("AgentOutput", json.dumps(json.dumps(WELL_FORMED)))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 5}}


def test_double_stringified_action_field():
    payload = dict(WELL_FORMED, action=json.dumps(WELL_FORMED["action"]))
    resp = response_with_tool_call("AgentOutput", json.dumps(payload))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 5}}


def test_primitive_coercion_single_required_field():
    payload = dict(WELL_FORMED, action={"click_element_by_index": 2})
    resp = response_with_tool_call("AgentOutput", json.dumps(payload))
    out = normalize_response(resp)
    assert out["action"] == {"click_element_by_index": {"index": 2}}


def test_missing_action_falls_back_to_wait():
    payload = {k: v for k, v in WELL_FORMED.items() if k != "action"}
    resp = response_with_tool_call("AgentOutput", json.dumps(payload))
    out = normalize_response(resp)
    assert out["action"] == {"wait": {"seconds": 1}}


def test_unknown_action_raises():
    payload = dict(WELL_FORMED, action={"launch_missiles": {"target": "moon"}})
    resp = response_with_tool_call("AgentOutput", json.dumps(payload))
    with pytest.raises(ParseError, match="launch_missiles"):
        normalize_response(resp)


def test_missing_required_arg_raises():
    payload = dict(WELL_FORMED, action={"input_text": {"index": 1}})  # no text
    resp = response_with_tool_call("AgentOutput", json.dumps(payload))
    with pytest.raises(ParseError, match="text"):
        normalize_response(resp)


def test_no_tool_call_no_json_content_raises():
    resp = response_with_content("I could not decide what to do next.")
    with pytest.raises(ParseError):
        normalize_response(resp)


def test_no_choices_raises():
    with pytest.raises(ParseError):
        normalize_response({"choices": []})
