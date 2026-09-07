"""Measure the accuracy of the learning-objective matching pipeline.

`scripts/map_questions_to_lo.py` routes every old-subtopic -> new-objective decision into
one of three bands: auto-bind at >= 0.85, LLM adjudication between 0.60 and 0.85, and
unmatched below 0.60. The embedding thresholds were calibrated against measured pair
distributions. The adjudicating model never was — there is no precision figure, no decline
rate, and no measure of how often a reviewer overrode it.

This script produces those numbers. It is READ-ONLY in every mode.

WHAT IS AND IS NOT MEASURED — read before quoting any figure
-------------------------------------------------------------
Items reach the review queue only when similarity was ambiguous or the model declined, so
the ground truth already in `lo_review_items` is a biased sample:

  * Adjudicator agreement is measured on the HARD SUBSET ONLY. It is a lower bound on
    overall precision, and must never be quoted as "pipeline accuracy".
  * The auto-bind band has NO stored labels — those questions never entered the queue.
    Mode 2 exports a sample for hand-labelling; mode 3 scores it.
  * REJECTED means "no candidate was right", which is a different signal from the model
    and the reviewer disagreeing about which candidate. They are counted separately.

RECOVERING THE AUTO-BIND BAND
-----------------------------
`map_questions_to_lo.py` writes report files for the review, unmatched, and LLM-decided
groups, but writes NOTHING for groups it auto-bound — `auto_matched` is only a counter in
a log line. The auto-bound set is therefore recovered by elimination: any snapshot group
absent from all three report files was auto-bound. That is exact.

Their similarities are recomputed rather than read, because they were never stored. This is
safe for the reason it would not have been otherwise: only the OLD side of each comparison
was transient. The NEW objectives' vectors are persisted in `learning_objectives.embedding`
and are the same ones the remap compared against, so re-embedding the old objective text
with the same configured model reproduces the original score.

It is also self-checking. Every recovered auto-bound similarity must be >= the auto-bind
threshold; any that is not means the embedding configuration has drifted since the remap,
and the run aborts rather than reporting numbers derived from a different model.

Usage (from backend/):
    python -m scripts.eval_lo_matching --mode report
    python -m scripts.eval_lo_matching --mode export-sample \\
        --snapshot ../backups/question_subtopic_snapshot_<ts>.json \\
        --reports ../backups --n 60 --out eval_sample.csv
    python -m scripts.eval_lo_matching --mode score-sample --in eval_sample_labeled.csv
"""

import argparse
import asyncio
import csv
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.eval_metrics import Rate, rate, stratify  # noqa: E402
from app.ai.similarity import cosine_similarity, embed_all  # noqa: E402
from app.core.config import settings  # noqa: E402
from scripts.map_questions_to_lo import (  # noqa: E402
    AUTO_BIND_THRESHOLD as PIPELINE_AUTO_BIND_THRESHOLD,
)
from scripts.map_questions_to_lo import (  # noqa: E402
    group_snapshot,
    load_candidate_objectives,
)

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# The band this evaluation describes. Pinned as a literal, and checked against the
# pipeline's live value below: if someone retunes the pipeline, an already-published report
# must not be silently reinterpreted against the new threshold — but neither should the two
# drift apart unnoticed.
AUTO_BIND_THRESHOLD = 0.85

# Strata for the hand-labelled auto-bind sample. Precision is expected to vary across the
# band — a single pooled number would hide exactly the signal that says whether the
# threshold sits in the right place.
SAMPLE_STRATUM_EDGES = [0.85, 0.90, 0.95]

# The adjudicated band spans 0.60-0.85, so auto-bind strata would pool every row into the
# single "below" bucket and report one undifferentiated number.
ADJUDICATION_STRATUM_EDGES = [0.60, 0.70, 0.80]


