import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from playwright.sync_api import sync_playwright

from txtwrght.browser import Browser
from txtwrght.config import Config

PAGES = Path(__file__).parent / "pages"


@pytest.fixture(scope="session")
def playwright_driver():
    """One sync Playwright driver per session; the thread cannot host two."""
    driver = sync_playwright().start()
    yield driver
    driver.stop()


@pytest.fixture(scope="session")
def browser(playwright_driver):
    b = Browser(Config(headless=True), playwright=playwright_driver)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def fixture_url():
    def _url(name: str) -> str:
        return (PAGES / name).resolve().as_uri()

    return _url


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep pytest output clean
        pass


@pytest.fixture(scope="session")
def page_server():
    """Serve tests/pages over http.

    file:// documents are opaque origins in Chromium, so same-origin iframe
    traversal only works over a real origin.
    """
    handler = functools.partial(_QuietHandler, directory=str(PAGES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
