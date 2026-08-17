"""structlog wiring.

Quiet by default: the CLI owns stdout, so logs go to stderr and only at WARNING
and above unless HERMD_LOG_LEVEL says otherwise (or --verbose bumps it to info).
"""

from __future__ import annotations

import logging
import os
import sys

import structlog

_configured = False

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure(level: str | None = None, json_logs: bool | None = None) -> None:
    """Configure structlog once per process. Safe to call repeatedly."""
    global _configured

    name = (level or os.getenv("HERMD_LOG_LEVEL", "warning")).lower()
    as_json = (
        json_logs
        if json_logs is not None
        else os.getenv("HERMD_LOG_JSON", "false").lower() == "true"
    )
    renderer = (
        structlog.processors.JSONRenderer()
        if as_json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _LEVELS.get(name, logging.WARNING)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    if not _configured:
        configure()
    return structlog.get_logger(name)
