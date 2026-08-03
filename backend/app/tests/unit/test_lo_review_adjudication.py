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