def infer_strata(similarities: list[float]) -> tuple[list[float], str]:
    """Pick strata matching the band the sample came from.

    A labelled file may hold auto-bound rows or adjudicated rows; the two occupy disjoint
    similarity ranges and need different cut points. Inferred rather than assumed, and the
    choice is reported, because silently applying the wrong strata produces a single pooled
    bucket that looks like a result.
    """
    if similarities and max(similarities) < AUTO_BIND_THRESHOLD:
        return ADJUDICATION_STRATUM_EDGES, "adjudicated (0.60-0.85)"
    return SAMPLE_STRATUM_EDGES, "auto-bind (>= 0.85)"


# Below this many labelled rows a stratum's interval is too wide to support any decision,
# so the sampler takes everything available rather than a proportional share.
MIN_PER_STRATUM = 15

# Outcome classes. Named rather than boolean because "the model was wrong" and "the model
# declined and a human then found a match" are different failures with different costs.
AGREEMENT = "agreement"
DISAGREEMENT = "disagreement"
DECLINED_RECOVERED = "declined_recovered"
DECLINED_CONFIRMED = "declined_confirmed"
SUGGESTED_REJECTED = "suggested_rejected"
UNRESOLVED = "unresolved"

VALID_VERDICTS = frozenset({"correct", "wrong", "unsure"})


def _warn_if_threshold_drifted() -> None:
    """Surface a pipeline retune rather than letting the report silently mislabel its band."""
    if PIPELINE_AUTO_BIND_THRESHOLD != AUTO_BIND_THRESHOLD:
        log.warning(
            "auto_bind_threshold_drift",
            evaluation_assumes=AUTO_BIND_THRESHOLD,
            pipeline_now=PIPELINE_AUTO_BIND_THRESHOLD,
            hint="Questions bound under the old threshold are still being measured against it.",
        )


class EvalError(Exception):
    """Raised when the evaluation cannot produce a trustworthy number."""


@dataclass(frozen=True)
class ReviewOutcome:
    """One review-queue item, flattened to what the metrics need."""

    source_code: str
    status: str
    llm_suggested_code: str | None
    chosen_code: str | None
    question_count: int
    top_similarity: float | None


def classify_outcome(outcome: ReviewOutcome) -> str:
    """Assign one review item to an outcome class.

    A PENDING or SPLIT item is UNRESOLVED: no human has ruled, so it carries no ground
    truth and must not land in any denominator. Counting it as a failure would penalise
    the model for a queue that has not been worked through.
    """
    if outcome.status == "APPROVED":
        if outcome.llm_suggested_code is None:
            # The model declined; a reviewer found a match anyway.
            return DECLINED_RECOVERED
        if outcome.chosen_code is None:
            # APPROVED without a chosen objective violates a DB check constraint. Treat
            # as unresolved rather than inventing an interpretation.
            return UNRESOLVED
        return AGREEMENT if outcome.llm_suggested_code == outcome.chosen_code else DISAGREEMENT

    if outcome.status == "REJECTED":
        # The reviewer found no candidate correct. If the model had also declined, they
        # agree; if the model had suggested one, the model was wrong.
        return DECLINED_CONFIRMED if outcome.llm_suggested_code is None else SUGGESTED_REJECTED

    return UNRESOLVED


def compute_report(outcomes: list[ReviewOutcome]) -> dict[str, Any]:
    """Derive every review-queue metric from classified outcomes.

    Pure: takes rows, returns numbers. The database query lives in the caller so that this
    is testable without one.
    """
    classified = [(o, classify_outcome(o)) for o in outcomes]
    counts: dict[str, int] = defaultdict(int)
    for _, label in classified:
        counts[label] += 1

    resolved = [(o, label) for o, label in classified if label != UNRESOLVED]

    agree = counts[AGREEMENT]
    disagree = counts[DISAGREEMENT]

    # Blast-radius weighting: a wrong call on a 300-question subtopic is not equivalent to
    # one on a 3-question subtopic. The review queue is ordered by question_count for the
    # same reason, so the accuracy metric is too.
    weighted_agree = sum(o.question_count for o, label in classified if label == AGREEMENT)
    weighted_total = sum(o.question_count for o, label in classified if label in (AGREEMENT, DISAGREEMENT))

    declined_total = counts[DECLINED_RECOVERED] + counts[DECLINED_CONFIRMED]
    suggested_resolved = agree + disagree + counts[SUGGESTED_REJECTED]

    disagreement_similarities = [
        o.top_similarity for o, label in classified if label == DISAGREEMENT and o.top_similarity is not None
    ]

    return {
        "counts": dict(counts),
        "resolved_total": len(resolved),
        "adjudicator_agreement": rate(agree, agree + disagree),
        "blast_radius_weighted_agreement": rate(weighted_agree, weighted_total),
        "decline_rate": rate(declined_total, declined_total + suggested_resolved),
        "decline_recoverability": rate(counts[DECLINED_RECOVERED], declined_total),
        "rejection_rate": rate(counts[DECLINED_CONFIRMED] + counts[SUGGESTED_REJECTED], len(resolved)),
        "disagreement_similarities": disagreement_similarities,
    }


