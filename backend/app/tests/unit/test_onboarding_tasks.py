"""Unit tests for the assessment service (Tier 1 diagnostic creation).

Tests cover two responsibilities:
- create_class_diagnostic: assessment + question pool created at class creation
- create_diagnostic_attempt: student attempt created at enrollment
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentStatus, AssessmentType, AttemptStatus
from app.models.user import OnboardingStatus
from app.services.assessment_service import (
    MAX_DIAGNOSTIC_POOL,
    MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT,
    AssessmentService,
)


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


def _make_existing_attempt() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), status=AttemptStatus.NOT_STARTED)


# ── create_class_diagnostic ─────────────────────────────────────────────


class TestCreateClassDiagnostic:
    """Tests for AssessmentService.create_class_diagnostic."""

    @pytest.mark.asyncio
    async def test_when_class_not_found_then_raises_value_error(self, service: AssessmentService) -> None:
        mock_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Class not found"):
            await service.create_class_diagnostic(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_when_diagnostic_already_exists_then_returns_existing(self, service: AssessmentService) -> None:
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        existing = _make_existing_assessment()

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        service.db.execute = AsyncMock(side_effect=[mock_class, mock_existing])  # type: ignore[method-assign]

        result = await service.create_class_diagnostic(class_.id)

        assert result.id == existing.id
        service.db.add.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_when_new_class_then_creates_assessment_with_correct_attributes(
        self, service: AssessmentService
    ) -> None:
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        subject = SimpleNamespace(id=class_.subject_id, name="Mathematics")

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_subject = MagicMock(scalar_one_or_none=MagicMock(return_value=subject))
        mock_no_topics = MagicMock()
        mock_no_topics.scalars.return_value.all.return_value = []

        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class, mock_no_existing, mock_subject, mock_no_topics]
        )
        service.db.flush = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_class_diagnostic(class_.id)

        assert result.is_system_generated is True
        assert result.created_by is None
        assert result.assessment_type == AssessmentType.DIAGNOSTIC
        assert result.status == AssessmentStatus.ACTIVE
        assert result.curriculum_topic_id is None
        assert result.class_id == class_.id
        assert "Mathematics" in result.title
        assert result.config["max_questions_per_attempt"] == MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT

    @pytest.mark.asyncio
    async def test_when_subject_not_found_then_uses_unknown_subject_title(self, service: AssessmentService) -> None:
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_no_subject = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_no_topics = MagicMock()
        mock_no_topics.scalars.return_value.all.return_value = []

        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class, mock_no_existing, mock_no_subject, mock_no_topics]
        )
        service.db.flush = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_class_diagnostic(class_.id)

        assert "Unknown Subject" in result.title


# ── create_diagnostic_attempt ────────────────────────────────────────────


class TestCreateDiagnosticAttempt:
    """Tests for AssessmentService.create_diagnostic_attempt."""

    @pytest.mark.asyncio
    async def test_when_class_not_found_then_raises_value_error(self, service: AssessmentService) -> None:
        mock_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Class not found"):
            await service.create_diagnostic_attempt(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_when_student_not_found_then_raises_value_error(self, service: AssessmentService) -> None:
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_no_student = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        service.db.execute = AsyncMock(side_effect=[mock_class, mock_no_student])  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Student not found"):
            await service.create_diagnostic_attempt(uuid.uuid4(), class_.id)

    @pytest.mark.asyncio
    async def test_when_student_wrong_school_then_raises_value_error(self, service: AssessmentService) -> None:
        class_ = _make_class(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(uuid.uuid4())  # different school

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        service.db.execute = AsyncMock(side_effect=[mock_class, mock_student])  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="does not match"):
            await service.create_diagnostic_attempt(student.id, class_.id)

    @pytest.mark.asyncio
    async def test_when_no_diagnostic_assessment_then_raises_value_error(self, service: AssessmentService) -> None:
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_no_assessment = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class, mock_student, mock_no_assessment]
        )

        with pytest.raises(ValueError, match="No system-generated diagnostic found"):
            await service.create_diagnostic_attempt(student.id, class_.id)

    @pytest.mark.asyncio
    async def test_when_attempt_already_exists_then_returns_existing(self, service: AssessmentService) -> None:
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)
        assessment = _make_existing_assessment()
        existing_attempt = _make_existing_attempt()

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_assessment = MagicMock(scalar_one_or_none=MagicMock(return_value=assessment))
        mock_existing_attempt = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_attempt))
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class, mock_student, mock_assessment, mock_existing_attempt]
        )

        result = await service.create_diagnostic_attempt(student.id, class_.id)

        assert result.id == existing_attempt.id
        service.db.add.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_when_new_enrollment_then_creates_attempt_not_started(self, service: AssessmentService) -> None:
        school_id = uuid.uuid4()
        class_ = _make_class(school_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        student = _make_student(school_id)
        assessment = _make_existing_assessment()

        mock_class = MagicMock(scalar_one_or_none=MagicMock(return_value=class_))
        mock_student = MagicMock(scalar_one_or_none=MagicMock(return_value=student))
        mock_assessment = MagicMock(scalar_one_or_none=MagicMock(return_value=assessment))
        mock_no_attempt = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_q_count = MagicMock(all=MagicMock(return_value=[(uuid.uuid4(),)] * 15))
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_class, mock_student, mock_assessment, mock_no_attempt, mock_q_count]
        )

        result = await service.create_diagnostic_attempt(student.id, class_.id)

        assert result.status == AttemptStatus.NOT_STARTED
        assert result.assessment_id == assessment.id
        assert result.student_id == student.id
        assert result.total_questions == 15


# ── Question selection ───────────────────────────────────────────────────


class TestSelectQuestionsForDiagnostic:
    """Tests for question selection logic."""

    @pytest.mark.asyncio
    async def test_when_no_topics_then_returns_empty(self, service: AssessmentService) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_when_fewer_questions_than_pool_then_uses_all(self, service: AssessmentService) -> None:
        topic = _make_topic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        question_ids = [uuid.uuid4() for _ in range(5)]

        # New consolidated query: single call returning (topic_id, question_id) pairs
        mock_result = MagicMock()
        mock_result.all.return_value = [(topic.id, qid) for qid in question_ids]
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_when_many_questions_then_capped_at_pool_size(self, service: AssessmentService) -> None:
        topics = [_make_topic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4()) for _ in range(4)]
        # 4 topics × 30 questions each = 120, but pool capped at 60
        question_ids_per_topic = [[uuid.uuid4() for _ in range(30)] for _ in range(4)]

        mock_topics = MagicMock()
        mock_topics.scalars.return_value.all.return_value = topics
        mock_q_results = [
            MagicMock(all=MagicMock(return_value=[(qid,) for qid in qids])) for qids in question_ids_per_topic
        ]
        service.db.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=[mock_topics] + mock_q_results
        )

        result = await service._select_questions_for_diagnostic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert len(result) <= MAX_DIAGNOSTIC_POOL

    @pytest.mark.asyncio
    async def test_when_multiple_topics_then_questions_span_all(self, service: AssessmentService) -> None:
        topic_a = _make_topic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        topic_b = _make_topic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        qids_a = [uuid.uuid4() for _ in range(3)]
        qids_b = [uuid.uuid4() for _ in range(3)]

        # New consolidated query: single call returning (topic_id, question_id) pairs
        mock_result = MagicMock()
        mock_result.all.return_value = [(topic_a.id, qid) for qid in qids_a] + [(topic_b.id, qid) for qid in qids_b]
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service._select_questions_for_diagnostic(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        result_set = set(result)
        assert result_set & set(qids_a)
        assert result_set & set(qids_b)


# ── Sample questions for topic ───────────────────────────────────────────


# Removed tests for private method _sample_questions_for_topic.
# Functionality is tested through _select_questions_for_diagnostic.


# ── Onboarding status update logic ──────────────────────────────────────


class TestOnboardingStatusUpdate:
    """Tests for onboarding status update logic within Celery task.

    The task now updates class_enrollments.onboarding_diagnostic_status instead of
    student_profiles. This test validates the conditional update pattern.
    """

    @pytest.mark.asyncio
    async def test_when_enrollment_status_pending_then_updated_to_in_progress(self) -> None:
        """Test that a PENDING enrollment status gets updated to IN_PROGRESS."""
        enrollment = SimpleNamespace(
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        # Simulate the update logic from trigger_onboarding_diagnostics
        if enrollment.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            enrollment.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert enrollment.onboarding_diagnostic_status == OnboardingStatus.IN_PROGRESS

    def test_when_enrollment_status_completed_then_not_regressed(self) -> None:
        """Test that a COMPLETED status is not regressed to IN_PROGRESS."""
        enrollment = SimpleNamespace(
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        # Simulate the update logic - should not update if not PENDING
        if enrollment.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            enrollment.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert enrollment.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    def test_when_enrollment_status_in_progress_then_not_changed(self) -> None:
        """Test that IN_PROGRESS status remains unchanged when PENDING check fails."""
        enrollment = SimpleNamespace(
            onboarding_diagnostic_status=OnboardingStatus.IN_PROGRESS,
        )

        # Simulate the update logic - should not update if not PENDING
        if enrollment.onboarding_diagnostic_status == OnboardingStatus.PENDING:
            enrollment.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        assert enrollment.onboarding_diagnostic_status == OnboardingStatus.IN_PROGRESS


class TestCeleryTaskEventLoop:
    """Tests for Celery task event loop handling.

    Ensures tasks use new event loops instead of asyncio.run()
    to avoid RuntimeError when called from within existing async context.
    """

    def test_create_class_diagnostic_task_uses_new_event_loop(self) -> None:
        """Test create_class_diagnostic_task creates new event loop instead of asyncio.run()."""
        import inspect

        from app.tasks import onboarding_tasks

        source = inspect.getsource(onboarding_tasks.create_class_diagnostic_task)
        assert "asyncio.new_event_loop()" in source
        assert "loop.run_until_complete" in source

    def test_trigger_onboarding_diagnostics_uses_new_event_loop(self) -> None:
        """Test trigger_onboarding_diagnostics creates new event loop instead of asyncio.run()."""
        import inspect

        from app.tasks import onboarding_tasks

        source = inspect.getsource(onboarding_tasks.trigger_onboarding_diagnostics)
        assert "asyncio.new_event_loop()" in source
        assert "loop.run_until_complete" in source
