"""Report LLM spend from `llm_usage_events`.

Read-only. Answers the questions that had no answer before MLH-T2: what does this cost, where
is it going, and which calls are slow.

TWO HONESTY INDICATORS ARE ALWAYS PRINTED
-----------------------------------------
  * unpriced %      — calls whose model has no price (self-hosted endpoints, mostly)
  * unattributed %  — calls with no `component`, meaning some entry point never wrapped
                      itself in `llm_component()`

A total that silently omits a third of calls is worse than no total, because it looks
authoritative. Both figures print even when zero, so their absence is never mistaken for
their being unremarkable.

Usage (from backend/):
    python -m scripts.llm_cost_report --since 2026-08-01
    python -m scripts.llm_cost_report --since 2026-08-01 --group-by component
    python -m scripts.llm_cost_report --group-by run_id
    python -m scripts.llm_cost_report --unit-costs
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# Only these may be interpolated into a GROUP BY. The value is never taken from user input
# directly — argparse restricts it and this map is the second gate.
GROUPABLE: dict[str, str] = {
    "task": "task",
    "component": "component",
    "model": "model",
    "run_id": "run_id",
}

DEFAULT_LOOKBACK_DAYS = 30


def _money(value: Decimal | None) -> str:
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


async def summarise(db: AsyncSession, since: datetime, group_by: str) -> dict[str, Any]:
    """Aggregate spend, tokens and latency over one grouping."""
    column = GROUPABLE[group_by]

    rows = await db.execute(
        text(
            f"""
            SELECT COALESCE({column}, '(unattributed)') AS bucket,
                   count(*)                              AS calls,
                   count(*) FILTER (WHERE NOT succeeded) AS failures,
                   COALESCE(sum(total_tokens), 0)        AS tokens,
                   sum(estimated_cost_usd)               AS cost,
                   count(*) FILTER (WHERE estimated_cost_usd IS NULL AND succeeded) AS unpriced,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)  AS p50,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95
            FROM llm_usage_events
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY COALESCE(sum(estimated_cost_usd), 0) DESC, count(*) DESC
            """  # noqa: S608 — `column` comes from GROUPABLE, never from user input
        ),
        {"since": since},
    )
    buckets = [dict(r) for r in rows.mappings()]

    totals = await db.execute(
        text(
            """
            SELECT count(*)                                                 AS calls,
                   COALESCE(sum(total_tokens), 0)                           AS tokens,
                   sum(estimated_cost_usd)                                  AS cost,
                   count(*) FILTER (WHERE estimated_cost_usd IS NULL AND succeeded) AS unpriced,
                   count(*) FILTER (WHERE succeeded)                        AS successes,
                   count(*) FILTER (WHERE component IS NULL)                AS unattributed,
                   count(*) FILTER (WHERE NOT succeeded)                    AS failures
            FROM llm_usage_events
            WHERE created_at >= :since
            """
        ),
        {"since": since},
    )
    summary = dict(totals.mappings().one())

    unpriced_models = await db.execute(
        text(
            """
            SELECT DISTINCT model FROM llm_usage_events
            WHERE created_at >= :since AND estimated_cost_usd IS NULL AND succeeded
            ORDER BY model
            """
        ),
        {"since": since},
    )
    summary["unpriced_models"] = [r[0] for r in unpriced_models.all()]

    return {"buckets": buckets, "summary": summary}


async def unit_costs(db: AsyncSession, since: datetime) -> list[tuple[str, str]]:
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
    row = generation.mappings().one()
    if row["calls"]:
        # One generation call covers one subtopic — see generate_gap_questions.py, which
        # batches per subtopic.
        cost = row["cost"]
        per_call = f"{_money(cost / row['calls'])} per subtopic" if cost else "unpriced"
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
        results.append(("Cost per mini-course explanation", f"{_money(row['cost'] / row['calls'])} per call"))
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
            results.append((f"Batch run {r['run_id']}", f"{_money(r['cost'])} over {r['calls']} calls"))
    else:
        results.append(
            (
                "Batch run costs",
                "unavailable — no run_id recorded. Wrap batch scripts in "
                "usage_context.llm_component(name, run_id=...) to enable this.",
            )
        )

    return results


def render(report: dict[str, Any], group_by: str, since: datetime) -> str:
    summary = report["summary"]
    calls = int(summary["calls"] or 0)

    lines = [
        "",
        "=" * 84,
        f"LLM USAGE — since {since:%Y-%m-%d %H:%M} UTC, grouped by {group_by}",
        "=" * 84,
        "",
    ]

    if calls == 0:
        lines += [
            "  No usage recorded in this window.",
            "",
            "  If calls are being made, check LLM_USAGE_TRACKING_ENABLED is set.",
            "",
        ]
        return "\n".join(lines)

    lines.append(f"  {group_by:<34} {'calls':>7} {'fail':>5} {'tokens':>12} {'cost':>10} {'p50ms':>7} {'p95ms':>7}")
    lines.append("  " + "-" * 82)
    for bucket in report["buckets"]:
        lines.append(
            f"  {str(bucket['bucket'])[:34]:<34} "
            f"{bucket['calls']:>7} "
            f"{bucket['failures']:>5} "
            f"{int(bucket['tokens']):>12,} "
            f"{_money(bucket['cost']):>10} "
            f"{int(bucket['p50'] or 0):>7} "
            f"{int(bucket['p95'] or 0):>7}"
        )

    lines += [
        "  " + "-" * 82,
        f"  {'TOTAL':<34} {calls:>7} {int(summary['failures'] or 0):>5} "
        f"{int(summary['tokens'] or 0):>12,} {_money(summary['cost']):>10}",
        "",
    ]

    unpriced = int(summary["unpriced"] or 0)
    successes = int(summary["successes"] or 0)
    unattributed = int(summary["unattributed"] or 0)
    # Denominator is successful calls: a failed call produced no tokens, so having no cost
    # is correct rather than a pricing gap, and including it would overstate the problem.
    share = f"{unpriced / successes:.1%}" if successes else "n/a"
    lines.append(f"  Unpriced      {unpriced:>6} / {successes} successful calls ({share})")
    if summary["unpriced_models"]:
        lines.append(f"                models: {', '.join(summary['unpriced_models'])}")
    lines.append(f"  Unattributed  {unattributed:>6} / {calls} calls ({unattributed / calls:.1%})")
    if unpriced:
        lines.append("")
        lines.append("  ⚠ The cost total EXCLUDES unpriced calls. Set LLM_PRICE_TABLE_PATH to a JSON")
        lines.append("    file with rates for the models above to include them. For self-hosted")
        lines.append("    endpoints the rate is a GPU-hour amortisation you choose, not provider billing.")
    if unattributed:
        lines.append("")
        lines.append("  ⚠ Unattributed calls came from a path that never entered llm_component().")
        lines.append("    Above ~5%, treat the component breakdown as incomplete.")
    lines.append("")
    return "\n".join(lines)


async def run(since: datetime, group_by: str, show_unit_costs: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            report = await summarise(db, since, group_by)
            units = await unit_costs(db, since) if show_unit_costs else []
            # Read-only by construction; the rollback makes an accidental future write
            # unable to survive this path.
            await db.rollback()
    finally:
        await engine.dispose()

    print(render(report, group_by, since))

    if show_unit_costs:
        print("-" * 84)
        print("UNIT COSTS")
        print("")
        for label, value in units:
            print(f"  {label}")
            print(f"    {value}")
            print("")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", type=str, help="ISO date, e.g. 2026-08-01. Defaults to 30 days ago.")
    parser.add_argument("--group-by", choices=sorted(GROUPABLE), default="component")
    parser.add_argument("--unit-costs", action="store_true", help="Derive per-unit-of-work costs")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.since:
        try:
            since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
        except ValueError:
            log.error("invalid_since", value=args.since, hint="Use an ISO date such as 2026-08-01")
            return 1
    else:
        since = datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    return asyncio.run(run(since, args.group_by, args.unit_costs))


if __name__ == "__main__":
    raise SystemExit(main())
