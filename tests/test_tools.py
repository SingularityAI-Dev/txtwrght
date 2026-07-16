"""Tools acting on fixtures through the selector map, asserted on DOM state."""

import re

from hermd import tools


def find_index(content: str, needle: str) -> int:
    for line in content.splitlines():
        if needle in line:
            m = re.match(r"^\t*\*?\[(\d+)\]", line.strip())
            if m:
                return int(m.group(1))
    raise AssertionError(f"{needle!r} not found in snapshot")


def test_input_text(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    idx = find_index(state.content, "Your username")
    tools.input_text(browser.page, idx, "geez")
    assert browser.page.input_value("#username") == "geez"


def test_click_checkbox(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    idx = find_index(state.content, "type=checkbox")
    tools.click_element_by_index(browser.page, idx)
    assert browser.page.is_checked("#terms")
    # next snapshot reflects it through the checked workaround attribute
    assert "checked=true" in browser.snapshot().content


def test_select_dropdown_option(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    idx = find_index(state.content, "<select")
    tools.select_dropdown_option(browser.page, idx, "South Africa")
    assert browser.page.input_value("#country") == "za"


def test_click_submit_updates_status(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    tools.input_text(browser.page, find_index(state.content, "Your username"), "geez")
    tools.click_element_by_index(browser.page, find_index(state.content, "Register"))
    assert browser.page.text_content("#status") == "submitted:geez"


def test_stale_index_raises(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    browser.snapshot()
    try:
        tools.click_element_by_index(browser.page, 999)
    except tools.ToolError as e:
        assert "999" in str(e)
    else:
        raise AssertionError("expected ToolError")


def test_window_scroll(browser, fixture_url):
    browser.goto(fixture_url("scroll.html"))
    browser.snapshot()
    before = browser.page.evaluate("window.scrollY")
    tools.scroll(browser.page, down=True, num_pages=1)
    after = browser.page.evaluate("window.scrollY")
    assert after > before

    tools.scroll(browser.page, down=False, num_pages=1)
    assert browser.page.evaluate("window.scrollY") < after


def test_container_scroll_by_index(browser, fixture_url):
    browser.goto(fixture_url("scroll.html"))
    state = browser.snapshot()
    idx = find_index(state.content, "data-scrollable=")
    tools.scroll(browser.page, down=True, num_pages=1, index=idx)
    assert browser.page.evaluate("document.getElementById('pane').scrollTop") > 0


def test_shadow_dom_click(browser, fixture_url):
    browser.goto(fixture_url("shadow.html"))
    state = browser.snapshot()
    idx = find_index(state.content, "Shadow button")
    tools.click_element_by_index(browser.page, idx)
    text = browser.page.evaluate(
        "document.querySelector('my-widget').shadowRoot.querySelector('p').textContent"
    )
    assert text == "shadow clicked"
