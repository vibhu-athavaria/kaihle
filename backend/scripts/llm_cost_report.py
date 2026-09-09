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
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.llm_usage_service import (  # noqa: E402
    GROUPABLE,
    UsageReport,
    compute_unit_costs,
    format_cost,
    resolve_since,
    summarise_usage,
)

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# The CLI has no pagination flag of its own — it wants "every bucket", which for
# task/component/model is a handful of rows and for run_id can be many. This cap keeps
# the query bounded (per .claude/rules/07-performance.md) without truncating any
# realistic report; a run_id count above this is itself worth knowing about.
_CLI_MAX_BUCKETS = 1000


def render(report: UsageReport, group_by: str, since: datetime) -> str:
    summary = report.summary
    calls = summary.calls

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
    for bucket in report.buckets:
        lines.append(
            f"  {bucket.bucket[:34]:<34} "
            f"{bucket.calls:>7} "
            f"{bucket.failures:>5} "
            f"{bucket.tokens:>12,} "
            f"{format_cost(bucket.cost):>10} "
            f"{bucket.p50_ms:>7} "
            f"{bucket.p95_ms:>7}"
        )

    lines += [
        "  " + "-" * 82,
        f"  {'TOTAL':<34} {calls:>7} {summary.failures:>5} {summary.tokens:>12,} {format_cost(summary.cost):>10}",
        "",
    ]

    if report.total_buckets > len(report.buckets):
        lines.append(
            f"  ⚠ Showing {len(report.buckets)} of {report.total_buckets} {group_by} groups — "
            f"the rest were cut off. Narrow --since to bring the group count under {_CLI_MAX_BUCKETS}."
        )
        lines.append("")

    successes = calls - summary.failures
    lines.append(
        f"  Unpriced      {summary.unpriced_count:>6} / {successes} successful calls ({summary.unpriced_percent:.1f}%)"
    )
    if summary.unpriced_models:
        lines.append(f"                models: {', '.join(summary.unpriced_models)}")
    lines.append(
        f"  Unattributed  {summary.unattributed_count:>6} / {calls} calls ({summary.unattributed_percent:.1f}%)"
    )
    if summary.unpriced_count:
        lines.append("")
        lines.append("  ⚠ The cost total EXCLUDES unpriced calls. Set LLM_PRICE_TABLE_PATH to a JSON")
        lines.append("    file with rates for the models above to include them. For self-hosted")
        lines.append("    endpoints the rate is a GPU-hour amortisation you choose, not provider billing.")
    if summary.unattributed_count:
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
            report = await summarise_usage(db, since, group_by, page=1, page_size=_CLI_MAX_BUCKETS)
            units = await compute_unit_costs(db, since) if show_unit_costs else []
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
        since = resolve_since(None)

    return asyncio.run(run(since, args.group_by, args.unit_costs))


if __name__ == "__main__":
    raise SystemExit(main())
