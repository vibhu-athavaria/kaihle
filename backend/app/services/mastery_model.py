"""Beta-Binomial mastery estimation.

Pure by design: no database, no I/O, no clock, no randomness. Same discipline as
`services/adaptive_selector.py`, and for the same reason — a number a teacher acts on has to
be reproducible and testable in isolation.

WHAT THIS REPLACES
------------------
Six undocumented coefficients spread across two places in `gap_service.py`:

    mastery = current * 0.7 if is_diagnostic else current * 1.0
    mastery = (current * 0.65) + (prev * 0.35)
    mastery = (current * 0.5) + (prev * 0.3) + (prev2 * 0.2)
    confidence = min(rolling_attempt_count / 5.0, 1.0)

Each was a hand-rolled approximation of something a Beta posterior does exactly:

  * The `× 0.7` diagnostic discount approximates SHRINKAGE TOWARD A PRIOR. Its purpose was
    "don't declare mastery from one cold assessment" — which is what a prior is for. The
    difference is that shrinkage weakens automatically as evidence accumulates, whereas a
    fixed multiplier applied the same 30% haircut to 3 questions and to 30.
  * The 0.65/0.35 and 0.5/0.3/0.2 sets approximate RECENCY WEIGHTING, here one `decay`
    parameter that extends to any number of attempts instead of stopping at three.
  * `min(n/5, 1)` approximates POSTERIOR VARIANCE, which now falls out of the same
    computation rather than being asserted alongside it.

Two interpretable parameters replace six opaque ones, and confidence stops being a separate
claim that could disagree with the score it describes.

WHY THE SCORE NEEDS NO CLAMPING
-------------------------------
A Beta posterior mean lies in the OPEN interval (0, 1) whenever the prior is positive. The
old code needed `max(0.0, min(1.0, mastery))` and still produced exactly 0.0 or 1.0 for a
subtopic scored on a single response — the defect `adaptive_selector.py`'s own docstring
names. That is now structurally impossible rather than clamped after the fact.

CHOOSING THE PRIOR
------------------
Beta(2, 3) is chosen ANALYTICALLY and is NOT an empirical fit. `scripts/calibrate_mastery_prior.py`
exists to derive one from data and currently refuses to: 77% of per-subtopic observations
rest on a single response, so the observed score distribution is bimodal by construction and
a method-of-moments fit returns roughly Beta(0.06, 0.06) — a prior of near-zero strength that
would apply no shrinkage and preserve the very defect this model removes.

Re-run that script once subtopics carry real denominators. Do not hand-tune in the meantime;
the current values and their justification are in `docs/design/MASTERY_MODEL_RATIONALE.md`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    """One attempt's evidence for a single subtopic.

    Counts, not a proportion. 3/5 and 30/50 are both 0.6 but carry very different evidential
    weight, and distinguishing them is the entire point of the model.

    `student_attempt_subtopic_scores` stores only a `score` float and cannot supply these,
    so callers derive counts from `student_responses`. Persisting them on that table is
    still outstanding — until then every consumer pays for the same derivation.
    """

    correct: int
    total: int
    # 0 = most recent attempt, 1 = the one before it, and so on. Not a timestamp: the
    # estimator stays pure, and the caller already knows the ordering.
    age_index: int


@dataclass(frozen=True)
class MasteryEstimate:
    """A posterior, reported with the evidence behind it.

    Frozen because these values are written to `gap_states` and shown to teachers; a mutable
    result invites adjusting an inconvenient number after the fact.
    """

    score: float
    confidence: float
    # Decay-weighted observation count. Not persisted — it exists so the calibration report
    # and the backfill diff can explain WHY a score moved, not just that it did.
    effective_n: float


def prior_mean(prior_alpha: float, prior_beta: float) -> float:
    """Mean of the prior — the score assigned to a student with no evidence at all."""
    return prior_alpha / (prior_alpha + prior_beta)


def _prior_sd(prior_alpha: float, prior_beta: float) -> float:
    """Standard deviation of the prior, the reference point for confidence."""
    total = prior_alpha + prior_beta
    variance = (prior_alpha * prior_beta) / (total * total * (total + 1.0))
    return float(variance**0.5)


def estimate(
    observations: list[Observation],
    prior_alpha: float,
    prior_beta: float,
    decay: float,
) -> MasteryEstimate:
    """Posterior mastery for one subtopic.

    Args:
        observations: Per-attempt counts for this subtopic, any order — `age_index` carries
            the recency, not list position.
        prior_alpha: Beta prior successes. Must be > 0.
        prior_beta: Beta prior failures. Must be > 0.
        decay: Per-attempt recency weight in [0, 1]. 1.0 pools every attempt equally;
            0.0 keeps only the most recent.

    Returns:
        The posterior mean, a confidence derived from posterior SD, and the decay-weighted
        evidence count.

    Raises:
        ValueError: On negative counts, `correct` exceeding `total`, a non-positive prior,
            or a decay outside [0, 1]. All indicate a miscounted or misconfigured caller,
            and returning a plausible-looking score would hide it.
    """
    if prior_alpha <= 0.0 or prior_beta <= 0.0:
        raise ValueError(f"prior parameters must be positive, got alpha={prior_alpha}, beta={prior_beta}")
    if not 0.0 <= decay <= 1.0:
        raise ValueError(f"decay must be in [0, 1], got {decay}")

    weighted_correct = 0.0
    weighted_total = 0.0

    for observation in observations:
        if observation.correct < 0 or observation.total < 0:
            raise ValueError(f"counts must not be negative: correct={observation.correct}, total={observation.total}")
        if observation.correct > observation.total:
            raise ValueError(f"correct ({observation.correct}) cannot exceed total ({observation.total})")
        if observation.total == 0:
            # A subtopic can appear on an attempt with every answer blank. It carries no
            # evidence either way, so it contributes nothing rather than counting as failure.
            continue
        if observation.age_index < 0:
            raise ValueError(f"age_index must not be negative, got {observation.age_index}")

        # 0.0 ** 0 == 1.0 in Python, so decay=0 keeps the most recent observation at full
        # weight and discards the rest — which is the intended reading of "no history".
        weight = decay**observation.age_index
        weighted_correct += weight * observation.correct
        weighted_total += weight * observation.total

    posterior_alpha = weighted_correct + prior_alpha
    posterior_beta = (weighted_total - weighted_correct) + prior_beta

    total = posterior_alpha + posterior_beta
    score = posterior_alpha / total

    posterior_variance = (posterior_alpha * posterior_beta) / (total * total * (total + 1.0))
    posterior_sd = float(posterior_variance**0.5)

    # Confidence is how far the posterior has tightened relative to knowing nothing: 0 with
    # no evidence, approaching 1 as evidence accumulates. Clamped because the ratio can
    # drift marginally outside [0,1] through floating point, and gap_states.confidence
    # carries a BETWEEN 0.0 AND 1.0 check constraint.
    reference_sd = _prior_sd(prior_alpha, prior_beta)
    confidence = 1.0 - (posterior_sd / reference_sd) if reference_sd > 0.0 else 0.0
    confidence = max(0.0, min(1.0, confidence))

    return MasteryEstimate(score=score, confidence=confidence, effective_n=weighted_total)
