"""Unit tests for AttemptService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
    AttemptStatus,
    StudentAttempt,
    StudentResponse,
)
from app.models.curriculum import QuestionBank
from app.services.attempt_service import (
    AttemptAccessDeniedError,
    AttemptAlreadyCompletedError,
    AttemptNotFoundError,
    AttemptService,
    DuplicateResponseError,
)


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return AttemptService(mock_db)


@pytest.fixture
def sample_attempt():
    """Create a sample StudentAttempt."""
    return StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        status=AttemptStatus.IN_PROGRESS,
        started_at=datetime.now(UTC),
        questions_answered=0,
    )


@pytest.fixture
def sample_assessment(sample_attempt):
    """Create a sample Assessment with config."""
    return Assessment(
        id=sample_attempt.assessment_id,
        school_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        title="Test Assessment",
        assessment_type=AssessmentType.PROGRESS_CHECK,
        status=AssessmentStatus.ACTIVE,
        config={"num_questions": 10},
        question_count=10,
    )


@pytest.fixture
def sample_questions():
    """Create sample QuestionBank rows."""
    return [
        QuestionBank(
            id=uuid.uuid4(),
            question_text="What is 2+2?",
            question_type="MCQ",
            options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}, {"key": "C", "text": "5"}],
            correct_answer="B",
            difficulty_level=1,
        ),
        QuestionBank(
            id=uuid.uuid4(),
            question_text="What is 3+3?",
            question_type="MCQ",
            options=[{"key": "A", "text": "5"}, {"key": "B", "text": "6"}, {"key": "C", "text": "7"}],
            correct_answer="B",
            difficulty_level=2,
        ),
    ]


@pytest.fixture
def sample_responses(sample_attempt):
    """Create sample StudentResponse rows for resume."""
    return [
        StudentResponse(
            id=uuid.uuid4(),
            attempt_id=sample_attempt.id,
            question_id=uuid.uuid4(),
            answer_given="A",
            is_correct=True,
            score=1.0,
        ),
        StudentResponse(
            id=uuid.uuid4(),
            attempt_id=sample_attempt.id,
            question_id=uuid.uuid4(),
            answer_given="B",
            is_correct=True,
            score=1.0,
        ),
    ]


class TestGetAttempt:
    """Tests for AttemptService.get_attempt()."""

    @pytest.mark.asyncio
    async def test_get_attempt_returns_responses_for_resume(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions, sample_responses
    ):
        """get_attempt should return existing responses for resume functionality."""
        # Setup mocks for multiple db.execute() calls:
        # 1. Load attempt (line 288)
        # 2. Load assessment (line 307)
        # 3. Load responses (line 315)
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = sample_attempt

        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment

        responses_result = MagicMock()
        responses_result.scalars.return_value.all.return_value = sample_responses

        # Order matters: attempt query, then assessment query, then responses query
        mock_db.execute.side_effect = [attempt_result, assessment_result, responses_result]

        # Patch _load_questions to return sample questions
        with patch.object(service, "_load_questions", AsyncMock(return_value=sample_questions)):
            result = await service.get_attempt(
                attempt_id=sample_attempt.id,
                requesting_user_id=sample_attempt.student_id,
                requesting_user_role="STUDENT",
                school_id=sample_assessment.school_id,
            )

        attempt, assessment, questions, responses = result

        # Verify all 4 values are returned
        assert isinstance(attempt, StudentAttempt)
        assert isinstance(assessment, Assessment)
        assert isinstance(questions, list)
        assert isinstance(responses, list)

        # Verify we got the responses we set up
        assert len(responses) == 2

    @pytest.mark.asyncio
    async def test_get_attempt_not_found(self, service, mock_db):
        """get_attempt should raise AttemptNotFoundError when attempt doesn't exist."""
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = attempt_result

        with pytest.raises(AttemptNotFoundError):
            await service.get_attempt(
                attempt_id=uuid.uuid4(),
                requesting_user_id=uuid.uuid4(),
                requesting_user_role="STUDENT",
                school_id=None,
            )

    @pytest.mark.asyncio
    async def test_get_attempt_student_cannot_access_other_student_attempt(self, service, mock_db, sample_attempt):
        """Student cannot access another student's attempt."""
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = sample_attempt
        mock_db.execute.return_value = attempt_result

        with pytest.raises(AttemptAccessDeniedError):
            await service.get_attempt(
                attempt_id=sample_attempt.id,
                requesting_user_id=uuid.uuid4(),  # Different student
                requesting_user_role="STUDENT",
                school_id=None,
            )


