"""Unit tests for concept_guide_service.

Tests verify concept explanation generation, modality detection,
and graceful fallback when learning profile is absent.

Run with: pytest app/tests/unit/test_concept_guide_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.concept_guide_service import (
    _get_dominant_modality,
    _parse_mcq,
    evaluate_mcq_answer,
)


class TestGetDominantModality:
    """Unit tests for the _get_dominant_modality helper."""

    def test_get_dominant_modality_when_visual_highest_then_returns_visual(self) -> None:
        scores = {"visual": 0.8, "auditory": 0.3, "reading_writing": 0.5, "kinesthetic": 0.4}
        assert _get_dominant_modality(scores) == "visual"

    def test_get_dominant_modality_when_kinesthetic_highest_then_returns_kinesthetic(self) -> None:
        scores = {"visual": 0.2, "auditory": 0.3, "reading_writing": 0.5, "kinesthetic": 0.9}
        assert _get_dominant_modality(scores) == "kinesthetic"

    def test_get_dominant_modality_when_reading_writing_highest_then_returns_readable_label(self) -> None:
        scores = {"visual": 0.1, "auditory": 0.2, "reading_writing": 0.9, "kinesthetic": 0.3}
        assert _get_dominant_modality(scores) == "reading/writing"

    def test_get_dominant_modality_when_empty_dict_then_returns_visual_fallback(self) -> None:
        assert _get_dominant_modality({}) == "visual"


class TestGenerateConceptExplanation:
    """Unit tests for the generate_concept_explanation service function."""

    @pytest.mark.asyncio
    async def test_generate_concept_explanation_when_valid_subtopic_then_returns_explanation(
        self,
    ) -> None:
        """generate_concept_explanation returns explanation and subtopic_name on success."""
        student_id = uuid4()
        subtopic_id = uuid4()

        mock_student = MagicMock()
        mock_student.id = student_id

        mock_subtopic = MagicMock()
        mock_subtopic.id = subtopic_id
        mock_subtopic.name = "Photosynthesis"
        mock_subtopic.description = "The process by which plants make food."
        mock_subtopic.learning_objective = "Understand the light and dark reactions."
        mock_subtopic.keywords = ["chlorophyll", "glucose", "ATP"]

        mock_profile = MagicMock()
        mock_profile.modality_scores = {"visual": 0.8, "auditory": 0.2}
        mock_profile.work_style = {"task_based": True}
        mock_profile.interests = ["football", "music"]

        mock_db = AsyncMock()

        async def mock_execute(query):
            result = MagicMock()
            # First call is subtopic, second is profile
            if not hasattr(mock_execute, "call_count"):
                mock_execute.call_count = 0
            mock_execute.call_count += 1
            if mock_execute.call_count == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_subtopic)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_profile)
            return result

        mock_db.execute = mock_execute

        with patch(
            "app.services.concept_guide_service.llm_router.complete",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = "Photosynthesis is how plants convert sunlight into food."

            from app.services.concept_guide_service import generate_concept_explanation

            result = await generate_concept_explanation(
                student=mock_student,
                subtopic_id=subtopic_id,
                question=None,
                db=mock_db,
            )

        assert result["subtopic_name"] == "Photosynthesis"
        assert "Photosynthesis" in result["explanation"]
        assert result["check_question"] is None  # LLM response had no JSON MCQ
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["task"] == "concept_guide"

    @pytest.mark.asyncio
    async def test_generate_concept_explanation_when_subtopic_not_found_then_raises_value_error(
        self,
    ) -> None:
        """generate_concept_explanation raises ValueError when subtopic does not exist."""
        mock_student = MagicMock()
        mock_student.id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.concept_guide_service import generate_concept_explanation

        with pytest.raises(ValueError, match="not found"):
            await generate_concept_explanation(
                student=mock_student,
                subtopic_id=uuid4(),
                question=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_generate_concept_explanation_when_no_profile_then_uses_fallback_modality(
        self,
    ) -> None:
        """Service uses 'visual' fallback when student has no completed learning profile."""
        mock_student = MagicMock()
        mock_student.id = uuid4()

        mock_subtopic = MagicMock()
        mock_subtopic.name = "Cell Division"
        mock_subtopic.description = None
        mock_subtopic.learning_objective = "Understand mitosis stages."
        mock_subtopic.keywords = None

        mock_db = AsyncMock()
        call_count = {"n": 0}

        async def mock_execute(query):
            result = MagicMock()
            call_count["n"] += 1
            if call_count["n"] == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_subtopic)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)  # No profile
            return result

        mock_db.execute = mock_execute

        with patch(
            "app.services.concept_guide_service.llm_router.complete",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = "Cell division explanation."

            from app.services.concept_guide_service import generate_concept_explanation

            result = await generate_concept_explanation(
                student=mock_student,
                subtopic_id=uuid4(),
                question=None,
                db=mock_db,
            )

        # Should still succeed with default visual modality
        assert result["subtopic_name"] == "Cell Division"
        rendered_prompt = mock_llm.call_args.kwargs["messages"][0]["content"]
        assert "visual" in rendered_prompt


class TestParseMcq:
    """Unit tests for the _parse_mcq helper."""

    def test_parse_mcq_when_valid_json_present_then_splits_explanation_and_mcq(self) -> None:
        raw = (
            "Photosynthesis is the process by which plants convert sunlight into glucose.\n"
            '{"question": "What does chlorophyll absorb?", '
            '"options": ["A) Water", "B) Light", "C) CO2", "D) Oxygen"], "correct": "B"}'
        )
        explanation, mcq = _parse_mcq(raw)
        assert "Photosynthesis" in explanation
        assert mcq is not None
        assert mcq["correct"] == "B"
        assert len(mcq["options"]) == 4

    def test_parse_mcq_when_no_json_present_then_returns_full_text_and_none(self) -> None:
        raw = "Photosynthesis is the process by which plants convert sunlight into glucose."
        explanation, mcq = _parse_mcq(raw)
        assert explanation == raw
        assert mcq is None

    def test_parse_mcq_when_json_missing_required_keys_then_returns_none_for_mcq(self) -> None:
        raw = 'Some explanation. {"question": "What is it?", "answer": "B"}'
        explanation, mcq = _parse_mcq(raw)
        assert mcq is None

    def test_parse_mcq_when_malformed_json_then_returns_full_text_and_none(self) -> None:
        raw = 'Some explanation. {"question": "What?", "options": [broken}, "correct": "A"}'
        explanation, mcq = _parse_mcq(raw)
        assert mcq is None


class TestEvaluateMcqAnswer:
    """Unit tests for the evaluate_mcq_answer service function."""

    @pytest.mark.asyncio
    async def test_evaluate_mcq_answer_when_correct_then_returns_is_correct_true(self) -> None:
        with patch(
            "app.services.concept_guide_service.llm_router.complete",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = "Well done! You understand photosynthesis."

            result = await evaluate_mcq_answer(
                subtopic_name="Photosynthesis",
                question="What does chlorophyll absorb?",
                options=["A) Water", "B) Light", "C) CO2", "D) Oxygen"],
                correct="B",
                student_answer="B",
            )

        assert result["is_correct"] == "true"
        assert "done" in result["response"].lower() or len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_evaluate_mcq_answer_when_incorrect_then_returns_is_correct_false(self) -> None:
        with patch(
            "app.services.concept_guide_service.llm_router.complete",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = "Actually, chlorophyll absorbs light energy from the sun."

            result = await evaluate_mcq_answer(
                subtopic_name="Photosynthesis",
                question="What does chlorophyll absorb?",
                options=["A) Water", "B) Light", "C) CO2", "D) Oxygen"],
                correct="B",
                student_answer="A",
            )

        assert result["is_correct"] == "false"
        assert len(result["response"]) > 0
