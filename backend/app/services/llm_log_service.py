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

# Only these may be interpolated into ORDER BY. Mirrors the GROUPABLE allowlist in
# llm_usage_service.py — sort_by crosses a network boundary, so it is validated here even
# though the route's Literal[...] type also restricts it.
SORTABLE: dict[str, str] = {
    "created_at": "created_at",
    "task": "task",
    "model": "model",
    "latency_ms": "latency_ms",
    "cost": "estimated_cost_usd",
    "tokens": "total_tokens",
}


class InvalidSortError(ValueError):
    """Raised when sort_by/sort_dir is not an allowed value — rejected before any query runs."""


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
    task: str | None = None,
    model: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[LlmLogSummary], int]:
    """Paginated page of individual LLM calls, optionally filtered by exact task/model
    and sorted by any SORTABLE column. Bounded by LIMIT/OFFSET per
    `.claude/rules/07-performance.md` — no unbounded scan, no default date filter (a log
    viewer that silently hides anything older than N days is the wrong default for
    debugging an incident from last month)."""
    if sort_by not in SORTABLE:
        raise InvalidSortError(f"Invalid sort_by: {sort_by!r}. Must be one of {sorted(SORTABLE)}.")
    if sort_dir not in ("asc", "desc"):
        raise InvalidSortError(f"Invalid sort_dir: {sort_dir!r}. Must be 'asc' or 'desc'.")

    column = SORTABLE[sort_by]
    direction = sort_dir.upper()
    offset = (page - 1) * page_size

    where_clauses: list[str] = []
    filter_params: dict[str, object] = {}
    if task:
        where_clauses.append("task = :task")
        filter_params["task"] = task
    if model:
        where_clauses.append("model = :model")
        filter_params["model"] = model
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    rows = await db.execute(
        text(
            f"""
            SELECT id, created_at, task, model, component, run_id, prompt_tokens,
                   completion_tokens, total_tokens, latency_ms, estimated_cost_usd,
                   succeeded, error_type
            FROM llm_usage_events
            {where_sql}
            ORDER BY {column} {direction} NULLS LAST
            LIMIT :limit OFFSET :offset
            """  # noqa: S608 — `column`/`direction` come from the SORTABLE allowlist above,
            # never from unvalidated input; `where_sql` is built from fixed literal
            # fragments, and the actual task/model values are always bound params.
        ),
        {**filter_params, "limit": page_size, "offset": offset},
    )
    summaries = [LlmLogSummary(**dict(r)) for r in rows.mappings()]

    total_row = await db.execute(
        text(f"SELECT count(*) FROM llm_usage_events {where_sql}"),  # noqa: S608 — see above
        filter_params,
    )
    total = int(total_row.scalar_one() or 0)

    return summaries, total


async def list_llm_log_filter_options(db: AsyncSession) -> tuple[list[str], list[str]]:
    """Distinct task/model values actually present in the table, for the filter dropdowns.

    Not `router.TASK_MODEL_MAP.keys()` for tasks: that lists every task the app *can*
    call, not the ones that actually have logged calls — an admin filtering by task
    should only see options that return results.
    """
    tasks_result = await db.execute(text("SELECT DISTINCT task FROM llm_usage_events ORDER BY task"))
    tasks = [r[0] for r in tasks_result.all()]

    models_result = await db.execute(text("SELECT DISTINCT model FROM llm_usage_events ORDER BY model"))
    models = [r[0] for r in models_result.all()]

    return tasks, models


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
