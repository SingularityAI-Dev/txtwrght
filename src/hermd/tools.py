"""Actions against the current snapshot's selector map.

Every function takes a live Playwright page whose window.__hermd_selector_map was
populated by the most recent Browser.snapshot(). Indices are invalid after any
action that changes the DOM; snapshot again before the next action.
"""

from __future__ import annotations

from playwright.sync_api import ElementHandle, Page


class ToolError(Exception):
    pass


def _element_handle(page: Page, index: int) -> ElementHandle:
    handle = page.evaluate_handle(
        "(i) => (window.__hermd_selector_map || {})[i]", index
    )
    element = handle.as_element()
    if element is None:
        raise ToolError(
            f"No element with index {index} in the current snapshot. "
            "Snapshot again to get fresh indices."
        )
    return element


def click_element_by_index(page: Page, index: int) -> None:
    element = _element_handle(page, index)
    try:
        element.click(timeout=2000)
    except Exception:
        # Overlay interception or off-screen geometry: dispatch in-page,
        # which is what page-agent itself does.
        element.evaluate("(el) => el.click()")


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
    if index is not None:
        element = _element_handle(page, index)
        element.evaluate(
            "(el, args) => { el.scrollBy(0, args.sign * (args.pixels ?? el.clientHeight * args.numPages)) }",
            {"sign": sign, "pixels": pixels, "numPages": num_pages},
        )
    else:
        page.evaluate(
            "(args) => { window.scrollBy(0, args.sign * (args.pixels ?? window.innerHeight * args.numPages)) }",
            {"sign": sign, "pixels": pixels, "numPages": num_pages},
        )


def scroll_horizontally(
    page: Page,
    right: bool = True,
    pixels: int | None = None,
    index: int | None = None,
) -> None:
    sign = 1 if right else -1
    if index is not None:
        element = _element_handle(page, index)
        element.evaluate(
            "(el, args) => { el.scrollBy(args.sign * (args.pixels ?? el.clientWidth / 2), 0) }",
            {"sign": sign, "pixels": pixels},
        )
    else:
        page.evaluate(
            "(args) => { window.scrollBy(args.sign * (args.pixels ?? window.innerWidth / 2), 0) }",
            {"sign": sign, "pixels": pixels},
        )
