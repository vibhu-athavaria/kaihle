"""Unit tests for MiniCourseGenerationService — quiz staging path (M3-1-T2).

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_mini_course_generation_service.py -v
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mini_course_generation_service import MiniCourseGenerationService, _parse_quiz_response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


_VALID_QUESTIONS = [
    {
        "question_text": "What is 2+2?",
        "options": [
            {"key": "A", "text": "3"},
            {"key": "B", "text": "4"},
            {"key": "C", "text": "5"},
            {"key": "D", "text": "6"},
        ],
        "correct_answer": "B",
        "explanation": "Basic arithmetic.",
    }
]


# ---------------------------------------------------------------------------
# Tests: _parse_quiz_response
# ---------------------------------------------------------------------------


def test_parse_quiz_response_when_valid_json_then_returns_list() -> None:
    import json

    raw = json.dumps(_VALID_QUESTIONS)
    result = _parse_quiz_response(raw)
    assert len(result) == 1
    assert result[0]["correct_answer"] == "B"


def test_parse_quiz_response_when_markdown_fenced_then_strips_and_parses() -> None:
    import json

    raw = f"```json\n{json.dumps(_VALID_QUESTIONS)}\n```"
    result = _parse_quiz_response(raw)
    assert len(result) == 1


def test_parse_quiz_response_when_invalid_json_then_raises_value_error() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_quiz_response("not json at all")


def test_parse_quiz_response_when_wrong_option_count_then_raises_value_error() -> None:
    import json

    bad = [
        {
            "question_text": "Q?",
            "options": [{"key": "A", "text": "a"}, {"key": "B", "text": "b"}],  # only 2
            "correct_answer": "A",
        }
    ]
    with pytest.raises(ValueError, match="4 options"):
        _parse_quiz_response(json.dumps(bad))


# ---------------------------------------------------------------------------
# Tests: quiz writes to subtopic_content staging (not question_bank)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_quiz_when_no_existing_content_then_creates_staging_row() -> None:
    """Generated questions go to subtopic_content(content_type='quiz'), NOT question_bank."""
    db = _make_db()
    subtopic_id = uuid.uuid4()

    # No existing quiz content row
    no_content_result = MagicMock()
    no_content_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
    db.execute = AsyncMock(return_value=no_content_result)

    import json

    service = MiniCourseGenerationService(db)

    with patch("app.services.mini_course_generation_service.llm_router") as mock_router:
        mock_router.complete = AsyncMock(return_value=json.dumps(_VALID_QUESTIONS))
        count = await service._generate_quiz_questions(
            subtopic_id=subtopic_id,
            subtopic_name="Linear Equations",
            topic_name="Algebra",
            subject_name="Mathematics",
            grade_level=8,
            dry_run=False,
        )

    assert count == 1
    # db.add must have been called with a SubtopicContent (not QuestionBank)
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    from app.models.subtopic_content import SubtopicContent

    assert isinstance(added_obj, SubtopicContent)
    assert added_obj.content_type == "quiz"
    assert added_obj.review_status == "pending"
    assert len(added_obj.quiz_questions) == 1


@pytest.mark.asyncio
async def test_generate_quiz_when_existing_quiz_content_then_updates_staging_row() -> None:
    """When a quiz staging row already exists, it is updated in place, not duplicated."""
    db = _make_db()
    subtopic_id = uuid.uuid4()

    from app.models.subtopic_content import SubtopicContent

    existing = SubtopicContent(
        subtopic_id=subtopic_id,
        content_type="quiz",
        quiz_questions=[],
        review_status="rejected",
    )
    existing_result = MagicMock()
    existing_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=existing)))
    db.execute = AsyncMock(return_value=existing_result)

    import json

    service = MiniCourseGenerationService(db)

    with patch("app.services.mini_course_generation_service.llm_router") as mock_router:
        mock_router.complete = AsyncMock(return_value=json.dumps(_VALID_QUESTIONS))
        count = await service._generate_quiz_questions(
            subtopic_id=subtopic_id,
            subtopic_name="Linear Equations",
            topic_name="Algebra",
            subject_name="Mathematics",
            grade_level=8,
            dry_run=False,
        )

    assert count == 1
    # db.add must NOT have been called — existing row updated in place
    db.add.assert_not_called()
    assert existing.review_status == "pending"
    assert len(existing.quiz_questions) == 1


@pytest.mark.asyncio
async def test_generate_quiz_when_dry_run_then_does_not_write_to_db() -> None:
    """dry_run=True returns count but never writes to DB."""
    db = _make_db()

    import json

    service = MiniCourseGenerationService(db)

    with patch("app.services.mini_course_generation_service.llm_router") as mock_router:
        mock_router.complete = AsyncMock(return_value=json.dumps(_VALID_QUESTIONS))
        count = await service._generate_quiz_questions(
            subtopic_id=uuid.uuid4(),
            subtopic_name="Linear Equations",
            topic_name="Algebra",
            subject_name="Mathematics",
            grade_level=8,
            dry_run=True,
        )

    assert count == 1
    db.add.assert_not_called()
    db.execute.assert_not_called()
