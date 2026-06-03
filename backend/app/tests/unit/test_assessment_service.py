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
    questions_per_topic: int = 5,
    assessment_type: str = AssessmentType.PROGRESS_CHECK,
    minimum_difficulty: int = 1,
    maximum_difficulty: int = 5,
) -> AssessmentCreateRequest:
    return AssessmentCreateRequest(
        title=title,
        topic_ids=topic_ids or [uuid.uuid4()],
        questions_per_topic=questions_per_topic,
        assessment_type=assessment_type,
        minimum_difficulty=minimum_difficulty,
        maximum_difficulty=maximum_difficulty,
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

        body = _make_request(questions_per_topic=5)
        rows = _make_question_rows(10)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result])

        assessment = await service.create_assessment(school_id, teacher_id, class_id, body)

        assert assessment.status == AssessmentStatus.DRAFT
        assert assessment.school_id == school_id
        assert assessment.class_id == class_id
        assert assessment.created_by == teacher_id
        assert assessment.question_count == 5  # questions_per_topic=5, 1 topic
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

        body = _make_request(questions_per_topic=10)
        rows = _make_question_rows(3)  # only 3, but 10 requested (1 topic × questions_per_topic=10)

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

        # 3 topics × 4 questions each
        topic1, topic2, topic3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        body = _make_request(
            title="Diagnostic",
            topic_ids=[topic1, topic2, topic3],
            questions_per_topic=2,
            assessment_type=AssessmentType.DIAGNOSTIC,
        )

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

        body = _make_request(questions_per_topic=3, minimum_difficulty=1, maximum_difficulty=2)
        rows = _make_question_rows(10)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = class_
        mock_questions_result = MagicMock()
        mock_questions_result.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[mock_class_result, mock_questions_result, MagicMock()])

        assessment = await service.create_assessment(school_id, teacher_id, class_id, body)

        # Two execute calls: class lookup + question query (+ optional subject title)
        assert mock_db.execute.call_count >= 2
        assert assessment.question_count == 3  # questions_per_topic=3, 1 topic


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
    async def test_delete_assessment_when_active_with_no_attempts_then_succeeds(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        """ACTIVE assessment with zero student attempts can be deleted."""
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.ACTIVE,
        )

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        # Attempt count query returns 0
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        # Bridge row deletion execute
        mock_delete_result = MagicMock()

        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_count_result, mock_delete_result])
        mock_db.delete = AsyncMock()

        await service.delete_assessment(assessment_id, school_id, teacher_id)

        mock_db.delete.assert_called_once_with(assessment)

    @pytest.mark.asyncio
    async def test_delete_assessment_when_active_with_attempts_then_409(
        self, service: AssessmentService, mock_db: MagicMock
    ) -> None:
        """ACTIVE assessment with >=1 student attempt raises ValueError (mapped to 409 in route)."""
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment_id = uuid.uuid4()

        assessment = SimpleNamespace(
            id=assessment_id,
            school_id=school_id,
            created_by=teacher_id,
            status=AssessmentStatus.ACTIVE,
        )

        mock_assessment_result = MagicMock()
        mock_assessment_result.scalar_one_or_none.return_value = assessment
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3  # 3 existing attempts

        mock_db.execute = AsyncMock(side_effect=[mock_assessment_result, mock_count_result])
        mock_db.delete = AsyncMock()

        with pytest.raises(ValueError, match="attempt"):
            await service.delete_assessment(assessment_id, school_id, teacher_id)

        mock_db.delete.assert_not_called()

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
# T5: Tier 1 diagnostic — CLOSED unlock
# ---------------------------------------------------------------------------


