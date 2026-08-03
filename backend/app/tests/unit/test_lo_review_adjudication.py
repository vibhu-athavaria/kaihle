"""Unit tests for per-question adjudication during a split.

A wrong binding here is silent: the question is served to students as evidence of a
skill it does not test, and nothing downstream detects it. Every failure mode must
therefore decline rather than guess, which is what these tests pin down.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.lo_review_service import adjudicate_question


def _question(text: str = "What is 3:4 simplified?") -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "question_text": text,
        "options": [{"key": "A", "text": "3:4"}],
    }


def _context(candidate_count: int = 3) -> dict:
    return {
        "subject_code": "MATH",
        "grade_level": 6,
        "old_learning_objective": "Write and simplify ratios; divide a quantity.",
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


@pytest.mark.asyncio
class TestAdjudicateQuestion:
    @staticmethod
    def _reply(text: str) -> AsyncMock:
        return AsyncMock(return_value=text)

    async def test_when_model_picks_candidate_then_returns_its_code(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 2}')):
            assert await adjudicate_question(_question(), _context()) == "MATH-CODE-2"

    async def test_when_reply_is_fenced_then_still_parsed(self) -> None:
        """Models wrap JSON in a code fence regardless of instructions."""
        with patch(
            "app.services.lo_review_service.complete",
            self._reply('```json\n{"choice": 1, "confidence": "high"}\n```'),
        ):
            assert await adjudicate_question(_question(), _context()) == "MATH-CODE-1"

    async def test_when_model_declines_then_returns_none(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": null}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_choice_out_of_range_then_returns_none(self) -> None:
        # Binding to a candidate never offered would be arbitrary.
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 9}')):
            assert await adjudicate_question(_question(), _context(3)) is None

    async def test_when_choice_is_zero_then_returns_none(self) -> None:
        """Candidates are 1-indexed; 0 would silently select the last one."""
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 0}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_choice_not_an_integer_then_returns_none(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": "MATH-CODE-1"}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_reply_unparseable_then_returns_none(self) -> None:
        with patch(
            "app.services.lo_review_service.complete",
            self._reply("I think candidate 2 fits best."),
        ):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_provider_raises_then_returns_none(self) -> None:
        """A provider outage must leave questions unbound, never abort the split."""
        with patch(
            "app.services.lo_review_service.complete",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_called_then_uses_deterministic_sampling(self) -> None:
        mock = self._reply('{"choice": 1}')
        with patch("app.services.lo_review_service.complete", mock):
            await adjudicate_question(_question(), _context())

        assert mock.call_args.kwargs["temperature"] == 0.0
        assert mock.call_args.args[0] == "lo_matching"

    async def test_when_called_then_prompt_carries_question_and_candidates(self) -> None:
        mock = self._reply('{"choice": 1}')
        with patch("app.services.lo_review_service.complete", mock):
            await adjudicate_question(_question("What is 6:8 simplified?"), _context())

        prompt = mock.call_args.args[1][0]["content"]
        assert "What is 6:8 simplified?" in prompt
        assert "MATH-CODE-1" in prompt
        # The old objective is included so the model knows why the group is splitting.
        assert "Write and simplify ratios" in prompt

    async def test_when_candidate_lacks_a_code_then_returns_none(self) -> None:
        context = _context(1)
        context["candidates"][0].pop("canonical_code")
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 1}')):
            assert await adjudicate_question(_question(), context) is None


class TestSerialise:
    """The list payload the review screen renders."""

    @staticmethod
    def _item() -> object:
        from types import SimpleNamespace

        return SimpleNamespace(
            id="a",
            item_type="QUESTION_REMAP",
            status="PENDING",
            source_code="MATH-NUM-G6-04",
            source_name="Ratio and Proportion",
            source_learning_objective="Write and simplify ratios.",
            subject_code="MATH",
            grade_level=6,
            question_count=103,
            candidates=[{"canonical_code": "MATH-X"}],
            llm_suggested_code=None,
            llm_reason=None,
            chosen_objective_id=None,
            admin_note=None,
            resolved_at=None,
        )

    def test_serialise_when_unresolved_then_ids_are_null_not_missing(self) -> None:
        from app.services.lo_review_service import LoReviewService

        payload = LoReviewService._serialise(self._item())  # type: ignore[arg-type]

        # The client distinguishes "no decision yet" from "field absent"; emitting the
        # key with null keeps that unambiguous.
        assert payload["chosen_objective_id"] is None
        assert payload["resolved_at"] is None

    def test_serialise_when_called_then_carries_the_blast_radius(self) -> None:
        from app.services.lo_review_service import LoReviewService

        payload = LoReviewService._serialise(self._item())  # type: ignore[arg-type]

        # question_count drives ordering and the confirm-button label.
        assert payload["question_count"] == 103
        assert payload["source_name"] == "Ratio and Proportion"


@pytest.mark.asyncio
class TestWithPlacements:
    """Placement attachment is what lets a reviewer tell a Grade 6 objective from a
    Grade 12 one; every search return path must apply it."""

    async def test_attaches_placements_by_objective_id(self) -> None:
        from unittest.mock import MagicMock

        from app.services.lo_review_service import LoReviewService

        service = LoReviewService(MagicMock())
        with patch.object(
            service,
            "_placements_for",
            AsyncMock(return_value={"1": [{"subject_code": "MATH", "grade_level": 6, "topic_name": "Fractions"}]}),
        ):
            result = await service._with_placements([{"objective_id": "1"}, {"objective_id": "2"}])

        assert result[0]["placements"][0]["grade_level"] == 6
        # An objective with no placement gets an empty list, never a missing key —
        # the UI renders that as an explicit data defect.
        assert result[1]["placements"] == []

    async def test_when_no_results_then_returns_empty_without_querying(self) -> None:
        from unittest.mock import MagicMock

        from app.services.lo_review_service import LoReviewService

        service = LoReviewService(MagicMock())
        with patch.object(service, "_placements_for", AsyncMock(return_value={})) as mock:
            assert await service._with_placements([]) == []
        mock.assert_awaited_once_with([])