class TestSubmitResponse:
    """Tests for AttemptService.submit_response()."""

    @pytest.mark.asyncio
    async def test_submit_response_saves_to_db(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """submit_response should save a StudentResponse to the DB."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]

        # Mock question lookup
        question_result = MagicMock()
        q = MagicMock()
        q.correct_answer = "B"
        question_result.scalar_one_or_none.return_value = q

        # Mock bridge lookup
        bridge_result = MagicMock()
        bridge_result.scalar_one_or_none.return_value = MagicMock()

        # Mock duplicate check
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [attempt_result, attempt_result, bridge_result, dup_result, question_result]

        await service.submit_response(
            attempt_id=sample_attempt.id,
            student_id=sample_attempt.student_id,
            school_id=sample_assessment.school_id,
            question_id=sample_questions[0].id,
            selected_key="B",
        )

        # Verify a new StudentResponse was added
        mock_db.add.assert_called_once()
        call_args = mock_db.add.call_args[0][0]
        assert call_args.answer_given == "B"
        assert call_args.is_correct is True

    @pytest.mark.asyncio
    async def test_submit_response_transitions_not_started_to_in_progress(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """First answer should transition attempt from NOT_STARTED to IN_PROGRESS."""
        sample_attempt.status = AttemptStatus.NOT_STARTED
        sample_attempt.started_at = None
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]

        question_result = MagicMock()
        q = MagicMock()
        q.correct_answer = "B"
        question_result.scalar_one_or_none.return_value = q

        bridge_result = MagicMock()
        bridge_result.scalar_one_or_none.return_value = MagicMock()

        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [attempt_result, attempt_result, bridge_result, dup_result, question_result]

        await service.submit_response(
            attempt_id=sample_attempt.id,
            student_id=sample_attempt.student_id,
            school_id=sample_assessment.school_id,
            question_id=sample_questions[0].id,
            selected_key="B",
        )

        # Verify status was updated to IN_PROGRESS
        assert sample_attempt.status == AttemptStatus.IN_PROGRESS
        assert sample_attempt.started_at is not None

    @pytest.mark.asyncio
    async def test_submit_response_duplicate_raises_error(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """Submitting the same question twice should raise DuplicateResponseError."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]

        question_result = MagicMock()
        q = MagicMock()
        q.correct_answer = "B"
        question_result.scalar_one_or_none.return_value = q

        bridge_result = MagicMock()
        bridge_result.scalar_one_or_none.return_value = MagicMock()

        # Simulate existing response found
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = MagicMock()  # Found existing response

        mock_db.execute.side_effect = [attempt_result, attempt_result, bridge_result, dup_result, question_result]

        with pytest.raises(DuplicateResponseError):
            await service.submit_response(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                question_id=sample_questions[0].id,
                selected_key="B",
            )

    @pytest.mark.asyncio
    async def test_submit_response_completed_attempt_raises_error(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Submitting to a completed attempt should raise AttemptAlreadyCompletedError."""
        sample_attempt.status = AttemptStatus.COMPLETED
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]
        mock_db.execute.return_value = attempt_result

        with pytest.raises(AttemptAlreadyCompletedError):
            await service.submit_response(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                question_id=uuid.uuid4(),
                selected_key="A",
            )
