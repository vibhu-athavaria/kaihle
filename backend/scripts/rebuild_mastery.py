"""Rebuild mastery_priors and gap_states from scratch, correctly.

MLH-T3-4. This is deterministic work — a pure function of student_responses plus the
curriculum tables, all of which prod already holds. Per this project's promotion strategy,
deterministic work just runs on prod; there is no data artifact to export/import.

NOT A MIGRATION-SAFE BACKFILL. Deliberately, per Vibhu's direction: Kaihle is pre-launch
pilot data, and the goal is that school admins and teachers see an accurate number, not
that today's (buggy) number survives. There is no old-formula replay, no before/after
band-change gate, and no dual-write mode — see docs/design/MASTERY_MODEL_RATIONALE.md for
the full reasoning. What DOES carry over from a more cautious design, because it is
operational safety and not a compatibility question:

  * pg_dump backup before running (this script prints the reminder; the dump itself is an
    operator step, not something this script executes for you — see --pg-dump-reminder).
  * --dry-run by default.
  * Idempotent: rerunning after an interruption is safe and produces the same result.

TWO STEPS, ONE RUN
------------------
1. Fit priors: exactly scripts.calibrate_mastery_prior's logic, imported and called
   directly. Not reimplemented.
2. Replay every COMPLETED attempt in chronological order (oldest first), calling
   GapService.resolve_subtopic_totals_for_attempt (the same attribution logic the live
   path uses) and mastery_model.estimate (the same estimator). gap_states ends up holding
   the result of a full chronological replay — not last-attempt-only — because each
   replayed attempt's history query sees every earlier attempt already processed in this
   same run.

WHY REPLAY RATHER THAN A ONE-SHOT AGGREGATE
--------------------------------------------
Mastery is recency-weighted. A single aggregate over all of a student's history for a
subtopic cannot reproduce the same posterior a chronological walk does, because the decay
weight on each attempt depends on how many MORE RECENT attempts exist — information a
one-shot query would have to reconstruct anyway. Replaying through the live code path is
simpler and cannot silently diverge from it.

WHY student_attempt_subtopic_scores NEEDS A DIFFERENT WRITE MODE HERE
------------------------------------------------------------------------
The live path (GapService.calculate_gap_states_for_attempt) writes that table with
ON CONFLICT DO NOTHING — a live re-submission must never retroactively rewrite history.
A rebuild has the opposite goal: backfill correct_count/total_count onto EXISTING rows
that predate those columns (score alone cannot recover them). This script's writes use
ON CONFLICT DO UPDATE for that reason; gap_states still goes through the ordinary
GapService.upsert_gap_state (already DO UPDATE, unchanged).

Usage (from backend/):
    python -m scripts.rebuild_mastery --dry-run
    python -m scripts.rebuild_mastery --apply
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.gap_service import GapService  # noqa: E402
from app.services.mastery_model import Observation  # noqa: E402
from app.services.mastery_model import estimate as estimate_mastery  # noqa: E402
from scripts.calibrate_mastery_prior import (  # noqa: E402
    gather_all_subtopic_pools,
    resolve_prior,
    write_priors,
)

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# Attempts committed per batch during --apply. Bounds how long row-level locks are held
# (a fully uncommitted rebuild over prod-sized history would block the live app's own
# gap-state writes for the whole run) and how much work is lost if the process is killed
# mid-run. Not tuned against a specific lock-contention measurement — a starting point,
# small enough to matter at pilot scale, cheap to revisit once real run times are known.
COMMIT_BATCH_SIZE = 50

PG_DUMP_REMINDER = """
  BEFORE RUNNING --apply IN PROD:

    pg_dump -Fc -t gap_states -t student_attempt_subtopic_scores \\
        "$DATABASE_URL" > pre_rebuild_mastery_$(date +%Y%m%d_%H%M).dump

  Both tables are fully derivable from student_responses (worst case: rerun this script),
  but a dump is the fast path back if something looks wrong after applying.