def identify_auto_bound(
    snapshot_codes: set[str],
    review_codes: set[str],
    unmatched_codes: set[str],
    llm_decision_codes: set[str],
) -> set[str]:
    """Recover the set of auto-bound groups by elimination.

    The remap writes no record of what it auto-bound, but it writes every other outcome.
    A snapshot group in none of those files was auto-bound. Exact, not inferred.
    """
    return snapshot_codes - review_codes - unmatched_codes - llm_decision_codes


def select_sample(
    similarities: list[float],
    n: int,
    seed: int,
    edges: list[float] | None = None,
    min_per_stratum: int = MIN_PER_STRATUM,
) -> list[int]:
    """Choose indices to hand-label, stratified across the auto-bind band.

    Deterministic for a given seed so a reviewer can stop half way and resume against the
    same sample, and so a published result can be reproduced.

    A stratum holding fewer than `min_per_stratum` rows contributes all of them: taking a
    proportional share of a thin stratum yields an interval too wide to support any
    decision, and the marginal labelling cost is small.
    """
    buckets = stratify(similarities, edges or SAMPLE_STRATUM_EDGES)
    # The sub-threshold bucket is a data-integrity alarm, not a stratum to sample.
    real_strata = {label: idx for label, idx in buckets.items() if not label.startswith("<")}

    rng = random.Random(seed)
    total_available = sum(len(idx) for idx in real_strata.values())
    if total_available == 0:
        return []

    chosen: list[int] = []
    for label in sorted(real_strata):
        indices = real_strata[label]
        if not indices:
            continue
        proportional = round(n * len(indices) / total_available)
        take = min(len(indices), max(proportional, min(min_per_stratum, len(indices))))
        chosen.extend(rng.sample(indices, take))

    return sorted(chosen)


