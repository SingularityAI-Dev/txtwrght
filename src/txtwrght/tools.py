"""Actions against the current snapshot's selector map.

Every function takes a live Playwright page whose window.__txtwrght_selector_map was
populated by the most recent Browser.snapshot(). Indices are invalid after any
action that changes the DOM; snapshot again before the next action.

The JavaScript half of each verb lives in `dom/actions.js`, installed here as
`window.__txtwrght_actions`; see `dom/js.py` for why it is a file rather than a
string constant. What is left in this module is the Playwright half: element
addressing, timeouts, and the fallback ladder each verb walks when the first
attempt does not land.
"""

from __future__ import annotations

from playwright.sync_api import ElementHandle, Page

from txtwrght.dom import js


class ToolError(Exception):
    pass


def _element_handle(page: Page, index: int) -> ElementHandle:
    js.install(page, js.ACTIONS)
    handle = page.evaluate_handle("(i) => window.__txtwrght_actions.lookup(i)", index)
    element = handle.as_element()
    if element is None:
        raise ToolError(
            f"No element with index {index} in the current snapshot. "
            "Snapshot again to get fresh indices."
        )
    return element


def describe_element(page: Page, index: int) -> dict:
    """Stable identity for the element at `index`, recorded in the trace.

    Indices die with the snapshot; these attributes are what Phase 5 distillation
    turns back into Playwright selectors long after the run.
    """
    try:
        element = _element_handle(page, index)
    except ToolError:
        return {}
    try:
        described = element.evaluate("(el) => window.__txtwrght_actions.describe(el)")
    except Exception:
        return {}
    return {k: v for k, v in described.items() if v is not None}


def click_element_by_index(page: Page, index: int) -> None:
    element = _element_handle(page, index)
    try:
        element.evaluate("(el) => window.__txtwrght_actions.watchClick(el)")
    except Exception:
        pass

    try:
        element.click(timeout=2000)
    except Exception:
        # Overlay interception or off-screen geometry: dispatch in-page,
        # which is what page-agent itself does.
        element.evaluate("(el) => window.__txtwrght_actions.click(el)")
        return

    # A reported click is not a delivered click. Over connect_over_cdp (which is
    # how session commands attach) Playwright can return success while the
    # browser drops the synthesized event, leaving the page untouched and the
    # driver convinced it acted.
    try:
        delivered = element.evaluate("(el) => window.__txtwrght_actions.clickSeen(el)")
    except Exception:
        return  # the context died with the click: it navigated, so it landed
    if not delivered:
        element.evaluate("(el) => window.__txtwrght_actions.click(el)")


def input_text(page: Page, index: int, text: str) -> None:
    element = _element_handle(page, index)
    try:
        element.fill(text)
    except Exception:
        element.click(timeout=2000)
        page.keyboard.type(text)


def select_dropdown_option(page: Page, index: int, text: str) -> None:
    element = _element_handle(page, index)
    element.select_option(label=text)


def scroll(
    page: Page,
    down: bool = True,
    num_pages: float = 1.0,
    pixels: int | None = None,
    index: int | None = None,
) -> None:
    """Scroll the window, or the scrollable container at `index`."""
    sign = 1 if down else -1
    args = {"sign": sign, "pixels": pixels, "numPages": num_pages}
    if index is not None:
        element = _element_handle(page, index)
        element.evaluate(
            "(el, args) => window.__txtwrght_actions.scrollElement(el, args)", args
        )
    else:
        js.install(page, js.ACTIONS)
        page.evaluate("(args) => window.__txtwrght_actions.scrollWindow(args)", args)


def scroll_horizontally(
    page: Page,
    right: bool = True,
    pixels: int | None = None,
    index: int | None = None,
) -> None:
    sign = 1 if right else -1
    args = {"sign": sign, "pixels": pixels}
    if index is not None:
        element = _element_handle(page, index)
        element.evaluate(
            "(el, args) => window.__txtwrght_actions.scrollElementHorizontally(el, args)",
            args,
        )
    else:
        js.install(page, js.ACTIONS)
        page.evaluate(
            "(args) => window.__txtwrght_actions.scrollWindowHorizontally(args)", args
        )
