"""Pre-flight checks before replacing the production database with dev.

Curriculum work happens on dev and reaches production by replacing the whole prod
database — thousands of human review decisions and generated questions live as rows,
not as code, and reconciling them into a live database is far more error-prone than
copying it wholesale.

The cost of that strategy is precise: ANY row created in production after the dev
database was seeded from it is destroyed by the swap. This script finds those rows
before they are lost, and refuses to bless a swap that would destroy user work.

It is read-only. It never writes to either database and never performs the swap.

Usage:
    python -m scripts.preflight_prod_swap \\
        --prod postgresql+asyncpg://USER:PASS@HOST:5432/kaihle_db \\
        --dev  postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle

Exit codes:
    0  safe to swap
    1  blocking finding — prod holds data that dev does not
    2  could not complete the checks
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = structlog.get_logger("preflight_prod_swap")

# Tables where a row created in prod represents real user work that a swap destroys.
# Curriculum tables are deliberately absent: those are authored on dev and are meant
# to be overwritten.
# Mapped to each table's own creation timestamp: two of the tables that matter most
# do not use created_at, and silently skipping them would hide exactly the rows —
# enrolments and answered questions — a swap is most likely to destroy.
_USER_WORK_TABLES: dict[str, str] = {
    "users": "created_at",
    "schools": "created_at",
    "classes": "created_at",
    "class_enrollments": "enrolled_at",
    "assessments": "created_at",
    "student_attempts": "created_at",
    "student_responses": "answered_at",
    "student_profiles": "created_at",
}

_ALEMBIC_SQL = "SELECT version_num FROM alembic_version"


async def _fetch(url: str, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(text(sql), params or {})
            return [dict(r) for r in rows.mappings().all()]
    finally:
        await engine.dispose()


async def check_alembic(prod_url: str, dev_url: str) -> bool:
    """A swap carries dev's schema and alembic_version across. Divergence here means
    the deployed code and the incoming database may disagree about the schema."""
    prod = (await _fetch(prod_url, _ALEMBIC_SQL))[0]["version_num"]
    dev = (await _fetch(dev_url, _ALEMBIC_SQL))[0]["version_num"]
    same = prod == dev
    print(f"\nALEMBIC VERSION\n  prod {prod}\n  dev  {dev}")
    if same:
        print("  → identical")
    else:
        print("  → differ. This is expected when dev is ahead; confirm dev is the newer one")
        print("    and that the deployed code matches dev's head before swapping.")
    return True


async def check_prod_only_rows(prod_url: str, dev_url: str, since: datetime) -> bool:
    """Rows created in prod after the dev snapshot. These are destroyed by the swap.

    Compared by count rather than by id: a cheap signal that something changed, which
    is enough to stop and look properly. Precise reconciliation is a human job.
    """
    print(f"\nPROD ROWS CREATED SINCE {since:%Y-%m-%d %H:%M} UTC")
    blocking = False
    for table, ts_col in _USER_WORK_TABLES.items():
        sql = f"SELECT count(*) AS n FROM {table} WHERE {ts_col} > :since"  # noqa: S608
        try:
            prod_n = (await _fetch(prod_url, sql, {"since": since}))[0]["n"]
        except Exception as exc:
            # Never silent: an unreadable table is an unchecked table, and the operator
            # must decide whether that is acceptable rather than have it hidden.
            print(f"  {table:24} ⚠  COULD NOT CHECK — {type(exc).__name__}: {str(exc)[:60]}")
            blocking = True
            continue
        dev_n = (await _fetch(dev_url, sql, {"since": since}))[0]["n"]
        flag = ""
        if prod_n > dev_n:
            flag = f"  ⚠  {prod_n - dev_n} row(s) exist only in prod — WILL BE DESTROYED"
            blocking = True
        print(f"  {table:24} prod {prod_n:6}   dev {dev_n:6}{flag}")
    return not blocking


async def check_row_counts(prod_url: str, dev_url: str) -> bool:
    """Whole-table comparison, so the operator sees the shape of what changes."""
    print("\nTABLE TOTALS (dev replaces prod)")
    for table in [*_USER_WORK_TABLES, "question_bank", "learning_objectives", "subtopics"]:
        sql = f"SELECT count(*) AS n FROM {table}"  # noqa: S608
        try:
            prod_n = (await _fetch(prod_url, sql))[0]["n"]
            dev_n = (await _fetch(dev_url, sql))[0]["n"]
        except Exception as exc:
            print(f"  {table:24} — skipped ({type(exc).__name__})")
            continue
        delta = dev_n - prod_n
        print(f"  {table:24} prod {prod_n:6} → dev {dev_n:6}   ({delta:+d})")
    return True


async def check_question_reachability(dev_url: str) -> bool:
    """Every active question must be reachable through the objective bridge.

    Selection never joins on question_bank.subtopic_id, so a question without a
    learning_objective_id is stored and then served to nobody. Swapping a database
    full of unreachable questions produces a bank that looks full and returns nothing.
    """
    rows = await _fetch(
        dev_url,
        """
        SELECT count(*) FILTER (WHERE learning_objective_id IS NULL) AS unreachable,
               count(*) AS total
        FROM question_bank WHERE is_active IS TRUE
        """,
    )
    unreachable, total = rows[0]["unreachable"], rows[0]["total"]
    print(f"\nQUESTION REACHABILITY (dev)\n  active {total}, unreachable {unreachable}")
    if unreachable:
        # Informational, not blocking. These are the remap's unresolved review-queue
        # questions: inert rather than harmful, and they are no worse in prod than in
        # dev. Reported because a large number here means the queue still has work.
        print(f"  ℹ  {unreachable} active questions have no objective and will never be served.")
        print("     These are the unresolved curriculum-review backlog, not a swap risk.")
    else:
        print("  → all active questions resolve through an objective")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prod", required=True, help="Production database URL (read-only use)")
    parser.add_argument("--dev", required=True, help="Dev database URL — the source of the swap")
    parser.add_argument(
        "--since-days",
        type=int,
        default=7,
        help="Look this many days back for prod-only rows (default: 7)",
    )
    args = parser.parse_args()

    since = datetime.now(UTC) - timedelta(days=args.since_days)

    print("=" * 70)
    print("PRE-FLIGHT: replacing production database with dev")
    print("=" * 70)

    try:
        results = [
            await check_alembic(args.prod, args.dev),
            await check_row_counts(args.prod, args.dev),
            await check_prod_only_rows(args.prod, args.dev, since),
            await check_question_reachability(args.dev),
        ]
    except Exception as exc:
        logger.error("preflight_failed", error=str(exc), exc_info=True)
        print(f"\nCould not complete checks: {exc}")
        return 2

    print("\n" + "=" * 70)
    if all(results):
        print("SAFE TO SWAP")
        print("  1. pg_dump prod  → prod_pre_swap_<date>.sql   (rollback point)")
        print("  2. pg_dump dev   → dev_<date>.sql")
        print("  3. psql prod     < dev_<date>.sql")
        print("  4. Confirm `alembic current` on prod matches dev's head.")
        print("=" * 70)
        return 0

    print("DO NOT SWAP — see the warnings above.")
    print("  Prod holds data that dev does not, or dev holds unreachable questions.")
    print("  Recreate that work on dev first, then re-run this check.")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
