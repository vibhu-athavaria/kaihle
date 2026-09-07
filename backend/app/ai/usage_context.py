"""Attribute LLM calls to the code path that issued them.

`router.TASK_MODEL_MAP` names the prompt family, not the caller, and only `question_quality`
has a single call site. `question_generation` is issued by both `ai/quiz_generator.py` and
`scripts/generate_gap_questions.py`; `lo_matching` by both `lo_review_service.py` and
`scripts/map_questions_to_lo.py`; `concept_guide` and `lesson_plan` by real services and by
`routes/smoke_tests.py`. Grouping spend by task alone therefore blends interactive student
traffic with offline batch runs, and counts smoke-test spend as production.

Attribution rides on structlog contextvars, which the project already uses for this shape of
problem: `core/logging.py` has `merge_contextvars` in the processor chain and
`core/middleware.py` binds `request_id` the same way.

WHY A CONTEXT MANAGER AND NOT A PARAMETER
-----------------------------------------
Adding `component=` to `router.complete()` would have to be threaded through every
intermediate function between an entry point and the call, and every missed site would record
NULL silently — producing a report that looks complete and is not. Bound once at the entry
point, everything beneath it is covered without touching the call sites at all.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, get_contextvars, unbind_contextvars

logger = structlog.get_logger()

COMPONENT_KEY = "llm_component"
RUN_ID_KEY = "llm_run_id"
SCHOOL_ID_KEY = "school_id"


@contextmanager
def llm_component(name: str, run_id: str | None = None) -> Iterator[None]:
    """Attribute every LLM call made inside this block to `name`.

    Args:
        name: Caller identity. Conventionally prefixed by entry-point kind —
            "api:<route>", "celery:<task>", "script:<name>" — so a report can separate
            interactive from batch spend without a lookup table.
        run_id: Groups one batch invocation. Lets a whole remap or generation run be costed
            as a single number rather than inferred from a time range.

    Restores whatever was bound before, including on exception. A leaked contextvar would
    misattribute every subsequent call in the same worker process — and because the value
    would still look plausible, the resulting report would be wrong without appearing wrong.
    """
    previous: dict[str, Any] = get_contextvars()
    had_component = COMPONENT_KEY in previous
    had_run_id = RUN_ID_KEY in previous
    prior_component = previous.get(COMPONENT_KEY)
    prior_run_id = previous.get(RUN_ID_KEY)

    bindings: dict[str, Any] = {COMPONENT_KEY: name}
    if run_id is not None:
        bindings[RUN_ID_KEY] = run_id
    bind_contextvars(**bindings)

    try:
        yield
    finally:
        restore: dict[str, Any] = {}
        drop: list[str] = []

        if had_component:
            restore[COMPONENT_KEY] = prior_component
        else:
            drop.append(COMPONENT_KEY)

        if run_id is not None:
            if had_run_id:
                restore[RUN_ID_KEY] = prior_run_id
            else:
                drop.append(RUN_ID_KEY)

        if restore:
            bind_contextvars(**restore)
        if drop:
            unbind_contextvars(*drop)


def current_component() -> str | None:
    """Component bound for the current context, or None outside any block."""
    value = get_contextvars().get(COMPONENT_KEY)
    return str(value) if value is not None else None


def current_run_id() -> str | None:
    """Run id bound for the current context, or None."""
    value = get_contextvars().get(RUN_ID_KEY)
    return str(value) if value is not None else None


def current_school_id() -> uuid.UUID | None:
    """School the current request belongs to, or None for platform-level work.

    Bound by RequestLoggingMiddleware from the JWT before the request is handled, so an LLM
    call made while serving a student is attributable to their school. Batch scripts and
    curriculum-scope Celery work bind nothing, which is what makes NULL mean "platform-level"
    rather than "we forgot".

    Returns None on an unparseable value rather than raising: this is read on the telemetry
    path, and a malformed claim in a token must not fail an LLM call.
    """
    value = get_contextvars().get(SCHOOL_ID_KEY)
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        logger.warning("llm_usage_school_id_unparseable", value=str(value)[:64])
        return None


def current_correlation_id() -> str | None:
    """Correlation id for the current request or job.

    `core/middleware.py` binds `request_id` per HTTP request. Celery tasks and scripts bind
    nothing today, so this is None there — which is why `run_id` exists for batch work.
    """
    value = get_contextvars().get("request_id")
    return str(value) if value is not None else None
