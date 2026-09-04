"""Persistent browser sessions for per-step driving (Phase 3).

`txtwrght run` keeps the browser inside one Python process. A driving agent like
Claude Code is not one process: it calls the CLI once per step. So the browser
cannot be owned by any single command.

Chromium is therefore launched detached, with a remote debugging port, and every
command reconnects to it over CDP, does one thing, and disconnects. The browser
outlives the CLI process; `txtwrght session end` is what kills it.

Active tab rule: whichever tab the last command left you on, tracked by CDP
target id. A popup or a `target=_blank` tab takes over automatically, since that
is where the click sent you. `session tabs` and `session switch` exist for when
that is not what you want.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from txtwrght.browser import Browser
from txtwrght.config import Config
from txtwrght.logging import get_logger
from txtwrght.trace import Trace, scrub_args

log = get_logger(__name__)

SESSION_DIR = Path(os.getenv("TXTWRGHT_SESSION_DIR", ".txtwrght"))
SESSION_FILE = SESSION_DIR / "session.json"

# One thread can host one sync Playwright driver. The CLI is a fresh process per
# command so it always starts its own; an embedder already holding a driver
# (or a test suite) lends it here instead.
_lent_driver: Any = None


def use_driver(driver: Any) -> None:
    """Lend an existing Playwright driver to every later connect()."""
    global _lent_driver
    _lent_driver = driver


class SessionError(Exception):
    pass


# -- session file ---------------------------------------------------------


def _read_session() -> dict[str, Any]:
    if not SESSION_FILE.exists():
        raise SessionError(
            "No active session. Start one with: txtwrght session start --url <url>"
        )
    return json.loads(SESSION_FILE.read_text())


def _write_session(data: dict[str, Any]) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, indent=2))


def _bump_step(data: dict[str, Any]) -> int:
    data["step"] = data.get("step", 0) + 1
    _write_session(data)
    return data["step"]


# -- chromium process -----------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _chromium_executable() -> str:
    # TXTWRGHT_CHROMIUM avoids spinning up a second Playwright driver just to ask
    # where Chromium lives, which a thread already hosting one cannot do.
    override = os.getenv("TXTWRGHT_CHROMIUM", "").strip()
    if override:
        return override
    with sync_playwright() as p:
        return p.chromium.executable_path


def _wait_for_cdp(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.15)
    raise SessionError(f"Chromium did not open a debugging port on {port} in {timeout:g}s")


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# -- tab identity ---------------------------------------------------------
#
# Chromium hands its target list back newest-first on reconnect, and that order
# is not a contract. Positional tab tracking therefore breaks the moment a
# command exits. CDP target ids survive both reconnects and navigation, so tabs
# are identified by target id and ordered by when this session first saw them.


def _target_id(context: Any, page: Any) -> str:
    cdp = context.new_cdp_session(page)
    try:
        return cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
    finally:
        cdp.detach()


def _ordered_tabs(context: Any, pages: list[Any], session: dict[str, Any]) -> list[tuple[str, Any]]:
    """[(target_id, page)] in discovery order, session file updated to match."""
    by_id = {}
    for page in reversed(pages):  # reversed == oldest first, best guess for new ones
        try:
            by_id[_target_id(context, page)] = page
        except Exception:  # a tab that died mid-inspection
            continue

    known: list[str] = [t for t in session.get("known_targets", []) if t in by_id]
    known += [t for t in by_id if t not in known]
    if known != session.get("known_targets"):
        session["known_targets"] = known
        _write_session(session)

    return [(target, by_id[target]) for target in known]


def _active_page(ordered: list[tuple[str, Any]], session: dict[str, Any]) -> Any:
    wanted = session.get("tab_target")
    for target, page in ordered:
        if target == wanted:
            return page
    return ordered[-1][1]  # newest tab this session knows about


# -- connection -----------------------------------------------------------


@dataclass
class Connection:
    browser: Browser
    session: dict[str, Any]
    trace: Trace
    owns_driver: bool = True
    ordered: list[tuple[str, Any]] = field(default_factory=list)

    def remember_active_tab(self) -> None:
        """Persist which tab the next command should attach to.

        A click can hand the active tab to a popup mid-command; without this the
        next command would attach to the tab we already left.
        """
        page = self.browser.page
        context = self.browser._context
        if page is None or context is None or page.is_closed():
            return
        try:
            target = _target_id(context, page)
        except Exception:
            return
        if target != self.session.get("tab_target"):
            self.session["tab_target"] = target
            if target not in self.session.get("known_targets", []):
                self.session.setdefault("known_targets", []).append(target)
            _write_session(self.session)

    def close(self) -> None:
        self.trace.close()
        # Only the driver is torn down, and only if we started it. The Chromium
        # process is never ours to close: it has to outlive this command.
        playwright = self.browser._playwright
        self.browser.page = None
        self.browser._context = None
        if playwright is not None and self.owns_driver:
            playwright.stop()


def connect() -> Connection:
    """Reconnect to the running session's browser over CDP."""
    session = _read_session()
    if not _process_alive(session["pid"]):
        raise SessionError(
            "The session's browser is gone. Clean up with: txtwrght session end"
        )

    config = Config.from_env()
    owns_driver = _lent_driver is None
    playwright = sync_playwright().start() if owns_driver else _lent_driver
    try:
        cdp = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{session['port']}")
        context = cdp.contexts[0]
    except Exception as error:
        if owns_driver:
            playwright.stop()
        raise SessionError(f"Could not attach to the session browser: {error}") from error

    open_pages = [p for p in context.pages if not p.is_closed()]
    if not open_pages:
        if owns_driver:
            playwright.stop()
        raise SessionError("The session browser has no open tab left.")

    ordered = _ordered_tabs(context, open_pages, session)
    page = _active_page(ordered, session)

    browser = Browser(config, playwright=playwright)
    browser._browser = cdp
    browser.attach(context, page)

    trace = Trace(run_id=session["run_id"])
    return Connection(
        browser=browser,
        session=session,
        trace=trace,
        owns_driver=owns_driver,
        ordered=ordered,
    )