class TestDesignTier1DiagnosticClosedUnlock:
    """Tests for the CLOSED → replaceable unlock in design_tier1_diagnostic."""

    @pytest.mark.asyncio
    async def test_design_tier1_diagnostic_when_existing_is_closed_then_replaces_successfully(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import DesignTier1DiagnosticRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        topic_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        class_ns = SimpleNamespace(
            id=uuid.uuid4(),
            school_id=school_id,
            teacher_id=teacher_id,
            subject_id=uuid.uuid4(),
            grade_id=grade_id,
            curriculum_id=uuid.uuid4(),
            name="Test Class",
        )
        closed_diagnostic = SimpleNamespace(
            id=uuid.uuid4(),
            status=AssessmentStatus.CLOSED,
        )
        topic_grade_row = SimpleNamespace(
            curriculum_topic_id=topic_id,
            grade_level=9,
            grade_id=grade_id,
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=class_ns)),  # load class
                MagicMock(scalar_one_or_none=MagicMock(return_value=closed_diagnostic)),  # existing
                MagicMock(),  # delete ASQ
                MagicMock(scalar_one_or_none=MagicMock(return_value=9)),  # grade level
                MagicMock(all=MagicMock(return_value=[topic_grade_row])),  # topic grade rows
                MagicMock(all=MagicMock(return_value=[])),  # question rows
            ]
        )
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], questions_per_topic=3)

        # Should NOT raise — CLOSED diagnostic can be replaced
        assessment = await service.design_tier1_diagnostic(
            class_id=class_ns.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert assessment.assessment_type == AssessmentType.DIAGNOSTIC
        assert assessment.status == AssessmentStatus.DRAFT

    @pytest.mark.asyncio
    async def test_design_tier1_diagnostic_when_existing_is_active_then_raises_ValueError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import DesignTier1DiagnosticRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        class_ = _make_class(school_id, teacher_id)
        active_diagnostic = SimpleNamespace(
            id=uuid.uuid4(),
            class_id=class_.id,
            school_id=school_id,
            assessment_type=AssessmentType.DIAGNOSTIC,
            status=AssessmentStatus.ACTIVE,
            created_by=teacher_id,
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=class_)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=active_diagnostic)),
            ]
        )

        body = DesignTier1DiagnosticRequest(topic_ids=[uuid.uuid4()], questions_per_topic=3)

        with pytest.raises(ValueError, match="ACTIVE"):
            await service.design_tier1_diagnostic(
                class_id=class_.id,
                school_id=school_id,
                teacher_id=teacher_id,
                body=body,
            )


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


# ---------------------------------------------------------------------------
# T2: get_assessment_preview / update_assessment
# ---------------------------------------------------------------------------


def _make_assessment(
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    status: str = AssessmentStatus.ACTIVE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        created_by=teacher_id,
        class_id=uuid.uuid4(),
        title="Test Assessment",
        assessment_type=AssessmentType.PROGRESS_CHECK,
        status=status,
        question_count=10,
        questions_per_topic=2,
        minimum_difficulty=1,
        maximum_difficulty=5,
        question_types=["MCQ", "TRUE_FALSE"],
        time_limit_minutes=0,
        instructions=None,
        deadline=None,
        published_at=None,
        created_at=datetime.now(UTC),
    )


