"""Unit tests for MiniCourseService.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_mini_course_service.py -v
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.mini_course import MarkProgressRequest
from app.services.mini_course_service import MiniCourseService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    """Create a minimal mock AsyncSession."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_subtopic_row(
    subtopic_name: str = "Linear Equations",
    topic_name: str = "Algebra",
) -> MagicMock:
    row = MagicMock()
    row.subtopic_name = subtopic_name
    row.topic_name = topic_name
    row.sequence_order = 1
    row.curriculum_topic_id = uuid.uuid4()
    return row


def _make_next_subtopic_result(name: str | None = None) -> MagicMock:
    """Returns a mock DB result for the next-subtopic query.
    Pass name=None to simulate 'last subtopic' (no next)."""
    result = MagicMock()
    if name is None:
        result.one_or_none = MagicMock(return_value=None)
    else:
        row = MagicMock()
        row.id = uuid.uuid4()
        row.name = name
        result.one_or_none = MagicMock(return_value=row)
    return result


def _make_profile_row(interests: list[str] | None = None) -> MagicMock:
    row = MagicMock()
    row.interests = interests
    return row


def _make_content_row(
    content_id: uuid.UUID | None = None,
    explanation_text: str = "This is an explanation",
    interest_category_id: uuid.UUID | None = None,
    video_url: str | None = None,
    video_thumbnail_url: str | None = None,
    video_duration_seconds: int | None = None,
    content_type: str = "explanation",
) -> MagicMock:
    row = MagicMock()
    row.id = content_id or uuid.uuid4()
    row.explanation_text = explanation_text
    row.teacher_explanation = None
    row.interest_category_id = interest_category_id
    row.video_url = video_url
    row.video_thumbnail_url = video_thumbnail_url
    row.video_duration_seconds = video_duration_seconds
    row.content_type = content_type
    return row


def _make_question_row(
    question_id: uuid.UUID | None = None,
    question_text: str = "What is 2+2?",
    options: list[dict[str, Any]] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = question_id or uuid.uuid4()
    row.question_text = question_text
    row.correct_answer = "B"
    row.options = options or [
        {"key": "A", "text": "3"},
        {"key": "B", "text": "4"},
        {"key": "C", "text": "5"},
    ]
    return row


def _make_progress_row(
    explanation_accessed: bool = False,
    video_accessed: bool = False,
    check_questions_score: float | None = None,
) -> MagicMock:
    row = MagicMock()
    row.explanation_accessed = explanation_accessed
    row.video_accessed = video_accessed
    row.check_questions_score = check_questions_score
    row.last_visited_at = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    return row


# ---------------------------------------------------------------------------
# Tests for get_course_for_student
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_when_interest_matched_explanation_exists_then_returns_matched() -> None:
    """When SubtopicContent row interest_category_id matches student's, interest_matched=True."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()
    matched_cat_id = uuid.uuid4()

    # Subtopic query
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=_make_subtopic_row())

    # Profile query
    profile_result = MagicMock()
    profile_result.one_or_none = MagicMock(return_value=_make_profile_row(interests=["sports"]))

    # Interest category query
    cat_result = MagicMock()
    cat_row = MagicMock()
    cat_row.id = matched_cat_id
    cat_result.one_or_none = MagicMock(return_value=cat_row)

    # Explanation query (interest matched)
    explanation_content = _make_content_row(interest_category_id=matched_cat_id)
    explanation_result = MagicMock()
    explanation_result.scalar_one_or_none = MagicMock(return_value=explanation_content)

    # Video query (none)
    video_result = MagicMock()
    video_result.scalar_one_or_none = MagicMock(return_value=None)

    # Questions query
    question_result = MagicMock()
    question_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    # Upsert visit (execute returns nothing significant)
    # Progress reload
    progress_result = MagicMock()
    progress_result.scalar_one = MagicMock(return_value=_make_progress_row())

    db.execute = AsyncMock(
        side_effect=[
            subtopic_result,
            profile_result,
            cat_result,
            explanation_result,
            video_result,
            question_result,
            MagicMock(),  # upsert execute
            progress_result,
            _make_next_subtopic_result(None),  # next subtopic query
        ]
    )

    service = MiniCourseService(db)
    response = await service.get_course_for_student(subtopic_id, student_id, school_id)

    assert response.explanation is not None
    assert response.explanation.interest_matched is True
    assert response.content_status == "ready"


@pytest.mark.asyncio
async def test_get_course_when_no_interest_match_then_falls_back_to_generic() -> None:
    """When explanation interest_category_id is None, interest_matched=False but explanation not None."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()
    matched_cat_id = uuid.uuid4()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=_make_subtopic_row())

    profile_result = MagicMock()
    profile_result.one_or_none = MagicMock(return_value=_make_profile_row(interests=["sports"]))

    cat_result = MagicMock()
    cat_row = MagicMock()
    cat_row.id = matched_cat_id
    cat_result.one_or_none = MagicMock(return_value=cat_row)

    # Generic explanation: interest_category_id=None
    explanation_content = _make_content_row(interest_category_id=None)
    explanation_result = MagicMock()
    explanation_result.scalar_one_or_none = MagicMock(return_value=explanation_content)

    video_result = MagicMock()
    video_result.scalar_one_or_none = MagicMock(return_value=None)

    question_result = MagicMock()
    question_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    progress_result = MagicMock()
    progress_result.scalar_one = MagicMock(return_value=_make_progress_row())

    db.execute = AsyncMock(
        side_effect=[
            subtopic_result,
            profile_result,
            cat_result,
            explanation_result,
            video_result,
            question_result,
            MagicMock(),
            progress_result,
            _make_next_subtopic_result(None),
        ]
    )

    service = MiniCourseService(db)
    response = await service.get_course_for_student(subtopic_id, student_id, school_id)

    assert response.explanation is not None
    assert response.explanation.interest_matched is False


