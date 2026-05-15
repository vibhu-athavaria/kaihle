"""Unit tests for generate_topic_mini_course Celery task and MiniCourseGenerationService.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_generate_course_task.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    """Minimal mock AsyncSession."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def _make_subtopic(name: str = "Quadratic Equations") -> MagicMock:
    subtopic = MagicMock()
    subtopic.id = uuid.uuid4()
    subtopic.name = name
    subtopic.is_active = True
    subtopic.sequence_order = 1
    return subtopic


def _make_interest_category(name: str, cat_id: uuid.UUID | None = None) -> MagicMock:
    cat = MagicMock()
    cat.id = cat_id or uuid.uuid4()
    cat.name = name
    return cat


def _make_scalars_result(items: list) -> MagicMock:
    """Mock result where result.scalars().all() returns items."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_first_result(value: object) -> MagicMock:
    """Mock result where result.first() returns value."""
    result = MagicMock()
    result.first.return_value = value
    return result


def _make_scalar_one_or_none_result(value: object) -> MagicMock:
    """Mock result where result.scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# MiniCourseGenerationService unit tests
# ---------------------------------------------------------------------------


class TestGenerateForTopic:
    """Tests for MiniCourseGenerationService.generate_for_topic."""

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_no_subtopics_then_logs_warning_and_returns(
        self,
    ) -> None:
        """Rule 17: log WARNING and return early when topic has no subtopics."""
        from app.services.mini_course_generation_service import MiniCourseGenerationService

        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())

        # _fetch_topic_context: returns a row
        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        # _fetch_subtopics: returns empty list
        db.execute.side_effect = [
            _make_first_result(topic_context_row),  # _fetch_topic_context
            _make_scalars_result([]),  # _fetch_subtopics
        ]

        service = MiniCourseGenerationService(db)

        with patch("app.services.mini_course_generation_service.logger") as mock_logger:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert result["subtopics_found"] == 0
        assert result["explanations_written"] == 0
        mock_logger.warning.assert_called_once()
        warning_call_event = mock_logger.warning.call_args[0][0]
        assert "no_subtopics" in warning_call_event

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_subtopics_exist_then_calls_llm_for_each_interest_category(
        self,
    ) -> None:
        """One LLM call per (subtopic, interest_category) pair — 4 calls for 1 subtopic."""
        from app.services.mini_course_generation_service import (
            INTEREST_CATEGORIES,
            MiniCourseGenerationService,
        )

        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        # execute call sequence per loop iteration (per category):
        #   _has_non_rejected_content → .first()
        #   _upsert_content rejected-row check → .scalar_one_or_none()
        # Interleaved: 1 subtopic × 4 categories = 8 per-loop calls, plus 3 setup.
        # Setup: _fetch_topic_context, _fetch_subtopics, _resolve_interest_category_ids
        # Loop (×4): has_non_rejected (first=None), upsert check (scalar_one_or_none=None)
        execute_returns = [
            _make_first_result(topic_context_row),  # _fetch_topic_context
            _make_scalars_result([subtopic]),  # _fetch_subtopics
            _make_scalars_result(categories),  # _resolve_interest_category_ids
            # cat 1 (sports_movement)
            _make_first_result(None),  # has_non_rejected → no content
            _make_scalar_one_or_none_result(None),  # upsert check → no rejected row
            # cat 2 (tech_gaming)
            _make_first_result(None),
            _make_scalar_one_or_none_result(None),
            # cat 3 (nature_animals)
            _make_first_result(None),
            _make_scalar_one_or_none_result(None),
            # cat 4 (arts_culture)
            _make_first_result(None),
            _make_scalar_one_or_none_result(None),
        ]
        db.execute.side_effect = execute_returns

        llm_response = "Great explanation about quadratic equations."

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(return_value=llm_response),
        ) as mock_llm:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert mock_llm.call_count == len(INTEREST_CATEGORIES)
        assert result["subtopics_found"] == 1
        assert result["subtopics_processed"] == 1
        assert result["explanations_written"] == len(INTEREST_CATEGORIES)
        # Every LLM call must use the mini_course_explanation task key
        for call in mock_llm.call_args_list:
            assert call.kwargs.get("task") == "mini_course_explanation" or call.args[0] == "mini_course_explanation"
        # Content rows are added to the session
        assert db.add.call_count == len(INTEREST_CATEGORIES)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_content_already_approved_then_skips_subtopic(
        self,
    ) -> None:
        """Non-rejected content row exists → skip LLM call for that pair."""
        from app.services.mini_course_generation_service import (
            INTEREST_CATEGORIES,
            MiniCourseGenerationService,
        )

        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        # All 4 interest categories already have approved content
        existing_row = MagicMock()
        existing_row.id = uuid.uuid4()

        execute_returns = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            # has_non_rejected × 4 — all return an existing row
            _make_first_result(existing_row),
            _make_first_result(existing_row),
            _make_first_result(existing_row),
            _make_first_result(existing_row),
        ]
        db.execute.side_effect = execute_returns

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(),
        ) as mock_llm:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        # LLM must not be called at all
        mock_llm.assert_not_called()
        assert result["subtopics_found"] == 1
        assert result["explanations_written"] == 0
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_llm_fails_then_retries(
        self,
    ) -> None:
        """LLM failure propagates as exception; caller (Celery task) handles retry."""
        from app.services.mini_course_generation_service import (
            INTEREST_CATEGORIES,
            MiniCourseGenerationService,
        )

        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        execute_returns = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            # First _has_non_rejected check — no existing content
            _make_first_result(None),
        ]
        db.execute.side_effect = execute_returns

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(side_effect=RuntimeError("LLM provider unavailable")),
        ):
            with pytest.raises(RuntimeError, match="LLM provider unavailable"):
                await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        # Session must NOT be committed on failure
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Celery task wrapper unit tests
# ---------------------------------------------------------------------------


class TestGenerateMiniCourseTask:
    """Tests for the generate_topic_mini_course Celery task wrapper."""

    def test_generate_topic_mini_course_task_on_failure_logs_critical(self) -> None:
        """GenerateMiniCourseTask.on_failure must emit a CRITICAL log (Rule 18)."""
        from app.tasks.mini_course_tasks import GenerateMiniCourseTask

        task = GenerateMiniCourseTask()
        topic_id = str(uuid.uuid4())
        exc = RuntimeError("Some unrecoverable error")

        with patch("app.tasks.mini_course_tasks.logger") as mock_logger:
            task.on_failure(
                exc=exc,
                task_id="celery-task-123",
                args=(topic_id, "school-id"),
                kwargs={},
                einfo=None,
            )

        mock_logger.critical.assert_called_once()
        call_kwargs = mock_logger.critical.call_args
        event_name = call_kwargs[0][0]
        assert "permanently_failed" in event_name
        assert call_kwargs[1].get("topic_id") == topic_id
        assert call_kwargs[1].get("exc_info") is True
