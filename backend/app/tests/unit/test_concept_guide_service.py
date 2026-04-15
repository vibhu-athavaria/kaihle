"""Unit tests for concept_guide_service.

Tests verify concept explanation generation, modality detection,
and graceful fallback when learning profile is absent.

Run with: pytest app/tests/unit/test_concept_guide_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.concept_guide_service import _get_dominant_modality


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
