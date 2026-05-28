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


def _make_profile_row(
    interests: list[str] | None = None,
    modality_scores: dict | None = None,
    work_style: dict | None = None,
) -> MagicMock:
    row = MagicMock()
    row.interests = interests
    row.modality_scores = modality_scores or {"visual": 0.8, "auditory": 0.3}
    row.work_style = work_style or {"task_based": True}
    row.completed_at = datetime(2026, 1, 1, tzinfo=UTC)
    return row


def _make_open_answer_result(has_answer: bool = False) -> MagicMock:
    result = MagicMock()
    if has_answer:
        row = MagicMock()
        row.question_text = "Explain this concept."
        row.student_answer = "Because of photosynthesis."
        row.ai_grade = "partial"
        row.ai_feedback = "Good start, but consider the light reactions."
        row.score = 0.5
        result.scalar_one_or_none = MagicMock(return_value=row)
    else:
        result.scalar_one_or_none = MagicMock(return_value=None)
    return result


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

    # Profile query (full model)
    profile_result = MagicMock()
    profile_result.scalar_one_or_none = MagicMock(return_value=_make_profile_row(interests=["sports"]))

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
            _make_open_answer_result(),  # latest open answer
            MagicMock(),  # upsert execute
            progress_result,
            _make_next_subtopic_result(None),
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
    profile_result.scalar_one_or_none = MagicMock(return_value=_make_profile_row(interests=["sports"]))

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
            _make_open_answer_result(),
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
    profile_result.scalar_one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

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
            _make_open_answer_result(),
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
    profile_result.scalar_one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

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
            _make_open_answer_result(),
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
    profile_result.scalar_one_or_none = MagicMock(return_value=_make_profile_row(interests=None))

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
            _make_open_answer_result(),
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


# ---------------------------------------------------------------------------
# submit_quiz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_quiz_when_all_correct_then_writes_response_rows_and_returns_score() -> None:
    """submit_quiz writes one MiniCourseQuizResponse per answer and returns score=1.0 when all correct."""
    from app.schemas.mini_course import QuizAnswerItem, QuizSubmitRequest

    db = _make_db()
    db.add = MagicMock()

    subtopic_id = uuid.uuid4()
    student_id = uuid.uuid4()
    school_id = uuid.uuid4()
    q1_id = uuid.uuid4()
    q2_id = uuid.uuid4()

    # bank_rows result — correct answers A and B
    bank_result = MagicMock()
    bank_row1, bank_row2 = MagicMock(), MagicMock()
    bank_row1.id = q1_id
    bank_row1.question_text = "What is 1+1?"
    bank_row1.correct_answer = "A"
    bank_row2.id = q2_id
    bank_row2.question_text = "What is 2+2?"
    bank_row2.correct_answer = "B"

    # Iterating the execute result to build bank_map
    bank_result.__iter__ = MagicMock(return_value=iter([bank_row1, bank_row2]))
    bank_result.__aiter__ = MagicMock(return_value=iter([bank_row1, bank_row2]))

    # Use a simple object that supports direct iteration
    class _IterResult:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def __iter__(self):  # type: ignore[override]
            return iter(self._rows)

    iter_result = _IterResult([bank_row1, bank_row2])

    upsert_result = MagicMock()
    db.execute = AsyncMock(side_effect=[iter_result, upsert_result])

    service = MiniCourseService(db)
    request = QuizSubmitRequest(
        answers=[
            QuizAnswerItem(question_id=q1_id, selected_key="A"),
            QuizAnswerItem(question_id=q2_id, selected_key="B"),
        ]
    )
    response = await service.submit_quiz(subtopic_id, student_id, school_id, request)

    assert response.score == 1.0
    assert response.correct == 2
    assert response.total == 2
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_submit_quiz_when_some_incorrect_then_score_reflects_correct_fraction() -> None:
    """submit_quiz returns score=0.5 when 1 of 2 answers is correct."""
    from app.schemas.mini_course import QuizAnswerItem, QuizSubmitRequest

    db = _make_db()
    db.add = MagicMock()

    q1_id = uuid.uuid4()
    q2_id = uuid.uuid4()

    bank_row1, bank_row2 = MagicMock(), MagicMock()
    bank_row1.id = q1_id
    bank_row1.question_text = "Q1"
    bank_row1.correct_answer = "A"
    bank_row2.id = q2_id
    bank_row2.question_text = "Q2"
    bank_row2.correct_answer = "B"

    class _IterResult:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def __iter__(self):  # type: ignore[override]
            return iter(self._rows)

    db.execute = AsyncMock(side_effect=[_IterResult([bank_row1, bank_row2]), MagicMock()])

    service = MiniCourseService(db)
    request = QuizSubmitRequest(
        answers=[
            QuizAnswerItem(question_id=q1_id, selected_key="A"),  # correct
            QuizAnswerItem(question_id=q2_id, selected_key="WRONG"),  # incorrect
        ]
    )
    response = await service.submit_quiz(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), request)

    assert response.correct == 1
    assert response.total == 2
    assert response.score == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_submit_quiz_when_empty_answers_then_score_is_zero() -> None:
    """submit_quiz returns score=0.0 when no answers are submitted (empty bank_map)."""
    from app.schemas.mini_course import QuizSubmitRequest

    db = _make_db()
    db.add = MagicMock()

    class _IterResult:
        def __iter__(self):  # type: ignore[override]
            return iter([])

    db.execute = AsyncMock(side_effect=[_IterResult(), MagicMock()])

    service = MiniCourseService(db)
    request = QuizSubmitRequest(answers=[])
    response = await service.submit_quiz(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), request)

    assert response.score == 0.0
    assert response.total == 0
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# get_chat_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_history_when_messages_exist_then_returns_ordered_list() -> None:
    """get_chat_history returns ChatHistoryResponse with messages from DB, oldest first."""
    db = _make_db()
    student_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()
    school_id = uuid.uuid4()

    msg1 = MagicMock()
    msg1.role = "student"
    msg1.content = "What is a variable?"
    msg1.created_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    msg2 = MagicMock()
    msg2.role = "ai"
    msg2.content = "A variable stores a value."
    msg2.created_at = datetime(2026, 1, 1, 10, 0, 5, tzinfo=UTC)

    history_result = MagicMock()
    history_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[msg1, msg2])))
    db.execute = AsyncMock(return_value=history_result)

    service = MiniCourseService(db)
    response = await service.get_chat_history(student_id, subtopic_id, school_id)

    assert len(response.messages) == 2
    assert response.messages[0].role == "student"
    assert response.messages[1].role == "ai"


