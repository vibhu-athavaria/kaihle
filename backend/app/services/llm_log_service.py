"""Per-call LLM log listing and detail — the read side of `llm_usage_events` for the
Kaihle Admin "LLM Logs" page.

Deliberately separate from `llm_usage_service.py`: that module is aggregate reporting
(grouped totals, cost/token sums) shared with `scripts/llm_cost_report.py`. This module is
a flat, per-row viewer — one admin looking at one call at a time. They read the same
table but answer different questions, so they stay two modules rather than one growing an
unrelated second responsibility.

The list view excludes `prompt_text`/`response_text`: those can be arbitrarily long, and a
page of 50 calls has no reason to carry all of them over the wire when only one row's text
is ever shown at a time (see `get_llm_log` for the single-row detail fetch).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_LOG_PAGE_SIZE = 50


@dataclass
class LlmLogSummary:
    id: uuid.UUID
    created_at: datetime
    task: str
    model: str
    component: str | None
    run_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    estimated_cost_usd: Decimal | None
    succeeded: bool
    error_type: str | None


@dataclass
class LlmLogDetail(LlmLogSummary):
    prompt_text: str | None
    response_text: str | None
    error_detail: str | None
    correlation_id: str | None
    school_id: uuid.UUID | None
    streamed: bool


async def list_llm_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = DEFAULT_LOG_PAGE_SIZE,
) -> tuple[list[LlmLogSummary], int]:
    """Most-recent-first page of individual LLM calls. Bounded by LIMIT/OFFSET per
    `.claude/rules/07-performance.md` — no unbounded scan, no default date filter (a log
    viewer that silently hides anything older than N days is the wrong default for
    debugging an incident from last month)."""
    offset = (page - 1) * page_size

    rows = await db.execute(
        text(
            """
            SELECT id, created_at, task, model, component, run_id, prompt_tokens,
                   completion_tokens, total_tokens, latency_ms, estimated_cost_usd,
                   succeeded, error_type
            FROM llm_usage_events
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": page_size, "offset": offset},
    )
    summaries = [LlmLogSummary(**dict(r)) for r in rows.mappings()]

    total_row = await db.execute(text("SELECT count(*) FROM llm_usage_events"))
    total = int(total_row.scalar_one() or 0)

    return summaries, total


async def get_llm_log(db: AsyncSession, log_id: uuid.UUID) -> LlmLogDetail | None:
    """One call's full detail, including prompt/response text. None if the id doesn't
    exist — the route maps that to 404."""
    row = await db.execute(
        text(
            """
            SELECT id, created_at, task, model, component, run_id, prompt_tokens,
                   completion_tokens, total_tokens, latency_ms, estimated_cost_usd,
                   succeeded, error_type, prompt_text, response_text, error_detail,
                   correlation_id, school_id, streamed
            FROM llm_usage_events
            WHERE id = :log_id
            """
        ),
        {"log_id": log_id},
    )
    mapping = row.mappings().one_or_none()
    if mapping is None:
        return None
    return LlmLogDetail(**dict(mapping))
