"""Unit tests for the LO-matching evaluation harness.

The harness produces the number that answers "how well does the matcher work?", so its own
failure mode is the dangerous kind: a wrong rate is not obviously wrong. These tests pin
the two places that could quietly mislead — what lands in a denominator, and what happens
to a row the harness cannot interpret.
"""

import pytest

from scripts.eval_lo_matching import (
    ADJUDICATION_STRATUM_EDGES,
    AGREEMENT,
    DECLINED_CONFIRMED,
    DECLINED_RECOVERED,
    DISAGREEMENT,
    SAMPLE_STRATUM_EDGES,
    SUGGESTED_REJECTED,
    UNRESOLVED,
    EvalError,
    ReviewOutcome,
    _chosen_similarity,
    classify_outcome,
    compute_report,
    identify_auto_bound,
    infer_strata,
    score_labelled,
    select_sample,
)


def _outcome(
    status: str = "APPROVED",
    llm_suggested_code: str | None = "MATH-NUM-G6-04",
    chosen_code: str | None = "MATH-NUM-G6-04",
    question_count: int = 10,
    top_similarity: float | None = 0.72,
    source_code: str = "OLD-MATH-01",
) -> ReviewOutcome:
    return ReviewOutcome(
        source_code=source_code,
        status=status,
        llm_suggested_code=llm_suggested_code,
        chosen_code=chosen_code,
        question_count=question_count,
        top_similarity=top_similarity,
    )


class TestClassifyOutcome:
    def test_agreement_when_llm_suggestion_matches_chosen_then_counted_as_agreement(self) -> None:
        assert classify_outcome(_outcome(llm_suggested_code="A", chosen_code="A")) == AGREEMENT

    def test_agreement_when_llm_suggestion_differs_from_chosen_then_counted_as_disagreement(self) -> None:
        assert classify_outcome(_outcome(llm_suggested_code="A", chosen_code="B")) == DISAGREEMENT

    def test_agreement_when_llm_declined_then_classified_as_declined_recovered(self) -> None:
        # The model declined and a reviewer still found a match — a recall loss, not a
        # precision failure, and it must not enter the agreement denominator.
        assert classify_outcome(_outcome(llm_suggested_code=None)) == DECLINED_RECOVERED

    def test_agreement_when_item_still_pending_then_excluded_entirely(self) -> None:
        assert classify_outcome(_outcome(status="PENDING", chosen_code=None)) == UNRESOLVED

    def test_classify_when_item_is_split_then_excluded_entirely(self) -> None:
        assert classify_outcome(_outcome(status="SPLIT", chosen_code=None)) == UNRESOLVED

    def test_classify_when_rejected_and_llm_declined_then_declined_confirmed(self) -> None:
        # Both agreed nothing matched. That is the model behaving correctly.
        assert classify_outcome(_outcome(status="REJECTED", llm_suggested_code=None, chosen_code=None)) == (
            DECLINED_CONFIRMED
        )

    def test_classify_when_rejected_but_llm_suggested_then_suggested_rejected(self) -> None:
        assert classify_outcome(_outcome(status="REJECTED", llm_suggested_code="A", chosen_code=None)) == (
            SUGGESTED_REJECTED
        )

    def test_classify_when_approved_without_chosen_code_then_unresolved_not_guessed(self) -> None:
        # Violates a DB check constraint. Refuse to interpret rather than inventing one.
        assert classify_outcome(_outcome(status="APPROVED", chosen_code=None)) == UNRESOLVED