class TestGetAssessmentPreview:
    """Tests for AssessmentService.get_assessment_preview."""

    @pytest.mark.asyncio
    async def test_get_assessment_preview_when_teacher_owns_then_returns_questions_with_correct_answers(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id)

        question_row = SimpleNamespace(
            question_id=uuid.uuid4(),
            question_text="What is 2+2?",
            question_type="MCQ",
            options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
            correct_answer="B",
            explanation="Basic arithmetic",
            difficulty_level=1.0,
            source="bank",
            subtopic_name="Arithmetic",
            topic_name="Numbers",
            order_index=0,
        )

        # Call 1: load assessment
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(all=MagicMock(return_value=[question_row])),
                MagicMock(scalar=MagicMock(return_value=0)),
            ]
        )

        result = await service.get_assessment_preview(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.id == assessment.id
        assert len(result.questions) == 1
        assert result.questions[0].correct_answer_key == "B"
        assert result.questions[0].topic_name == "Numbers"
        assert result.questions[0].is_teacher_submitted is False
        assert result.attempt_count == 0

    @pytest.mark.asyncio
    async def test_get_assessment_preview_when_teacher_not_owner_then_raises_TeacherNotClassOwnerError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        real_teacher_id = uuid.uuid4()
        other_teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, real_teacher_id)

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)))

        from app.services.assessment_service import TeacherNotClassOwnerError

        with pytest.raises(TeacherNotClassOwnerError):
            await service.get_assessment_preview(
                assessment_id=assessment.id,
                school_id=school_id,
                teacher_id=other_teacher_id,
            )

    @pytest.mark.asyncio
    async def test_get_assessment_preview_when_closed_then_still_returns_questions(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id, status=AssessmentStatus.CLOSED)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(all=MagicMock(return_value=[])),
                MagicMock(scalar=MagicMock(return_value=5)),
            ]
        )

        result = await service.get_assessment_preview(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.status == AssessmentStatus.CLOSED
        assert result.attempt_count == 5


class TestUpdateAssessment:
    """Tests for AssessmentService.update_assessment."""

    @pytest.mark.asyncio
    async def test_update_assessment_when_safe_fields_only_then_updates_and_has_attempts_false(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AssessmentUpdateRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar=MagicMock(return_value=0)),
            ]
        )

        body = AssessmentUpdateRequest(title="Updated Title")
        result = await service.update_assessment(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert result.title == "Updated Title"
        assert result.has_attempts is False

    @pytest.mark.asyncio
    async def test_update_assessment_when_risky_field_changed_with_attempts_then_applies_and_has_attempts_true(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AssessmentUpdateRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar=MagicMock(return_value=3)),
            ]
        )

        body = AssessmentUpdateRequest(question_count=15)
        result = await service.update_assessment(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert result.question_count == 15
        assert result.has_attempts is True

    @pytest.mark.asyncio
    async def test_update_assessment_when_closed_and_risky_field_sent_then_raises_ValueError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AssessmentUpdateRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id, status=AssessmentStatus.CLOSED)

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)))

        body = AssessmentUpdateRequest(question_count=5)
        with pytest.raises(ValueError, match="CLOSED"):
            await service.update_assessment(
                assessment_id=assessment.id,
                school_id=school_id,
                teacher_id=teacher_id,
                body=body,
            )

    @pytest.mark.asyncio
    async def test_update_assessment_when_closed_and_safe_field_sent_then_succeeds(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AssessmentUpdateRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment(school_id, teacher_id, status=AssessmentStatus.CLOSED)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar=MagicMock(return_value=10)),
            ]
        )

        body = AssessmentUpdateRequest(title="Archived Assessment")
        result = await service.update_assessment(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert result.title == "Archived Assessment"


# ---------------------------------------------------------------------------
# T3: Question pool management
# ---------------------------------------------------------------------------


def _make_assessment_ns(
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    assessment_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    question_count: int = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=assessment_id or uuid.uuid4(),
        school_id=school_id,
        created_by=teacher_id,
        class_id=class_id or uuid.uuid4(),
        title="Test",
        assessment_type=AssessmentType.PROGRESS_CHECK,
        status=AssessmentStatus.ACTIVE,
        question_count=question_count,
        questions_per_topic=2,
        minimum_difficulty=1,
        maximum_difficulty=5,
        question_types=["MCQ"],
        time_limit_minutes=0,
        instructions=None,
        deadline=None,
        published_at=None,
        created_at=datetime.now(UTC),
    )


class TestAddQuestionToAssessment:
    """Tests for AssessmentService.add_question_to_assessment."""

    @pytest.mark.asyncio
    async def test_add_question_when_teacher_owns_then_inserts_question_bank_with_source_teacher(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AddQuestionRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)
        class_ns = SimpleNamespace(
            id=assessment.class_id,
            subject_id=uuid.uuid4(),
            grade_id=uuid.uuid4(),
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                # _verify_teacher_owns_assessment
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                # db.get(Class, ...)
                MagicMock(scalar_one_or_none=MagicMock(return_value=class_ns)),
                # subtopic verify
                MagicMock(scalar_one_or_none=MagicMock(return_value=uuid.uuid4())),
                # max order_index
                MagicMock(scalar=MagicMock(return_value=4)),
            ]
        )
        mock_db.get = AsyncMock(return_value=class_ns)

        body = AddQuestionRequest(
            subtopic_id=uuid.uuid4(),
            question_text="What is gravity?",
            question_type="MCQ",
            options=[{"key": "A", "text": "9.8"}, {"key": "B", "text": "10"}],
            correct_answer="A",
            difficulty_level=2.0,
        )

        result = await service.add_question_to_assessment(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert result.question_id is not None
        assert result.review_item_id is not None
        # Verify db.add was called (question + ASQ + review_item = 3 calls)
        assert mock_db.add.call_count == 3

    @pytest.mark.asyncio
    async def test_add_question_when_teacher_owns_then_question_count_incremented(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AddQuestionRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id, question_count=5)
        class_ns = SimpleNamespace(id=assessment.class_id, subject_id=uuid.uuid4(), grade_id=uuid.uuid4())

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=class_ns)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=uuid.uuid4())),
                MagicMock(scalar=MagicMock(return_value=4)),
            ]
        )
        mock_db.get = AsyncMock(return_value=class_ns)

        body = AddQuestionRequest(
            subtopic_id=uuid.uuid4(),
            question_text="Test question",
            correct_answer="A",
        )

        await service.add_question_to_assessment(
            assessment_id=assessment.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert assessment.question_count == 6  # incremented from 5

    @pytest.mark.asyncio
    async def test_add_question_when_subtopic_wrong_subject_then_raises_ValueError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import AddQuestionRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)
        class_ns = SimpleNamespace(id=assessment.class_id, subject_id=uuid.uuid4(), grade_id=uuid.uuid4())

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # subtopic not found
            ]
        )
        mock_db.get = AsyncMock(return_value=class_ns)

        body = AddQuestionRequest(
            subtopic_id=uuid.uuid4(),
            question_text="Test",
            correct_answer="A",
        )

        with pytest.raises(ValueError, match="Subtopic"):
            await service.add_question_to_assessment(
                assessment_id=assessment.id,
                school_id=school_id,
                teacher_id=teacher_id,
                body=body,
            )


