"""Phase 2 hardening: popups, dialogs, settle, same-origin iframes.

Every assertion here is about the browser layer surviving something that would
otherwise stall the agent loop: a new tab stealing focus, a modal dialog blocking
the driver, a slow page judged too early, content locked inside a frame.
"""

import pytest

from hermd import tools
from hermd.browser import Browser
from hermd.config import Config
from tests.test_tools import find_index


@pytest.fixture
def fresh_browser(playwright_driver):
    """Own browser per test: popups and dialogs mutate context-wide state."""
    b = Browser(Config(headless=True), playwright=playwright_driver)
    b.start()
    yield b
    b.stop()


# -- popups / new tabs ---------------------------------------------------


def test_target_blank_link_becomes_active_page(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/popup.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Open in new tab"))
    fresh_browser.settle()

    assert fresh_browser.page.url.endswith("popup-child.html")
    assert fresh_browser.page.text_content("#status") == "child page"
    assert any("new tab opened" in e for e in fresh_browser.events)


def test_window_open_becomes_active_page(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/popup.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "window.open"))
    fresh_browser.settle()

    assert fresh_browser.page.url.endswith("popup-child.html")
    # the new tab is snapshottable, indices come from it
    assert "Child button" in fresh_browser.snapshot().content


def test_closing_active_tab_falls_back_to_previous(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/popup.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Open in new tab"))
    fresh_browser.settle()
    opened = fresh_browser.page

    opened.close()
    assert fresh_browser.page is not opened
    assert fresh_browser.page.url.endswith("popup.html")


def test_drain_events_empties(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/popup.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Open in new tab"))
    fresh_browser.settle()

    assert fresh_browser.drain_events()
    assert fresh_browser.drain_events() == []


# -- dialogs --------------------------------------------------------------


def test_alert_does_not_block_the_driver(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/dialog.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Trigger alert"))
    fresh_browser.settle()

    # the click handler ran past the alert, so the driver was never stuck
    assert fresh_browser.page.text_content("#status") == "alert-returned"
    assert any("auto-dismissed" in e for e in fresh_browser.events)


def test_confirm_dismissed_by_default(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/dialog.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Trigger confirm"))
    fresh_browser.settle()

    assert fresh_browser.page.text_content("#status") == "cancelled"


def test_confirm_accepted_under_accept_policy(page_server, playwright_driver):
    b = Browser(Config(headless=True, dialog_policy="accept"), playwright=playwright_driver)
    b.start()
    try:
        b.goto(f"{page_server}/dialog.html")
        state = b.snapshot()
        tools.click_element_by_index(b.page, find_index(state.content, "Trigger confirm"))
        b.settle()
        assert b.page.text_content("#status") == "confirmed"
    finally:
        b.stop()


# -- settle ---------------------------------------------------------------


def test_settle_is_bounded_and_safe_on_closed_page(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/form.html")
    fresh_browser.page.close()
    fresh_browser.settle()  # must not raise


def test_settle_after_navigation_click(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/spa.html")
    state = fresh_browser.snapshot()
    idx = find_index(state.content, "About")
    tools.click_element_by_index(fresh_browser.page, idx)
    fresh_browser.settle()
    assert "About" in fresh_browser.snapshot().content


# -- same-origin iframes --------------------------------------------------


def test_iframe_content_is_indexed(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/iframe.html")
    content = fresh_browser.snapshot().content
    assert "Outer button" in content
    assert "Inner button" in content, "same-origin frame content must be indexed"


def test_iframe_element_is_clickable(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/iframe.html")
    state = fresh_browser.snapshot()
    tools.click_element_by_index(fresh_browser.page, find_index(state.content, "Inner button"))
    frame = fresh_browser.page.frame(name="") or fresh_browser.page.frames[1]
    assert frame.text_content("#inner-status") == "inner clicked"


def test_iframe_input_is_fillable(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/iframe.html")
    state = fresh_browser.snapshot()
    tools.input_text(
        fresh_browser.page, find_index(state.content, "Type inside the fram"), "geez"
    )
    assert fresh_browser.page.frames[1].input_value("#inner-input") == "geez"


# -- element description (Phase 5 fuel) -----------------------------------


def test_describe_element_captures_identity(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/login.html")
    state = fresh_browser.snapshot()
    described = tools.describe_element(
        fresh_browser.page, find_index(state.content, "Your username")
    )
    assert described["tag"] == "input"
    assert described["id"] == "user"
    assert described["name"] == "username"
    assert described["css"] == "#user"


def test_describe_element_unknown_index_is_empty(fresh_browser, page_server):
    fresh_browser.goto(f"{page_server}/login.html")
    fresh_browser.snapshot()
    assert tools.describe_element(fresh_browser.page, 999) == {}
