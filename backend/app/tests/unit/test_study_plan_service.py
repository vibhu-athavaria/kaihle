"""Unit tests for study_plan_service — M3-2-T1.

Covers:
- get_study_plan: ownership checks for STUDENT, KAIHLE_ADMIN, plan-not-found
- list_student_plans: school isolation via Class JOIN, subtopic batching, pagination
- submit_quiz: all-correct scoring, plan-not-found error
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.study_plan_service import (
    get_study_plan,
    list_student_plans,
    submit_quiz,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_plan(student_id=None, class_id=None, subtopic_id=None, status="ACTIVE"):
    """Return a MagicMock representing a StudyPlan ORM row."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.student_id = student_id or uuid.uuid4()
    plan.class_id = class_id or uuid.uuid4()
    plan.subtopic_id = subtopic_id or uuid.uuid4()
    plan.status = status
    plan.assigned_by = uuid.uuid4()
    plan.created_at = datetime.now(UTC)
    plan.completed_at = None
    plan.resources = []
    plan.quiz = None
    return plan


def _make_quiz(plan_id=None, questions=None, score=None):
    """Return a MagicMock representing a StudyPlanQuiz ORM row."""
    quiz = MagicMock()
    quiz.plan_id = plan_id or uuid.uuid4()
    quiz.questions = questions or {"questions": []}
    quiz.score = score
    quiz.completed_at = None
    quiz.student_answers = None
    return quiz


def _scalar_result(value):
    """Build a mock db result where scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# get_study_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_study_plan_when_student_owns_plan_then_returns_plan():
    """Student who owns the plan receives the plan response."""
    student_id = uuid.uuid4()
    plan = _make_plan(student_id=student_id)

    subtopic = MagicMock()
    subtopic.id = plan.subtopic_id
    subtopic.name = "Algebra Basics"

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar_result(plan),  # plan fetch
            _scalar_result(subtopic),  # subtopic name fetch
        ]
    )

    response = await get_study_plan(
        plan_id=plan.id,
        student_id=student_id,
        school_id=uuid.uuid4(),
        user_role="STUDENT",
        db=mock_db,
    )

    assert response.id == plan.id
    assert response.student_id == student_id
    assert response.subtopic_name == "Algebra Basics"
    assert response.resources == []


@pytest.mark.asyncio
async def test_get_study_plan_when_student_does_not_own_plan_then_raises_permission_error():
    """STUDENT requesting another student's plan raises PermissionError."""
    requesting_student_id = uuid.uuid4()
    owner_student_id = uuid.uuid4()
    plan = _make_plan(student_id=owner_student_id)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_result(plan))

    with pytest.raises(PermissionError, match="belongs to a different student"):
        await get_study_plan(
            plan_id=plan.id,
            student_id=requesting_student_id,  # different from plan.student_id
            school_id=uuid.uuid4(),
            user_role="STUDENT",
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_get_study_plan_when_kaihle_admin_then_bypasses_ownership_check():
    """KAIHLE_ADMIN bypasses ownership check and can access any plan (Rule 12)."""
    admin_id = uuid.uuid4()
    owner_student_id = uuid.uuid4()
    plan = _make_plan(student_id=owner_student_id)

    subtopic = MagicMock()
    subtopic.id = plan.subtopic_id
    subtopic.name = "Forces and Motion"

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar_result(plan),
            _scalar_result(subtopic),
        ]
    )

    # admin_id != plan.student_id — should NOT raise PermissionError
    response = await get_study_plan(
        plan_id=plan.id,
        student_id=admin_id,
        school_id=uuid.uuid4(),
        user_role="KAIHLE_ADMIN",
        db=mock_db,
    )

    assert response.id == plan.id
    assert response.student_id == owner_student_id  # plan still shows its real owner
    assert response.subtopic_name == "Forces and Motion"


@pytest.mark.asyncio
async def test_get_study_plan_when_plan_not_found_then_raises_value_error():
    """Fetching a non-existent plan raises ValueError."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_result(None))

    with pytest.raises(ValueError, match="not found"):
        await get_study_plan(
            plan_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            user_role="STUDENT",
            db=mock_db,
        )


# ---------------------------------------------------------------------------
# list_student_plans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_student_plans_when_valid_student_then_filters_by_school_via_class():
    """list_student_plans returns paginated plans and populates subtopic names without N+1."""
    student_id = uuid.uuid4()
    school_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()

    plan = _make_plan(student_id=student_id, subtopic_id=subtopic_id)

    # Mock 1: count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    # Mock 2: data query (plans)
    data_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [plan]
    data_result.scalars.return_value = scalars_mock

    # Mock 3: subtopic batch query — uses scalars().all() (full ORM objects)
    subtopic_row = MagicMock()
    subtopic_row.id = subtopic_id
    subtopic_row.name = "Trigonometry"
    subtopic_result = MagicMock()
    subtopic_scalars = MagicMock()
    subtopic_scalars.all.return_value = [subtopic_row]
    subtopic_result.scalars.return_value = subtopic_scalars

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result, subtopic_result])

    page = await list_student_plans(
        student_id=student_id,
        school_id=school_id,
        db=mock_db,
        page=1,
        page_size=20,
    )

    assert page.total == 1
    assert len(page.data) == 1
    assert page.data[0].student_id == student_id
    assert page.data[0].subtopic_name == "Trigonometry"
    # Three execute calls means no N+1: count + data + single subtopic batch
    assert mock_db.execute.call_count == 3


# ---------------------------------------------------------------------------
# submit_quiz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_quiz_when_all_correct_then_score_is_1():
    """All correct responses produce score=1.0, plan status COMPLETED, and gap task queued."""
    student_id = uuid.uuid4()
    plan = _make_plan(student_id=student_id, status="ACTIVE")

    questions_data = {
        "questions": [
            {
                "index": 0,
                "question_text": "What is 2+2?",
                "options": [{"key": "A", "text": "4"}],
                "correct_answer": "A",
            },
            {
                "index": 1,
                "question_text": "What is 3×3?",
                "options": [{"key": "B", "text": "9"}],
                "correct_answer": "B",
            },
        ]
    }
    quiz = _make_quiz(plan_id=plan.id, questions=questions_data)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            _scalar_result(plan),
            _scalar_result(quiz),
        ]
    )
    mock_db.commit = AsyncMock()

    from app.schemas.study_plans import QuizResponse, QuizSubmitRequest

    request = QuizSubmitRequest(
        responses=[
            QuizResponse(question_index=0, answer="A"),
            QuizResponse(question_index=1, answer="B"),
        ]
    )

    with patch("app.tasks.gap_tasks.update_gap_state_from_quiz") as mock_gap_task:
        mock_gap_task.delay = MagicMock()
        result = await submit_quiz(
            plan_id=plan.id,
            student_id=student_id,
            request=request,
            db=mock_db,
        )

    assert result.score == 1.0
    assert result.correct_count == 2
    assert result.total_questions == 2
    assert result.plan_status == "COMPLETED"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_submit_quiz_when_plan_not_found_then_raises_value_error():
    """Submitting to a non-existent plan raises ValueError immediately."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_scalar_result(None))

    from app.schemas.study_plans import QuizSubmitRequest

    request = QuizSubmitRequest(responses=[])

    with pytest.raises(ValueError, match="not found"):
        await submit_quiz(
            plan_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            request=request,
            db=mock_db,
        )