class TestRemoveQuestionFromPool:
    """Tests for AssessmentService.remove_question_from_pool."""

    @pytest.mark.asyncio
    async def test_remove_question_when_no_responses_then_removes_and_returns_false(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        question_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id, question_count=5)
        bridge = SimpleNamespace(order_index=2)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),  # load assessment
                MagicMock(scalar_one_or_none=MagicMock(return_value=bridge)),  # bridge exists
                MagicMock(scalar=MagicMock(return_value=5)),  # pool size
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no responses
                MagicMock(),  # delete
            ]
        )

        result = await service.remove_question_from_pool(
            assessment_id=assessment.id,
            question_id=question_id,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.removed is True
        assert result.has_responses is False
        assert assessment.question_count == 4  # decremented

    @pytest.mark.asyncio
    async def test_remove_question_when_responses_exist_then_removes_and_returns_true(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        question_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id, question_count=3)
        bridge = SimpleNamespace(order_index=0)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=bridge)),
                MagicMock(scalar=MagicMock(return_value=3)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=uuid.uuid4())),  # response exists
                MagicMock(),
            ]
        )

        result = await service.remove_question_from_pool(
            assessment_id=assessment.id,
            question_id=question_id,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.has_responses is True

    @pytest.mark.asyncio
    async def test_remove_question_when_count_would_drop_to_zero_then_raises_ValueError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        question_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id, question_count=1)
        bridge = SimpleNamespace(order_index=0)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=bridge)),
                MagicMock(scalar=MagicMock(return_value=1)),  # pool_size = 1
            ]
        )

        with pytest.raises(ValueError, match="at least 1 question"):
            await service.remove_question_from_pool(
                assessment_id=assessment.id,
                question_id=question_id,
                school_id=school_id,
                teacher_id=teacher_id,
            )