def score_labelled(rows: list[dict[str, str]], edges: list[float] | None = None) -> dict[str, Any]:
    """Score a hand-labelled sample, per stratum.

    `unsure` rows are excluded from BOTH numerator and denominator and reported separately.
    An unsure share above roughly 15% means the sample or the labelling instructions are
    the problem, not the model, and the precision figure should not be trusted.

    An unrecognised verdict raises. Coercing it to `wrong` would understate precision
    silently, which is the worst available failure for a measurement tool.
    """
    per_stratum: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "wrong": 0, "unsure": 0})
    similarities: list[float] = []
    verdicts: list[str] = []

    for line_number, row in enumerate(rows, start=2):  # start=2: row 1 is the CSV header
        verdict = (row.get("verdict") or "").strip().lower()
        if verdict not in VALID_VERDICTS:
            raise EvalError(
                f"Row {line_number}: unrecognised verdict {verdict!r}. "
                f"Expected one of {sorted(VALID_VERDICTS)}. "
                "Every row must be labelled — an unlabelled sample cannot be scored."
            )
        try:
            similarity = float(row["similarity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EvalError(f"Row {line_number}: missing or non-numeric similarity") from exc

        similarities.append(similarity)
        verdicts.append(verdict)

    chosen_edges, band_name = infer_strata(similarities)
    buckets = stratify(similarities, edges or chosen_edges)
    for label, indices in buckets.items():
        for index in indices:
            per_stratum[label][verdicts[index]] += 1

    results: dict[str, Rate] = {}
    for label, tally in per_stratum.items():
        scored = tally["correct"] + tally["wrong"]
        results[label] = rate(tally["correct"], scored)

    by_confidence: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "wrong": 0, "unsure": 0})
    for row, verdict in zip(rows, verdicts, strict=True):
        stated = (row.get("model_confidence") or "").strip().lower()
        if stated:
            by_confidence[stated][verdict] += 1

    total_correct = sum(t["correct"] for t in per_stratum.values())
    total_wrong = sum(t["wrong"] for t in per_stratum.values())
    total_unsure = sum(t["unsure"] for t in per_stratum.values())

    # Blast-radius weighting. One wrong call on a 115-question group outweighs a dozen
    # right calls on 5-question groups, and the group-level rate hides that entirely.
    weighted_correct = 0
    weighted_scored = 0
    weighted_unsure = 0
    for row, verdict in zip(rows, verdicts, strict=True):
        try:
            questions = int(row.get("question_count") or 0)
        except (TypeError, ValueError):
            questions = 0
        if verdict == "unsure":
            weighted_unsure += questions
            continue
        weighted_scored += questions
        if verdict == "correct":
            weighted_correct += questions

    confidence_results = {
        stated: rate(tally["correct"], tally["correct"] + tally["wrong"]) for stated, tally in by_confidence.items()
    }

    return {
        "per_stratum": results,
        "per_stratum_counts": {k: dict(v) for k, v in per_stratum.items()},
        "by_confidence": confidence_results,
        "by_confidence_counts": {k: dict(v) for k, v in by_confidence.items()},
        "band": band_name,
        "overall": rate(total_correct, total_correct + total_wrong),
        "overall_weighted": rate(weighted_correct, weighted_scored),
        "unsure_questions": weighted_unsure,
        "unsure_count": total_unsure,
        "unsure_rate": rate(total_unsure, total_correct + total_wrong + total_unsure),
    }


async def load_outcomes(db: AsyncSession) -> list[ReviewOutcome]:
    """Read every review item, joined to the objective a reviewer chose."""
    result = await db.execute(
        text(
            """
            SELECT r.source_code,
                   r.status,
                   r.llm_suggested_code,
                   r.question_count,
                   r.candidates,
                   lo.canonical_code AS chosen_code
            FROM lo_review_items r
            LEFT JOIN learning_objectives lo ON lo.id = r.chosen_objective_id
            ORDER BY r.question_count DESC, r.source_code
            """
        )
    )

    outcomes: list[ReviewOutcome] = []
    for row in result.mappings():
        candidates = row["candidates"] or []
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        top = candidates[0].get("similarity") if candidates else None
        outcomes.append(
            ReviewOutcome(
                source_code=row["source_code"],
                status=row["status"],
                llm_suggested_code=row["llm_suggested_code"],
                chosen_code=row["chosen_code"],
                question_count=int(row["question_count"] or 0),
                top_similarity=float(top) if top is not None else None,
            )
        )
    return outcomes


