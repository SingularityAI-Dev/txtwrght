"""Playwright lifecycle and DOM snapshot production."""

from __future__ import annotations

from importlib import resources

from playwright.sync_api import Browser as PlaywrightBrowser
from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from hermd.config import Config
from hermd.dom.serializer import flat_tree_to_string
from hermd.dom.state import BrowserState

_EXTRACTOR_JS = resources.files("hermd.dom").joinpath("extractor.js").read_text()


class Browser:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self._playwright: Playwright | None = None
        self._browser: PlaywrightBrowser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        self._context = self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            }
        )
        self.page = self._context.new_page()

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self.page = None
        self._context = None

    def __enter__(self) -> "Browser":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def goto(self, url: str) -> None:
        assert self.page is not None, "Browser not started"
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass  # busy pages never go idle; domcontentloaded is enough

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
