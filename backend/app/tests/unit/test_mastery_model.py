"""Unit tests for the Beta-Binomial mastery estimator.

Pure by design — no database, no mocks, no clock. If a test here needs a fixture, the
estimator has grown a dependency it should not have.

These replace `TestMasteryWeightingFormulas` in test_gap_calculation.py, which reimplemented
the formula inside the test file and asserted against its own copy. Every test in that class
would have passed if gap_service.py had been deleted.
"""

import pytest

from app.services.mastery_model import (
    Observation,
    estimate,
    prior_mean,
)

# Beta(2, 3): prior mean 0.4 — the Developing/Needs-Work boundary, which is the correct
# neutral assumption for a student we know nothing about — and prior strength 5, matching
# the intuition behind the old min(n/5, 1) confidence ramp.
ALPHA = 2.0
BETA = 3.0
DECAY = 0.7


def _obs(correct: int, total: int, age: int = 0) -> Observation:
    return Observation(correct=correct, total=total, age_index=age)


class TestNoEvidence:
    def test_estimate_when_no_observations_then_score_equals_prior_mean(self) -> None:
        # With nothing observed the honest answer is the prior, not zero. The old formula
        # had no such state: it could only be reached with a real score in hand.
        result = estimate([], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.score == pytest.approx(prior_mean(ALPHA, BETA))
        assert result.score == pytest.approx(0.4)

    def test_estimate_when_no_observations_then_confidence_is_zero(self) -> None:
        result = estimate([], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.confidence == pytest.approx(0.0)

    def test_estimate_when_no_observations_then_effective_n_is_zero(self) -> None:
        assert estimate([], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY).effective_n == pytest.approx(0.0)


class TestShrinkage:
    """The property the old `× 0.7` multiplier was hand-approximating.

    A prior does this correctly: the discount weakens automatically as evidence accumulates,
    where a fixed multiplier applied the same 30% haircut to 3 questions and to 30.
    """

    def test_estimate_when_all_correct_then_score_below_one_due_to_shrinkage(self) -> None:
        result = estimate([_obs(5, 5)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.score < 1.0

    def test_estimate_when_all_incorrect_then_score_above_zero_due_to_shrinkage(self) -> None:
        result = estimate([_obs(0, 5)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.score > 0.0

    def test_estimate_when_single_response_then_score_not_exactly_zero_or_one(self) -> None:
        # The defect adaptive_selector.py's own docstring names: "a subtopic scored on one
        # response yields mastery of exactly 0.0 or 1.0". A Beta posterior mean is in the
        # OPEN interval (0,1) by construction, so this is now structurally impossible.
        one_right = estimate([_obs(1, 1)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        one_wrong = estimate([_obs(0, 1)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert 0.0 < one_right.score < 1.0
        assert 0.0 < one_wrong.score < 1.0

    def test_estimate_when_evidence_grows_then_score_approaches_raw_proportion(self) -> None:
        # Shrinkage must fade, not persist. A student with a long record should be judged
        # on that record, not on the prior.
        small = estimate([_obs(8, 10)], prior_alpha=ALPHA, prior_beta=BETA, decay=1.0)
        large = estimate(
            [_obs(80, 100)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=1.0,
        )
        raw = 0.8
        assert abs(large.score - raw) < abs(small.score - raw)

    def test_estimate_when_beta_2_3_prior_and_five_of_five_then_score_is_zero_point_seven(self) -> None:
        # Continuity at the boundary that matters most. The old code stipulated
        # `current_score * 0.7` for a first diagnostic; under Beta(2,3) a perfect 5/5
        # yields (5+2)/(5+5) = 0.70 as a CONSEQUENCE of the model rather than a constant.
        result = estimate([_obs(5, 5)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.score == pytest.approx(0.7)


class TestConfidence:
    """Confidence is posterior SD, not a second hand-rolled ramp."""

    def test_estimate_when_evidence_grows_then_confidence_increases_monotonically(self) -> None:
        confidences = [
            estimate([_obs(n // 2, n)], prior_alpha=ALPHA, prior_beta=BETA, decay=1.0).confidence
            for n in (1, 2, 5, 10, 40, 100)
        ]
        assert confidences == sorted(confidences)
        assert confidences[0] < confidences[-1]

    def test_estimate_when_evidence_is_large_then_confidence_approaches_one(self) -> None:
        result = estimate([_obs(500, 1000)], prior_alpha=ALPHA, prior_beta=BETA, decay=1.0)
        assert result.confidence > 0.9

    def test_estimate_when_confidence_computed_then_always_within_unit_interval(self) -> None:
        # Clamped: the SD ratio can drift marginally outside [0,1] through floating point,
        # and gap_states.confidence carries a BETWEEN 0.0 AND 1.0 check constraint.
        for obs in ([], [_obs(0, 1)], [_obs(1, 1)], [_obs(999, 1000)]):
            result = estimate(obs, prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
            assert 0.0 <= result.confidence <= 1.0


class TestRecencyWeighting:
    """One decay parameter replaces the old 0.65/0.35 and 0.5/0.3/0.2 coefficient sets."""

    def test_estimate_when_recent_and_old_conflict_then_recent_dominates(self) -> None:
        # Improved recently after a poor start: the estimate should follow the improvement.
        improving = estimate(
            [_obs(9, 10, age=0), _obs(1, 10, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=DECAY,
        )
        declining = estimate(
            [_obs(1, 10, age=0), _obs(9, 10, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=DECAY,
        )
        assert improving.score > declining.score

    def test_estimate_when_decay_is_one_then_all_observations_weighted_equally(self) -> None:
        # decay=1 is plain pooling: order must not matter.
        forward = estimate(
            [_obs(9, 10, age=0), _obs(1, 10, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=1.0,
        )
        reversed_order = estimate(
            [_obs(1, 10, age=0), _obs(9, 10, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=1.0,
        )
        assert forward.score == pytest.approx(reversed_order.score)

    def test_estimate_when_decay_is_zero_then_only_most_recent_counts(self) -> None:
        # decay=0 discards all history. 0**0 == 1 in Python, so the most recent observation
        # keeps full weight — the boundary that a naive implementation gets wrong.
        with_history = estimate(
            [_obs(4, 5, age=0), _obs(0, 100, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=0.0,
        )
        alone = estimate([_obs(4, 5, age=0)], prior_alpha=ALPHA, prior_beta=BETA, decay=0.0)
        assert with_history.score == pytest.approx(alone.score)

    def test_estimate_when_decay_between_zero_and_one_then_effective_n_below_raw_total(self) -> None:
        result = estimate(
            [_obs(5, 10, age=0), _obs(5, 10, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=0.5,
        )
        assert result.effective_n == pytest.approx(15.0)  # 10 * 1.0 + 10 * 0.5


class TestDegenerateInput:
    def test_estimate_when_observation_total_is_zero_then_ignored_without_error(self) -> None:
        # A subtopic can appear on an attempt with every answer left blank; gap_service
        # filters those, but the estimator must not depend on that having happened.
        with_empty = estimate(
            [_obs(3, 5, age=0), _obs(0, 0, age=1)],
            prior_alpha=ALPHA,
            prior_beta=BETA,
            decay=DECAY,
        )
        without = estimate([_obs(3, 5, age=0)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert with_empty.score == pytest.approx(without.score)

    def test_estimate_when_all_observations_empty_then_falls_back_to_prior(self) -> None:
        result = estimate([_obs(0, 0), _obs(0, 0)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert result.score == pytest.approx(prior_mean(ALPHA, BETA))
        assert result.confidence == pytest.approx(0.0)

    def test_estimate_when_correct_exceeds_total_then_raises(self) -> None:
        # A miscounted caller must fail loudly rather than produce a plausible score.
        with pytest.raises(ValueError, match="correct"):
            estimate([_obs(6, 5)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)

    def test_estimate_when_counts_negative_then_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            estimate([_obs(-1, 5)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)

    def test_estimate_when_prior_not_positive_then_raises(self) -> None:
        # A Beta is undefined for non-positive parameters; silently substituting a default
        # would hide a misconfiguration behind plausible-looking scores.
        with pytest.raises(ValueError, match="prior"):
            estimate([_obs(1, 1)], prior_alpha=0.0, prior_beta=BETA, decay=DECAY)

    def test_estimate_when_decay_out_of_range_then_raises(self) -> None:
        with pytest.raises(ValueError, match="decay"):
            estimate([_obs(1, 1)], prior_alpha=ALPHA, prior_beta=BETA, decay=1.5)


class TestDeterminism:
    def test_estimate_when_called_twice_then_identical(self) -> None:
        obs = [_obs(3, 5, age=0), _obs(2, 4, age=1)]
        first = estimate(obs, prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        second = estimate(obs, prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        assert first == second

    def test_estimate_result_is_frozen(self) -> None:
        result = estimate([_obs(1, 2)], prior_alpha=ALPHA, prior_beta=BETA, decay=DECAY)
        with pytest.raises((AttributeError, TypeError)):
            result.score = 0.99  # type: ignore[misc]
