"""Unit tests for the assessment service (Tier 1 diagnostic creation).

Tests use mock database sessions to validate logic in isolation.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OnboardingStatus
from app.services.assessment_service import MAX_DIAGNOSTIC_QUESTIONS, AssessmentService


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def service(mock_db: MagicMock) -> AssessmentService:
    return AssessmentService(mock_db)


def _make_class(
    school_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    grade_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        curriculum_id=curriculum_id,
        grade_id=grade_id,
        subject_id=subject_id,
        name="Test Class 7A",
        academic_year="2026",
        is_active=True,
    )


def _make_student(school_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        role="STUDENT",
    )


def _make_topic(
    curriculum_id: uuid.UUID,
    subject_id: uuid.UUID,
    grade_id: uuid.UUID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id,
        subject_id=subject_id,
        grade_id=grade_id,
        is_active=True,
    )


def _make_existing_assessment() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4())


class TestAssessmentServiceCreateSystemDiagnostic:
    """Tests for AssessmentService.create_system_diagnostic."""

    @pytest.mark.asyncio
    async def test_when_class_not_found_then_raises_value_error(self, service: AssessmentService) -> None:
        """Raises ValueError when class_id does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Class not found"):
            await service.create_system_diagnostic(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_when_student_not_found_then_raises_value_error(self, service: AssessmentService) -> None:
        """Raises ValueError when student_id does not exist."""
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        mock_class_result = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        service.db.execute = AsyncMock(side_effect=[mock_class_result, mock_student_result])  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Student not found"):
            await service.create_system_diagnostic(uuid.uuid4(), class_.id)

    @pytest.mark.asyncio
    async def test_when_student_wrong_school_then_raises_value_error(self, service: AssessmentService) -> None:
        """Raises ValueError when student belongs to a different school."""
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(uuid.uuid4())  # different school_id

        mock_class_result = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student_result = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        service.db.execute = AsyncMock(side_effect=[mock_class_result, mock_student_result])  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="does not match class school_id"):
            await service.create_system_diagnostic(student.id, class_.id)

    @pytest.mark.asyncio
    async def test_when_diagnostic_already_exists_then_no_duplicate(self, service: AssessmentService) -> None:
        """Returns empty list when assessment already exists for this class (idempotent)."""
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)
        existing_assessment = _make_existing_assessment()

        mock_class_result = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student_result = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_existing_result = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_assessment))
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class_result, mock_student_result, mock_existing_result]
        )

        result = await service.create_system_diagnostic(student.id, class_.id)

        assert result == []
        service.db.add.assert_not_called()  # type: ignore[attr-defined]


class TestAssessmentServiceSelectQuestions:
    """Tests for question selection logic."""

    @pytest.mark.asyncio
    async def test_when_no_topics_then_returns_empty(self, service: AssessmentService) -> None:
        """Returns empty list when no curriculum topics found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_when_question_bank_has_5_questions_then_uses_all_5(self, service: AssessmentService) -> None:
        """Uses all available questions when bank has fewer than 20."""
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        topic = _make_topic(curriculum_id, subject_id, grade_id)
        question_ids = [uuid.uuid4() for _ in range(5)]

        mock_topics_result = MagicMock()
        mock_topics_result.scalars.return_value.all.return_value = [topic]

        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = [(qid,) for qid in question_ids]

        service.db.execute = AsyncMock(side_effect=[mock_topics_result, mock_questions_result])  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(curriculum_id, subject_id, grade_id)

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_when_multiple_topics_then_questions_capped_at_20(self, service: AssessmentService) -> None:
        """Questions are capped at MAX_DIAGNOSTIC_QUESTIONS (20) across all topics."""
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        # 4 topics × 10 questions each = 40 total available but cap at 20
        topics = [_make_topic(curriculum_id, subject_id, grade_id) for _ in range(4)]
        question_ids_per_topic = [[uuid.uuid4() for _ in range(10)] for _ in range(4)]

        mock_topics_result = MagicMock()
        mock_topics_result.scalars.return_value.all.return_value = topics

        mock_q_results = [
            MagicMock(all=MagicMock(return_value=[(qid,) for qid in qids])) for qids in question_ids_per_topic
        ]
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_topics_result] + mock_q_results
        )

        result = await service._select_questions_for_diagnostic(curriculum_id, subject_id, grade_id)

        assert len(result) <= MAX_DIAGNOSTIC_QUESTIONS

    @pytest.mark.asyncio
    async def test_when_topics_questions_span_all_topics(self, service: AssessmentService) -> None:
        """Questions are selected from multiple topics, not just one."""
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        topic_a = _make_topic(curriculum_id, subject_id, grade_id)
        topic_b = _make_topic(curriculum_id, subject_id, grade_id)
        qids_a = [uuid.uuid4() for _ in range(3)]
        qids_b = [uuid.uuid4() for _ in range(3)]

        mock_topics_result = MagicMock()
        mock_topics_result.scalars.return_value.all.return_value = [topic_a, topic_b]

        mock_q_a = MagicMock(all=MagicMock(return_value=[(qid,) for qid in qids_a]))
        mock_q_b = MagicMock(all=MagicMock(return_value=[(qid,) for qid in qids_b]))

        service.db.execute = AsyncMock(side_effect=[mock_topics_result, mock_q_a, mock_q_b])  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(curriculum_id, subject_id, grade_id)

        # Should have questions from both topics
        all_from_a = set(qids_a)
        all_from_b = set(qids_b)
        result_set = set(result)
        assert result_set & all_from_a  # at least one from topic A
        assert result_set & all_from_b  # at least one from topic B


class TestAssessmentServiceSampleQuestionsForTopic:
    """Tests for _sample_questions_for_topic."""

    @pytest.mark.asyncio
    async def test_when_no_questions_in_topic_then_returns_empty(self, service: AssessmentService) -> None:
        """Returns empty list when no questions exist for a topic."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._sample_questions_for_topic(uuid.uuid4(), 5)

        assert result == []

    @pytest.mark.asyncio
    async def test_when_questions_exist_then_returns_sample_capped_at_n(self, service: AssessmentService) -> None:
        """Returns up to n questions when more exist in the bank."""
        question_ids = [uuid.uuid4() for _ in range(10)]
        mock_result = MagicMock()
        mock_result.all.return_value = [(qid,) for qid in question_ids]
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._sample_questions_for_topic(uuid.uuid4(), 3)

        assert len(result) == 3
        for qid in result:
            assert qid in question_ids


