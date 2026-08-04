"""Unit tests for the orphaned-question remap.

Focus is the two places a mistake would silently mis-target questions: collapsing the
snapshot into per-subtopic groups, and interpreting the adjudicating model's reply.
A malformed or out-of-range reply must always become a decline, never a guess.
"""

from unittest.mock import AsyncMock, patch

import pytest

from scripts.map_questions_to_lo import adjudicate, group_snapshot


def _snapshot_row(code: str, question_id: str, **overrides: object) -> dict:
    row = {
        "question_id": question_id,
        "canonical_code": code,
        "subtopic_name": f"Name for {code}",
        "learning_objective": f"Objective for {code}.",
        "topic_code": "MATH-NUM",
        "subject_code": "MATH",
        "grade_level": 6,
    }
    row.update(overrides)
    return row


def _record(candidate_count: int = 3) -> dict:
    return {
        "old_canonical_code": "MATH-NUM-G6-01",
        "old_subtopic_name": "Integers",
        "old_learning_objective": "Order integers on a number line.",
        "subject_code": "MATH",
        "grade_level": 6,
        "question_count": 42,
        "candidates": [
            {
                "objective_id": f"0000000{i}-0000-0000-0000-000000000000",
                "canonical_code": f"MATH-CODE-{i}",
                "learning_objective": f"Candidate {i}.",
                "similarity": 0.7,
            }
            for i in range(1, candidate_count + 1)
        ],
    }


class TestGroupSnapshot:
    """One decision per old subtopic is the whole point — grouping must be exact."""

    def test_group_when_questions_share_subtopic_then_collapsed_into_one_group(self) -> None:
        snapshot = [_snapshot_row("MATH-NUM-G6-01", f"q{i}") for i in range(5)]

        groups = group_snapshot(snapshot)

        assert len(groups) == 1
        assert len(groups["MATH-NUM-G6-01"]["question_ids"]) == 5

    def test_group_when_subtopics_differ_then_kept_separate(self) -> None:
        snapshot = [_snapshot_row("MATH-NUM-G6-01", "q1"), _snapshot_row("MATH-ALG-G7-02", "q2")]

        groups = group_snapshot(snapshot)

        assert set(groups) == {"MATH-NUM-G6-01", "MATH-ALG-G7-02"}

    def test_group_when_collapsed_then_no_question_is_lost(self) -> None:
        snapshot = [_snapshot_row("A", "q1"), _snapshot_row("A", "q2"), _snapshot_row("B", "q3")]

        groups = group_snapshot(snapshot)

        recovered = {q for g in groups.values() for q in g["question_ids"]}
        assert recovered == {"q1", "q2", "q3"}

    def test_group_when_built_then_carries_matching_context(self) -> None:
        groups = group_snapshot([_snapshot_row("MATH-NUM-G6-01", "q1")])

        group = groups["MATH-NUM-G6-01"]
        assert group["subject_code"] == "MATH"
        assert group["grade_level"] == 6
        assert group["learning_objective"] == "Objective for MATH-NUM-G6-01."

    def test_group_when_snapshot_empty_then_returns_empty(self) -> None:
        assert group_snapshot([]) == {}


@pytest.mark.asyncio
class TestAdjudicate:
    """Every failure mode must degrade to a decline, which routes to a human."""

    @staticmethod
    def _patch_complete(response: str) -> AsyncMock:
        return AsyncMock(return_value=response)

    async def test_adjudicate_when_model_picks_candidate_then_returns_it(self) -> None:
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('{"choice": 2, "confidence": "high", "reason": "same skill"}'),
        ):
            result = await adjudicate(_record())

        assert result is not None
        assert result["candidate"]["canonical_code"] == "MATH-CODE-2"
        assert result["confidence"] == "high"

    async def test_adjudicate_when_response_is_fenced_json_then_still_parsed(self) -> None:
        """Models routinely wrap JSON in a code fence despite instructions."""
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('```json\n{"choice": 1, "confidence": "high", "reason": "ok"}\n```'),
        ):
            result = await adjudicate(_record())

        assert result is not None
        assert result["candidate"]["canonical_code"] == "MATH-CODE-1"

    async def test_adjudicate_when_model_declines_then_returns_none(self) -> None:
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('{"choice": null, "confidence": "low", "reason": "no match"}'),
        ):
            assert await adjudicate(_record()) is None

    async def test_adjudicate_when_choice_out_of_range_then_returns_none(self) -> None:
        # Binding to a candidate that was never offered would be arbitrary.
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('{"choice": 9, "confidence": "high", "reason": "nope"}'),
        ):
            assert await adjudicate(_record(candidate_count=3)) is None

    async def test_adjudicate_when_choice_is_zero_then_returns_none(self) -> None:
        """Candidates are 1-indexed; 0 would silently select the last one."""
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('{"choice": 0, "confidence": "high", "reason": "nope"}'),
        ):
            assert await adjudicate(_record()) is None

    async def test_adjudicate_when_choice_not_an_integer_then_returns_none(self) -> None:
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete('{"choice": "MATH-CODE-1", "confidence": "high", "reason": "x"}'),
        ):
            assert await adjudicate(_record()) is None

    async def test_adjudicate_when_response_unparseable_then_returns_none(self) -> None:
        with patch(
            "scripts.map_questions_to_lo.complete",
            self._patch_complete("I think candidate 2 is the best match."),
        ):
            assert await adjudicate(_record()) is None

    async def test_adjudicate_when_provider_raises_then_returns_none(self) -> None:
        """A provider outage must not abort the run or bind anything."""
        with patch("scripts.map_questions_to_lo.complete", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adjudicate(_record()) is None

    async def test_adjudicate_when_called_then_uses_deterministic_sampling(self) -> None:
        mock = self._patch_complete('{"choice": 1, "confidence": "high", "reason": "ok"}')
        with patch("scripts.map_questions_to_lo.complete", mock):
            await adjudicate(_record())

        assert mock.call_args.kwargs["temperature"] == 0.0
        assert mock.call_args.args[0] == "lo_matching"

    async def test_adjudicate_when_called_then_prompt_carries_old_and_candidate_text(self) -> None:
        mock = self._patch_complete('{"choice": 1, "confidence": "high", "reason": "ok"}')
        with patch("scripts.map_questions_to_lo.complete", mock):
            await adjudicate(_record())

        prompt = mock.call_args.args[1][0]["content"]
        assert "Order integers on a number line." in prompt
        assert "MATH-CODE-1" in prompt
        # The blast radius is stated so the model weighs a loose match appropriately.
        assert "42" in prompt