class TestComputeReport:
    def test_agreement_when_llm_declined_then_excluded_from_agreement_denominator(self) -> None:
        report = compute_report(
            [
                _outcome(llm_suggested_code="A", chosen_code="A"),
                _outcome(llm_suggested_code="A", chosen_code="B"),
                _outcome(llm_suggested_code=None),
                _outcome(llm_suggested_code=None),
            ]
        )
        assert report["adjudicator_agreement"].denominator == 2
        assert report["adjudicator_agreement"].numerator == 1

    def test_agreement_when_items_pending_then_excluded_from_every_denominator(self) -> None:
        report = compute_report(
            [
                _outcome(llm_suggested_code="A", chosen_code="A"),
                _outcome(status="PENDING", chosen_code=None),
                _outcome(status="PENDING", chosen_code=None),
            ]
        )
        assert report["adjudicator_agreement"].denominator == 1
        assert report["resolved_total"] == 1

    def test_blast_radius_weighting_when_large_item_disagrees_then_weighted_rate_below_unweighted(self) -> None:
        # Nine small agreements and one large disagreement: unweighted looks excellent,
        # weighted tells the truth about how many questions were mis-bound.
        outcomes = [_outcome(llm_suggested_code="A", chosen_code="A", question_count=2) for _ in range(9)]
        outcomes.append(_outcome(llm_suggested_code="A", chosen_code="B", question_count=300))
        report = compute_report(outcomes)

        assert report["adjudicator_agreement"].point == pytest.approx(0.9)
        assert report["blast_radius_weighted_agreement"].point < 0.1

    def test_decline_recoverability_when_declined_item_later_approved_then_counted_recoverable(self) -> None:
        report = compute_report(
            [
                _outcome(status="APPROVED", llm_suggested_code=None),
                _outcome(status="APPROVED", llm_suggested_code=None),
                _outcome(status="REJECTED", llm_suggested_code=None, chosen_code=None),
            ]
        )
        assert report["decline_recoverability"].numerator == 2
        assert report["decline_recoverability"].denominator == 3

    def test_compute_report_when_no_outcomes_then_returns_zero_rates_without_error(self) -> None:
        report = compute_report([])
        assert report["resolved_total"] == 0
        assert report["adjudicator_agreement"].point == 0.0
        # No evidence means the whole range is admissible, not "measured zero".
        assert report["adjudicator_agreement"].high == 1.0

    def test_compute_report_when_disagreements_then_similarities_collected(self) -> None:
        report = compute_report(
            [
                _outcome(llm_suggested_code="A", chosen_code="B", top_similarity=0.64),
                _outcome(llm_suggested_code="A", chosen_code="A", top_similarity=0.81),
            ]
        )
        assert report["disagreement_similarities"] == [0.64]


class TestIdentifyAutoBound:
    """The remap records every outcome except the one this measures.

    `map_questions_to_lo.py` writes review, unmatched, and llm_decisions files, and nothing
    at all for groups it auto-bound. Elimination against those three files is exact.
    """

    def test_identify_auto_bound_when_group_in_no_report_then_treated_as_auto_bound(self) -> None:
        result = identify_auto_bound({"A", "B", "C", "D"}, {"B"}, {"C"}, {"D"})
        assert result == {"A"}

    def test_identify_auto_bound_when_every_group_reported_then_empty(self) -> None:
        assert identify_auto_bound({"A", "B"}, {"A"}, {"B"}, set()) == set()

    def test_identify_auto_bound_when_reports_mention_unknown_codes_then_ignored(self) -> None:
        # A stale report file from an earlier run must not remove a real group.
        assert identify_auto_bound({"A"}, {"ZZZ"}, set(), set()) == {"A"}


class TestSelectSample:
    def test_export_sample_when_same_seed_then_produces_identical_sample(self) -> None:
        similarities = [0.85 + i * 0.001 for i in range(120)]
        first = select_sample(similarities, n=30, seed=7)
        second = select_sample(similarities, n=30, seed=7)
        assert first == second

    def test_export_sample_when_different_seed_then_sample_differs(self) -> None:
        similarities = [0.85 + i * 0.001 for i in range(120)]
        assert select_sample(similarities, n=30, seed=1) != select_sample(similarities, n=30, seed=2)

    def test_export_sample_when_stratum_below_minimum_then_takes_all_available_rows(self) -> None:
        # Two rows in the top stratum: take both rather than a proportional fraction.
        similarities = [0.86] * 100 + [0.97, 0.98]
        picked = select_sample(similarities, n=20, seed=0)
        assert 100 in picked
        assert 101 in picked

    def test_export_sample_when_pool_empty_then_returns_empty_list(self) -> None:
        assert select_sample([], n=10, seed=0) == []

    def test_export_sample_when_values_below_band_then_excluded_from_sample(self) -> None:
        # Sub-threshold values signal a data problem; they are not a stratum to sample.
        picked = select_sample([0.10, 0.20], n=10, seed=0)
        assert picked == []

    def test_export_sample_when_called_then_returns_sorted_indices(self) -> None:
        similarities = [0.85 + i * 0.001 for i in range(80)]
        picked = select_sample(similarities, n=20, seed=3)
        assert picked == sorted(picked)


