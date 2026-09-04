"""Phase 5: a recorded run becomes a Playwright script that actually replays.

The strong test here is not that a file gets written. It is that a flow driven
through the session CLI, distilled to a script, and replayed with no agent and
no model still reaches the same end state.
"""

import json
import subprocess
import sys

import pytest

from txtwrght import distill
from txtwrght import session as sess


@pytest.fixture
def live_session(tmp_path, monkeypatch, playwright_driver, page_server):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TXTWRGHT_CHROMIUM", playwright_driver.chromium.executable_path)
    monkeypatch.setattr(sess, "_lent_driver", playwright_driver)
    sess.start(f"{page_server}/form.html", headless=True)
    yield
    try:
        sess.end()
    except sess.SessionError:
        pass


def trace_path(tmp_path):
    return next((tmp_path / "traces").glob("*.jsonl"))


# -- selectors ------------------------------------------------------------


def test_selector_prefers_id():
    assert distill.selector_for({"tag": "input", "id": "user", "name": "username"}) == "#user"


def test_selector_falls_back_through_identity():
    assert distill.selector_for({"tag": "input", "name": "email"}) == 'input[name="email"]'
    assert (
        distill.selector_for({"tag": "input", "placeholder": "Your name"})
        == 'input[placeholder="Your name"]'
    )
    assert (
        distill.selector_for({"tag": "button", "text": "Register"})
        == 'button:has-text("Register")'
    )
    assert distill.selector_for({"tag": "div", "css": "main > div:nth-of-type(2)"}) == (
        "main > div:nth-of-type(2)"
    )


def test_selector_without_identity_is_an_error():
    with pytest.raises(distill.DistillError, match="no recorded identity"):
        distill.selector_for({"tag": "span"})


# -- reading --------------------------------------------------------------


def test_empty_trace_is_refused(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    with pytest.raises(distill.DistillError, match="empty"):
        distill.load_run(path)


def test_trace_without_actions_is_refused(tmp_path):
    path = tmp_path / "noop.jsonl"
    path.write_text(json.dumps({"type": "browser_state", "url": "http://x/"}) + "\n")
    with pytest.raises(distill.DistillError, match="nothing to distill"):
        distill.load_run(path)


# -- secrets --------------------------------------------------------------


def test_scrubbed_values_become_env_lookups(tmp_path, live_session, page_server):
    sess.act("goto", {"url": f"{page_server}/login.html"})
    sess.act("input", {"index": 1, "text": "geez"})
    sess.act("input", {"index": 3, "text": "hunter2"})

    result = distill.distill(trace_path(tmp_path), out_dir=tmp_path / "distilled")
    source = (tmp_path / "distilled" / result["script"].split("/")[-1]).read_text()

    assert "hunter2" not in source
    assert "***scrubbed***" not in source
    assert 'os.environ["TXTWRGHT_SECRET_PASSWORD"]' in source
    assert result["secrets"] == ["TXTWRGHT_SECRET_PASSWORD"]


def test_verify_refuses_to_replay_a_script_needing_secrets(tmp_path, live_session, page_server):
    sess.act("goto", {"url": f"{page_server}/login.html"})
    sess.act("input", {"index": 3, "text": "hunter2"})

    result = distill.distill(
        trace_path(tmp_path), out_dir=tmp_path / "distilled", verify=True
    )
    assert result["verified"] is None
    assert "TXTWRGHT_SECRET_PASSWORD" in result["output"]


# -- the real proof -------------------------------------------------------


def test_distilled_script_replays_the_flow(tmp_path, live_session, page_server):
    """Drive a form by hand, distill, replay with no agent involved."""
    sess.act("input", {"index": 0, "text": "geez"})
    state = sess.snapshot()
    assert "geez" in state

    # find the submit button in the current view, act on it
    submit = next(
        int(line.strip().split("]")[0].lstrip("*[").lstrip("["))
        for line in state.splitlines()
        if "Register" in line and "[" in line
    )
    sess.act("click", {"index": submit})
    sess.end()

    result = distill.distill(
        trace_path(tmp_path), out_dir=tmp_path / "distilled", name="form_flow.py"
    )
    script = tmp_path / "distilled" / "form_flow.py"
    assert script.exists()

    source = script.read_text()
    assert "page.fill" in source and "page.click" in source
    assert result["secrets"] == []

    completed = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=180
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ok" in completed.stdout


def test_verify_flag_replays_and_reports(tmp_path, live_session):
    sess.act("input", {"index": 0, "text": "geez"})
    sess.end()

    result = distill.distill(
        trace_path(tmp_path), out_dir=tmp_path / "distilled", verify=True
    )
    assert result["verified"] is True, result["output"]


# -- candidate flag -------------------------------------------------------


def test_long_sessions_are_flagged_as_candidates(tmp_path, live_session):
    for _ in range(5):
        sess.act("wait", {"seconds": 0})
    sess.end()

    footer = [
        json.loads(line)
        for line in trace_path(tmp_path).read_text().splitlines()
        if '"session_end"' in line
    ][-1]
    assert footer["distill_candidate"] is True


def test_short_sessions_are_not_flagged(tmp_path, live_session):
    sess.act("wait", {"seconds": 0})
    sess.end()

    footer = [
        json.loads(line)
        for line in trace_path(tmp_path).read_text().splitlines()
        if '"session_end"' in line
    ][-1]
    assert footer["distill_candidate"] is False
