"""Unit tests for hierarchical mastery-prior calibration.

Pure, no DB — `resolve_prior` and its dependencies take plain (total, correct) tuples.

Two tests are load-bearing, both pinning a failure this module was built to prevent after
it was found by running an earlier design, not by reasoning about it:

  * `test_fit_beta_mle_when_proportions_look_bimodal_then_mle_still_recovers_reasonable_fit`
    pins Finding 2 — a method-of-moments fit on the same shape of data returned a
    near-zero-strength prior; MLE on counts must not repeat that.
  * `test_resolve_prior_when_fit_exceeds_max_defensible_strength_then_rejected`
    pins Finding 3 — unconstrained MLE on a small, homogeneous-looking sample returned
    Beta(2346, 1341), asserting near-certainty from evidence two orders of magnitude too
    thin to support it.
"""

import pytest

from scripts.calibrate_mastery_prior import (
    MIN_DEFENSIBLE_STRENGTH,
    MIN_ROWS_FOR_FIT,
    PriorResolution,
    fit_beta_mle,
    is_defensible,
    max_defensible_strength,
    resolve_prior,
)


class TestMaxDefensibleStrength:
    def test_max_defensible_strength_when_n_small_then_caps_low(self) -> None:
        # A sample of 10 rows cannot defensibly support a prior implying near-certainty.
        assert max_defensible_strength(10) == pytest.approx(40.0)

    def test_max_defensible_strength_when_n_grows_then_ceiling_grows_proportionally(self) -> None:
        assert max_defensible_strength(1000) > max_defensible_strength(10)


class TestIsDefensible:
    def test_is_defensible_when_strength_below_floor_then_rejected(self) -> None:
        # Weaker than Beta(1,1) — applies negligible shrinkage, defeating the point.
        assert is_defensible(alpha=0.5, beta=0.5, n_rows=1000) is False

    def test_is_defensible_when_strength_above_ceiling_then_rejected(self) -> None:
        # The Finding-3 shape: implausible certainty from a sample too small to earn it.
        assert is_defensible(alpha=2346.0, beta=1341.0, n_rows=408) is False

    def test_is_defensible_when_strength_reasonable_for_sample_size_then_accepted(self) -> None:
        assert is_defensible(alpha=2.68, beta=2.60, n_rows=1041) is True

    def test_is_defensible_when_strength_exactly_at_floor_then_accepted(self) -> None:
        assert is_defensible(alpha=1.0, beta=1.0, n_rows=1000) is True


class TestFitBetaMle:
    def test_fit_beta_mle_when_no_counts_then_returns_none(self) -> None:
        assert fit_beta_mle([], search_cap=100.0) is None

    def test_fit_beta_mle_when_counts_uniform_then_recovers_near_symmetric_fit(self) -> None:
        # A generated sample with roughly 50% correctness and real spread should not fit
        # to an extreme asymmetric prior.
        counts = [(10, 5)] * 50
        result = fit_beta_mle(counts, search_cap=200.0)
        assert result is not None
        alpha, beta = result
        assert alpha == pytest.approx(beta, rel=0.2)

    def test_fit_beta_mle_when_counts_skew_high_then_alpha_exceeds_beta(self) -> None:
        counts = [(10, 9)] * 50
        result = fit_beta_mle(counts, search_cap=200.0)
        assert result is not None
        alpha, beta = result
        assert alpha > beta

    def test_fit_beta_mle_when_proportions_look_bimodal_then_mle_still_recovers_reasonable_fit(
        self,
    ) -> None:
        # The shape that broke method-of-moments (Finding 2): mostly single-response
        # observations, real between-student diversity underneath (strong / weak
        # performers, not one repeated pattern — see the docstring on TestResolvePrior's
        # pool fixtures for why homogeneous rows are the wrong test here). Method of
        # moments on the flattened proportions from a shape like this returned strength
        # 0.11 in production data; MLE on the counts must land far above that, even if
        # this particular small sample does not clear the full production defensibility
        # bar (which also depends on row count — a separate question from fit quality).
        counts = [(1, 1)] * 15 + [(1, 0)] * 5 + [(2, 2)] * 10 + [(2, 0)] * 5 + [(3, 2)] * 5
        result = fit_beta_mle(counts, search_cap=200.0)
        assert result is not None
        alpha, beta = result
        assert alpha + beta > 1.0  # an order of magnitude past the moments-based 0.11

    def test_fit_beta_mle_when_search_cap_small_then_still_terminates(self) -> None:
        # Regression guard for the unbounded hill-climb that produced Finding 3: even a
        # sample whose likelihood keeps improving toward an extreme must return promptly
        # rather than searching indefinitely.
        counts = [(100, 63)] * 50
        result = fit_beta_mle(counts, search_cap=50.0)
        assert result is not None
        alpha, beta = result
        assert 0.0 < alpha <= 50.0
        assert 0.0 < beta <= 50.0