def render_report(report: dict[str, Any]) -> str:
    """Format the review-queue metrics, caveats first."""
    lines = [
        "",
        "=" * 78,
        "LO MATCHING — REVIEW QUEUE EVALUATION",
        "=" * 78,
        "",
        "SCOPE — read before quoting any figure below.",
        "  Items reach the review queue only when embedding similarity was ambiguous or",
        "  the adjudicating model declined. These rates therefore describe the HARD",
        "  SUBSET of decisions, not the pipeline as a whole. Adjudicator agreement here",
        "  is a LOWER BOUND on overall precision.",
        f"  The auto-bind band (>= {AUTO_BIND_THRESHOLD}) has no stored labels and is not",
        "  measured here — use --mode export-sample and --mode score-sample for that.",
        "",
        "-" * 78,
        f"Resolved items: {report['resolved_total']}",
        "",
    ]
    for label, count in sorted(report["counts"].items()):
        lines.append(f"  {label:<22} {count:>5}")

    lines += [
        "",
        "-" * 78,
        "RATES (95% Wilson intervals)",
        "",
        f"  Adjudicator agreement          {report['adjudicator_agreement'].format()}",
        f"    ...weighted by question count {report['blast_radius_weighted_agreement'].format()}",
        f"  Decline rate                   {report['decline_rate'].format()}",
        f"  Decline recoverability         {report['decline_recoverability'].format()}",
        f"  Rejection rate                 {report['rejection_rate'].format()}",
        "",
        "  Decline recoverability is how often a human found a match after the model",
        "  declined. High means the model over-declines, which costs review time but not",
        "  correctness. Low means its declines were genuine.",
        "",
    ]

    similarities = report["disagreement_similarities"]
    if similarities:
        lines += [
            "-" * 78,
            "DISAGREEMENTS BY TOP-CANDIDATE SIMILARITY",
            "  Where the reviewer overrode the model, how similar was its top candidate?",
            "",
        ]
        buckets = stratify(similarities, [0.60, 0.70, 0.80])
        for label, indices in buckets.items():
            if indices:
                lines.append(f"  {label:<12} {len(indices):>4}")
        lines.append("")

    return "\n".join(lines)


async def run_report() -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            outcomes = await load_outcomes(db)
            # Read-only by construction: no writes are issued, and the session is rolled
            # back so an accidental future write cannot survive this path.
            await db.rollback()
    finally:
        await engine.dispose()

    if not outcomes:
        log.warning("no_review_items_found", hint="Has the remap been run against this database?")
    print(render_report(compute_report(outcomes)))
    return 0


def _codes_in(path: Path) -> set[str]:
    """Old canonical codes recorded in one of the remap's report files."""
    if not path.exists():
        return set()
    items = json.loads(path.read_text())
    return {item["old_canonical_code"] for item in items if "old_canonical_code" in item}


def _latest(report_dir: Path, prefix: str) -> Path | None:
    """Most recent report file of a kind. The remap writes one per run."""
    matches = sorted(report_dir.glob(f"question_remap_{prefix}_*.json"))
    return matches[-1] if matches else None


