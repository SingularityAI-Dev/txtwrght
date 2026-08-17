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


if __name__ == "__main__":
    main()