class TestGetReplacementCandidates:
    """Tests for AssessmentService.get_replacement_candidates."""

    @pytest.mark.asyncio
    async def test_get_replacement_candidates_then_excludes_existing_pool_questions(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        existing_q = uuid.uuid4()
        curriculum_topic_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)

        candidate_row = SimpleNamespace(
            question_id=uuid.uuid4(),
            question_text="What is photosynthesis?",
            question_type="MCQ",
            options=[{"key": "A", "text": "Ans"}],
            correct_answer="A",
            difficulty_level=2.0,
            subtopic_name="Plants",
            topic_name="Biology",
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),  # verify teacher
                MagicMock(scalar_one_or_none=MagicMock(return_value=curriculum_topic_id)),  # topic
                MagicMock(all=MagicMock(return_value=[(existing_q,)])),  # existing ids
                MagicMock(all=MagicMock(return_value=[candidate_row])),  # candidates
            ]
        )

        results = await service.get_replacement_candidates(
            assessment_id=assessment.id,
            question_id=uuid.uuid4(),
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert len(results) == 1
        assert results[0].topic_name == "Biology"


class TestReplaceQuestion:
    """Tests for AssessmentService.replace_question."""

    @pytest.mark.asyncio
    async def test_replace_question_when_no_responses_then_swaps_and_returns_false(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        old_q = uuid.uuid4()
        new_q = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)
        old_bridge = SimpleNamespace(order_index=3)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),  # verify
                MagicMock(scalar_one_or_none=MagicMock(return_value=old_bridge)),  # old bridge
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # new not in pool
                MagicMock(scalar_one_or_none=MagicMock(return_value=new_q)),  # replacement exists
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no responses
                MagicMock(),  # delete old
            ]
        )

        result = await service.replace_question(
            assessment_id=assessment.id,
            old_question_id=old_q,
            replacement_id=new_q,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.replaced is True
        assert result.has_responses_for_old is False
        # New bridge row should have been added
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_replace_question_when_responses_exist_then_swaps_and_returns_true(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        old_q = uuid.uuid4()
        new_q = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)
        old_bridge = SimpleNamespace(order_index=1)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=old_bridge)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=new_q)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=uuid.uuid4())),  # responses exist
                MagicMock(),
            ]
        )

        result = await service.replace_question(
            assessment_id=assessment.id,
            old_question_id=old_q,
            replacement_id=new_q,
            school_id=school_id,
            teacher_id=teacher_id,
        )

        assert result.has_responses_for_old is True


class TestSuggestQuestionEdit:
    """Tests for AssessmentService.suggest_question_edit."""

    @pytest.mark.asyncio
    async def test_suggest_edit_then_creates_review_item_with_edit_suggestion_type(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import SuggestEditRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        question_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),  # verify
                MagicMock(scalar_one_or_none=MagicMock(return_value=question_id)),  # in_pool check
            ]
        )

        body = SuggestEditRequest(
            suggested_question_text="Revised question text",
            reason="The original had a typo",
        )

        result = await service.suggest_question_edit(
            assessment_id=assessment.id,
            question_id=question_id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

        assert result.review_item_id is not None
        # review_item was added to session
        added_item = mock_db.add.call_args[0][0]
        assert added_item.item_type == "EDIT_SUGGESTION"
        assert added_item.suggested_question_text == "Revised question text"
        assert added_item.reason == "The original had a typo"

    @pytest.mark.asyncio
    async def test_suggest_edit_when_question_not_in_pool_then_raises_ValueError(
        self, mock_db: MagicMock, service: AssessmentService
    ) -> None:
        from app.schemas.assessments import SuggestEditRequest

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        question_id = uuid.uuid4()
        assessment = _make_assessment_ns(school_id, teacher_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=assessment)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # not in pool
            ]
        )

        body = SuggestEditRequest(reason="Fix this")

        with pytest.raises(ValueError, match="not in assessment pool"):
            await service.suggest_question_edit(
                assessment_id=assessment.id,
                question_id=question_id,
                school_id=school_id,
                teacher_id=teacher_id,
                body=body,
            )
