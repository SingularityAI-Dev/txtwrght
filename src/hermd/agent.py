"""The agent loop: observe -> think -> act, ported from page-agent's PageAgentCore.

Semantics kept from upstream: max steps, step delay, URL-change and step-budget
observations injected as <sys> notes, per-step history with reflection fields,
error events recorded in the trace but excluded from the LLM context. Element
indices regenerate on every snapshot.

Deviation from upstream, on purpose: a failed tool execution becomes the step's
Action Result string (the model sees the error and can recover) instead of
aborting the run; only LLM-chain exhaustion and unexpected exceptions abort.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from hermd import tools
from hermd.browser import Browser
from hermd.config import Config
from hermd.llm import LLMClient, LLMError, LLMResult
from hermd.trace import Trace

SYSTEM_PROMPT = (
    resources.files("hermd.prompts").joinpath("system_prompt.md").read_text()
)

SCRUBBED = "***scrubbed***"


@dataclass
class ExecutionResult:
    success: bool
    data: str
    steps: int
    usage: dict[str, int] = field(default_factory=dict)
    trace_path: str = ""


class Agent:
    def __init__(
        self,
        task: str,
        browser: Browser,
        llm: LLMClient,
        config: Config | None = None,
        trace: Trace | None = None,
        verbose: bool = False,
    ):
        self.task = task
        self.browser = browser
        self.llm = llm
        self.config = config or Config.from_env()
        self.trace = trace or Trace()
        self.verbose = verbose

        self.history: list[dict[str, Any]] = []
        self._observations: list[str] = []
        self._last_url = ""
        self._total_wait_time = 0.0
        self._usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def run(self) -> ExecutionResult:
        self.trace.write("task_start", task=self.task, max_steps=self.config.max_steps)
        step = 0
        result: ExecutionResult

        while True:
            try:
                if step > 0:
                    time.sleep(self.config.step_delay)

                # observe
                state = self.browser.snapshot()
                self._handle_observations(state.url, step)
                self.trace.write(
                    "browser_state",
                    step=step,
                    url=state.url,
                    title=state.title,
                    selector_count=state.selector_count,
                    content=state.content,
                )

                # think
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._assemble_user_prompt(state)},
                ]
                think_started = time.time()
                llm_result = self.llm.invoke(messages)
                think_duration = round(time.time() - think_started, 3)

                for key in self._usage:
                    self._usage[key] += llm_result.usage.get(key, 0)
                self.trace.write(
                    "llm_output",
                    step=step,
                    model=llm_result.model,
                    duration=think_duration,
                    usage=llm_result.usage,
                    evaluation_previous_goal=llm_result.evaluation_previous_goal,
                    memory=llm_result.memory,
                    next_goal=llm_result.next_goal,
                    action=self._scrub_action(llm_result.action),
                )
                self._log_reflection(llm_result)

                # act
                action_name = next(iter(llm_result.action))
                action_input = llm_result.action[action_name]

                if action_name == "done":
                    success = bool(action_input.get("success", True))
                    data = action_input.get("text") or "no text provided"
                    self.history.append(self._step_event(step, llm_result, "Task completed"))
                    result = self._finish(success, data, step + 1)
                    break

                act_started = time.time()
                try:
                    output = self._execute_action(action_name, action_input)
                except tools.ToolError as error:
                    output = f"Error: {error}"
                act_duration = round(time.time() - act_started, 3)

                self.trace.write(
                    "action_result",
                    step=step,
                    action=action_name,
                    input=self._scrub_action(llm_result.action)[action_name],
                    output=output,
                    duration=act_duration,
                )
                self.history.append(self._step_event(step, llm_result, output))
                if self.verbose:
                    print(f"  -> {output}")

            except Exception as error:  # noqa: BLE001 - mirror upstream catch-all
                message = f"Task failed: {error}"
                self.history.append({"type": "error", "message": message})
                self.trace.write("error", step=step, message=message)
                result = self._finish(False, message, step + 1)
                break

            step += 1
            if step >= self.config.max_steps:
                message = "Step count exceeded maximum limit"
                self.history.append({"type": "error", "message": message})
                self.trace.write("error", step=step, message=message)
                result = self._finish(False, message, step)
                break

        return result

    def _finish(self, success: bool, data: str, steps: int) -> ExecutionResult:
        self.trace.write(
            "task_end", success=success, data=data, steps=steps, usage=self._usage
        )
        return ExecutionResult(
            success=success,
            data=data,
            steps=steps,
            usage=dict(self._usage),
            trace_path=str(self.trace.path),
        )

    # -- observe ----------------------------------------------------------

    def _handle_observations(self, url: str, step: int) -> None:
        if self._total_wait_time >= 3:
            self._observations.append(
                f"You have waited {self._total_wait_time:.0f} seconds accumulatively. "
                "DO NOT wait any longer unless you have a good reason."
            )

        if url != self._last_url:
            self._observations.append(f"Page navigated to -> {url}")
            self._last_url = url
            time.sleep(0.5)  # let the page stabilize

        remaining = self.config.max_steps - step
        if remaining == 5:
            self._observations.append(
                f"Warning: Only {remaining} steps remaining. "
                "Consider wrapping up or calling done with partial results."
            )
        elif remaining == 2:
            self._observations.append(
                f"Critical: Only {remaining} steps left! "
                "You must finish the task or call done immediately."
            )

        for content in self._observations:
            self.history.append({"type": "observation", "content": content})
            self.trace.write("observation", step=step, content=content)
        self._observations = []

    # -- think ------------------------------------------------------------

    def _assemble_user_prompt(self, state: Any) -> str:
        step_count = sum(1 for e in self.history if e["type"] == "step")

        prompt = "<agent_state>\n<user_request>\n"
        prompt += f"{self.task}\n"
        prompt += "</user_request>\n<step_info>\n"
        prompt += f"Step {step_count + 1} of {self.config.max_steps} max possible steps\n"
        prompt += "</step_info>\n</agent_state>\n\n"

        prompt += "<agent_history>\n"
        step_index = 0
        for event in self.history:
            if event["type"] == "step":
                step_index += 1
                prompt += f"<step_{step_index}>\n"
                prompt += f"Evaluation of Previous Step: {event['reflection']['evaluation_previous_goal']}\n"
                prompt += f"Memory: {event['reflection']['memory']}\n"
                prompt += f"Next Goal: {event['reflection']['next_goal']}\n"
                prompt += f"Action Results: {event['action']['output']}\n"
                prompt += f"</step_{step_index}>\n"
            elif event["type"] == "observation":
                prompt += f"<sys>{event['content']}</sys>\n"
            # error events stay out of the LLM context on purpose
        prompt += "</agent_history>\n\n"

        prompt += "<browser_state>\n"
        prompt += state.render() + "\n"
        prompt += "</browser_state>\n\n"

        return prompt

    def _step_event(self, step: int, llm_result: LLMResult, output: str) -> dict[str, Any]:
        action_name = next(iter(llm_result.action))
        return {
            "type": "step",
            "step": step,
            "reflection": {
                "evaluation_previous_goal": llm_result.evaluation_previous_goal,
                "memory": llm_result.memory,
                "next_goal": llm_result.next_goal,
            },
            "action": {
                "name": action_name,
                "input": llm_result.action[action_name],
                "output": output,
            },
        }

    def _log_reflection(self, llm_result: LLMResult) -> None:
        if not self.verbose:
            return
        for label, value in (
            ("eval", llm_result.evaluation_previous_goal),
            ("memory", llm_result.memory),
            ("goal", llm_result.next_goal),
        ):
            if value:
                print(f"  {label}: {value}")
        print(f"  action: {llm_result.action}")

    # -- act --------------------------------------------------------------

    def _execute_action(self, name: str, args: dict[str, Any]) -> str:
        page = self.browser.page
        assert page is not None, "Browser not started"

        if name == "wait":
            seconds = min(max(float(args.get("seconds", 1)), 0), 10)
            time.sleep(seconds)
            self._total_wait_time += seconds
            return f"Waited for {seconds:g} seconds."
        self._total_wait_time = 0.0

        if name == "click_element_by_index":
            tools.click_element_by_index(page, args["index"])
            return f"Clicked element {args['index']}."
        if name == "input_text":
            tools.input_text(page, args["index"], args["text"])
            shown = SCRUBBED if self._is_password_input(args["index"]) else args["text"]
            return f"Typed \"{shown}\" into element {args['index']}."
        if name == "select_dropdown_option":
            tools.select_dropdown_option(page, args["index"], args["text"])
            return f"Selected option \"{args['text']}\" in element {args['index']}."
        if name == "scroll":
            tools.scroll(
                page,
                down=args.get("down", True),
                num_pages=args.get("num_pages", 1.0),
                pixels=args.get("pixels"),
                index=args.get("index"),
            )
            return "Scrolled " + ("down." if args.get("down", True) else "up.")
        if name == "scroll_horizontally":
            tools.scroll_horizontally(
                page,
                right=args.get("right", True),
                pixels=args.get("pixels"),
                index=args.get("index"),
            )
            return "Scrolled horizontally."

        raise tools.ToolError(f"Unknown action: {name}")

    def _is_password_input(self, index: int) -> bool:
        page = self.browser.page
        assert page is not None
        try:
            return bool(
                page.evaluate(
                    "(i) => ((window.__hermd_selector_map || {})[i] || {}).type === 'password'",
                    index,
                )
            )
        except Exception:
            return False

    def _scrub_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of the action safe for the trace (passwords scrubbed)."""
        name = next(iter(action))
        if name != "input_text":
            return action
        args = action[name]
        if isinstance(args, dict) and self._is_password_input(args.get("index", -1)):
            return {name: dict(args, text=SCRUBBED)}
        return action
