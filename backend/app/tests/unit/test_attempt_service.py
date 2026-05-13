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
from app.models.school import ClassEnrollment
from app.models.user import UserRole
from app.services.attempt_service import (
    AttemptAccessDeniedError,
    AttemptAlreadyCompletedError,
    AttemptNotFoundError,
    AttemptService,
    DuplicateResponseError,
    QuestionNotInAssessmentError,
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


class TestGetClassDiagnostic:
    """Tests for AttemptService.get_class_diagnostic()."""

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_no_active_assessment_then_raises(self, service, mock_db):
        """Raises ValueError when no ACTIVE DIAGNOSTIC assessment exists for the class."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="No active diagnostic"):
            await service.get_class_diagnostic(
                class_id=uuid.uuid4(),
                student_id=uuid.uuid4(),
                school_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_no_attempt_then_raises(self, service, mock_db, sample_assessment):
        """Raises AttemptNotFoundError when assessment exists but student has no attempt row."""
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [assessment_result, attempt_result]

        with pytest.raises(AttemptNotFoundError):
            await service.get_class_diagnostic(
                class_id=uuid.uuid4(),
                student_id=uuid.uuid4(),
                school_id=sample_assessment.school_id,
            )

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_pool_larger_than_count_then_samples(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """When pool has more questions than question_count, student sees only question_count."""
        sample_assessment.question_count = 1  # student sees 1, pool has 2
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = sample_attempt
        responses_result = MagicMock()
        responses_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [assessment_result, attempt_result, responses_result]

        with patch.object(service, "_load_questions", AsyncMock(return_value=sample_questions)):
            _, _, questions, _ = await service.get_class_diagnostic(
                class_id=uuid.uuid4(),
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
            )

        assert len(questions) == 1  # capped to question_count


class TestGetOrCreateAttempt:
    """Tests for AttemptService.get_or_create_attempt()."""

    @pytest.mark.asyncio
    async def test_get_or_create_attempt_when_assessment_not_found_then_raises(self, service, mock_db):
        """Raises ValueError when assessment does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="Assessment not found"):
            await service.get_or_create_attempt(
                assessment_id=uuid.uuid4(),
                student_id=uuid.uuid4(),
                school_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_or_create_attempt_when_not_active_then_raises(self, service, mock_db, sample_assessment):
        """Raises ValueError when assessment is DRAFT, not ACTIVE."""
        sample_assessment.status = AssessmentStatus.DRAFT
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_assessment
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="not active"):
            await service.get_or_create_attempt(
                assessment_id=sample_assessment.id,
                student_id=uuid.uuid4(),
                school_id=sample_assessment.school_id,
            )

    @pytest.mark.asyncio
    async def test_get_or_create_attempt_when_existing_attempt_then_returns_it(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """Returns existing attempt without creating a new one."""
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = sample_attempt
        responses_result = MagicMock()
        responses_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [assessment_result, existing_result, responses_result]

        with patch.object(service, "_load_questions", AsyncMock(return_value=sample_questions)):
            attempt, _, _, _ = await service.get_or_create_attempt(
                assessment_id=sample_assessment.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
            )

        assert attempt.id == sample_attempt.id
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_attempt_when_not_enrolled_then_raises(self, service, mock_db, sample_assessment):
        """Raises ValueError when student is not enrolled in the class."""
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        no_attempt_result = MagicMock()
        no_attempt_result.scalar_one_or_none.return_value = None
        no_enrollment_result = MagicMock()
        no_enrollment_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [assessment_result, no_attempt_result, no_enrollment_result]

        with pytest.raises(ValueError, match="not enrolled"):
            await service.get_or_create_attempt(
                assessment_id=sample_assessment.id,
                student_id=uuid.uuid4(),
                school_id=sample_assessment.school_id,
            )

    @pytest.mark.asyncio
    async def test_get_or_create_attempt_when_new_student_then_creates_attempt(
        self, service, mock_db, sample_assessment, sample_questions
    ):
        """Creates a new NOT_STARTED attempt for an enrolled student."""
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        no_attempt_result = MagicMock()
        no_attempt_result.scalar_one_or_none.return_value = None
        enrollment_result = MagicMock()
        enrollment_result.scalar_one_or_none.return_value = ClassEnrollment()
        mock_db.execute.side_effect = [assessment_result, no_attempt_result, enrollment_result]
        mock_db.flush = AsyncMock()

        with patch.object(service, "_load_questions", AsyncMock(return_value=sample_questions)):
            attempt, _, _, responses = await service.get_or_create_attempt(
                assessment_id=sample_assessment.id,
                student_id=uuid.uuid4(),
                school_id=sample_assessment.school_id,
            )

        assert attempt.status == AttemptStatus.NOT_STARTED
        assert responses == []
        mock_db.add.assert_called_once()


class TestGetAttemptAccessControl:
    """Tests for get_attempt role-based access control branches."""

    @pytest.mark.asyncio
    async def test_get_attempt_when_teacher_wrong_school_then_raises(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Teacher from a different school cannot access the attempt."""
        sample_assessment.school_id = uuid.uuid4()
        different_school = uuid.uuid4()

        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = sample_attempt
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        mock_db.execute.side_effect = [attempt_result, assessment_result]

        with pytest.raises(AttemptAccessDeniedError):
            await service.get_attempt(
                attempt_id=sample_attempt.id,
                requesting_user_id=uuid.uuid4(),
                requesting_user_role=UserRole.TEACHER,
                school_id=different_school,
            )

    @pytest.mark.asyncio
    async def test_get_attempt_when_kaihle_admin_then_succeeds_any_school(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """KAIHLE_ADMIN bypasses school check and accesses any attempt."""
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = sample_attempt
        assessment_result = MagicMock()
        assessment_result.scalar_one_or_none.return_value = sample_assessment
        responses_result = MagicMock()
        responses_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [attempt_result, assessment_result, responses_result]

        with patch.object(service, "_load_questions", AsyncMock(return_value=sample_questions)):
            attempt, _, _, _ = await service.get_attempt(
                attempt_id=sample_attempt.id,
                requesting_user_id=uuid.uuid4(),
                requesting_user_role=UserRole.KAIHLE_ADMIN,
                school_id=None,
            )

        assert attempt.id == sample_attempt.id


class TestSubmitAttempt:
    """Tests for AttemptService.submit_attempt()."""

    def _make_onboarding_service(self):
        svc = MagicMock()
        svc.check_and_update_onboarding_complete = AsyncMock(return_value=True)
        return svc

    @pytest.mark.asyncio
    async def test_submit_attempt_when_already_completed_then_raises(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Raises AttemptAlreadyCompletedError when attempt is already COMPLETED."""
        sample_attempt.status = AttemptStatus.COMPLETED
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]
        mock_db.execute.return_value = attempt_result

        with pytest.raises(AttemptAlreadyCompletedError):
            await service.submit_attempt(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                answers=[],
                onboarding_service=self._make_onboarding_service(),
            )

    @pytest.mark.asyncio
    async def test_submit_attempt_when_valid_then_marks_completed_and_scores(
        self, service, mock_db, sample_attempt, sample_assessment, sample_questions
    ):
        """Valid submission marks attempt COMPLETED with correct score."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        sample_attempt.started_at = datetime.now(UTC)

        q = sample_questions[0]
        q.correct_answer = "B"

        # execute call order: _load_and_verify_attempt (2 calls), assessment load,
        # existing_responses, bridge, question, flush, all_responses
        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        assessment_r = MagicMock()
        assessment_r.scalar_one_or_none.return_value = sample_assessment
        existing_r = MagicMock()
        existing_r.all.return_value = []
        bridge_r = MagicMock()
        bridge_r.scalar_one_or_none.return_value = MagicMock()
        question_r = MagicMock()
        question_r.scalar_one_or_none.return_value = q
        all_responses_r = MagicMock()
        all_responses_r.scalars.return_value.all.return_value = [
            MagicMock(is_correct=True),
        ]
        mock_db.execute.side_effect = [
            attempt_r,
            assessment_r,  # _load_and_verify_attempt
            assessment_r,  # load assessment for type check
            existing_r,  # already_answered
            bridge_r,  # bridge check
            question_r,  # question load
            all_responses_r,  # final score computation
        ]
        mock_db.flush = AsyncMock()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.submit_attempt(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                answers=[{"question_id": q.id, "selected_key": "B"}],
                onboarding_service=self._make_onboarding_service(),
            )

        assert sample_attempt.status == AttemptStatus.COMPLETED
        assert result.correct_count == 1
        assert result.score == 1.0
        mock_task.delay.assert_called_once_with(str(sample_attempt.id))

    @pytest.mark.asyncio
    async def test_submit_attempt_when_diagnostic_then_calls_onboarding_service(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Diagnostic submission triggers check_and_update_onboarding_complete."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        sample_attempt.started_at = datetime.now(UTC)
        sample_assessment.assessment_type = AssessmentType.DIAGNOSTIC

        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        # _load_and_verify_attempt uses scalar_one_or_none; submit_attempt uses scalar_one
        assessment_r_verify = MagicMock()
        assessment_r_verify.scalar_one_or_none.return_value = sample_assessment
        assessment_r_type = MagicMock()
        assessment_r_type.scalar_one.return_value = sample_assessment
        existing_r = MagicMock()
        existing_r.all.return_value = []
        all_responses_r = MagicMock()
        all_responses_r.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [attempt_r, assessment_r_verify, assessment_r_type, existing_r, all_responses_r]
        mock_db.flush = AsyncMock()

        onboarding_svc = self._make_onboarding_service()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            await service.submit_attempt(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                answers=[],
                onboarding_service=onboarding_svc,
            )

        onboarding_svc.check_and_update_onboarding_complete.assert_called_once_with(
            student_id=sample_attempt.student_id,
            class_id=sample_assessment.class_id,
        )


class TestGetAttemptResults:
    """Tests for AttemptService.get_attempt_results()."""

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_not_found_then_raises(self, service, mock_db):
        """Raises ValueError when attempt does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="Attempt not found"):
            await service.get_attempt_results(
                attempt_id=uuid.uuid4(),
                requesting_user_id=uuid.uuid4(),
                requesting_user_role=UserRole.STUDENT,
                school_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_not_completed_then_raises(self, service, mock_db, sample_attempt):
        """Raises ValueError when attempt is not yet COMPLETED."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_attempt
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="not yet completed"):
            await service.get_attempt_results(
                attempt_id=sample_attempt.id,
                requesting_user_id=sample_attempt.student_id,
                requesting_user_role=UserRole.STUDENT,
                school_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_student_accesses_own_then_returns_score(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Student can access their own completed attempt results."""
        sample_attempt.status = AttemptStatus.COMPLETED
        sample_attempt.overall_score = 0.75
        sample_attempt.completed_at = datetime.now(UTC)
        sample_attempt.time_taken_seconds = 120

        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        responses_r = MagicMock()
        responses_r.scalars.return_value.all.return_value = [
            MagicMock(is_correct=True),
            MagicMock(is_correct=False),
            MagicMock(is_correct=True),
            MagicMock(is_correct=True),
        ]
        mock_db.execute.side_effect = [attempt_r, responses_r]

        result = await service.get_attempt_results(
            attempt_id=sample_attempt.id,
            requesting_user_id=sample_attempt.student_id,
            requesting_user_role=UserRole.STUDENT,
            school_id=uuid.uuid4(),
        )

        assert result.score == 0.75
        assert result.total_questions == 4
        assert result.correct_count == 3

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_student_accesses_other_then_raises(self, service, mock_db, sample_attempt):
        """Student cannot access another student's results."""
        sample_attempt.status = AttemptStatus.COMPLETED
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_attempt
        mock_db.execute.return_value = result

        with pytest.raises(AttemptAccessDeniedError):
            await service.get_attempt_results(
                attempt_id=sample_attempt.id,
                requesting_user_id=uuid.uuid4(),  # different student
                requesting_user_role=UserRole.STUDENT,
                school_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_kaihle_admin_then_bypasses_school_check(
        self, service, mock_db, sample_attempt
    ):
        """KAIHLE_ADMIN can access any attempt without school restriction."""
        sample_attempt.status = AttemptStatus.COMPLETED
        sample_attempt.overall_score = 0.5
        sample_attempt.completed_at = datetime.now(UTC)
        sample_attempt.time_taken_seconds = None

        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        responses_r = MagicMock()
        responses_r.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [attempt_r, responses_r]

        result = await service.get_attempt_results(
            attempt_id=sample_attempt.id,
            requesting_user_id=uuid.uuid4(),
            requesting_user_role=UserRole.KAIHLE_ADMIN,
            school_id=uuid.uuid4(),
        )

        assert result.score == 0.5


class TestLoadAndVerifyAttempt:
    """Tests for AttemptService._load_and_verify_attempt() boundary conditions."""

    @pytest.mark.asyncio
    async def test_load_and_verify_when_different_student_then_raises(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Raises ValueError when attempt belongs to a different student."""
        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        mock_db.execute.return_value = attempt_r

        with pytest.raises(ValueError, match="different student"):
            await service._load_and_verify_attempt(
                attempt_id=sample_attempt.id,
                student_id=uuid.uuid4(),
                school_id=sample_assessment.school_id,
            )

    @pytest.mark.asyncio
    async def test_load_and_verify_when_school_mismatch_then_raises(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Raises ValueError when assessment belongs to a different school."""
        sample_assessment.school_id = uuid.uuid4()
        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.return_value = sample_attempt
        assessment_r = MagicMock()
        assessment_r.scalar_one_or_none.return_value = sample_assessment
        mock_db.execute.side_effect = [attempt_r, assessment_r]

        with pytest.raises(ValueError, match="school mismatch"):
            await service._load_and_verify_attempt(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=uuid.uuid4(),  # different school
            )


class TestSubmitResponseQuestionNotInAssessment:
    """Tests for QuestionNotInAssessmentError paths in submit_response."""

    @pytest.mark.asyncio
    async def test_submit_response_when_question_not_in_assessment_then_raises(
        self, service, mock_db, sample_attempt, sample_assessment
    ):
        """Raises QuestionNotInAssessmentError when question is not in the assessment pool."""
        sample_attempt.status = AttemptStatus.IN_PROGRESS
        attempt_r = MagicMock()
        attempt_r.scalar_one_or_none.side_effect = [sample_attempt, sample_assessment]
        bridge_r = MagicMock()
        bridge_r.scalar_one_or_none.return_value = None  # not in assessment
        mock_db.execute.side_effect = [attempt_r, attempt_r, bridge_r]

        with pytest.raises(QuestionNotInAssessmentError):
            await service.submit_response(
                attempt_id=sample_attempt.id,
                student_id=sample_attempt.student_id,
                school_id=sample_assessment.school_id,
                question_id=uuid.uuid4(),
                selected_key="A",
            )
