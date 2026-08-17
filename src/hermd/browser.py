"""Playwright lifecycle and DOM snapshot production.

Hardening (Phase 2) lives here rather than in the tools: popups and new tabs are
adopted as the active page, JavaScript dialogs are auto-handled so they can never
block the driver, and `settle()` gives navigation a bounded chance to finish
after an action.
"""

from __future__ import annotations

from importlib import resources

from playwright.sync_api import Browser as PlaywrightBrowser
from playwright.sync_api import BrowserContext, Dialog, Page, Playwright, sync_playwright

from hermd.config import Config
from hermd.dom.serializer import flat_tree_to_string
from hermd.dom.state import BrowserState
from hermd.logging import get_logger

_EXTRACTOR_JS = resources.files("hermd.dom").joinpath("extractor.js").read_text()

log = get_logger(__name__)

_DOM_QUIET_JS = """
(cfg) => new Promise((resolve) => {
  let last = performance.now();
  const started = last;
  const observer = new MutationObserver(() => { last = performance.now(); });
  observer.observe(document.documentElement, {
    subtree: true, childList: true, attributes: true, characterData: true,
  });
  const tick = () => {
    const now = performance.now();
    if (now - last >= cfg.quietMs || now - started >= cfg.capMs) {
      observer.disconnect();
      resolve(Math.round(now - started));
    } else {
      setTimeout(tick, 25);
    }
  };
  setTimeout(tick, 25);
})
"""


class Browser:
    def __init__(self, config: Config | None = None, playwright: Playwright | None = None):
        self.config = config or Config.from_env()
        # A borrowed driver is never stopped by us: one thread can only host one
        # sync Playwright instance, so callers running several browsers share it.
        self._playwright: Playwright | None = playwright
        self._owns_playwright = playwright is None
        self._browser: PlaywrightBrowser | None = None
        self._context: BrowserContext | None = None
        self._pages: list[Page] = []
        self.page: Page | None = None
        self.events: list[str] = []  # popup/dialog notes drained by the agent

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        self._context = self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            }
        )
        self._context.on("page", self._on_new_page)
        self.adopt(self._context.new_page())

    def attach(self, context: BrowserContext, page: Page) -> None:
        """Bind to a context/page owned by someone else (CDP session reuse)."""
        self._context = context
        context.on("page", self._on_new_page)
        self.adopt(page)

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None and self._owns_playwright:
            self._playwright.stop()
            self._playwright = None
        self._pages = []
        self.page = None
        self._context = None

    def __enter__(self) -> "Browser":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- page/tab management ----------------------------------------------

    def adopt(self, page: Page) -> None:
        """Track a page, auto-handle its dialogs, make it the active page."""
        if page not in self._pages:
            self._pages.append(page)
            page.on("dialog", self._on_dialog)
            page.on("close", self._on_page_closed)
        self.page = page

    def _on_new_page(self, page: Page) -> None:
        self.adopt(page)
        note = f"A new tab opened and is now the active tab -> {page.url or 'about:blank'}"
        self.events.append(note)
        log.info("popup_adopted", url=page.url)

    def _on_page_closed(self, page: Page) -> None:
        if page in self._pages:
            self._pages.remove(page)
        if self.page is page:
            self.page = self._pages[-1] if self._pages else None
            if self.page is not None:
                self.events.append(
                    f"The active tab closed; back on -> {self.page.url}"
                )

    def _on_dialog(self, dialog: Dialog) -> None:
        """Never let a modal dialog block the driver (see AGENTS.md gotcha)."""
        kind, message = dialog.type, dialog.message
        try:
            if self.config.dialog_policy == "accept":
                dialog.accept()
                action = "accepted"
            else:
                dialog.dismiss()
                action = "dismissed"
        except Exception as error:  # dialog already handled by the page
            log.warning("dialog_handling_failed", error=str(error))
            return
        self.events.append(f'A {kind} dialog said "{message}" and was auto-{action}.')
        log.info("dialog_handled", type=kind, action=action)

    def drain_events(self) -> list[str]:
        events, self.events = self.events, []
        return events

    # -- navigation --------------------------------------------------------

    def goto(self, url: str) -> None:
        assert self.page is not None, "Browser not started"
        self.page.goto(url, wait_until="domcontentloaded")
        self.settle()

    def settle(self) -> None:
        """Give navigation, popups and in-flight requests a bounded chance to finish.

        Called after every action. The short grace wait exists to pump the
        Playwright event channel: a `target=_blank` click or `window.open` only
        surfaces as a "page" event once the driver is given a moment, and the
        popup must be adopted before we decide which page to settle. Busy pages
        never reach networkidle, so every wait here is best-effort by design.
        """
        page = self.page
        if page is None or page.is_closed():
            return
        try:
            page.wait_for_timeout(self.config.popup_grace_ms)
        except Exception:
            pass

        page = self.page  # a popup may have taken over during the grace wait
        if page is None or page.is_closed():
            return
        timeout = self.config.settle_timeout_ms
        for state in ("domcontentloaded", "networkidle"):
            try:
                page.wait_for_load_state(state, timeout=timeout)
            except Exception:
                break  # still loading; the next snapshot sees whatever is there

        self._wait_for_dom_quiet()

    def _wait_for_dom_quiet(self) -> None:
        """Wait until the DOM stops changing, or the settle budget runs out.

        Client-rendered pages finish loading long before they finish rendering.
        networkidle says nothing about a framework still writing to the DOM, so
        we watch mutations directly and stop once they pause.
        """
        page = self.page
        quiet_ms = self.config.dom_quiet_ms
        if page is None or page.is_closed() or quiet_ms <= 0:
            return
        try:
            page.evaluate(
                _DOM_QUIET_JS, {"quietMs": quiet_ms, "capMs": self.config.settle_timeout_ms}
            )
        except Exception:
            pass  # navigated mid-wait, or the context went away: not fatal

    # -- observation -------------------------------------------------------

    def snapshot(self, viewport_expansion: int | None = None) -> BrowserState:
        """Extract the DOM, refresh the in-page selector map, serialize for the LLM.

        Element indices are only valid until the next snapshot or navigation.
        """
        assert self.page is not None, "Browser not started"
        ve = self.config.viewport_expansion if viewport_expansion is None else viewport_expansion

        self.page.evaluate(_EXTRACTOR_JS)  # idempotent installer
        raw = self.page.evaluate(
            "(cfg) => window.__hermd_extract(cfg)", {"viewportExpansion": ve}
        )
        selector_count = self.page.evaluate(
            "() => Object.keys(window.__hermd_selector_map).length"
        )

        return BrowserState(
            url=self.page.url,
            title=self.page.title(),
            content=flat_tree_to_string(raw["tree"]),
            page_info=raw["pageInfo"],
            tree=raw["tree"],
            viewport_expansion=ve,
            selector_count=selector_count,
        )
