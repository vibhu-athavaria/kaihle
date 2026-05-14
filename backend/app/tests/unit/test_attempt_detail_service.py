"""Unit tests for AttemptService.get_attempt_detail — per-question teacher view.

TDD: tests written before implementation.
Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AttemptStatus
from app.models.user import UserRole
from app.services.attempt_service import AttemptService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def service(mock_db: MagicMock) -> AttemptService:
    return AttemptService(mock_db)


def _make_attempt(
    student_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    status: str | AttemptStatus = AttemptStatus.COMPLETED,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        student_id=student_id or uuid.uuid4(),
        assessment_id=assessment_id or uuid.uuid4(),
        status=status,
        overall_score=0.75,
        completed_at=None,
    )


def _make_assessment(school_id: uuid.UUID, class_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id or uuid.uuid4(),
        title="Test Diagnostic",
        assessment_type="DIAGNOSTIC",
    )


def _make_question(
    question_id: uuid.UUID,
    subtopic_id: uuid.UUID,
    subtopic_name: str = "Algebra",
    topic_name: str = "Mathematics",
    difficulty: int = 2,
    question_text: str = "What is 2+2?",
    correct_answer: str = "A",
    options: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=question_id,
        subtopic_id=subtopic_id,
        subtopic_name=subtopic_name,
        topic_name=topic_name,
        difficulty_level=difficulty,
        question_text=question_text,
        correct_answer=correct_answer,
        options=options or [{"key": "A", "text": "4"}, {"key": "B", "text": "3"}],
        position=1,
    )


def _make_user_execute_mock(first_name: str = "Test", last_name: str = "Student") -> MagicMock:
    """Mock for the user name lookup execute call."""
    mock = MagicMock()
    mock.one_or_none.return_value = SimpleNamespace(first_name=first_name, last_name=last_name)
    return mock


def _make_response(
    question_id: uuid.UUID,
    answer_given: str = "A",
    is_correct: bool = True,
    position: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        question_id=question_id,
        answer_given=answer_given,
        is_correct=is_correct,
        position=position,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_attempt_detail_when_teacher_requests_completed_attempt_then_returns_question_list(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """Happy path — teacher retrieves per-question detail for a completed attempt."""
    school_id = uuid.uuid4()
    question_id = uuid.uuid4()
    subtopic_id = uuid.uuid4()

    attempt = _make_attempt()
    assessment = _make_assessment(school_id=school_id)
    question = _make_question(question_id=question_id, subtopic_id=subtopic_id)
    response = _make_response(question_id=question_id, answer_given="A", is_correct=True)

    mock_db.get.side_effect = [attempt, assessment]

    # Three execute calls: responses, joined question detail, user name
    mock_responses_result = MagicMock()
    mock_responses_result.scalars.return_value.all.return_value = [response]
    mock_questions_result = MagicMock()
    mock_questions_result.all.return_value = [question]
    mock_db.execute.side_effect = [mock_responses_result, mock_questions_result, _make_user_execute_mock()]

    result = await service.get_attempt_detail(
        attempt_id=attempt.id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.TEACHER,
        school_id=school_id,
    )

    assert result.attempt_id == attempt.id
    assert result.assessment_title == assessment.title
    assert result.assessment_type == assessment.assessment_type
    assert len(result.questions) == 1
    q = result.questions[0]
    assert q.question_id == question_id
    assert q.question_text == question.question_text
    assert q.subtopic_name == "Algebra"
    assert q.topic_name == "Mathematics"
    assert q.difficulty_level == 2
    assert q.selected_key == "A"
    assert q.correct_answer == "A"
    assert q.is_correct is True


@pytest.mark.asyncio
async def test_get_attempt_detail_when_attempt_not_completed_then_raises_value_error(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """Incomplete attempts must not be viewable."""
    attempt = _make_attempt(status=AttemptStatus.IN_PROGRESS)
    mock_db.get.return_value = attempt

    with pytest.raises(ValueError, match="not yet completed"):
        await service.get_attempt_detail(
            attempt_id=attempt.id,
            requesting_user_id=uuid.uuid4(),
            requesting_user_role=UserRole.TEACHER,
            school_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_get_attempt_detail_when_attempt_not_found_then_raises_value_error(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """Missing attempt returns descriptive ValueError."""
    mock_db.get.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await service.get_attempt_detail(
            attempt_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            requesting_user_role=UserRole.TEACHER,
            school_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_get_attempt_detail_when_teacher_cross_school_then_raises_access_denied(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """Teacher in a different school cannot view the attempt."""
    from app.services.attempt_service import AttemptAccessDeniedError

    school_id_a = uuid.uuid4()
    school_id_b = uuid.uuid4()

    attempt = _make_attempt()
    assessment = _make_assessment(school_id=school_id_a)

    mock_db.get.side_effect = [attempt, assessment]

    with pytest.raises(AttemptAccessDeniedError):
        await service.get_attempt_detail(
            attempt_id=attempt.id,
            requesting_user_id=uuid.uuid4(),
            requesting_user_role=UserRole.TEACHER,
            school_id=school_id_b,
        )


@pytest.mark.asyncio
async def test_get_attempt_detail_when_wrong_answer_then_question_has_both_keys(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """Wrong answer: selected_key and correct_answer must both be populated."""
    school_id = uuid.uuid4()
    question_id = uuid.uuid4()

    attempt = _make_attempt()
    assessment = _make_assessment(school_id=school_id)
    question = _make_question(question_id=question_id, subtopic_id=uuid.uuid4(), correct_answer="B")
    response = _make_response(question_id=question_id, answer_given="A", is_correct=False)

    mock_db.get.side_effect = [attempt, assessment]
    mock_responses_result = MagicMock()
    mock_responses_result.scalars.return_value.all.return_value = [response]
    mock_questions_result = MagicMock()
    mock_questions_result.all.return_value = [question]
    mock_db.execute.side_effect = [mock_responses_result, mock_questions_result, _make_user_execute_mock()]

    result = await service.get_attempt_detail(
        attempt_id=attempt.id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.TEACHER,
        school_id=school_id,
    )

    q = result.questions[0]
    assert q.selected_key == "A"
    assert q.correct_answer == "B"
    assert q.is_correct is False


@pytest.mark.asyncio
async def test_get_attempt_detail_when_kaihle_admin_then_no_school_check(
    service: AttemptService, mock_db: MagicMock
) -> None:
    """KAIHLE_ADMIN bypasses school check — CONSTITUTION Rule 12."""
    question_id = uuid.uuid4()
    attempt = _make_attempt()
    # Assessment belongs to a completely different school — admin must still get data
    assessment = _make_assessment(school_id=uuid.uuid4())
    question = _make_question(question_id=question_id, subtopic_id=uuid.uuid4())
    response = _make_response(question_id=question_id, answer_given="")

    mock_db.get.side_effect = [attempt, assessment]
    mock_responses_result = MagicMock()
    mock_responses_result.scalars.return_value.all.return_value = [response]
    mock_questions_result = MagicMock()
    mock_questions_result.all.return_value = [question]
    mock_db.execute.side_effect = [mock_responses_result, mock_questions_result, _make_user_execute_mock()]

    result = await service.get_attempt_detail(
        attempt_id=attempt.id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.KAIHLE_ADMIN,
        school_id=uuid.UUID(int=0),  # sentinel — no school
    )

    assert len(result.questions) == 1