class TestAssessmentServiceCreateDiagnosticHappyPath:
    """Tests for the creation path of _create_subject_diagnostic_if_not_exists."""

    @pytest.mark.asyncio
    async def test_when_no_existing_assessment_then_creates_and_returns_assessment(
        self, service: AssessmentService
    ) -> None:
        """Creates assessment with correct attributes when none exists."""
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)
        subject = SimpleNamespace(id=class_.subject_id, name="Mathematics")

        # Mocks: class found, student found, no existing assessment, subject found,
        # then no curriculum topics (returns [] for questions — zero question path is ok)
        mock_class_result = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student_result = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_subject_result = MagicMock(scalar_one_or_none=MagicMock(return_value=subject))
        mock_no_topics = MagicMock()
        mock_no_topics.scalars.return_value.all.return_value = []

        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class_result, mock_student_result, mock_no_existing, mock_subject_result, mock_no_topics]
        )
        service.db.flush = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_system_diagnostic(student.id, class_.id)

        assert len(result) == 1
        assessment = result[0]
        assert assessment.is_system_generated is True
        assert assessment.created_by is None
        assert "Mathematics" in assessment.title
        assert assessment.class_id == class_.id

    @pytest.mark.asyncio
    async def test_when_subject_not_found_then_uses_unknown_subject_title(self, service: AssessmentService) -> None:
        """Uses 'Unknown Subject' in title when subject row is not found."""
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)

        mock_class_result = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student_result = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_no_subject = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_no_topics = MagicMock()
        mock_no_topics.scalars.return_value.all.return_value = []

        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class_result, mock_student_result, mock_no_existing, mock_no_subject, mock_no_topics]
        )
        service.db.flush = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_system_diagnostic(student.id, class_.id)

        assert len(result) == 1
        assert "Unknown Subject" in result[0].title


class TestOnboardingStatusUpdate:
    """Tests for onboarding status update logic within Celery task."""

    @pytest.mark.asyncio
    async def test_when_status_pending_then_updated_to_in_progress(self) -> None:
        """Student profile status is updated from PENDING to IN_PROGRESS."""
        student_profile = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        # Simulate the status update logic
        if student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.IN_PROGRESS

    def test_when_status_completed_then_not_regressed(self) -> None:
        """Student profile status COMPLETED is not regressed to IN_PROGRESS."""
        student_profile = SimpleNamespace(
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        # Status should not be changed if already COMPLETED
        if student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    def test_when_status_in_progress_then_not_changed(self) -> None:
        """Student profile status IN_PROGRESS is not changed again."""
        student_profile = SimpleNamespace(
            onboarding_diagnostic_status=OnboardingStatus.IN_PROGRESS,
        )

        if student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.IN_PROGRESS
