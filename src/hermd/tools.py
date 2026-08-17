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


_DESCRIBE_JS = """
(el) => {
  const attr = (n) => el.getAttribute(n) || undefined;
  const cssPath = (node) => {
    const parts = [];
    while (node && node.nodeType === 1 && parts.length < 8) {
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (!parent) { parts.unshift(tag); break; }
      const sameTag = [...parent.children].filter((c) => c.tagName === node.tagName);
      parts.unshift(sameTag.length > 1
        ? tag + ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')'
        : tag);
      node = parent;
    }
    return parts.join(' > ');
  };
  return {
    tag: el.tagName.toLowerCase(),
    id: el.id || undefined,
    name: attr('name'),
    type: attr('type'),
    role: attr('role'),
    placeholder: attr('placeholder'),
    aria_label: attr('aria-label'),
    href: attr('href'),
    value_attr: attr('value'),
    text: (el.innerText || el.textContent || '').trim().slice(0, 80) || undefined,
    css: cssPath(el),
    frame_url: el.ownerDocument?.defaultView !== window
      ? el.ownerDocument?.location?.href
      : undefined,
  };
}
"""


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
        described = element.evaluate(_DESCRIBE_JS)
    except Exception:
        return {}
    return {k: v for k, v in described.items() if v is not None}


_WATCH_CLICK = """
(el) => {
  const doc = el.ownerDocument;
  doc.__hermdClickSeen = false;
  doc.addEventListener('click', () => { doc.__hermdClickSeen = true; },
    { capture: true, once: true });
}
"""


def click_element_by_index(page: Page, index: int) -> None:
    element = _element_handle(page, index)
    try:
        element.evaluate(_WATCH_CLICK)
    except Exception:
        pass

    try:
        element.click(timeout=2000)
    except Exception:
        # Overlay interception or off-screen geometry: dispatch in-page,
        # which is what page-agent itself does.
        element.evaluate("(el) => el.click()")
        return

    # A reported click is not a delivered click. Over connect_over_cdp (which is
    # how session commands attach) Playwright can return success while the
    # browser drops the synthesized event, leaving the page untouched and the
    # driver convinced it acted.
    try:
        delivered = element.evaluate("(el) => el.ownerDocument.__hermdClickSeen === true")
    except Exception:
        return  # the context died with the click: it navigated, so it landed
    if not delivered:
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
