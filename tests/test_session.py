"""Phase 3: the per-step session CLI, where the caller is the loop.

These tests launch a real detached Chromium and reconnect to it over CDP once
per command, exactly as a driving agent would. The point being proven is that
the browser survives between commands and that each command sees the state the
previous one left behind.
"""

import json

import pytest

from txtwrght import session as sess


@pytest.fixture
def live_session(tmp_path, monkeypatch, playwright_driver, page_server):
    """An isolated session rooted in tmp_path, always torn down."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TXTWRGHT_CHROMIUM", playwright_driver.chromium.executable_path)
    # In the CLI every command is its own process and starts its own driver;
    # here the suite already owns one, so lend it.
    monkeypatch.setattr(sess, "_lent_driver", playwright_driver)

    started = sess.start(f"{page_server}/login.html", headless=True)
    yield started
    try:
        sess.end()
    except sess.SessionError:
        pass


def trace_records(tmp_path):
    (path,) = list((tmp_path / "traces").glob("*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


# -- lifecycle ------------------------------------------------------------


def test_start_returns_the_indexed_view(live_session):
    assert "Sign in" in live_session["state"]
    assert "[1]<input" in live_session["state"]


def test_browser_survives_between_commands(live_session):
    first = sess.snapshot()
    second = sess.snapshot()
    assert "Sign in" in first and "Sign in" in second
    assert sess.status()["alive"] is True


def test_state_carries_across_separate_commands(live_session):
    sess.act("input", {"index": 1, "text": "geez"})
    view = sess.snapshot()
    assert "geez" in view, "the value typed by the previous command must persist"


def test_act_returns_a_fresh_snapshot(live_session):
    result = sess.act("input", {"index": 1, "text": "geez"})
    assert result["output"] == "Typed into element 1."
    assert "Sign in" in result["state"]


def test_full_login_flow(live_session):
    sess.act("input", {"index": 1, "text": "geez"})
    sess.act("input", {"index": 3, "text": "hunter2"})
    sess.act("click", {"index": 4})
    # The fixture answers after a deliberate 400ms delay, longer than settle
    # will hold for. A driver that sees a stale page waits and looks again,
    # exactly as it would against a slow real app.
    result = sess.act("wait", {"seconds": 1})
    assert "welcome geez" in result["state"]


def test_end_kills_the_browser(live_session):
    info = sess.end()
    assert info["steps"] >= 0
    with pytest.raises(sess.SessionError):
        sess.snapshot()


def test_commands_without_a_session_are_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(sess.SessionError, match="No active session"):
        sess.snapshot()


def test_second_start_is_refused(live_session, page_server):
    with pytest.raises(sess.SessionError, match="already running"):
        sess.start(f"{page_server}/form.html")


# -- tabs -----------------------------------------------------------------


def test_popup_becomes_the_active_tab(live_session, page_server):
    sess.act("goto", {"url": f"{page_server}/popup.html"})
    result = sess.act("click", {"index": 0})  # the target=_blank link

    assert "Second tab" in result["state"]
    listed = sess.tabs()
    assert len(listed) == 2
    assert listed[-1]["active"] is True


def test_switch_back_to_the_first_tab(live_session, page_server):
    sess.act("goto", {"url": f"{page_server}/popup.html"})
    sess.act("click", {"index": 0})

    sess.switch(0)
    assert "popup.html" in sess.snapshot()
    assert sess.tabs()[0]["active"] is True

    sess.switch(-1)  # back to newest
    assert "Second tab" in sess.snapshot()


def test_switch_rejects_an_unknown_tab(live_session):
    with pytest.raises(sess.SessionError, match="No tab"):
        sess.switch(9)


# -- trace ----------------------------------------------------------------


def test_trace_records_actions_with_element_identity(live_session, tmp_path):
    sess.act("input", {"index": 1, "text": "geez"})
    actions = [r for r in trace_records(tmp_path) if r["type"] == "action_result"]

    assert actions[-1]["action"] == "input"
    assert actions[-1]["element"]["id"] == "user"
    assert actions[-1]["element"]["css"] == "#user"
    assert actions[-1]["driver"] == "session"


def test_passwords_never_reach_the_trace(live_session, tmp_path):
    sess.act("input", {"index": 3, "text": "hunter2"})
    raw = (next((tmp_path / "traces").glob("*.jsonl"))).read_text()

    assert "hunter2" not in raw
    assert "***scrubbed***" in raw


def test_typed_value_is_visible_in_the_next_snapshot(live_session):
    sess.act("input", {"index": 1, "text": "geez"})
    assert "value=geez" in sess.snapshot()


def test_password_value_is_masked_in_the_view(live_session):
    view = sess.act("input", {"index": 3, "text": "hunter2"})["state"]
    assert "hunter2" not in view
    assert "value=***" in view


def test_a_plain_link_click_actually_navigates(live_session, page_server):
    """Regression: over CDP a click can report success and never be delivered."""
    sess.act("goto", {"url": f"{page_server}/link.html"})
    result = sess.act("click", {"index": 0})

    assert "popup-child.html" in result["state"]
    assert "Second tab" in result["state"]
