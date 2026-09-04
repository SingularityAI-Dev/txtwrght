"""LLM client tests: failover chain order, parse-retry, config loading. No network.

httpx transport is mocked via httpx.MockTransport.
"""

import json

import httpx
import pytest

from txtwrght.config import Config, LLMEndpoint
from txtwrght.llm import LLMClient, LLMError


def agent_output_response(action: dict) -> dict:
    args = {
        "evaluation_previous_goal": "ok",
        "memory": "m",
        "next_goal": "g",
        "action": action,
    }
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "AgentOutput",
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


ENDPOINTS = [
    LLMEndpoint(base_url="http://one.test/v1", api_key="k1", model="m1"),
    LLMEndpoint(base_url="http://two.test/v1", api_key="", model="m2"),
]

MESSAGES = [{"role": "user", "content": "hi"}]


def make_client(handler) -> LLMClient:
    return LLMClient(ENDPOINTS, transport=httpx.MockTransport(handler))


def test_primary_endpoint_used_first():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        return httpx.Response(200, json=agent_output_response({"wait": {"seconds": 1}}))

    result = make_client(handler).invoke(MESSAGES)
    assert calls == ["one.test"]
    assert result.action == {"wait": {"seconds": 1}}
    assert result.usage["total_tokens"] == 15
    assert result.model == "m1"


def test_transport_failure_falls_through_to_second_endpoint():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "one.test":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=agent_output_response({"wait": {"seconds": 1}}))

    result = make_client(handler).invoke(MESSAGES)
    assert calls == ["one.test", "two.test"]
    assert result.model == "m2"


def test_auth_failure_falls_through():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "one.test":
            return httpx.Response(401, json={"error": {"message": "bad key"}})
        return httpx.Response(200, json=agent_output_response({"wait": {"seconds": 1}}))

    result = make_client(handler).invoke(MESSAGES)
    assert result.model == "m2"


def test_parse_retry_twice_then_next_endpoint():
    calls = []
    garbage = {
        "choices": [
            {"message": {"role": "assistant", "content": "no json here"},
             "finish_reason": "stop"}
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "one.test":
            return httpx.Response(200, json=garbage)
        return httpx.Response(200, json=agent_output_response({"wait": {"seconds": 1}}))

    result = make_client(handler).invoke(MESSAGES)
    # 1 initial + 2 parse retries on endpoint one, then endpoint two
    assert calls == ["one.test", "one.test", "one.test", "two.test"]
    assert result.model == "m2"


def test_all_endpoints_down_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError):
        make_client(handler).invoke(MESSAGES)


def test_blank_api_key_omits_authorization_header():
    headers_seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        headers_seen[request.url.host] = "authorization" in request.headers
        if request.url.host == "one.test":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=agent_output_response({"wait": {"seconds": 1}}))

    make_client(handler).invoke(MESSAGES)
    assert headers_seen == {"one.test": True, "two.test": False}


def test_config_loads_endpoint_chain(monkeypatch):
    monkeypatch.setenv("LLM_1_BASE_URL", "http://a.test/v1")
    monkeypatch.setenv("LLM_1_API_KEY", "ka")
    monkeypatch.setenv("LLM_1_MODEL", "ma")
    # slot 2 blank -> skipped; slot 3 set -> kept in order
    # (blank, not deleted: load_dotenv would repopulate deleted vars from .env)
    monkeypatch.setenv("LLM_2_BASE_URL", "")
    monkeypatch.setenv("LLM_3_BASE_URL", "http://c.test/v1")
    monkeypatch.setenv("LLM_3_API_KEY", "")
    monkeypatch.setenv("LLM_3_MODEL", "mc")
    monkeypatch.setenv("MAX_STEPS", "7")
    monkeypatch.setenv("STEP_DELAY", "0.1")

    config = Config.from_env()
    assert [e.base_url for e in config.llm_endpoints] == [
        "http://a.test/v1",
        "http://c.test/v1",
    ]
    assert config.llm_endpoints[1].api_key == ""
    assert config.max_steps == 7
    assert config.step_delay == 0.1