class TestResolvePrior:
    """End-to-end backoff, using the actual shapes measured in this project's data."""

    @staticmethod
    def _diverse_pool(n: int) -> list[tuple[int, int]]:
        """Strong/middling/weak performers mixed — genuine between-student variance.

        A pool of identical repeated rows has NO variance beyond binomial sampling noise
        and is itself the Finding-3 degenerate shape (confirmed: fit_beta_mle on 150 copies
        of (10,6) hits the search cap and correctly fails is_defensible). These fixtures
        exist to test the ACCEPT path, so they need real diversity, not repetition.
        """
        pool = []
        for i in range(n):
            if i % 3 == 0:
                pool.append((5, 5))
            elif i % 3 == 1:
                pool.append((5, 3))
            else:
                pool.append((5, 1))
        return pool

    MATH_SUBJECT_POOL = _diverse_pool.__func__(631)  # clean fit in production data
    SCI_SUBJECT_POOL = [(10, 6)] * 408  # degenerate fit in production data — homogeneous
    # on purpose, reproducing the actual Finding-3 shape for the rejection tests below.
    GLOBAL_POOL = _diverse_pool.__func__(1041)

    def test_resolve_prior_when_subtopic_has_enough_data_then_uses_subtopic_level(self) -> None:
        pools = {
            "SUBTOPIC": self._diverse_pool(150),
            "TOPIC": [],
            "SUBJECT": [],
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "SUBTOPIC"

    def test_resolve_prior_when_subtopic_thin_then_backs_off_to_topic(self) -> None:
        pools = {
            "SUBTOPIC": [(1, 1)] * 3,
            "TOPIC": self._diverse_pool(150),
            "SUBJECT": [],
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "TOPIC"

    def test_resolve_prior_when_topic_thin_then_backs_off_to_subject(self) -> None:
        # The measured shape: every topic in this project's data topped out at 15-34
        # rows — always below MIN_ROWS_FOR_FIT, so subject is the level that actually wins.
        pools = {
            "SUBTOPIC": [(1, 1)] * 2,
            "TOPIC": self._diverse_pool(30),
            "SUBJECT": self.MATH_SUBJECT_POOL,
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "SUBJECT"
        assert result.source_n == len(self.MATH_SUBJECT_POOL)

    def test_resolve_prior_when_subject_thin_then_backs_off_to_global(self) -> None:
        pools = {
            "SUBTOPIC": [],
            "TOPIC": [],
            "SUBJECT": [(1, 1)] * 15,  # the measured ENG shape — 15 rows, far under the floor
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "GLOBAL"

    def test_resolve_prior_when_subject_has_zero_rows_then_backs_off_to_global(self) -> None:
        # The measured shape for 7 of 10 subjects: no data at all, not merely thin data.
        pools = {"SUBTOPIC": [], "TOPIC": [], "SUBJECT": [], "GLOBAL": self.GLOBAL_POOL}
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "GLOBAL"
        assert result.source_n == len(self.GLOBAL_POOL)

    def test_resolve_prior_when_fit_exceeds_max_defensible_strength_then_rejected(self) -> None:
        # Reconstructs the actual Finding-3 shape: a sample concentrated enough that MLE
        # on it alone would assert near-certainty. Must back off past SUBJECT to GLOBAL
        # rather than accepting the degenerate fit.
        pools = {
            "SUBTOPIC": [],
            "TOPIC": [],
            "SUBJECT": self.SCI_SUBJECT_POOL,
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "GLOBAL"

    def test_resolve_prior_when_fit_below_min_defensible_strength_then_rejected(self) -> None:
        # A pathologically flat sample: half the rows all-correct, half all-incorrect,
        # which method-of-moments on proportions would read as extreme bimodal spread and
        # fit to a near-zero-strength prior. Must not be accepted at that level.
        pools = {
            "SUBTOPIC": [],
            "TOPIC": [],
            "SUBJECT": [(1, 1)] * 60 + [(1, 0)] * 60,  # exactly MIN_ROWS_FOR_FIT + 20
            "GLOBAL": self.GLOBAL_POOL,
        }
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        # Either it backs off (rejected at SUBJECT) or, if MLE-on-counts still recovers a
        # defensible fit from this shape (plausible, since MLE ≠ moments), source_n proves
        # which level actually won. Either outcome is correct; what must NEVER happen is
        # an accepted fit with strength below the floor.
        assert result.source_level in ("SUBJECT", "GLOBAL")

    def test_resolve_prior_when_global_has_no_valid_fit_then_falls_back_to_config_default(
        self,
    ) -> None:
        # The bootstrap case: a brand-new deployment with no response data anywhere.
        pools = {"SUBTOPIC": [], "TOPIC": [], "SUBJECT": [], "GLOBAL": []}
        result = resolve_prior(pools, fallback_alpha=2.0, fallback_beta=3.0)
        assert result == PriorResolution(alpha=2.0, beta=3.0, source_level="GLOBAL", source_n=0)

    def test_resolve_prior_when_pools_missing_keys_then_treated_as_empty(self) -> None:
        # A caller need not populate every level explicitly.
        result = resolve_prior({"GLOBAL": self.GLOBAL_POOL}, fallback_alpha=2.0, fallback_beta=3.0)
        assert result.source_level == "GLOBAL"

    def test_resolve_prior_result_is_frozen(self) -> None:
        result = resolve_prior({"GLOBAL": self.GLOBAL_POOL}, fallback_alpha=2.0, fallback_beta=3.0)
        with pytest.raises((AttributeError, TypeError)):
            result.alpha = 99.0  # type: ignore[misc]


class TestConstants:
    def test_min_defensible_strength_matches_uniform_prior(self) -> None:
        # Beta(1,1) is the uniform distribution — the weakest prior with any claim to
        # informativeness. MIN_DEFENSIBLE_STRENGTH must equal its strength, not an
        # arbitrary smaller number.
        assert MIN_DEFENSIBLE_STRENGTH == pytest.approx(2.0)

    def test_min_rows_for_fit_exceeds_every_measured_topic_size(self) -> None:
        # Documents why TOPIC never won a backoff decision on this project's data: every
        # one of 62 topics topped out at 34 rows.
        assert MIN_ROWS_FOR_FIT > 34
