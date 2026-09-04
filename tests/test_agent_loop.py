"""Agent loop tests with a scripted fake LLM. Real browser, no network.

Covers: full form completion, per-step history assembly, <sys> observations
(navigation, step budget), error-event exclusion from LLM context, trace
writing, password scrubbing in the trace.
"""

import json
import re

import pytest

from txtwrght.agent import Agent, ExecutionResult
from txtwrght.config import Config
from txtwrght.llm import LLMResult
from txtwrght.trace import Trace


class ScriptedLLM:
    """Returns scripted actions in order; records every prompt it saw."""

    def __init__(self, script):
        self.script = list(script)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages[1]["content"])
        if not self.script:
            raise AssertionError("Script exhausted: agent asked for one step too many")
        entry = self.script.pop(0)
        action = entry(self.prompts[-1]) if callable(entry) else entry
        return LLMResult(
            action=action,
            evaluation_previous_goal="scripted eval",
            memory="scripted memory",
            next_goal="scripted goal",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            model="scripted",
        )


def index_of(prompt: str, marker: str) -> int:
    """Find the element index of the serialized line containing `marker`."""
    for line in prompt.splitlines():
        if marker in line:
            match = re.search(r"\[(\d+)\]<", line)
            if match:
                return int(match.group(1))
    raise AssertionError(f"No indexed line containing {marker!r} in prompt")


def fast_config() -> Config:
    return Config(headless=True, max_steps=10, step_delay=0)


@pytest.fixture
def trace(tmp_path):
    return Trace(directory=tmp_path)


def test_agent_completes_form(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))

    llm = ScriptedLLM(
        [
            lambda p: {"input_text": {"index": index_of(p, "Your username"), "text": "geez"}},
            lambda p: {"input_text": {"index": index_of(p, "Your password"), "text": "hunter2"}},
            lambda p: {"click_element_by_index": {"index": index_of(p, "terms")}},
            lambda p: {"click_element_by_index": {"index": index_of(p, "Register")}},
            {"done": {"text": "Form submitted for geez", "success": True}},
        ]
    )
    agent = Agent("fill the form", browser, llm, config=fast_config(), trace=trace)
    result = agent.run()

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.data == "Form submitted for geez"
    assert result.steps == 5
    assert result.usage["total_tokens"] == 15 * 5

    status = browser.page.evaluate("document.getElementById('status').textContent")
    assert status == "submitted:geez"


def test_first_prompt_has_navigation_observation(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))
    llm = ScriptedLLM([{"done": {"text": "ok", "success": True}}])
    Agent("noop", browser, llm, config=fast_config(), trace=trace).run()

    assert "<sys>Page navigated to -> " in llm.prompts[0]


def test_step_history_carried_between_steps(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))
    llm = ScriptedLLM(
        [
            lambda p: {"input_text": {"index": index_of(p, "Your username"), "text": "geez"}},
            {"done": {"text": "ok", "success": True}},
        ]
    )
    Agent("type the name", browser, llm, config=fast_config(), trace=trace).run()

    second = llm.prompts[1]
    assert "<step_1>" in second
    assert "Evaluation of Previous Step: scripted eval" in second
    assert "Memory: scripted memory" in second
    assert 'Typed "geez"' in second


def test_step_budget_exhaustion_and_warnings(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))
    config = Config(headless=True, max_steps=3, step_delay=0)
    llm = ScriptedLLM([{"wait": {"seconds": 1}}] * 3)
    result = Agent("stall forever", browser, llm, config=config, trace=trace).run()

    assert result.success is False
    assert "Step count exceeded maximum limit" in result.data
    # max_steps=3: at step 1 remaining == 2 -> critical warning in that prompt
    assert any("Critical: Only 2 steps left" in p for p in llm.prompts)


def test_tool_error_becomes_action_result(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))
    llm = ScriptedLLM(
        [
            {"click_element_by_index": {"index": 9999}},
            {"done": {"text": "gave up", "success": False}},
        ]
    )
    result = Agent("click nothing", browser, llm, config=fast_config(), trace=trace).run()

    assert result.success is False
    # The failure surfaced to the model as an Action Result, loop continued
    assert any("Action Results: Error:" in p for p in llm.prompts)


def test_error_events_excluded_from_llm_context(browser, fixture_url, trace):
    browser.goto(fixture_url("form.html"))
    llm = ScriptedLLM([{"done": {"text": "ok", "success": True}}])
    agent = Agent("noop", browser, llm, config=fast_config(), trace=trace)
    agent.history.append({"type": "error", "message": "SECRET-INTERNAL-FAILURE"})
    agent.run()

    assert "SECRET-INTERNAL-FAILURE" not in llm.prompts[0]


def test_trace_written_with_password_scrubbed(browser, fixture_url, tmp_path):
    browser.goto(fixture_url("form.html"))
    trace = Trace(directory=tmp_path)
    llm = ScriptedLLM(
        [
            lambda p: {"input_text": {"index": index_of(p, "Your password"), "text": "hunter2"}},
            {"done": {"text": "ok", "success": True}},
        ]
    )
    result = Agent("type password", browser, llm, config=fast_config(), trace=trace).run()

    raw = open(result.trace_path, encoding="utf-8").read()
    assert "hunter2" not in raw
    assert "***scrubbed***" in raw

    events = [json.loads(line) for line in raw.splitlines()]
    types = {e["type"] for e in events}
    assert {"task_start", "browser_state", "llm_output", "action_result", "task_end"} <= types
    end = [e for e in events if e["type"] == "task_end"][0]
    assert end["success"] is True
    assert end["usage"]["total_tokens"] == 30
