"""Unit tests for evaluation metric primitives.

These functions report accuracy for the curriculum-remap pipeline, so their own
correctness is load-bearing: a metric that silently returns a wrong rate produces a
confident, wrong claim about how well the matcher works.

Every test here runs without a database, a clock, or a mock — the module under test is
pure by design.
"""

import pytest

from app.ai.eval_metrics import Rate, rate, stratify, wilson_interval


class TestWilsonInterval:
    """The interval is what keeps a small-n rate honest.

    The remap produced ~71 reviewable decisions. A bare point estimate over that many
    samples invites over-reading, and the normal approximation misbehaves badly near 0
    and 1 — which is exactly where a well-tuned matcher's rates live.
    """

    def test_wilson_interval_when_all_successes_then_upper_bound_is_one(self) -> None:
        low, high = wilson_interval(20, 20)
        assert high == pytest.approx(1.0)
        # The lower bound must stay well below 1.0: 20/20 is not proof of perfection.
        assert low < 0.9

    def test_wilson_interval_when_zero_successes_then_lower_bound_is_zero(self) -> None:
        low, high = wilson_interval(0, 20)
        assert low == pytest.approx(0.0)
        assert high > 0.1

    def test_wilson_interval_when_small_n_then_interval_wider_than_large_n(self) -> None:
        small_low, small_high = wilson_interval(4, 5)
        large_low, large_high = wilson_interval(400, 500)
        assert (small_high - small_low) > (large_high - large_low)

    def test_wilson_interval_when_n_is_zero_then_returns_zero_to_one(self) -> None:
        # No evidence means the full range is admissible, not a ZeroDivisionError.
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_wilson_interval_when_half_successes_then_interval_brackets_point(self) -> None:
        low, high = wilson_interval(50, 100)
        assert low < 0.5 < high

    def test_wilson_interval_when_successes_exceed_trials_then_raises(self) -> None:
        with pytest.raises(ValueError, match="successes"):
            wilson_interval(11, 10)

    def test_wilson_interval_when_negative_successes_then_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            wilson_interval(-1, 10)


class TestRate:
    def test_rate_when_denominator_zero_then_point_is_zero_and_does_not_raise(self) -> None:
        result = rate(0, 0)
        assert result.point == 0.0
        assert result.low == 0.0
        assert result.high == 1.0

    def test_rate_when_half_correct_then_point_is_zero_point_five(self) -> None:
        result = rate(5, 10)
        assert result.point == pytest.approx(0.5)
        assert result.numerator == 5
        assert result.denominator == 10

    def test_rate_when_all_correct_then_point_is_one(self) -> None:
        assert rate(7, 7).point == pytest.approx(1.0)

    def test_rate_is_frozen_so_a_reported_metric_cannot_be_mutated(self) -> None:
        result = rate(1, 2)
        with pytest.raises((AttributeError, TypeError)):
            result.point = 0.99  # type: ignore[misc]

    def test_rate_when_formatted_then_shows_point_and_interval(self) -> None:
        # The report renders these directly; a broken format is a broken report.
        assert "50.0%" in rate(5, 10).format()
        assert "n=10" in rate(5, 10).format()


class TestStratify:
    """Bucketing for the hand-labelled auto-bind sample.

    Strata exist because precision is expected to vary across the auto-bind band. A
    single pooled number would hide exactly the signal that decides whether
    AUTO_BIND_THRESHOLD is set correctly.
    """

    EDGES = [0.85, 0.90, 0.95]

    def test_stratify_when_value_on_edge_then_lands_in_upper_bucket(self) -> None:
        # Bands are lower-inclusive, matching how the pipeline's own thresholds read
        # (">= AUTO_BIND_THRESHOLD binds automatically").
        buckets = stratify([0.90], self.EDGES)
        assert buckets["0.90-0.95"] == [0]
        assert buckets["0.85-0.90"] == []

    def test_stratify_when_value_above_last_edge_then_lands_in_final_bucket(self) -> None:
        buckets = stratify([0.99, 1.0], self.EDGES)
        assert buckets["0.95+"] == [0, 1]

    def test_stratify_when_value_below_first_edge_then_lands_in_below_bucket(self) -> None:
        # Not silently folded into the lowest real stratum: a sub-threshold value here
        # means the caller filtered wrongly, and burying it would corrupt the result.
        buckets = stratify([0.50], self.EDGES)
        assert buckets["<0.85"] == [0]

    def test_stratify_when_values_empty_then_returns_empty_buckets_not_error(self) -> None:
        buckets = stratify([], self.EDGES)
        assert set(buckets) == {"<0.85", "0.85-0.90", "0.90-0.95", "0.95+"}
        assert all(v == [] for v in buckets.values())

    def test_stratify_when_called_then_returns_indices_not_values(self) -> None:
        # Indices let the caller recover the full row; values alone would lose it.
        buckets = stratify([0.86, 0.99, 0.87], self.EDGES)
        assert buckets["0.85-0.90"] == [0, 2]
        assert buckets["0.95+"] == [1]

    def test_stratify_when_every_value_placed_then_no_row_is_lost(self) -> None:
        values = [0.10, 0.85, 0.899, 0.90, 0.949, 0.95, 1.0]
        buckets = stratify(values, self.EDGES)
        placed = sorted(i for indices in buckets.values() for i in indices)
        assert placed == list(range(len(values)))

    def test_stratify_when_edges_unsorted_then_raises(self) -> None:
        with pytest.raises(ValueError, match="ascending"):
            stratify([0.9], [0.95, 0.85])

    def test_stratify_when_edges_empty_then_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            stratify([0.9], [])


class TestRateDataclass:
    def test_rate_when_constructed_then_carries_interval_bounds(self) -> None:
        result = rate(3, 4)
        assert isinstance(result, Rate)
        assert result.low <= result.point <= result.high
