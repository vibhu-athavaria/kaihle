"""Fit hierarchical mastery priors and write them to `mastery_priors`.

Every active subtopic gets exactly one row, always — including one with zero observed
data. The backoff chain tries the most specific level first and falls back:

    SUBTOPIC -> TOPIC -> SUBJECT -> GLOBAL

A level is used only if it has enough pooled (student, subtopic) observation rows AND its
fitted Beta is neither too weak nor implausibly strong for that much data (see the two
failure modes below). GLOBAL always resolves to something — its own fit if defensible,
otherwise the analytically-chosen config default (`settings.mastery_prior_alpha/beta`) — so
every subtopic in the curriculum has a row after this script runs, regardless of how much
data currently exists for it.

TWO FAILURE MODES THIS SCRIPT EXISTS TO CATCH, BOTH FOUND BY RUNNING IT, NOT BY REASONING
ABOUT IT
-------------------------------------------------------------------------------------------
1. TOO WEAK. Method-of-moments fit on PROPORTIONS (not counts) returned Beta(0.058, 0.055)
   on this project's first response data — strength 0.11, applying almost no shrinkage.
   77% of per-subtopic observations rest on exactly one response, which can only score 0.0
   or 1.0, so a proportion-based fit sees a bimodal distribution and concludes there is no
   real spread to shrink toward — encoding the very defect the mastery model exists to
   remove. Beta-Binomial MLE fit on (correct, total) COUNTS does not have this failure: it
   models sampling noise explicitly, so a 0/1 observation is correctly weak evidence rather
   than an extreme measurement.

2. TOO STRONG. Unconstrained MLE has no ceiling. Fit against this project's Integrated
   Science data (91 subtopics, 15 students, 408 observation rows) returned Beta(2346, 1341)
   — strength 3687, asserting near-certainty that every SCI student scores 63.6%, from a
   sample two orders of magnitude too small to support that. A small, superficially
   homogeneous sample can make the likelihood improve monotonically toward an unbounded,
   near-point-mass solution. `fit_beta_mle` bounds its search so this terminates instead of
   wandering toward infinity, and `is_defensible` independently rejects the result.

Usage (from backend/):
    python -m scripts.calibrate_mastery_prior --dry-run
    python -m scripts.calibrate_mastery_prior --apply
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from math import lgamma
from pathlib import Path

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

# Levels tried in order, most specific first. Each is a distinct query scope; see
# `gather_pools`.
LEVELS = ("SUBTOPIC", "TOPIC", "SUBJECT", "GLOBAL")

# Below this many pooled (student, subtopic) observation rows, a level is rejected without
# attempting a fit — an MLE fit needs enough independent rows to estimate two parameters
# reliably, and fewer than this measures noise, not students. Empirically: every one of 62
# topics in this project's data topped out at 15-34 rows, well under this floor, which is
# why TOPIC never won a backoff decision on the data this was built against — expected to
# change as usage grows, not a sign the threshold is wrong.
MIN_ROWS_FOR_FIT = 100

# A fit weaker than Beta(1,1) — the uniform distribution, strength 2 — applies negligible
# shrinkage and defeats the purpose of having a prior at all.
MIN_DEFENSIBLE_STRENGTH = 2.0


def max_defensible_strength(n_rows: int) -> float:
    """A level's fit must not claim more certainty than its own sample size supports.

    The exact multiple (4x) is a starting point, calibrated against one observed failure
    (Finding 3: SCI's 408-row sample returned a fit an order of magnitude past any
    defensible bound), not a value tuned to a target. Revisit once more subjects clear
    MIN_ROWS_FOR_FIT and there is a second data point to check it against.
    """
    return n_rows * 4.0


def is_defensible(alpha: float, beta: float, n_rows: int) -> bool:
    """Both bounds from Findings 2 and 3: a level's fit must be neither too weak nor
    stronger than its own evidence can support."""
    strength = alpha + beta
    return MIN_DEFENSIBLE_STRENGTH <= strength <= max_defensible_strength(n_rows)


def _log_beta(a: float, b: float) -> float:
    return lgamma(a) + lgamma(b) - lgamma(a + b)


def _log_likelihood(counts: list[tuple[int, int]], a: float, b: float) -> float:
    """Beta-Binomial marginal log-likelihood on (total, correct) counts.

    Unlike a fit on proportions, this treats a 0/1 observation correctly: the binomial
    sampling variance is inside the model, not confounded with between-student variance —
    which is the whole reason it does not fail the way method-of-moments does (Finding 2).
    """
    lb = _log_beta(a, b)
    return sum(_log_beta(correct + a, total - correct + b) - lb for total, correct in counts)


def fit_beta_mle(counts: list[tuple[int, int]], search_cap: float) -> tuple[float, float] | None:
    """Beta-Binomial MLE on (total, correct) pairs, via bounded grid search + refinement.

    Args:
        counts: (total, correct) pairs. May include n=1 rows — MLE handles them correctly,
            unlike a moments fit on proportions.
        search_cap: Bounds alpha and beta INDIVIDUALLY (not their sum) so the search
            terminates in bounded time rather than wandering toward an unbounded,
            near-point-mass solution as a degenerate sample's likelihood keeps improving
            (Finding 3). This is a computational bound only — the business-rule ceiling on
            the SUM is `is_defensible`, checked separately by the caller regardless of
            where within this cap the search lands. On this project's SCI data the search
            still finds alpha+beta far past any defensible bound (~3700 against a ~2400
            ceiling) — `is_defensible` is what actually rejects it, not this cap.

    Returns:
        (alpha, beta), or None if `counts` is empty.
    """
    if not counts:
        return None

    # Coarse log-spaced grid: covers several orders of magnitude cheaply, which a linear
    # grid cannot without either missing small-strength priors or being enormous. Fixed
    # 0.01 floor rather than one scaled by search_cap — the cap can be large (thousands,
    # for a well-evidenced level), and scaling the floor with it would blind the grid to
    # legitimate small individual alpha/beta values on exactly those levels.
    steps = 40
    floor = 0.01
    candidates = [floor * (search_cap / floor) ** (i / (steps - 1)) for i in range(steps)]

    best_ll = float("-inf")
    best_a, best_b = candidates[0], candidates[0]
    for a in candidates:
        for b in candidates:
            ll = _log_likelihood(counts, a, b)
            if ll > best_ll:
                best_ll, best_a, best_b = ll, a, b

    # Bounded coordinate-ascent refinement. Every step is clamped to (0, search_cap], so
    # this converges to a local optimum within the search space rather than escaping it —
    # the fix for the unbounded hill-climb that produced Finding 3's degenerate result.
    step = search_cap / steps
    for _ in range(10):
        improved = True
        while improved:
            improved = False
            for da, db in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
                na, nb = best_a + da, best_b + db
                if not (0.0 < na <= search_cap) or not (0.0 < nb <= search_cap):
                    continue
                ll = _log_likelihood(counts, na, nb)
                if ll > best_ll:
                    best_ll, best_a, best_b, improved = ll, na, nb, True
        step /= 2.0

    return (best_a, best_b)


@dataclass(frozen=True)
class PriorResolution:
    """The prior a subtopic resolves to, and which level produced it."""

    alpha: float
    beta: float
    source_level: str
    source_n: int


def _attempt_level(rows: list[tuple[int, int]]) -> tuple[float, float, int] | None:
    """Try to fit one level's pool. None if too thin or not defensible.

    Factored out from resolve_prior so callers fitting MANY subtopics can cache by pool
    identity (see `resolve_prior`'s `level_cache` parameter) — a TOPIC, SUBJECT, or GLOBAL
    pool is the same Python list object shared across every subtopic in that scope, so
    fitting it once and reusing the result is correct, not an approximation.
    """
    if len(rows) < MIN_ROWS_FOR_FIT:
        return None
    cap = max_defensible_strength(len(rows)) * 1.5  # headroom so the search can find the
    # true optimum before the reject boundary, rather than being pinched at it.
    fit = fit_beta_mle(rows, search_cap=cap)
    if fit is None:
        return None
    alpha, beta = fit
    if not is_defensible(alpha, beta, len(rows)):
        return None
    return (alpha, beta, len(rows))


def resolve_prior(
    pools: dict[str, list[tuple[int, int]]],
    fallback_alpha: float,
    fallback_beta: float,
    level_cache: dict[int, tuple[float, float, int] | None] | None = None,
) -> PriorResolution:
    """Walk the backoff chain for one subtopic and return the first defensible level.

    Args:
        pools: One entry per level in `LEVELS`, each the pooled (total, correct) rows in
            scope at that level (SUBTOPIC = this subtopic alone; TOPIC = every subtopic
            under the same topic; and so on). Missing keys are treated as empty.
        fallback_alpha, fallback_beta: Used only if GLOBAL itself has no defensible fit —
            the platform-wide bootstrap default (settings.mastery_prior_alpha/beta),
            reached only when there is not yet enough response data anywhere to fit
            anything, e.g. a brand-new deployment.
        level_cache: Keyed by `id()` of a pool list, not its contents — safe because a
            TOPIC/SUBJECT/GLOBAL pool is the literal same list object across every
            subtopic sharing that scope within one script run, never mutated in place.
            Pass ONE shared dict across many calls to fit each level once instead of once
            per subtopic — with ~900 subtopics backing off to a ~1-second GLOBAL fit, the
            unmemoized version does not finish in a reasonable time. Omit (default None)
            for a single, isolated call — every unit test does this and is unaffected.

    Returns:
        The resolved prior. Always returns something — GLOBAL is the floor.
    """
    cache = level_cache if level_cache is not None else {}

    for level in LEVELS:
        rows = pools.get(level, [])
        key = id(rows)
        if key not in cache:
            cache[key] = _attempt_level(rows)
        attempt = cache[key]
        if attempt is not None:
            alpha, beta, n = attempt
            return PriorResolution(alpha=alpha, beta=beta, source_level=level, source_n=n)

    return PriorResolution(
        alpha=fallback_alpha,
        beta=fallback_beta,
        source_level="GLOBAL",
        source_n=len(pools.get("GLOBAL", [])),
    )


async def gather_all_subtopic_pools(db: AsyncSession) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """For every ACTIVE subtopic, the pooled observation rows at each backoff level.

    One query per level, not per subtopic — the topic/subject/global pools are the same
    query result reused across every subtopic that shares that scope, which is what makes
    this tractable at curriculum scale rather than one query per subtopic.
    """
    subtopics = await db.execute(
        text(
            """
            SELECT s.id AS subtopic_id, s.curriculum_topic_id, ct.subject_id
            FROM subtopics s
            JOIN curriculum_topics ct ON ct.id = s.curriculum_topic_id
            WHERE s.is_active = TRUE AND ct.is_active = TRUE
            """
        )
    )
    subtopic_scope = {
        str(row.subtopic_id): (str(row.curriculum_topic_id), str(row.subject_id)) for row in subtopics.all()
    }

    # One row per (student, subtopic) with qualifying evidence, joined through the
    # objective bridge exactly as GapService.calculate_gap_states_for_attempt resolves it
    # (ADR-003) — the same path, not a parallel one.
    observations = await db.execute(
        text(
            """
            SELECT sa.student_id, s.id AS subtopic_id, s.curriculum_topic_id, ct.subject_id,
                   count(*) AS total, count(*) FILTER (WHERE sr.is_correct) AS correct
            FROM student_responses sr
            JOIN student_attempts sa    ON sa.id = sr.attempt_id
            JOIN question_bank qb       ON qb.id = sr.question_id
            JOIN subtopic_objectives so ON so.learning_objective_id = qb.learning_objective_id
            JOIN subtopics s            ON s.id = so.subtopic_id
            JOIN curriculum_topics ct   ON ct.id = s.curriculum_topic_id
            WHERE sr.answer_given <> '' AND sa.status = 'COMPLETED'
              AND s.is_active = TRUE AND ct.is_active = TRUE
            GROUP BY 1, 2, 3, 4
            """
        )
    )

    global_pool: list[tuple[int, int]] = []
    by_topic: dict[str, list[tuple[int, int]]] = {}
    by_subject: dict[str, list[tuple[int, int]]] = {}
    by_subtopic: dict[str, list[tuple[int, int]]] = {}

    for row in observations.all():
        pair = (int(row.total), int(row.correct))
        global_pool.append(pair)
        by_topic.setdefault(str(row.curriculum_topic_id), []).append(pair)
        by_subject.setdefault(str(row.subject_id), []).append(pair)
        by_subtopic.setdefault(str(row.subtopic_id), []).append(pair)

    result: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for subtopic_id, (topic_id, subject_id) in subtopic_scope.items():
        result[subtopic_id] = {
            "SUBTOPIC": by_subtopic.get(subtopic_id, []),
            "TOPIC": by_topic.get(topic_id, []),
            "SUBJECT": by_subject.get(subject_id, []),
            "GLOBAL": global_pool,
        }
    return result


async def write_priors(db: AsyncSession, resolutions: dict[str, PriorResolution]) -> None:
    """Upsert one mastery_priors row per subtopic. Idempotent: a rerun with identical
    input data overwrites with the same values."""
    for subtopic_id, resolution in resolutions.items():
        await db.execute(
            text(
                """
                INSERT INTO mastery_priors (subtopic_id, alpha, beta, source_level, source_n, fitted_at)
                VALUES (:subtopic_id, :alpha, :beta, :source_level, :source_n, NOW())
                ON CONFLICT (subtopic_id) DO UPDATE SET
                    alpha = EXCLUDED.alpha,
                    beta = EXCLUDED.beta,
                    source_level = EXCLUDED.source_level,
                    source_n = EXCLUDED.source_n,
                    fitted_at = EXCLUDED.fitted_at
                """
            ),
            {
                "subtopic_id": subtopic_id,
                "alpha": resolution.alpha,
                "beta": resolution.beta,
                "source_level": resolution.source_level,
                "source_n": resolution.source_n,
            },
        )


def render(resolutions: dict[str, PriorResolution]) -> str:
    counts_by_level: dict[str, int] = {level: 0 for level in LEVELS}
    for resolution in resolutions.values():
        counts_by_level[resolution.source_level] += 1

    lines = [
        "",
        "=" * 78,
        "MASTERY PRIOR CALIBRATION",
        "=" * 78,
        "",
        f"  Active subtopics resolved   {len(resolutions):>8}",
        "",
        "  Resolution by level:",
    ]
    for level in LEVELS:
        lines.append(f"    {level:<10} {counts_by_level[level]:>8}")
    lines.append("")
    return "\n".join(lines)


async def run(apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            pools_by_subtopic = await gather_all_subtopic_pools(db)
            if not pools_by_subtopic:
                log.warning("no_active_subtopics_found")
                return 0

            # One shared cache across the whole loop: a TOPIC/SUBJECT/GLOBAL pool is the
            # same object for every subtopic in that scope, so it is fit once here rather
            # than once per subtopic — see resolve_prior's level_cache docstring.
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

            print(render(resolutions))

            if apply:
                await write_priors(db, resolutions)
                await db.commit()
                log.info("mastery_priors_written", count=len(resolutions))
            else:
                await db.rollback()
                log.warning("dry_run_no_changes_made", hint="re-run with --apply to write")
    finally:
        await engine.dispose()

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Report without writing")
    group.add_argument("--apply", action="store_true", help="Write mastery_priors")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