# -- commands -------------------------------------------------------------


def start(url: str, headless: bool = True) -> dict[str, Any]:
    if SESSION_FILE.exists():
        existing = _read_session()
        if _process_alive(existing["pid"]):
            raise SessionError(
                f"A session is already running (pid {existing['pid']}). "
                "End it first: txtwrght session end"
            )

    config = Config.from_env()
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="txtwrght-profile-")
    args = [
        _chromium_executable(),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        f"--window-size={config.viewport_width},{config.viewport_height}",
    ]
    if headless:
        args.append("--headless=new")
    args.append("about:blank")

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # survives this CLI process
    )
    try:
        _wait_for_cdp(port)
    except SessionError:
        process.kill()
        shutil.rmtree(profile, ignore_errors=True)
        raise

    run_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-session"
    session = {
        "pid": process.pid,
        "port": port,
        "profile": profile,
        "run_id": run_id,
        "headless": headless,
        "started_at": time.time(),
        "step": 0,
        "known_targets": [],
        "tab_target": None,
    }
    _write_session(session)
    log.info("session_started", pid=process.pid, port=port)

    connection = connect()
    try:
        connection.trace.write("session_start", url=url, headless=headless)
        connection.browser.goto(url)
        state = _snapshot_and_trace(connection, step=0)
    finally:
        connection.close()

    return {"session": session, "state": state}


def snapshot() -> str:
    connection = connect()
    try:
        return _snapshot_and_trace(connection, step=connection.session.get("step", 0))
    finally:
        connection.close()