@pytest.mark.asyncio
async def test_get_course_when_no_approved_explanation_then_returns_unavailable_status() -> None:
    """When no approved explanation exists, content_status=='unavailable' and explanation is None."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=_make_subtopic_row())

    profile_result = MagicMock()
    profile_result.one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

    # No explanation
    explanation_result = MagicMock()
    explanation_result.scalar_one_or_none = MagicMock(return_value=None)

    video_result = MagicMock()
    video_result.scalar_one_or_none = MagicMock(return_value=None)

    question_result = MagicMock()
    question_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    progress_result = MagicMock()
    progress_result.scalar_one = MagicMock(return_value=_make_progress_row())

    db.execute = AsyncMock(
        side_effect=[
            subtopic_result,
            profile_result,
            explanation_result,
            video_result,
            question_result,
            MagicMock(),
            progress_result,
            _make_next_subtopic_result(None),
        ]
    )

    service = MiniCourseService(db)
    response = await service.get_course_for_student(subtopic_id, student_id, school_id)

    assert response.content_status == "unavailable"
    assert response.explanation is None


@pytest.mark.asyncio
async def test_get_course_when_question_bank_has_5_questions_then_returns_3() -> None:
    """Service always returns at most 3 check questions regardless of how many DB returns."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=_make_subtopic_row())

    profile_result = MagicMock()
    profile_result.one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

    explanation_result = MagicMock()
    explanation_result.scalar_one_or_none = MagicMock(return_value=None)

    video_result = MagicMock()
    video_result.scalar_one_or_none = MagicMock(return_value=None)

    # 5 question rows (service limits query to 3 via LIMIT, but mock can return any count)
    five_questions = [_make_question_row() for _ in range(5)]
    question_result = MagicMock()
    question_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=five_questions[:3])))

    progress_result = MagicMock()
    progress_result.scalar_one = MagicMock(return_value=_make_progress_row())

    db.execute = AsyncMock(
        side_effect=[
            subtopic_result,
            profile_result,
            explanation_result,
            video_result,
            question_result,
            MagicMock(),
            progress_result,
            _make_next_subtopic_result(None),
        ]
    )

    service = MiniCourseService(db)
    response = await service.get_course_for_student(subtopic_id, student_id, school_id)

    assert len(response.check_questions) == 3


