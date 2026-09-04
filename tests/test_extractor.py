"""Extractor + serializer against real pages through Playwright."""

import re


def indexed_lines(content: str) -> dict[int, str]:
    out = {}
    for line in content.splitlines():
        m = re.match(r"^\t*\*?\[(\d+)\]", line.strip())
        if m:
            out[int(m.group(1))] = line.strip()
    return out


def test_form_page_interactive_elements_all_indexed(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    lines = indexed_lines(state.content)

    joined = "\n".join(lines.values())
    assert "<input type=text" in joined
    assert "<input type=password" in joined
    assert "<select" in joined
    assert "<textarea" in joined
    assert "Register" in joined
    assert "Open menu" in joined
    assert "Example site" in joined
    # checkbox carries the checked workaround attribute
    assert "type=checkbox" in joined and "checked=false" in joined

    # indices are unique, contiguous from 0, and match the in-page selector map
    assert sorted(lines.keys()) == list(range(len(lines)))
    assert state.selector_count == len(lines)


def test_non_interactive_text_appears_plain(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    plain = [
        line for line in state.content.splitlines() if line.strip() and "[" not in line
    ]
    assert any("Registration" in line for line in plain)
    assert any("idle" in line for line in plain)


def test_first_snapshot_marks_all_new_then_settles(browser, fixture_url):
    browser.goto(fixture_url("form.html"))
    first = browser.snapshot()
    assert "*[" in first.content  # everything is new on first observation

    second = browser.snapshot()
    assert "*[" not in second.content  # nothing changed, nothing is new


def test_revealed_elements_marked_new(browser, fixture_url):
    from txtwrght import tools

    browser.goto(fixture_url("form.html"))
    state = browser.snapshot()
    toggle_index = next(
        i for i, line in indexed_lines(state.content).items() if "Open menu" in line
    )
    browser.snapshot()  # settle: nothing marked new after this
    tools.click_element_by_index(browser.page, toggle_index)
    after = browser.snapshot()

    new_lines = [
        line for line in after.content.splitlines() if line.strip().startswith("*[")
    ]
    assert any("Profile" in line for line in new_lines)
    assert any("Settings" in line for line in new_lines)


def test_shadow_dom_button_is_indexed(browser, fixture_url):
    browser.goto(fixture_url("shadow.html"))
    state = browser.snapshot()
    joined = "\n".join(indexed_lines(state.content).values())
    assert "Shadow button" in joined


def test_scrollable_container_flagged(browser, fixture_url):
    browser.goto(fixture_url("scroll.html"))
    state = browser.snapshot()
    assert "data-scrollable=" in state.content


def test_render_header_and_footer(browser, fixture_url):
    browser.goto(fixture_url("scroll.html"))
    rendered = browser.snapshot().render()
    assert rendered.startswith("Current Page: [Scroll Test](file://")
    assert "Page info: 1280x720px viewport" in rendered
    assert "Interactive elements from top layer of the current page (full page):" in rendered
    assert "[Start of page]" in rendered
    assert rendered.endswith("[End of page]")
