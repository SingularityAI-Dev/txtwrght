"""hermd CLI."""

from __future__ import annotations

import click

from hermd.browser import Browser
from hermd.config import Config


@click.group()
def main() -> None:
    """hermd: CLI-first browser agent. Headless, text-only DOM, zero screenshots."""


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
        browser.goto(url)
        state = browser.snapshot(viewport_expansion)
        click.echo(state.render())


if __name__ == "__main__":
    main()