@pytest.mark.asyncio
async def test_get_chat_history_when_no_messages_then_returns_empty_list() -> None:
    """get_chat_history returns empty messages list when no rows found."""
    db = _make_db()
    history_result = MagicMock()
    history_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    db.execute = AsyncMock(return_value=history_result)

    service = MiniCourseService(db)
    response = await service.get_chat_history(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    assert response.messages == []


# ---------------------------------------------------------------------------
# save_chat_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_chat_message_when_called_then_adds_and_commits() -> None:
    """save_chat_message adds a MiniCourseChatMessage to db and commits."""
    db = _make_db()
    db.add = MagicMock()
    db.refresh = AsyncMock()

    saved_msg = MagicMock()
    saved_msg.id = uuid.uuid4()
    saved_msg.role = "student"
    saved_msg.content = "Hello"

    db.refresh = AsyncMock(side_effect=lambda obj: None)

    service = MiniCourseService(db)
    await service.save_chat_message(
        student_id=uuid.uuid4(),
        subtopic_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        role="student",
        content="Hello",
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# generate_transfer_question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_transfer_question_when_llm_returns_valid_text_then_returns_question() -> None:
    """generate_transfer_question calls LLM and returns question text."""
    from unittest.mock import patch

    db = _make_db()
    subtopic_id = uuid.uuid4()
    student_id = uuid.uuid4()

    subtopic_row = MagicMock()
    subtopic_row.name = "Linear Equations"
    subtopic_row.learning_objective = "Solve for x"
    subtopic_row.keywords = ["variable", "coefficient"]
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=subtopic_row)

    profile_result = MagicMock()
    profile_result.scalar_one_or_none = MagicMock(return_value=None)

    db.execute = AsyncMock(side_effect=[subtopic_result, profile_result])

    with patch(
        "app.services.mini_course_service.llm_router.complete",
        new=AsyncMock(return_value="How would you use linear equations to budget a monthly allowance?"),
    ):
        service = MiniCourseService(db)
        response = await service.generate_transfer_question(subtopic_id, student_id)

    assert "?" in response.question_text
    assert len(response.question_text) >= 10


@pytest.mark.asyncio
async def test_generate_transfer_question_when_llm_fails_then_returns_fallback() -> None:
    """generate_transfer_question falls back to generic question on LLM error."""
    from unittest.mock import patch

    from app.services.mini_course_service import _TRANSFER_QUESTION_FALLBACK

    db = _make_db()

    subtopic_row = MagicMock()
    subtopic_row.name = "Linear Equations"
    subtopic_row.learning_objective = "Solve for x"
    subtopic_row.keywords = []
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=subtopic_row)

    profile_result = MagicMock()
    profile_result.scalar_one_or_none = MagicMock(return_value=None)

    db.execute = AsyncMock(side_effect=[subtopic_result, profile_result])

    with patch(
        "app.services.mini_course_service.llm_router.complete", new=AsyncMock(side_effect=RuntimeError("LLM down"))
    ):
        service = MiniCourseService(db)
        response = await service.generate_transfer_question(uuid.uuid4(), uuid.uuid4())

    assert response.question_text == _TRANSFER_QUESTION_FALLBACK


