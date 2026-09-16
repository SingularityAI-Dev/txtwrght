"""Loader for the JavaScript payloads injected into the page.

Every payload lives in a `.js` file beside this module rather than in a Python
string constant. That is not tidiness: a Chrome MV3 extension may not evaluate
source text it received over a wire, so anything the planned extension driver
has to run must already exist as a file a content script can load. One copy,
read by whichever driver is in play, is what keeps the two from drifting.

The payloads are self-installing: evaluating one assigns a registry onto
`window`, and Python then calls into that registry by name. Assignment is
idempotent and cheap, so callers re-install rather than tracking whether a
navigation wiped the previous document.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any, Protocol

EXTRACTOR = "extractor.js"
ACTIONS = "actions.js"
SETTLE = "settle.js"


class _Evaluates(Protocol):
    """The one thing a loader needs from a page, kept driver-agnostic."""

    def evaluate(self, expression: str, arg: Any = None) -> Any: ...


@lru_cache(maxsize=None)
def source(name: str) -> str:
    """The text of a payload. Read once; these files never change at runtime."""
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


def install(page: _Evaluates, name: str) -> None:
    """Install a payload's registry into the page's main frame."""
    page.evaluate(source(name))