class TestScoreLabelled:
    @staticmethod
    def _row(verdict: str, similarity: float = 0.87) -> dict[str, str]:
        return {"similarity": str(similarity), "verdict": verdict}

    def test_score_sample_when_verdict_unsure_then_excluded_from_both_numerator_and_denominator(self) -> None:
        result = score_labelled([self._row("correct"), self._row("wrong"), self._row("unsure"), self._row("unsure")])
        assert result["overall"].numerator == 1
        assert result["overall"].denominator == 2
        assert result["unsure_count"] == 2

    def test_score_sample_when_verdict_unrecognised_then_raises_not_silently_coerced(self) -> None:
        # Coercing an unknown verdict to "wrong" would understate precision invisibly.
        with pytest.raises(EvalError, match="unrecognised verdict"):
            score_labelled([self._row("correct"), self._row("probably?")])

    def test_score_sample_when_verdict_blank_then_raises(self) -> None:
        with pytest.raises(EvalError, match="unrecognised verdict"):
            score_labelled([self._row("")])

    def test_score_sample_when_verdict_has_mixed_case_then_accepted(self) -> None:
        # A human filling a spreadsheet will type "Correct".
        assert score_labelled([self._row("Correct"), self._row("WRONG")])["overall"].denominator == 2

    def test_score_sample_when_similarity_missing_then_raises(self) -> None:
        with pytest.raises(EvalError, match="similarity"):
            score_labelled([{"verdict": "correct"}])

    def test_score_sample_when_similarity_not_numeric_then_raises(self) -> None:
        with pytest.raises(EvalError, match="similarity"):
            score_labelled([{"verdict": "correct", "similarity": "high"}])

    def test_score_sample_when_rows_span_strata_then_reported_per_stratum(self) -> None:
        result = score_labelled(
            [
                self._row("correct", 0.86),
                self._row("wrong", 0.87),
                self._row("correct", 0.97),
            ]
        )
        assert result["per_stratum"]["0.85-0.90"].denominator == 2
        assert result["per_stratum"]["0.95+"].denominator == 1

    def test_score_sample_when_error_raised_then_names_the_offending_row(self) -> None:
        # Row 2 is the first data row: a reviewer needs to find it in the spreadsheet.
        with pytest.raises(EvalError, match="Row 3"):
            score_labelled([self._row("correct"), self._row("nope")])


class TestChosenSimilarity:
    """The model does not always pick the top candidate.

    Reading the highest similarity instead of the chosen one would systematically
    overstate the scores at which the model succeeds, and hide the cases where wording
    similarity and meaning disagree — which is the whole reason adjudication exists.
    """

    @staticmethod
    def _record(chosen: str) -> dict:
        return {
            "chosen": chosen,
            "candidates": [
                {"canonical_code": "A", "similarity": 0.81, "learning_objective": "a"},
                {"canonical_code": "B", "similarity": 0.74, "learning_objective": "b"},
            ],
        }

    def test_chosen_similarity_when_model_picked_second_candidate_then_returns_its_score(self) -> None:
        assert _chosen_similarity(self._record("B")) == pytest.approx(0.74)

    def test_chosen_similarity_when_model_picked_top_candidate_then_returns_its_score(self) -> None:
        assert _chosen_similarity(self._record("A")) == pytest.approx(0.81)

    def test_chosen_similarity_when_chosen_code_absent_then_returns_none_not_top(self) -> None:
        assert _chosen_similarity(self._record("MISSING")) is None

    def test_chosen_similarity_when_no_candidates_then_returns_none(self) -> None:
        assert _chosen_similarity({"chosen": "A", "candidates": []}) is None


