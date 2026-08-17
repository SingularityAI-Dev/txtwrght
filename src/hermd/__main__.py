"""hermd CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from hermd.browser import Browser
from hermd.config import Config
from hermd.logging import configure as configure_logging


def resolve_url(url: str) -> str:
    """Accept plain filesystem paths for fixtures, not just URLs."""
    if "://" not in url and Path(url).exists():
        return Path(url).resolve().as_uri()
    return url


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"]),
    default=None,
    help="Structured logs to stderr. Default warning (HERMD_LOG_LEVEL).",
)
def main(log_level: str | None) -> None:
    """hermd: CLI-first browser agent. Headless, text-only DOM, zero screenshots."""
    configure_logging(log_level)


@main.command()
@click.argument("task")
@click.option("--url", required=True, help="Page to start on.")
@click.option("--max-steps", type=int, default=None, help="Override MAX_STEPS.")
@click.option("--verbose", is_flag=True, help="Stream reflection fields per step.")
def run(task: str, url: str, max_steps: int | None, verbose: bool) -> None:
    """Run an agent task against a page. Writes a JSONL trace to traces/."""
    from hermd.agent import Agent
    from hermd.llm import LLMClient, LLMError
    from hermd.trace import Trace

    if verbose:
        configure_logging("info")

    config = Config.from_env()
    if max_steps is not None:
        config.max_steps = max_steps

    url = resolve_url(url)

    try:
        llm = LLMClient(config.llm_endpoints)
    except LLMError as error:
        raise click.ClickException(str(error)) from error

    trace = Trace()
    with Browser(config) as browser:
        browser.goto(url)
        agent = Agent(task, browser, llm, config=config, trace=trace, verbose=verbose)
        result = agent.run()

    click.echo()
    click.echo(f"{'DONE' if result.success else 'FAILED'} after {result.steps} step(s)")
    click.echo(result.data)
    click.echo(f"tokens: {result.usage.get('total_tokens', 0)}  trace: {result.trace_path}")
    llm.close()
    trace.close()
    sys.exit(0 if result.success else 1)


@main.command()
@click.option("--url", required=True, help="Page to snapshot.")
@click.option(
    "--viewport-expansion",
    type=int,
    default=None,
    help="-1 = full page (default), 0 = viewport only, N = viewport + N pixels.",
)
def snapshot(url: str, viewport_expansion: int | None) -> None:
    """Print the indexed text view of a page and exit."""
    with Browser(Config.from_env()) as browser:
        browser.goto(resolve_url(url))
        state = browser.snapshot(viewport_expansion)
        click.echo(state.render())


@main.group()
def session() -> None:
    """Drive a page step by step, with the browser living between commands.

    This is the binding surface: the caller (Claude Code, a shell script, any
    agent) is the loop. Snapshot, pick one action, act, repeat.
    """


def _session_call(fn, *args, **kwargs):
    from hermd.session import SessionError

    try:
        return fn(*args, **kwargs)
    except SessionError as error:
        raise click.ClickException(str(error)) from error


@session.command("start")
@click.option("--url", required=True, help="Page to open.")
@click.option("--headed", is_flag=True, help="Show the browser window.")
def session_start(url: str, headed: bool) -> None:
    """Launch a browser that outlives this command, open URL, print the view."""
    from hermd import session as sess

    result = _session_call(sess.start, resolve_url(url), headless=not headed)
    click.echo(result["state"])


@session.command("snapshot")
def session_snapshot() -> None:
    """Print the current indexed text view. Indices are valid until you act."""
    from hermd import session as sess

    click.echo(_session_call(sess.snapshot))


@session.command("act", context_settings={"ignore_unknown_options": True})
@click.argument("action", type=click.Choice(
    ["click", "input", "select", "scroll", "scroll_horizontally", "press", "goto", "wait"]
))
@click.argument("target", required=False)
@click.argument("text", required=False)
@click.option("--index", type=int, default=None, help="Element index to scroll inside.")
@click.option("--up", "up", is_flag=True, help="Scroll up instead of down.")
@click.option("--left", "left", is_flag=True, help="Scroll left instead of right.")
@click.option("--pages", type=float, default=1.0, help="Scroll distance in pages.")
@click.option("--pixels", type=int, default=None, help="Scroll distance in pixels.")
@click.option("--quiet", is_flag=True, help="Print the result line only, no new snapshot.")
def session_act(
    action: str,
    target: str | None,
    text: str | None,
    index: int | None,
    up: bool,
    left: bool,
    pages: float,
    pixels: int | None,
    quiet: bool,
) -> None:
    """Perform one action, then print the resulting page view.

    \b
    hermd session act click 12
    hermd session act input 3 "geez"
    hermd session act select 7 "South Africa"
    hermd session act scroll --up --pages 0.5
    hermd session act press Enter
    hermd session act goto https://example.com
    hermd session act wait 2
    """
    from hermd import session as sess

    args: dict[str, object] = {}
    if action in ("click", "input", "select"):
        if target is None:
            raise click.ClickException(f"{action} needs an element index.")
        args["index"] = int(target)
        if action in ("input", "select"):
            if text is None:
                raise click.ClickException(f"{action} needs text.")
            args["text"] = text
    elif action == "press":
        if target is None:
            raise click.ClickException("press needs a key, for example Enter.")
        args["key"] = target
    elif action == "goto":
        if target is None:
            raise click.ClickException("goto needs a URL.")
        args["url"] = resolve_url(target)
    elif action == "wait":
        args["seconds"] = float(target) if target else 1.0
    elif action == "scroll":
        args.update(down=not up, num_pages=pages, pixels=pixels, index=index)
    elif action == "scroll_horizontally":
        args.update(right=not left, pixels=pixels, index=index)

    result = _session_call(sess.act, action, args)
    click.echo(result["output"])
    for note in result["events"]:
        click.echo(f"<sys>{note}</sys>")
    if not quiet:
        click.echo()
        click.echo(result["state"])


@session.command("tabs")
def session_tabs() -> None:
    """List open tabs in the order this session first saw them."""
    from hermd import session as sess

    for tab in _session_call(sess.tabs):
        marker = "*" if tab["active"] else " "
        click.echo(f"{marker} [{tab['index']}] {tab['title']} -- {tab['url']}")


@session.command("switch")
@click.argument("index", type=int)
def session_switch(index: int) -> None:
    """Make tab INDEX the active tab (-1 is the newest)."""
    from hermd import session as sess

    click.echo(f"Active tab -> {_session_call(sess.switch, index)}")


@session.command("status")
def session_status() -> None:
    """Show the running session: pid, port, steps taken, trace path."""
    from hermd import session as sess

    info = _session_call(sess.status)
    for key in ("pid", "port", "alive", "step", "headless", "trace"):
        click.echo(f"{key}: {info[key]}")


@session.command("end")
def session_end() -> None:
    """Kill the session browser and keep the trace."""
    from hermd import session as sess

    info = _session_call(sess.end)
    click.echo(f"Session ended after {info['steps']} action(s). Trace: {info['trace']}")


if __name__ == "__main__":
    main()