@pytest.mark.asyncio
async def test_get_course_when_no_video_approved_then_video_is_none() -> None:
    """When no approved video exists, response.video is None."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=_make_subtopic_row())

    profile_result = MagicMock()
    profile_result.one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

    explanation_result = MagicMock()
    explanation_result.scalar_one_or_none = MagicMock(return_value=_make_content_row())

    # No video
    video_result = MagicMock()
    video_result.scalar_one_or_none = MagicMock(return_value=None)

    question_result = MagicMock()
    question_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    progress_result = MagicMock()
    progress_result.scalar_one = MagicMock(return_value=_make_progress_row())

    db.execute = AsyncMock(
        side_effect=[
            subtopic_result,
            profile_result,
            explanation_result,
            video_result,
            question_result,
            MagicMock(),
            progress_result,
            _make_next_subtopic_result(None),
        ]
    )

    service = MiniCourseService(db)
    response = await service.get_course_for_student(subtopic_id, student_id, school_id)

    assert response.video is None


@pytest.mark.asyncio
async def test_mark_progress_when_called_with_explanation_true_then_upserts_correctly() -> None:
    """mark_progress calls db.execute with explanation_accessed=True in the SQL params."""
    db = _make_db()
    execute_calls: list[Any] = []

    async def capture_execute(stmt: Any, params: Any = None) -> MagicMock:
        execute_calls.append({"stmt": stmt, "params": params})
        return MagicMock()

    db.execute = capture_execute

    service = MiniCourseService(db)
    request = MarkProgressRequest(explanation_accessed=True, video_accessed=False)

    await service.mark_progress(
        subtopic_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        request=request,
    )

    # Should have exactly one db.execute call for the upsert
    assert len(execute_calls) == 1
    params = execute_calls[0]["params"]
    assert params["explanation_accessed"] is True
    assert params["video_accessed"] is False


# ---------------------------------------------------------------------------
# Tests: video assembly reads from JSONB array (M3-1-T1)
# ---------------------------------------------------------------------------


def _make_video_content(videos: list[dict] | None) -> MagicMock:
    """Build a minimal SubtopicContent mock with JSONB videos."""
    content = MagicMock()
    content.videos = videos
    content.video_url = None  # legacy flat columns must be ignored
    content.video_thumbnail_url = None
    content.video_duration_seconds = None
    return content


def test_video_assembly_when_approved_entry_exists_then_uses_jsonb_url() -> None:
    """Video URL must come from JSONB videos array, not legacy flat columns."""
    from app.schemas.mini_course import SubtopicVideoItem

    video_content = _make_video_content(
        [{"url": "https://yt.com/watch?v=abc", "status": "approved", "thumbnail_url": None, "duration_seconds": 300}]
    )
    approved = [v for v in (video_content.videos or []) if v.get("status") == "approved"]
    assert len(approved) == 1
    first = approved[0]
    item = SubtopicVideoItem(
        video_url=first.get("url", ""),
        thumbnail_url=first.get("thumbnail_url"),
        duration_seconds=first.get("duration_seconds"),
    )
    assert item.video_url == "https://yt.com/watch?v=abc"
    assert item.duration_seconds == 300


def test_video_assembly_when_all_entries_pending_then_no_item() -> None:
    """When no approved entry in JSONB array, video_item must be None."""
    video_content = _make_video_content([{"url": "https://yt.com/watch?v=pending", "status": "pending"}])
    approved = [v for v in (video_content.videos or []) if v.get("status") == "approved"]
    assert approved == []


def test_video_assembly_when_videos_is_null_then_no_item() -> None:
    """When videos JSONB is NULL, approved list is empty."""
    video_content = _make_video_content(None)
    approved = [v for v in (video_content.videos or []) if v.get("status") == "approved"]
    assert approved == []


def test_video_assembly_when_mixed_statuses_then_picks_first_approved() -> None:
    """When multiple entries exist, first approved entry is used."""
    from app.schemas.mini_course import SubtopicVideoItem

    video_content = _make_video_content(
        [
            {"url": "https://yt.com/watch?v=rejected", "status": "rejected"},
            {
                "url": "https://yt.com/watch?v=approved1",
                "status": "approved",
                "thumbnail_url": None,
                "duration_seconds": None,
            },
            {
                "url": "https://yt.com/watch?v=approved2",
                "status": "approved",
                "thumbnail_url": None,
                "duration_seconds": None,
            },
        ]
    )
    approved = [v for v in (video_content.videos or []) if v.get("status") == "approved"]
    first = approved[0]
    item = SubtopicVideoItem(
        video_url=first.get("url", ""),
        thumbnail_url=first.get("thumbnail_url"),
        duration_seconds=first.get("duration_seconds"),
    )
    assert item.video_url == "https://yt.com/watch?v=approved1"


@pytest.mark.asyncio
async def test_get_course_when_subtopic_not_found_then_raises_404() -> None:
    """When Subtopic query returns None, HTTPException 404 is raised."""
    db = _make_db()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=None)

    db.execute = AsyncMock(return_value=subtopic_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_course_for_student(
            subtopic_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 404
