"""Structured logging configuration using structlog."""

import logging

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging to stdout.

    This is the single source of truth for log format across the application.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_MASKED = "***"


def mask_email(email: str | None) -> str:
    """Return a deterministic, non-reversible form of an email address for log output.

    ``alice@school.edu`` -> ``a***@school.edu``. Missing, empty or malformed input
    (non-string, no ``@``, empty local part or domain) becomes ``***``. Never raises.
    """
    # A log helper must never break the request it is logging for, so anything that is not a
    # non-empty str (bytes, an enum, an ORM/Pydantic proxy) is masked instead of raising.
    if not isinstance(email, str) or not email or "@" not in email:
        return _MASKED
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return _MASKED
    return f"{local[0]}{_MASKED}@{domain}"