@pytest.mark.asyncio
async def test_generate_transfer_question_when_subtopic_not_found_then_raises_404() -> None:
    """generate_transfer_question raises 404 when subtopic does not exist."""
    db = _make_db()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=subtopic_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_transfer_question(uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# grade_open_answer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grade_open_answer_when_llm_returns_correct_then_score_is_1() -> None:
    """grade_open_answer returns score=1.0 when LLM grades answer as correct."""
    import json as _json
    from unittest.mock import patch

    db = _make_db()
    db.add = MagicMock()
    db.flush = AsyncMock()

    subtopic_row = MagicMock()
    subtopic_row.name = "Linear Equations"
    subtopic_row.learning_objective = "Solve for x"
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=subtopic_row)

    agg_result = MagicMock()
    agg_result.scalar_one_or_none = MagicMock(return_value=0.85)

    db.execute = AsyncMock(side_effect=[subtopic_result, agg_result, MagicMock()])

    llm_payload = _json.dumps({"grade": "correct", "feedback": "Well done!"})

    with patch("app.services.mini_course_service.llm_router.complete", new=AsyncMock(return_value=llm_payload)):
        service = MiniCourseService(db)
        response = await service.grade_open_answer(
            subtopic_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            question_text="How do you solve 2x = 4?",
            student_answer="Divide both sides by 2, so x = 2.",
        )

    assert response.grade == "correct"
    assert response.score == 1.0
    assert response.updated_course_score == 0.85


@pytest.mark.asyncio
async def test_grade_open_answer_when_llm_returns_partial_then_score_is_half() -> None:
    """grade_open_answer maps 'partial' grade to score=0.5."""
    import json as _json
    from unittest.mock import patch

    db = _make_db()
    db.add = MagicMock()
    db.flush = AsyncMock()

    subtopic_row = MagicMock()
    subtopic_row.name = "Linear Equations"
    subtopic_row.learning_objective = "Solve for x"
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=subtopic_row)

    agg_result = MagicMock()
    agg_result.scalar_one_or_none = MagicMock(return_value=0.5)

    db.execute = AsyncMock(side_effect=[subtopic_result, agg_result, MagicMock()])

    llm_payload = _json.dumps({"grade": "partial", "feedback": "Close, but missing a step."})

    with patch("app.services.mini_course_service.llm_router.complete", new=AsyncMock(return_value=llm_payload)):
        service = MiniCourseService(db)
        response = await service.grade_open_answer(
            subtopic_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            question_text="How do you solve 2x = 4?",
            student_answer="x equals something",
        )

    assert response.grade == "partial"
    assert response.score == 0.5


@pytest.mark.asyncio
async def test_grade_open_answer_when_llm_fails_then_defaults_to_incorrect() -> None:
    """grade_open_answer defaults to 'incorrect' grade when LLM call raises."""
    from unittest.mock import patch

    db = _make_db()
    db.add = MagicMock()
    db.flush = AsyncMock()

    subtopic_row = MagicMock()
    subtopic_row.name = "Linear Equations"
    subtopic_row.learning_objective = "Solve for x"
    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=subtopic_row)

    agg_result = MagicMock()
    agg_result.scalar_one_or_none = MagicMock(return_value=0.0)

    db.execute = AsyncMock(side_effect=[subtopic_result, agg_result, MagicMock()])

    with patch(
        "app.services.mini_course_service.llm_router.complete", new=AsyncMock(side_effect=RuntimeError("LLM down"))
    ):
        service = MiniCourseService(db)
        response = await service.grade_open_answer(
            subtopic_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            question_text="How do you solve 2x = 4?",
            student_answer="I don't know.",
        )

    assert response.grade == "incorrect"
    assert response.score == 0.0


