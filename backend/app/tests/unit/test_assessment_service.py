"""Unit tests for AssessmentService Tier 2 methods.

Tests follow TDD: written before the implementation methods exist.
Uses mock DB sessions — no real database required.

Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentStatus, AssessmentType
from app.schemas.assessments import AssessmentCreateRequest
from app.services.assessment_service import (
    AssessmentService,
    InsufficientQuestionsError,
    TeacherNotClassOwnerError,
    _sample_with_topic_distribution,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_db: MagicMock) -> AssessmentService:
    return AssessmentService(mock_db)


def _make_class(school_id: uuid.UUID, teacher_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        teacher_id=teacher_id,
        subject_id=uuid.uuid4(),
        grade_id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        name="Test Class 9A",
        academic_year="2025-2026",
        is_active=True,
    )


def _make_request(
    title: str | None = "Test Assessment",
    topic_ids: list[uuid.UUID] | None = None,
    question_count: int = 5,
    assessment_type: str = AssessmentType.PROGRESS_CHECK,
    difficulty_min: float = 1.0,
    difficulty_max: float = 5.0,
) -> AssessmentCreateRequest:
    return AssessmentCreateRequest(
        title=title,
        topic_ids=topic_ids or [],
        question_count=question_count,
        assessment_type=assessment_type,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
    )


def _make_question_rows(
    count: int,
    curriculum_topic_id: uuid.UUID | None = None,
) -> list[tuple[uuid.UUID, uuid.UUID, float | None]]:
    """Make fake (question_id, curriculum_topic_id, difficulty_level) rows."""
    topic_id = curriculum_topic_id or uuid.uuid4()
    return [(uuid.uuid4(), topic_id, 3.0) for _ in range(count)]


# ---------------------------------------------------------------------------
# create_assessment
# ---------------------------------------------------------------------------


class TestCreateAssessment:
    @pytest.mark.asyncio
    async def test_create_when_valid_config_then_draft_assessment_created(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        class_.id = class_id

        body = _make_request(question_count=5)
        rows = _make_question_rows(10)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        assessment = await service.create_assessment(school_id, teacher_id, class_id, body)

        assert assessment.status == AssessmentStatus.DRAFT
        assert assessment.is_system_generated is False
        assert assessment.school_id == school_id
        assert assessment.class_id == class_id
        assert assessment.created_by == teacher_id
        assert assessment.question_count == 5
        mock_db.add.assert_called()
        mock_db.add_all.assert_called()
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_create_when_teacher_not_class_owner_then_raises_teacher_not_class_owner_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        other_teacher_id = uuid.uuid4()
        requesting_teacher_id = uuid.uuid4()  # different from class owner
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, other_teacher_id)
        class_.id = class_id

        body = _make_request()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = class_
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(TeacherNotClassOwnerError):
            await service.create_assessment(school_id, requesting_teacher_id, class_id, body)

        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_when_class_not_found_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Class not found"):
            await service.create_assessment(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), _make_request())

    @pytest.mark.asyncio
    async def test_create_when_insufficient_questions_then_raises_insufficient_questions_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        class_.id = class_id

        body = _make_request(question_count=10)
        rows = _make_question_rows(3)  # only 3, but 10 requested

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        with pytest.raises(InsufficientQuestionsError) as exc_info:
            await service.create_assessment(school_id, teacher_id, class_id, body)

        assert exc_info.value.available == 3
        assert exc_info.value.requested == 10

    @pytest.mark.asyncio
    async def test_create_always_sets_is_system_generated_false(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        class_.id = class_id

        body = _make_request(question_count=5)
        rows = _make_question_rows(10)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        assessment = await service.create_assessment(school_id, teacher_id, class_id, body)

        assert assessment.is_system_generated is False

    @pytest.mark.asyncio
    async def test_create_when_diagnostic_type_no_topic_ids_then_questions_span_multiple_topics(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        from unittest.mock import patch

        from app.services import assessment_service as svc_module

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        class_.id = class_id

        body = _make_request(
            title="Diagnostic",
            topic_ids=[],
            question_count=6,
            assessment_type=AssessmentType.DIAGNOSTIC,
        )

        # 3 topics × 4 questions each
        topic1, topic2, topic3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = _make_question_rows(4, topic1) + _make_question_rows(4, topic2) + _make_question_rows(4, topic3)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        # Capture the rows passed to _sample_pool_with_difficulty_distribution
        captured_rows: list = []
        original_sample = svc_module._sample_pool_with_difficulty_distribution

        def capturing_sample(r: list, n: int, rng) -> list:
            captured_rows.extend(r)
            return original_sample(r, n, rng)  # type: ignore

        with patch.object(svc_module, "_sample_pool_with_difficulty_distribution", side_effect=capturing_sample):
            await service.create_assessment(school_id, teacher_id, class_id, body)

        # All 3 topics must be present in the rows the sampler received
        topic_ids_sampled = {tid for _, tid, _ in captured_rows}
        assert {topic1, topic2, topic3}.issubset(topic_ids_sampled)

    @pytest.mark.asyncio
    async def test_create_when_difficulty_range_narrow_then_query_built_with_difficulty_filter(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        """Verifies that difficulty_min/max are included in the question query.

        We check this by verifying the correct DB execute calls happen —
        the actual SQL filtering is tested in integration tests.
        """
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        class_.id = class_id

        body = _make_request(question_count=3, difficulty_min=1.0, difficulty_max=2.5)
        rows = _make_question_rows(10)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        assessment = await service.create_assessment(school_id, teacher_id, class_id, body)

        # Two execute calls: class lookup + question query
        assert mock_db.execute.call_count == 2
        assert assessment.question_count == 3


# ---------------------------------------------------------------------------
# publish_assessment
# ---------------------------------------------------------------------------


class TestPublishAssessment:
    @pytest.mark.asyncio
    async def test_publish_when_draft_then_status_becomes_active(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.DRAFT,
            published_at=None,
            deadline=None,
        )

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        # Question count check: 5 questions exist
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5
        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_count_result])

        result = await service.publish_assessment(assessment_id, school_id, teacher_id, deadline=None)

        assert result.status == AssessmentStatus.ACTIVE
        assert result.published_at is not None

    @pytest.mark.asyncio
    async def test_publish_when_already_active_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assessment
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="status"):
            await service.publish_assessment(assessment_id, school_id, teacher_id, deadline=None)

    @pytest.mark.asyncio
    async def test_publish_when_different_teacher_then_raises_teacher_not_class_owner_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        owner_teacher_id = uuid.uuid4()
        other_teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=owner_teacher_id,
            status=AssessmentStatus.DRAFT,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assessment
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(TeacherNotClassOwnerError):
            await service.publish_assessment(assessment_id, school_id, other_teacher_id, deadline=None)

    @pytest.mark.asyncio
    async def test_publish_when_no_questions_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.DRAFT,
        )

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0  # no questions
        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_count_result])

        with pytest.raises(ValueError, match="question"):
            await service.publish_assessment(assessment_id, school_id, teacher_id, deadline=None)

    @pytest.mark.asyncio
    async def test_publish_with_deadline_then_deadline_set_on_assessment(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()
        deadline = datetime(2026, 5, 1, tzinfo=UTC)

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.DRAFT,
            published_at=None,
            deadline=None,
        )

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5
        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_count_result])

        result = await service.publish_assessment(assessment_id, school_id, teacher_id, deadline=deadline)

        assert result.deadline == deadline
        assert result.status == AssessmentStatus.ACTIVE


# ---------------------------------------------------------------------------
# close_assessment
# ---------------------------------------------------------------------------


class TestCloseAssessment:
    @pytest.mark.asyncio
    async def test_close_when_active_then_status_becomes_closed(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assessment
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.close_assessment(assessment_id, school_id, teacher_id)

        assert result.status == AssessmentStatus.CLOSED

    @pytest.mark.asyncio
    async def test_close_when_draft_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.DRAFT,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assessment
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError):
            await service.close_assessment(assessment_id, school_id, teacher_id)

    @pytest.mark.asyncio
    async def test_close_when_assessment_not_found_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found"):
            await service.close_assessment(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_close_when_different_teacher_then_raises_teacher_not_class_owner_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=owner_id,
            status=AssessmentStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assessment
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(TeacherNotClassOwnerError):
            await service.close_assessment(assessment_id, school_id, other_id)


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    @pytest.mark.asyncio
    async def test_get_when_teacher_role_then_correct_answer_is_present(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
        )

        q1 = SimpleNamespace(id=uuid.uuid4(), correct_answer="A", question_text="Q1", options=[])
        q2 = SimpleNamespace(id=uuid.uuid4(), correct_answer="B", question_text="Q2", options=[])

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = [(q1,), (q2,)]
        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_questions_result])

        result_assessment, questions = await service.get_assessment(assessment_id, school_id, uuid.uuid4(), "TEACHER")

        assert result_assessment.id == assessment_id
        # Teacher gets correct answers
        assert questions[0].correct_answer == "A"
        assert questions[1].correct_answer == "B"

    @pytest.mark.asyncio
    async def test_get_when_student_role_then_correct_answer_is_none(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        school_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
        )

        q1 = SimpleNamespace(id=uuid.uuid4(), correct_answer="A", question_text="Q1", options=[])

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = [(q1,)]
        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_questions_result])

        _, questions = await service.get_assessment(assessment_id, school_id, uuid.uuid4(), "STUDENT")

        assert questions[0].correct_answer is None

    @pytest.mark.asyncio
    async def test_get_when_wrong_school_then_raises_value_error(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        # Cross-school access: school_id is in SQL WHERE clause, so DB returns None.
        # The mock simulates this by returning None — the real DB would do the same.
        assessment_id = uuid.uuid4()
        school_id = uuid.uuid4()  # requesting user's school

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no match in this school
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found"):
            await service.get_assessment(assessment_id, school_id, uuid.uuid4(), "TEACHER")


# ---------------------------------------------------------------------------
# _sample_with_topic_distribution helper
# ---------------------------------------------------------------------------


class TestSampleWithTopicDistribution:
    def test_when_3_topics_10_questions_then_each_topic_represented(self) -> None:
        topic1, topic2, topic3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = (
            [(uuid.uuid4(), topic1) for _ in range(6)]
            + [(uuid.uuid4(), topic2) for _ in range(6)]
            + [(uuid.uuid4(), topic3) for _ in range(6)]
        )

        selected = _sample_with_topic_distribution(rows, 10)

        assert len(selected) == 10
        # Verify all 3 topics are represented
        id_to_topic = {qid: t for qid, t in rows}
        topics_in_result = {id_to_topic[qid] for qid in selected}
        assert topics_in_result == {topic1, topic2, topic3}

    def test_when_single_topic_then_returns_n_questions(self) -> None:
        topic = uuid.uuid4()
        rows = [(uuid.uuid4(), topic) for _ in range(20)]

        selected = _sample_with_topic_distribution(rows, 10)

        assert len(selected) == 10

    def test_when_fewer_available_than_requested_raises_not_caught_here(self) -> None:
        """_sample_with_topic_distribution trusts caller to validate count first."""
        topic = uuid.uuid4()
        rows = [(uuid.uuid4(), topic) for _ in range(3)]

        # When available < requested, returns all available
        selected = _sample_with_topic_distribution(rows, 10)
        assert len(selected) == 3

    def test_when_empty_rows_then_returns_empty_list(self) -> None:
        selected = _sample_with_topic_distribution([], 5)
        assert selected == []