"""


async def _fetch_all_priors(db: AsyncSession) -> dict[str, tuple[float, float]]:
    """The just-written mastery_priors, keyed by subtopic_id string — read once, reused
    across every attempt in the replay rather than re-queried per attempt."""
    rows = await db.execute(text("SELECT subtopic_id, alpha, beta FROM mastery_priors"))
    return {str(r.subtopic_id): (float(r.alpha), float(r.beta)) for r in rows.all()}


async def _upsert_subtopic_score(
    db: AsyncSession,
    *,
    student_id: Any,
    subtopic_id: Any,
    attempt_id: Any,
    correct: int,
    total: int,
    attempted_at: Any,
) -> None:
    """Backfill correct_count/total_count, overwriting any existing row.

    ON CONFLICT DO UPDATE, not DO NOTHING (contrast GapService's live-path insert) — the
    whole point of a rebuild is to set counts on rows that predate them.

    Raises rather than silently computing a fake score: total<=0 or correct>total means a
    caller passed a broken (correct, total) pair. Today this is unreachable — the only
    caller, replay_attempt, already skips total==0, and correct<=total is structurally
    guaranteed by how subtopic_correct/subtopic_total are built in
    resolve_subtopic_totals_for_attempt. Guarded anyway (Kilo review, PR #263): a future
    caller that skips that guarantee should fail loudly here, not write a score > 1.0 or a
    0.0 that looks like "confirmed wrong" rather than "broken input".
    """
    if total <= 0 or correct < 0 or correct > total:
        raise ValueError(f"invalid (correct, total) pair for subtopic score: correct={correct}, total={total}")

    await db.execute(
        text(
            """
            INSERT INTO student_attempt_subtopic_scores
                (id, student_id, subtopic_id, attempt_id, score, correct_count, total_count, attempted_at)
            VALUES
                (gen_random_uuid(), :student_id, :subtopic_id, :attempt_id,
                 :score, :correct_count, :total_count, :attempted_at)
            ON CONFLICT (student_id, subtopic_id, attempt_id) DO UPDATE SET
                score = EXCLUDED.score,
                correct_count = EXCLUDED.correct_count,
                total_count = EXCLUDED.total_count
            """
        ),
        {
            "student_id": student_id,
            "subtopic_id": subtopic_id,
            "attempt_id": attempt_id,
            "score": correct / total,
            "correct_count": correct,
            "total_count": total,
            "attempted_at": attempted_at,
        },
    )


async def _historical_observations(
    db: AsyncSession, student_id: Any, subtopic_id: Any, before_attempt_id: Any
) -> list[Observation]:
    """Every already-replayed attempt's counts for this (student, subtopic), most recent
    first. Correct by construction: attempts are replayed in completed_at order, so by the
    time attempt N is processed, only earlier attempts have counts written."""
    rows = await db.execute(
        text(
            """
            SELECT correct_count, total_count
            FROM student_attempt_subtopic_scores
            WHERE student_id = :student_id
              AND subtopic_id = :subtopic_id
              AND attempt_id != :attempt_id
              AND correct_count IS NOT NULL
            ORDER BY attempted_at DESC
            """
        ),
        {"student_id": student_id, "subtopic_id": subtopic_id, "attempt_id": before_attempt_id},
    )
    return [
        Observation(correct=int(r.correct_count), total=int(r.total_count), age_index=i + 1)
        for i, r in enumerate(rows.all())
    ]


async def replay_attempt(
    db: AsyncSession,
    service: GapService,
    attempt: Any,
    assessment: Any,
    priors: dict[str, tuple[float, float]],
) -> int:
    """Backfill counts and recompute gap_states for one attempt. Returns subtopics updated.

    Deliberately does not call GapService.calculate_gap_states_for_attempt end-to-end:
    that method's student_attempt_subtopic_scores write is DO NOTHING (correct for the live
    path, wrong for a backfill — see module docstring). It DOES reuse that method's
    attribution resolution and the estimator, so the only genuinely new logic here is the
    write-mode difference the backfill requires.
    """
    resolved = await service.resolve_subtopic_totals_for_attempt(attempt.id)
    if resolved is None:
        return 0
    subtopic_correct = resolved.subtopic_correct
    subtopic_total = resolved.subtopic_total

    updated = 0
    assessed_at = attempt.completed_at
    for sub_id, total in subtopic_total.items():
        if total == 0:
            continue
        correct = subtopic_correct[sub_id]

        await _upsert_subtopic_score(
            db,
            student_id=attempt.student_id,
            subtopic_id=sub_id,
            attempt_id=attempt.id,
            correct=correct,
            total=total,
            attempted_at=assessed_at,
        )

        historical = await _historical_observations(db, attempt.student_id, sub_id, attempt.id)
        observations = [Observation(correct=correct, total=total, age_index=0), *historical]

        prior_alpha, prior_beta = priors.get(str(sub_id), (settings.mastery_prior_alpha, settings.mastery_prior_beta))
        posterior = estimate_mastery(
            observations, prior_alpha=prior_alpha, prior_beta=prior_beta, decay=settings.mastery_recency_decay
        )

        await service.upsert_gap_state(
            student_id=attempt.student_id,
            subtopic_id=sub_id,
            school_id=assessment.school_id,
            class_id=assessment.class_id,
            new_mastery=posterior.score,
            confidence=posterior.confidence,
            rolling_attempt_count=len(historical) + 1,
            last_assessed_at=assessed_at,
        )
        updated += 1

    return updated


async def run(apply: bool) -> int:
    print(PG_DUMP_REMINDER)
    if not apply:
        print("  Running in --dry-run mode: no writes will be made.\n")

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            # Step 1: fit priors. Identical logic to calibrate_mastery_prior.py --apply.
            # Written now so the replay below can read them back (Postgres sees your own
            # uncommitted writes within one transaction), but nothing is DURABLE until the
            # final commit — a dry run rolls this back too, along with the replay, so
            # "no changes were made" stays literally true.
            log.info("rebuild_mastery_fitting_priors")
            pools_by_subtopic = await gather_all_subtopic_pools(db)
            if not pools_by_subtopic:
                log.warning("rebuild_mastery_no_active_subtopics")
                return 0

            level_cache: dict[int, tuple[float, float, int] | None] = {}
            resolutions = {
                subtopic_id: resolve_prior(
                    pools,
                    fallback_alpha=settings.mastery_prior_alpha,
                    fallback_beta=settings.mastery_prior_beta,
                    level_cache=level_cache,
                )
                for subtopic_id, pools in pools_by_subtopic.items()
            }
            await write_priors(db, resolutions)
            priors = await _fetch_all_priors(db)
            log.info("rebuild_mastery_priors_fitted", subtopics=len(priors))

            # Step 2: replay every COMPLETED attempt, oldest first.
            attempts_result = await db.execute(
                text(
                    """
                    SELECT sa.id, sa.student_id, sa.completed_at, a.school_id, a.class_id
                    FROM student_attempts sa
                    JOIN assessments a ON a.id = sa.assessment_id
                    WHERE sa.status = 'COMPLETED' AND sa.completed_at IS NOT NULL
                    ORDER BY sa.completed_at ASC, sa.id ASC
                    """
                )
            )
            attempt_rows = attempts_result.all()
            log.info("rebuild_mastery_replay_starting", attempts=len(attempt_rows))

            service = GapService(db)
            total_updated = 0
            for i, row in enumerate(attempt_rows):
                updated = await replay_attempt(
                    db,
                    service,
                    attempt=row,
                    assessment=row,  # school_id/class_id are on this same row
                    priors=priors,
                )
                total_updated += updated

                # Commit periodically, --apply only (Kilo review, PR #263). The whole
                # rebuild in one transaction holds row-level locks for its full duration,
                # blocking the live app's own gap-state writes on prod-sized data — a
                # single 39-attempt dev run never surfaced this. A dry run must still
                # commit NOTHING until the final rollback, so this is strictly gated on
                # apply; once a batch is committed it is durable regardless of what
                # happens afterward, which is also what makes resuming after a kill safe
                # (only work since the last batch boundary is at risk, not the whole run).
                if apply and (i + 1) % COMMIT_BATCH_SIZE == 0:
                    await db.commit()
                    log.info("rebuild_mastery_batch_committed", attempts_committed=i + 1, total=len(attempt_rows))
                if (i + 1) % 200 == 0:
                    log.info("rebuild_mastery_replay_progress", processed=i + 1, total=len(attempt_rows))

            if apply:
                await db.commit()  # final partial batch, if any
                log.info(
                    "rebuild_mastery_committed", attempts_replayed=len(attempt_rows), subtopics_updated=total_updated
                )
            else:
                await db.rollback()
                log.warning("rebuild_mastery_dry_run_no_changes_made", hint="re-run with --apply to write")
    finally:
        await engine.dispose()

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
