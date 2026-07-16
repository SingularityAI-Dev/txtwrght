from pathlib import Path

import pytest

from hermd.browser import Browser
from hermd.config import Config

PAGES = Path(__file__).parent / "pages"


@pytest.fixture(scope="session")
def browser():
    b = Browser(Config(headless=True))
    b.start()
    yield b
    b.stop()


@pytest.fixture
def fixture_url():
    def _url(name: str) -> str:
        return (PAGES / name).resolve().as_uri()

    return _url