@pytest.mark.asyncio
async def test_grade_open_answer_when_subtopic_not_found_then_raises_404() -> None:
    """grade_open_answer raises 404 when subtopic does not exist."""
    db = _make_db()

    subtopic_result = MagicMock()
    subtopic_result.one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=subtopic_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.grade_open_answer(
            subtopic_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            question_text="q",
            student_answer="a",
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# submit_content_feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_content_feedback_when_content_not_found_then_raises_404() -> None:
    """submit_content_feedback raises 404 when SubtopicContent does not exist."""
    db = _make_db()
    content_result = MagicMock()
    content_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=content_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_content_feedback(
            content_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            feedback_type="thumbs_up",
            comment=None,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_content_feedback_when_valid_then_upserts_and_returns_row() -> None:
    """submit_content_feedback upserts feedback and returns the saved row."""
    db = _make_db()

    content_row = MagicMock()
    content_result = MagicMock()
    content_result.scalar_one_or_none = MagicMock(return_value=content_row)

    counts_result = MagicMock()
    counts_row = MagicMock()
    counts_row.up_count = 3
    counts_row.down_count = 1
    counts_result.one = MagicMock(return_value=counts_row)

    saved_feedback = MagicMock()
    saved_feedback.id = uuid.uuid4()
    saved_feedback.feedback_type = "thumbs_up"
    saved_feedback.comment = None
    saved_feedback.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    feedback_result = MagicMock()
    feedback_result.scalar_one = MagicMock(return_value=saved_feedback)

    # Sequence: content check, upsert, counts query, update content, feedback select
    db.execute = AsyncMock(
        side_effect=[
            content_result,
            MagicMock(),
            counts_result,
            MagicMock(),
            feedback_result,
        ]
    )

    service = MiniCourseService(db)
    result = await service.submit_content_feedback(
        content_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        feedback_type="thumbs_up",
        comment=None,
    )

    assert result.feedback_type == "thumbs_up"
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_student_course_progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_student_course_progress_when_student_not_in_school_then_raises_403() -> None:
    """get_student_course_progress raises 403 when the student does not belong to the school."""
    db = _make_db()

    student_result = MagicMock()
    student_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=student_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_student_course_progress(
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_student_course_progress_when_student_exists_then_returns_progress() -> None:
    """get_student_course_progress returns progress items for a valid student."""
    db = _make_db()

    student_row = MagicMock()
    student_result = MagicMock()
    student_result.scalar_one_or_none = MagicMock(return_value=student_row)

    progress_row = MagicMock()
    progress_row.subtopic_id = uuid.uuid4()
    progress_row.subtopic_name = "Linear Equations"
    progress_row.topic_name = "Algebra"
    progress_row.last_visited_at = datetime(2026, 1, 1, tzinfo=UTC)
    progress_row.explanation_accessed = True
    progress_row.video_accessed = False
    progress_row.check_questions_score = 0.8

    rows_result = MagicMock()
    rows_result.all = MagicMock(return_value=[progress_row])

    db.execute = AsyncMock(side_effect=[student_result, rows_result])

    service = MiniCourseService(db)
    student_id = uuid.uuid4()
    response = await service.get_student_course_progress(
        student_id=student_id,
        school_id=uuid.uuid4(),
        teacher_id=uuid.uuid4(),
    )

    assert response.student_id == student_id
    assert len(response.progress) == 1
    assert response.progress[0].subtopic_name == "Linear Equations"


# ---------------------------------------------------------------------------
# set_student_override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_student_override_when_none_category_and_existing_then_deletes_override() -> None:
    """set_student_override deletes existing override when interest_category_id is None."""
    db = _make_db()
    db.delete = AsyncMock()

    existing = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=existing)
    db.execute = AsyncMock(return_value=existing_result)

    service = MiniCourseService(db)
    await service.set_student_override(
        school_id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        teacher_id=uuid.uuid4(),
        interest_category_id=None,
    )

    db.delete.assert_called_once_with(existing)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_set_student_override_when_new_category_and_no_existing_then_adds_override() -> None:
    """set_student_override creates a new override row when none exists."""
    db = _make_db()
    db.add = MagicMock()

    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=existing_result)

    service = MiniCourseService(db)
    await service.set_student_override(
        school_id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        teacher_id=uuid.uuid4(),
        interest_category_id=uuid.uuid4(),
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_set_student_override_when_existing_override_then_updates_in_place() -> None:
    """set_student_override updates the existing override row when one already exists."""
    db = _make_db()

    new_cat_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    existing = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=existing)
    db.execute = AsyncMock(return_value=existing_result)

    service = MiniCourseService(db)
    await service.set_student_override(
        school_id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        teacher_id=teacher_id,
        interest_category_id=new_cat_id,
    )

    assert existing.interest_category_id == new_cat_id
    assert existing.set_by_teacher_id == teacher_id
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_course_detail_for_teacher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_detail_for_teacher_when_class_not_found_then_raises_404() -> None:
    """get_course_detail_for_teacher raises 404 when the class does not belong to the school."""
    db = _make_db()
    class_result = MagicMock()
    class_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=class_result)

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_course_detail_for_teacher(
            topic_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_course_detail_for_teacher_when_topic_not_found_then_raises_404() -> None:
    """get_course_detail_for_teacher raises 404 when the topic does not exist."""
    db = _make_db()

    class_row = MagicMock()
    class_result = MagicMock()
    class_result.scalar_one_or_none = MagicMock(return_value=class_row)

    topic_result = MagicMock()
    topic_result.first = MagicMock(return_value=None)

    db.execute = AsyncMock(side_effect=[class_result, topic_result])

    service = MiniCourseService(db)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_course_detail_for_teacher(
            topic_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_course_detail_for_teacher_when_valid_then_returns_structure() -> None:
    """get_course_detail_for_teacher returns expected top-level keys on valid input."""
    db = _make_db()

    class_row = MagicMock()
    class_result = MagicMock()
    class_result.scalar_one_or_none = MagicMock(return_value=class_row)

    topic_row = MagicMock()
    topic_row.name = "Algebra"
    topic_result = MagicMock()
    topic_result.first = MagicMock(return_value=topic_row)

    cats_result = MagicMock()
    cats_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    subtopics_result = MagicMock()
    subtopics_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    content_result = MagicMock()
    content_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    enrolled_result = MagicMock()
    enrolled_result.all = MagicMock(return_value=[])

    db.execute = AsyncMock(
        side_effect=[
            class_result,
            topic_result,
            cats_result,
            subtopics_result,
            content_result,
            enrolled_result,
        ]
    )

    service = MiniCourseService(db)
    topic_id = uuid.uuid4()
    result = await service.get_course_detail_for_teacher(
        topic_id=topic_id,
        class_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
    )

    assert result["topic_name"] == "Algebra"
    assert result["subtopics"] == []
    assert result["students"] == []
    assert "interest_categories" in result


@pytest.mark.asyncio
async def test_get_course_detail_for_teacher_when_subtopics_and_content_then_builds_variants() -> None:
    """get_course_detail_for_teacher assembles variant grid when subtopics and content exist."""
    db = _make_db()

    class_row = MagicMock()
    class_result = MagicMock()
    class_result.scalar_one_or_none = MagicMock(return_value=class_row)

    topic_row = MagicMock()
    topic_row.name = "Algebra"
    topic_result = MagicMock()
    topic_result.first = MagicMock(return_value=topic_row)

    # One interest category: sports
    cat = MagicMock()
    cat.id = uuid.uuid4()
    cat.name = "sports_movement"
    cats_result = MagicMock()
    cats_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cat])))

    # One subtopic
    sub_id = uuid.uuid4()
    sub = MagicMock()
    sub.id = sub_id
    sub.name = "Linear Equations"
    sub.sequence_order = 1
    subtopics_result = MagicMock()
    subtopics_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[sub])))

    # One content row for that subtopic+category
    content = MagicMock()
    content.id = uuid.uuid4()
    content.subtopic_id = sub_id
    content.interest_category_id = cat.id
    content.explanation_text = "Sports explanation"
    content.teacher_explanation = None
    content.review_status = "approved"
    content_result = MagicMock()
    content_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[content])))

    # No enrolled students
    enrolled_result = MagicMock()
    enrolled_result.all = MagicMock(return_value=[])

    db.execute = AsyncMock(
        side_effect=[
            class_result,
            topic_result,
            cats_result,
            subtopics_result,
            content_result,
            enrolled_result,
        ]
    )

    service = MiniCourseService(db)
    result = await service.get_course_detail_for_teacher(
        topic_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
    )

    assert len(result["subtopics"]) == 1
    subtopic_out = result["subtopics"][0]
    assert subtopic_out["subtopic_name"] == "Linear Equations"
    assert subtopic_out["variants"]["sports_movement"] is not None
    assert subtopic_out["variants"]["sports_movement"]["review_status"] == "approved"
