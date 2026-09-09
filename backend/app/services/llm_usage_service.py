"""LLM spend aggregation — the single source of truth for `llm_usage_events` reporting.

Used by both `scripts/llm_cost_report.py` (CLI) and `GET /api/v1/platform/llm-usage`
(Kaihle Admin page). Neither caller runs its own copy of these queries: a total that the
CLI and the admin page could disagree on would be worse than either being wrong alone,
because there would be no way to tell which one to trust.

TWO HONESTY INDICATORS, computed here so every caller gets the same numbers:
  * unpriced_percent     — of SUCCESSFUL calls only. A failed call has no tokens, so
                            having no cost is correct, not a pricing gap.
  * unattributed_percent — of ALL calls with `component IS NULL`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Only these may be interpolated into a GROUP BY. `group_by` crosses a network boundary
# (the route's `Literal[...]` is a static-analysis hint, not a runtime guarantee once a
# string arrives over HTTP), so this dict is the actual gate — checked again here even
# though the CLI's argparse `choices` and the route's `Literal` both also restrict it.
GROUPABLE: dict[str, str] = {
    "task": "task",
    "component": "component",
    "model": "model",
    "run_id": "run_id",
}

DEFAULT_LOOKBACK_DAYS = 30


class InvalidGroupByError(ValueError):
    """Raised when `group_by` is not a key of GROUPABLE — rejected before any query runs."""


@dataclass
class UsageBucket:
    bucket: str
    calls: int
    failures: int
    tokens: int
    cost: Decimal | None
    p50_ms: int
    p95_ms: int


@dataclass
class UsageSummary:
    calls: int
    tokens: int
    cost: Decimal | None
    unpriced_count: int
    unpriced_percent: float
    unpriced_models: list[str]
    unattributed_count: int
    unattributed_percent: float
    failures: int
    p95_ms: int  # across the whole window, not just the current page of buckets


@dataclass
class UsageReport:
    buckets: list[UsageBucket]
    summary: UsageSummary
    total_buckets: int


def format_cost(value: Decimal | None) -> str:
    """Render a cost, distinguishing 'zero' from 'not priceable'.

    Precision adapts to magnitude: a per-call cost is routinely in the 1e-3 to 1e-5 range,
    and rendering those at two decimals prints $0.00 for every row — which reads as free
    rather than as small.
    """
    if value is None:
        return "     —"
    if value == 0:
        return "$0.00"
    if abs(value) < Decimal("0.01"):
        return f"${value:.6f}"
    if abs(value) < Decimal("1"):
        return f"${value:.4f}"
    return f"${value:,.2f}"


async def summarise_usage(
    db: AsyncSession,
    since: datetime,
    group_by: str,
    page: int = 1,
    page_size: int = 20,
) -> UsageReport:
    """Aggregate spend, tokens and latency over one grouping, one page at a time.

    Pagination applies only to the bucket list (a `run_id` grouping can have far more
    distinct values than `task`/`component`/`model`, and an unbounded scan there is
    exactly what `.claude/rules/07-performance.md` prohibits). The summary totals below
    are computed over the full window regardless of page, so the KPI row never changes
    as someone pages through buckets.
    """
    if group_by not in GROUPABLE:
        raise InvalidGroupByError(f"Invalid group_by: {group_by!r}. Must be one of {sorted(GROUPABLE)}.")
    column = GROUPABLE[group_by]
    offset = (page - 1) * page_size

    bucket_rows = await db.execute(
        text(
            f"""
            SELECT COALESCE({column}, '(unattributed)') AS bucket,
                   count(*)                              AS calls,
                   count(*) FILTER (WHERE NOT succeeded) AS failures,
                   COALESCE(sum(total_tokens), 0)        AS tokens,
                   sum(estimated_cost_usd)               AS cost,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)  AS p50,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95
            FROM llm_usage_events
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY COALESCE(sum(estimated_cost_usd), 0) DESC, count(*) DESC
            LIMIT :limit OFFSET :offset
            """  # noqa: S608 — `column` comes from GROUPABLE, never from user input
        ),
        {"since": since, "limit": page_size, "offset": offset},
    )
    buckets = [
        UsageBucket(
            bucket=str(r["bucket"]),
            calls=int(r["calls"]),
            failures=int(r["failures"]),
            tokens=int(r["tokens"] or 0),
            cost=r["cost"],
            p50_ms=int(r["p50"] or 0),
            p95_ms=int(r["p95"] or 0),
        )
        for r in bucket_rows.mappings()
    ]

    bucket_count_row = await db.execute(
        text(
            f"""
            SELECT count(*) FROM (
                SELECT 1 FROM llm_usage_events WHERE created_at >= :since GROUP BY {column}
            ) sub
            """  # noqa: S608 — `column` comes from GROUPABLE, never from user input
        ),
        {"since": since},
    )
    total_buckets = int(bucket_count_row.scalar_one() or 0)

    totals_row = await db.execute(
        text(
            """
            SELECT count(*)                                                       AS calls,
                   COALESCE(sum(total_tokens), 0)                                  AS tokens,
                   sum(estimated_cost_usd)                                         AS cost,
                   count(*) FILTER (WHERE estimated_cost_usd IS NULL AND succeeded) AS unpriced,
                   count(*) FILTER (WHERE succeeded)                               AS successes,
                   count(*) FILTER (WHERE component IS NULL)                       AS unattributed,
                   count(*) FILTER (WHERE NOT succeeded)                           AS failures,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)        AS p95
            FROM llm_usage_events
            WHERE created_at >= :since
            """
        ),
        {"since": since},
    )
    totals = totals_row.mappings().one()

    unpriced_models_result = await db.execute(
        text(
            """
            SELECT DISTINCT model FROM llm_usage_events
            WHERE created_at >= :since AND estimated_cost_usd IS NULL AND succeeded
            ORDER BY model
            """
        ),
        {"since": since},
    )
    unpriced_models = [r[0] for r in unpriced_models_result.all()]

    calls = int(totals["calls"] or 0)
    successes = int(totals["successes"] or 0)
    unpriced_count = int(totals["unpriced"] or 0)
    unattributed_count = int(totals["unattributed"] or 0)

    summary = UsageSummary(
        calls=calls,
        tokens=int(totals["tokens"] or 0),
        cost=totals["cost"],
        unpriced_count=unpriced_count,
        unpriced_percent=(unpriced_count / successes * 100) if successes else 0.0,
        unpriced_models=unpriced_models,
        unattributed_count=unattributed_count,
        unattributed_percent=(unattributed_count / calls * 100) if calls else 0.0,
        failures=int(totals["failures"] or 0),
        p95_ms=int(totals["p95"] or 0),
    )

    return UsageReport(buckets=buckets, summary=summary, total_buckets=total_buckets)


async def compute_unit_costs(db: AsyncSession, since: datetime) -> list[tuple[str, str]]:
    """Derive the per-unit-of-work figures worth quoting.

    Where `run_id` or `component` cannot support a join, the metric is reported as
    unavailable and the missing instrumentation named — rather than approximated. An
    approximate unit cost is indistinguishable from a real one once it is on a slide.
    """
    results: list[tuple[str, str]] = []

    diagnostics = await db.execute(
        text(
            """
            SELECT count(*) FROM student_attempts sa
            JOIN assessments a ON a.id = sa.assessment_id
            WHERE sa.status = 'COMPLETED' AND a.assessment_type = 'DIAGNOSTIC'
              AND sa.completed_at >= :since
            """
        ),
        {"since": since},
    )
    completed = int(diagnostics.scalar_one() or 0)
    # Diagnostics are served from the pre-generated bank: selection and scoring are
    # deterministic, with no LLM in the student's path. The honest answer is a structural
    # zero, not a number derived from unrelated spend.
    results.append(
        (
            "Cost during a completed diagnostic (student-time only)",
            f"$0.00 marginal — {completed} completed since cutoff. Adaptive selection and MCQ "
            "scoring are deterministic; no LLM call is made while a student sits a diagnostic. "
            "This is NOT the full cost of a diagnostic: the question bank it draws from was "
            "LLM-generated, and that spend is amortised into 'Cost per subtopic of generated "
            "questions' below. Quoting this line alone would understate the true figure.",
        )
    )

    generation = await db.execute(
        text(
            """
            SELECT count(*) AS calls, sum(estimated_cost_usd) AS cost,
                   count(*) FILTER (WHERE estimated_cost_usd IS NULL) AS unpriced
            FROM llm_usage_events
            WHERE created_at >= :since AND task = 'question_generation'
            """
        ),
        {"since": since},
    )
    row: Any = generation.mappings().one()
    if row["calls"]:
        # One generation call covers one subtopic — see generate_gap_questions.py, which
        # batches per subtopic.
        cost = row["cost"]
        per_call = f"{format_cost(cost / row['calls'])} per subtopic" if cost else "unpriced"
        results.append(
            (
                "Cost per subtopic of generated questions",
                f"{per_call} over {row['calls']} calls" + (f" ({row['unpriced']} unpriced)" if row["unpriced"] else ""),
            )
        )
    else:
        results.append(("Cost per subtopic of generated questions", "no calls recorded since cutoff"))

    mini = await db.execute(
        text(
            """
            SELECT count(*) AS calls, sum(estimated_cost_usd) AS cost
            FROM llm_usage_events
            WHERE created_at >= :since AND task = 'mini_course_explanation'
            """
        ),
        {"since": since},
    )
    row = mini.mappings().one()
    if row["calls"] and row["cost"]:
        results.append(("Cost per mini-course explanation", f"{format_cost(row['cost'] / row['calls'])} per call"))
    else:
        results.append(("Cost per mini-course explanation", "no priced calls recorded since cutoff"))

    runs = await db.execute(
        text(
            """
            SELECT run_id, count(*) AS calls, sum(estimated_cost_usd) AS cost
            FROM llm_usage_events
            WHERE created_at >= :since AND run_id IS NOT NULL
            GROUP BY run_id ORDER BY sum(estimated_cost_usd) DESC NULLS LAST LIMIT 5
            """
        ),
        {"since": since},
    )
    run_rows = list(runs.mappings())
    if run_rows:
        for r in run_rows:
            results.append((f"Batch run {r['run_id']}", f"{format_cost(r['cost'])} over {r['calls']} calls"))
    else:
        results.append(
            (
                "Batch run costs",
                "unavailable — no run_id recorded. Wrap batch scripts in "
                "usage_context.llm_component(name, run_id=...) to enable this.",
            )
        )

    return results