async def run_export_sample(snapshot_path: Path, report_dir: Path, n: int, seed: int, out_path: Path) -> int:
    """Export a stratified sample of AUTO-BOUND groups for hand labelling."""
    if not snapshot_path.exists():
        log.error("snapshot_not_found", path=str(snapshot_path))
        return 1

    snapshot = json.loads(snapshot_path.read_text())
    groups = group_snapshot(snapshot)

    review = _codes_in(_latest(report_dir, "review") or Path("/nonexistent"))
    unmatched = _codes_in(_latest(report_dir, "unmatched") or Path("/nonexistent"))
    decided = _codes_in(_latest(report_dir, "llm_decisions") or Path("/nonexistent"))

    if not (review or unmatched or decided):
        log.error(
            "no_remap_reports_found",
            dir=str(report_dir),
            hint="Auto-bound groups are identified by elimination and need these files.",
        )
        return 1

    auto_bound = identify_auto_bound(set(groups), review, unmatched, decided)
    log.info(
        "auto_bound_identified",
        snapshot_groups=len(groups),
        auto_bound=len(auto_bound),
        review=len(review),
        unmatched=len(unmatched),
        llm_decided=len(decided),
    )
    if not auto_bound:
        log.error("no_auto_bound_groups", hint="Every group was reviewed, decided, or unmatched.")
        return 1

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            candidates = await load_candidate_objectives(db)
            await db.rollback()
    finally:
        await engine.dispose()

    ordered = [groups[code] for code in sorted(auto_bound)]
    log.info("embedding_old_objectives", count=len(ordered))
    vectors = await embed_all([g["learning_objective"] for g in ordered])

    rows: list[dict[str, Any]] = []
    for group, vector in zip(ordered, vectors, strict=True):
        pool = candidates.get(group["subject_code"], [])
        if not pool:
            continue
        # load_candidate_objectives has already run parse_vector over these.
        scored = [(cosine_similarity(vector, c["embedding"]), c) for c in pool if c["embedding"]]
        if not scored:
            continue
        best_score, best = max(scored, key=lambda pair: pair[0])
        rows.append(
            {
                "source_code": group["canonical_code"],
                "old_objective": group["learning_objective"],
                "bound_objective_code": best["canonical_code"],
                "bound_objective_text": best["learning_objective"],
                "question_count": len(group["question_ids"]),
                "similarity": round(best_score, 4),
                "verdict": "",
            }
        )

    drifted = [r for r in rows if r["similarity"] < AUTO_BIND_THRESHOLD]
    if drifted:
        # These groups were auto-bound, so at remap time they scored above the threshold.
        # Scoring below it now means the embedding configuration has changed, and every
        # similarity in this export describes a different model than the one that decided.
        raise EvalError(
            f"{len(drifted)} of {len(rows)} recovered auto-bound similarities fall below "
            f"{AUTO_BIND_THRESHOLD}, so the embedding configuration has drifted since the remap. "
            "Sampling would stratify on scores the pipeline never saw. Restore the original "
            "LLM_EMBEDDINGS_MODEL and LLM_EMBEDDINGS_DIMENSIONS, or evaluate a fresh remap run."
        )

    picked = select_sample([r["similarity"] for r in rows], n=n, seed=seed)
    sample = [rows[i] for i in picked]

    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["verdict"])
        writer.writeheader()
        writer.writerows(sample)

    log.info("sample_written", file=str(out_path), rows=len(sample), seed=seed, pool=len(rows))
    print(
        f"\nWrote {len(sample)} rows to {out_path}.\n"
        "Fill the 'verdict' column with correct / wrong / unsure, then run:\n"
        f"  python -m scripts.eval_lo_matching --mode score-sample --in {out_path}\n"
    )
    return 0


def _chosen_similarity(record: dict[str, Any]) -> float | None:
    """Similarity of the candidate the model actually picked.

    The record stores the top three candidates with their scores and the chosen code
    separately, so the score has to be looked up rather than assumed to be the highest —
    the model frequently picks the second candidate, and that is precisely the case where
    similarity and meaning disagree.
    """
    for candidate in record.get("candidates", []):
        if candidate.get("canonical_code") == record.get("chosen"):
            return float(candidate["similarity"])
    return None


def run_export_decisions(decisions_path: Path, out_path: Path) -> int:
    """Export every LLM-adjudicated group for hand labelling.

    This is the population that measures the adjudicator, and nothing else does. Groups the
    model decided were bound immediately and never entered the review queue, so no human
    ever ruled on them: `lo_review_items.llm_suggested_code` is NULL for every row because
    the queue only receives declines and un-adjudicated items.

    Every group is exported rather than a sample. There are tens of them, not thousands, and
    a census removes sampling error from a figure that is already interval-bound by a small n.
    """
    if not decisions_path.exists():
        log.error("decisions_file_not_found", path=str(decisions_path))
        return 1

    records = json.loads(decisions_path.read_text())
    if not records:
        log.error("decisions_file_empty", path=str(decisions_path))
        return 1

    rows = []
    for record in records:
        similarity = _chosen_similarity(record)
        rows.append(
            {
                "source_code": record["old_canonical_code"],
                "old_objective": record["old_learning_objective"],
                "chosen_code": record["chosen"],
                "chosen_objective": next(
                    (
                        c["learning_objective"]
                        for c in record.get("candidates", [])
                        if c.get("canonical_code") == record["chosen"]
                    ),
                    "",
                ),
                "model_confidence": record.get("confidence") or "",
                "model_reason": record.get("reason") or "",
                "question_count": record["question_count"],
                # Falls back to 0.0 only so the row is still scoreable; the stratifier
                # buckets it under "<" where it is visible rather than silently pooled.
                "similarity": similarity if similarity is not None else 0.0,
                "verdict": "",
            }
        )

    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    total_questions = sum(r["question_count"] for r in rows)
    log.info("decisions_exported", file=str(out_path), groups=len(rows), questions=total_questions)
    print(
        f"\nWrote {len(rows)} adjudicated groups ({total_questions} questions) to {out_path}.\n"
        "Label the 'verdict' column with correct / wrong / unsure, then run:\n"
        f"  python -m scripts.eval_lo_matching --mode score-sample --in {out_path}\n"
    )
    return 0