class TestConfidenceCalibration:
    """A stated confidence is only useful if precision tracks it."""

    @staticmethod
    def _row(verdict: str, confidence: str, similarity: float = 0.75) -> dict[str, str]:
        return {"verdict": verdict, "similarity": str(similarity), "model_confidence": confidence}

    def test_score_sample_when_confidence_present_then_precision_reported_per_level(self) -> None:
        result = score_labelled(
            [
                self._row("correct", "high"),
                self._row("correct", "high"),
                self._row("wrong", "low"),
                self._row("correct", "low"),
            ]
        )
        assert result["by_confidence"]["high"].point == pytest.approx(1.0)
        assert result["by_confidence"]["low"].point == pytest.approx(0.5)

    def test_score_sample_when_confidence_absent_then_calibration_section_empty(self) -> None:
        assert score_labelled([{"verdict": "correct", "similarity": "0.9"}])["by_confidence"] == {}

    def test_score_sample_when_confidence_unsure_then_excluded_from_calibration_rate(self) -> None:
        result = score_labelled([self._row("correct", "high"), self._row("unsure", "high")])
        assert result["by_confidence"]["high"].denominator == 1

    def test_score_sample_when_confidence_mixed_case_then_normalised(self) -> None:
        result = score_labelled([self._row("correct", "High"), self._row("wrong", "HIGH")])
        assert result["by_confidence"]["high"].denominator == 2


class TestInferStrata:
    """A labelled file may hold auto-bound rows or adjudicated rows.

    The two bands are disjoint, so applying auto-bind cut points to adjudicated data
    pools every row into the single "below" bucket and reports one undifferentiated
    number that looks like a result.
    """

    def test_infer_strata_when_all_below_auto_bind_then_uses_adjudication_edges(self) -> None:
        edges, name = infer_strata([0.62, 0.71, 0.84])
        assert edges == ADJUDICATION_STRATUM_EDGES
        assert "adjudicated" in name

    def test_infer_strata_when_any_at_or_above_auto_bind_then_uses_sample_edges(self) -> None:
        edges, name = infer_strata([0.62, 0.86])
        assert edges == SAMPLE_STRATUM_EDGES
        assert "auto-bind" in name

    def test_infer_strata_when_empty_then_defaults_to_sample_edges(self) -> None:
        assert infer_strata([])[0] == SAMPLE_STRATUM_EDGES


class TestWeightedPrecision:
    """The number that matters counts questions, not decisions."""

    @staticmethod
    def _row(verdict: str, questions: int, similarity: float = 0.65) -> dict[str, str]:
        return {"verdict": verdict, "similarity": str(similarity), "question_count": str(questions)}

    def test_score_sample_when_error_on_large_group_then_weighted_below_unweighted(self) -> None:
        result = score_labelled([self._row("correct", 5), self._row("correct", 5), self._row("wrong", 200)])
        assert result["overall"].point == pytest.approx(2 / 3)
        assert result["overall_weighted"].point < 0.06

    def test_score_sample_when_unsure_then_questions_excluded_from_weighted_denominator(self) -> None:
        result = score_labelled([self._row("correct", 10), self._row("unsure", 90)])
        assert result["overall_weighted"].denominator == 10
        assert result["unsure_questions"] == 90

    def test_score_sample_when_question_count_missing_then_treated_as_zero_not_crash(self) -> None:
        result = score_labelled([{"verdict": "correct", "similarity": "0.65"}])
        assert result["overall_weighted"].denominator == 0

    def test_score_sample_when_question_count_not_numeric_then_treated_as_zero(self) -> None:
        result = score_labelled([self._row("correct", 5) | {"question_count": "many"}])
        assert result["overall_weighted"].denominator == 0
