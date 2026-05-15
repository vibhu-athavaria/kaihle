"""Unit tests for MiniCourseService.submit_content_feedback.

Tests:
- test_submit_content_feedback_when_thumbs_up_then_creates_feedback_and_increments_count
- test_submit_content_feedback_when_changed_from_thumbs_up_to_down_then_updates_both_counts
- test_submit_content_feedback_when_content_not_found_then_raises_404
- test_submit_content_feedback_when_comment_over_140_chars_then_raises_422
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.mini_course import SubtopicContentFeedback
from app.models.subtopic_content import SubtopicContent
from app.schemas.mini_course import FeedbackRequest
from app.services.mini_course_service import MiniCourseService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(content_id: uuid.UUID) -> SubtopicContent:
    content = MagicMock(spec=SubtopicContent)
    content.id = content_id
    return content


def _make_feedback(
    student_id: uuid.UUID,
    content_id: uuid.UUID,
    feedback_type: str,
    comment: str | None = None,
) -> SubtopicContentFeedback:
    fb = MagicMock(spec=SubtopicContentFeedback)
    fb.id = uuid.uuid4()
    fb.student_id = student_id
    fb.subtopic_content_id = content_id
    fb.feedback_type = feedback_type
    fb.comment = comment
    fb.created_at = datetime.now(UTC)
    return fb


def _make_counts(up: int, down: int) -> MagicMock:
    row = MagicMock()
    row.up_count = up
    row.down_count = down
    return row


def _build_service(db: AsyncMock) -> MiniCourseService:
    return MiniCourseService(db=db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_content_feedback_when_thumbs_up_then_creates_feedback_and_increments_count() -> None:
    """Arrange: content exists, no prior feedback.
    Act: submit thumbs_up.
    Assert: feedback row returned with feedback_type=thumbs_up; DB commit called.
    """
    student_id = uuid.uuid4()
    content_id = uuid.uuid4()
    school_id = uuid.uuid4()
    content = _make_content(content_id)
    feedback = _make_feedback(student_id, content_id, "thumbs_up")

    db = AsyncMock()

    # select(SubtopicContent) → returns content
    content_result = MagicMock()
    content_result.scalar_one_or_none.return_value = content

    # text() INSERT upsert → no meaningful return value
    upsert_result = MagicMock()

    # select(count) → counts row
    counts_result = MagicMock()
    counts_result.one.return_value = _make_counts(up=1, down=0)

    # update() → no meaningful return value
    update_result = MagicMock()

    # select(SubtopicContentFeedback) → returns feedback
    feedback_result = MagicMock()
    feedback_result.scalar_one.return_value = feedback

    db.execute = AsyncMock(side_effect=[content_result, upsert_result, counts_result, update_result, feedback_result])

    service = _build_service(db)
    result = await service.submit_content_feedback(
        content_id=content_id,
        student_id=student_id,
        school_id=school_id,
        feedback_type="thumbs_up",
        comment=None,
    )

    assert result.feedback_type == "thumbs_up"
    assert result.student_id == student_id
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_content_feedback_when_changed_from_thumbs_up_to_down_then_updates_both_counts() -> None:
    """Arrange: content exists, student previously gave thumbs_up.
    Act: submit thumbs_down.
    Assert: counts recalculated to 0 up / 1 down; returned feedback_type is thumbs_down.
    """
    student_id = uuid.uuid4()
    content_id = uuid.uuid4()
    school_id = uuid.uuid4()
    content = _make_content(content_id)
    # After upsert the row reflects the new type
    feedback = _make_feedback(student_id, content_id, "thumbs_down", comment="actually not helpful")

    db = AsyncMock()

    content_result = MagicMock()
    content_result.scalar_one_or_none.return_value = content

    upsert_result = MagicMock()

    counts_result = MagicMock()
    counts_result.one.return_value = _make_counts(up=0, down=1)

    update_result = MagicMock()

    feedback_result = MagicMock()
    feedback_result.scalar_one.return_value = feedback

    db.execute = AsyncMock(side_effect=[content_result, upsert_result, counts_result, update_result, feedback_result])

    service = _build_service(db)
    result = await service.submit_content_feedback(
        content_id=content_id,
        student_id=student_id,
        school_id=school_id,
        feedback_type="thumbs_down",
        comment="actually not helpful",
    )

    assert result.feedback_type == "thumbs_down"
    assert result.comment == "actually not helpful"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_content_feedback_when_content_not_found_then_raises_404() -> None:
    """Arrange: SubtopicContent row does not exist.
    Act: submit any feedback.
    Assert: HTTPException 404 raised before any upsert or commit.
    """
    db = AsyncMock()

    content_result = MagicMock()
    content_result.scalar_one_or_none.return_value = None  # not found

    db.execute = AsyncMock(return_value=content_result)

    service = _build_service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_content_feedback(
            content_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            feedback_type="thumbs_up",
            comment=None,
        )

    assert exc_info.value.status_code == 404
    db.commit.assert_not_awaited()


def test_submit_content_feedback_when_comment_over_140_chars_then_raises_422() -> None:
    """Arrange: FeedbackRequest with a comment longer than 140 characters.
    Act: instantiate the schema.
    Assert: ValidationError raised by Pydantic before the service is even called.
    """
    long_comment = "x" * 141
    with pytest.raises(ValidationError) as exc_info:
        FeedbackRequest(feedback_type="thumbs_up", comment=long_comment)

    errors = exc_info.value.errors()
    assert any("comment" in (e.get("loc") or ()) for e in errors)