def act(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one action, then return the resulting page view.

    The snapshot after the action is the point: indices are only valid for the
    snapshot they came from, so every act hands back fresh ones.
    """
    from txtwrght import tools

    connection = connect()
    try:
        step = _bump_step(connection.session)
        browser = connection.browser
        page = browser.page
        index = args.get("index")

        element = (
            tools.describe_element(page, index) if isinstance(index, int) else {}
        )

        started = time.time()
        try:
            output = _dispatch(browser, action, args)
            browser.settle()
        except tools.ToolError as error:
            output = f"Error: {error}"
        duration = round(time.time() - started, 3)

        connection.trace.write(
            "action_result",
            step=step,
            action=action,
            input=scrub_args(args, element),
            element=element,
            output=output,
            duration=duration,
            driver="session",
        )
        connection.remember_active_tab()
        events = browser.drain_events()
        for note in events:
            connection.trace.write("observation", step=step, content=note)

        state = _snapshot_and_trace(connection, step=step)
        return {"output": output, "events": events, "state": state}
    finally:
        connection.close()


def _dispatch(browser: Browser, action: str, args: dict[str, Any]) -> str:
    from txtwrght import tools

    page = browser.page
    if action == "click":
        tools.click_element_by_index(page, args["index"])
        return f"Clicked element {args['index']}."
    if action == "input":
        tools.input_text(page, args["index"], args["text"])
        return f"Typed into element {args['index']}."
    if action == "select":
        tools.select_dropdown_option(page, args["index"], args["text"])
        return f"Selected \"{args['text']}\" in element {args['index']}."
    if action == "scroll":
        tools.scroll(
            page,
            down=args.get("down", True),
            num_pages=args.get("num_pages", 1.0),
            pixels=args.get("pixels"),
            index=args.get("index"),
        )
        return "Scrolled " + ("down." if args.get("down", True) else "up.")
    if action == "scroll_horizontally":
        tools.scroll_horizontally(
            page,
            right=args.get("right", True),
            pixels=args.get("pixels"),
            index=args.get("index"),
        )
        return "Scrolled horizontally."
    if action == "wait":
        seconds = min(max(float(args.get("seconds", 1)), 0), 30)
        page.wait_for_timeout(seconds * 1000)
        return f"Waited {seconds:g} second(s)."
    if action == "press":
        page.keyboard.press(args["key"])
        return f"Pressed {args['key']}."
    if action == "goto":
        browser.goto(args["url"])
        return f"Navigated to {args['url']}."
    raise SessionError(f"Unknown action: {action}")


def tabs() -> list[dict[str, Any]]:
    connection = connect()
    try:
        active = connection.browser.page
        return [
            {
                "index": i,
                "url": page.url,
                "title": page.title(),
                "active": page is active,
            }
            for i, (_, page) in enumerate(connection.ordered)
        ]
    finally:
        connection.close()


def switch(index: int) -> str:
    connection = connect()
    try:
        ordered = connection.ordered
        if not -len(ordered) <= index < len(ordered):
            raise SessionError(
                f"No tab {index}: the session has {len(ordered)} open tab(s)."
            )
        target, page = ordered[index]
        connection.session["tab_target"] = target
        _write_session(connection.session)
        return page.url
    finally:
        connection.close()


def end() -> dict[str, Any]:
    """Kill the browser, keep the trace."""
    session = _read_session()
    trace_path = Path("traces") / f"run-{session['run_id']}.jsonl"
    steps = session.get("step", 0)

    if trace_path.exists():
        with Trace(run_id=session["run_id"]) as trace:
            trace.write(
                "session_end",
                steps=steps,
                distill_candidate=steps >= Config.from_env().distill_threshold,
            )

    if _process_alive(session["pid"]):
        try:
            os.killpg(os.getpgid(session["pid"]), signal.SIGTERM)
        except OSError:
            try:
                os.kill(session["pid"], signal.SIGTERM)
            except OSError:
                pass
        for _ in range(20):
            if not _process_alive(session["pid"]):
                break
            time.sleep(0.1)

    shutil.rmtree(session.get("profile", ""), ignore_errors=True)
    SESSION_FILE.unlink(missing_ok=True)
    log.info("session_ended", pid=session["pid"])
    return {"steps": steps, "trace": str(trace_path)}


def status() -> dict[str, Any]:
    session = _read_session()
    return {
        **session,
        "alive": _process_alive(session["pid"]),
        "trace": str(Path("traces") / f"run-{session['run_id']}.jsonl"),
    }


# -- shared ---------------------------------------------------------------


def _snapshot_and_trace(connection: Connection, step: int) -> str:
    state = connection.browser.snapshot()
    connection.trace.write(
        "browser_state",
        step=step,
        url=state.url,
        title=state.title,
        selector_count=state.selector_count,
        content=state.content,
        driver="session",
    )
    return state.render()