def run_score_sample(in_path: Path) -> int:
    if not in_path.exists():
        log.error("labelled_file_not_found", path=str(in_path))
        return 1

    with in_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        log.error("labelled_file_empty", path=str(in_path))
        return 1

    result = score_labelled(rows)

    print("")
    print("=" * 78)
    print(f"LO MATCHING — PRECISION, {result['band'].upper()} BAND (hand-labelled)")
    print("=" * 78)
    print("")
    for label in sorted(result["per_stratum"]):
        counts = result["per_stratum_counts"][label]
        if sum(counts.values()) == 0:
            continue
        print(f"  {label:<12} {result['per_stratum'][label].format()}    {counts}")
    print("")
    if result["by_confidence"]:
        print("")
        print("  CALIBRATION — is the model's self-reported confidence informative?")
        for stated in ("high", "medium", "low"):
            if stated in result["by_confidence"]:
                counts = result["by_confidence_counts"][stated]
                print(f"    {stated:<8} {result['by_confidence'][stated].format()}    {counts}")
        print("")
        print("    Confidence is useful only if precision falls as the stated level falls.")
        print("    Flat precision across levels means the label carries no information and")
        print("    must not be used to decide what skips human review.")
        print("")

    print(f"  OVERALL               {result['overall'].format()}")
    print(f"  WEIGHTED BY QUESTIONS {result['overall_weighted'].format()}")
    print("")
    print("    Weighted precision counts questions, not decisions. A gap between the two")
    print("    means the errors landed on the large groups.")
    print("")
    print(f"  Unsure       {result['unsure_rate'].format()}  ({result['unsure_questions']} questions)")
    if result["unsure_rate"].point > 0.15:
        print("")
        print("  ⚠ Unsure rate above 15%. Either the labelling task is under-specified, or")
        print("    the source objectives are compound and cannot be ruled on from their text")
        print("    alone. Check which before treating the precision figure as settled.")
    print("")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--mode",
        required=True,
        choices=["report", "export-sample", "export-decisions", "score-sample"],
    )
    parser.add_argument("--decisions", type=Path, help="question_remap_llm_decisions_*.json (export-decisions)")
    parser.add_argument("--snapshot", type=Path, help="Wipe snapshot JSON (export-sample)")
    parser.add_argument("--reports", type=Path, default=Path("../backups"), help="Remap report directory")
    parser.add_argument("--n", type=int, default=60, help="Target sample size (export-sample)")
    parser.add_argument("--seed", type=int, default=0, help="Sampling seed — keep fixed to reproduce a sample")
    parser.add_argument("--out", type=Path, default=Path("eval_sample.csv"))
    parser.add_argument("--in", dest="in_path", type=Path, help="Labelled CSV (score-sample)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _warn_if_threshold_drifted()
    try:
        if args.mode == "report":
            return asyncio.run(run_report())
        if args.mode == "export-decisions":
            if not args.decisions:
                log.error("decisions_required", hint="--decisions is required for export-decisions")
                return 1
            return run_export_decisions(args.decisions, args.out)
        if args.mode == "export-sample":
            if not args.snapshot:
                log.error("snapshot_required", hint="--snapshot is required for export-sample")
                return 1
            return asyncio.run(run_export_sample(args.snapshot, args.reports, args.n, args.seed, args.out))
        if not args.in_path:
            log.error("input_required", hint="--in is required for score-sample")
            return 1
        return run_score_sample(args.in_path)
    except EvalError as exc:
        log.error("evaluation_aborted", reason=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
