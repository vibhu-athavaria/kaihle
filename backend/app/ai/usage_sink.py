"""Persist one row per LLM call.

THE INVARIANT: recording usage must never fail an LLM call. A student waiting on an
explanation does not get an error because a telemetry insert deadlocked. Everything here is
wrapped, and failures are logged and swallowed.

That is the one place a broad `except` is correct in this codebase. `.claude/rules/01` bans
*silent* swallowing, not structured handling — the failure is logged at WARNING with
`exc_info`, so it is visible without being fatal.

WHY NullPool
------------
`core/database.py` exposes a pooled factory for FastAPI (one long-lived event loop) and an
unpooled one for Celery (a fresh loop per task). The sink is called from FastAPI requests,
Celery tasks, AND standalone scripts, and cannot know which. Using the pooled factory from a
Celery task's loop would share asyncio primitives across event loops — precisely the bug
`CeleryAsyncSessionLocal` exists to avoid.

So the sink always takes the unpooled factory. The cost is one connection open/close per LLM
call, against a call that already took seconds over the network. That is not a tradeoff worth
agonising over.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from app.ai.usage_context import current_component, current_correlation_id, current_run_id
from app.core.config import settings
from app.core.database import CeleryAsyncSessionLocal
from app.models.llm_usage import LlmUsageEvent

logger = structlog.get_logger()


async def record_usage(
    task: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
    streamed: bool = False,
    succeeded: bool = True,
    error_type: str | None = None,
    error_detail: str | None = None,
    school_id: uuid.UUID | None = None,
    prompt_text: str | None = None,
    response_text: str | None = None,
) -> None:
    """Write one `llm_usage_events` row. Never raises.

    A no-op unless `LLM_USAGE_TRACKING_ENABLED` is set, so unit tests and offline scripts do
    not need a database to make an LLM call.

    Component, run id, and correlation id are read from structlog contextvars rather than
    passed in — see `usage_context.llm_component` for why threading them through every call
    site would guarantee gaps.

    `prompt_text`/`response_text` are stored raw, no truncation, no masking (explicit product
    decision 2026-09-09, for the LLM Logs admin viewer) — unlike `error_detail` below, which
    predates that decision and keeps its own 2000-char cap.
    """
    if not settings.llm_usage_tracking_enabled:
        return

    try:
        async with CeleryAsyncSessionLocal() as session:
            session.add(
                LlmUsageEvent(
                    id=uuid.uuid4(),
                    task=task,
                    model=model,
                    component=current_component(),
                    run_id=current_run_id(),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=max(0, latency_ms),
                    estimated_cost_usd=estimated_cost_usd,
                    streamed=streamed,
                    succeeded=succeeded,
                    error_type=error_type,
                    error_detail=error_detail[:2000] if error_detail else None,
                    correlation_id=current_correlation_id(),
                    school_id=school_id,
                    prompt_text=prompt_text,
                    response_text=response_text,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
    except Exception as exc:
        # Deliberately broad and deliberately not re-raised. See the module docstring:
        # telemetry must not be able to fail inference. Logged so a broken sink is visible.
        logger.warning(
            "llm_usage_record_failed",
            task=task,
            model=model,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )


def prompt_text_from_messages(messages: list[dict[str, Any]]) -> str:
    """Flatten an OpenAI-format message list into one string for the LLM Logs detail view.

    Multi-turn / system+user messages are joined with a role label so the full exchange is
    visible, not just the last turn.
    """
    return "\n\n".join(f"[{m.get('role', 'unknown')}] {m.get('content', '')}" for m in messages)


def usage_kwargs_from_response(response: Any) -> dict[str, int | None]:
    """Pull token counts off a provider response, tolerating absence.

    Providers vary in whether and where they report usage, and a missing field must yield
    None rather than an exception — the call already succeeded by the time this runs.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
