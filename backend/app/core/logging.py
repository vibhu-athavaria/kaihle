"""Structured logging configuration using structlog.

Configures structlog to emit JSON lines to stdout with context variable
propagation. Call configure_logging() once at application startup before
any routes or middleware are registered.
"""

import logging

import structlog

from app.core.config import settings

# Map string log levels to stdlib numeric values used by structlog's
# make_filtering_bound_logger. This avoids relying on implicit name resolution.
_LOG_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(log_level: str | None = None) -> None:
    """Configure structlog for JSON output to stdout.

    Args:
        log_level: Minimum log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Falls back to settings.log_level when not provided.

    Raises:
        ValueError: If log_level is not a recognised level name.
    """
    level_name = (log_level or settings.log_level).upper()
    numeric_level = _LOG_LEVEL_MAP.get(level_name)
    if numeric_level is None:
        raise ValueError(f"Invalid log level: {level_name!r}. Must be one of {sorted(_LOG_LEVEL_MAP.keys())}")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
