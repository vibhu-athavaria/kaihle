"""Unit tests for AssessmentService.get_assessment_results — topic-level aggregation.

TDD: tests for the topic_breakdown field added to AssessmentResultsSummary.
Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentType
from app.models.user import UserRole
from app.services.assessment_service import AssessmentService


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def service(mock_db: MagicMock) -> AssessmentService:
    return AssessmentService(mock_db)


def _make_assessment(school_id: uuid.UUID, class_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id or uuid.uuid4(),
        title="Diagnostic Q1",
        assessment_type=AssessmentType.DIAGNOSTIC,
    )


def _make_class(school_id: uuid.UUID, teacher_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        teacher_id=teacher_id or uuid.uuid4(),
        name="9A English",
    )


def _make_enrollment_row(
    student_id: uuid.UUID | None = None,
    attempt_id: uuid.UUID | None = None,
    score: float | None = None,
    status: str | None = None,
    completed_at=None,
    first_name: str = "Alice",
    last_name: str = "Wong",
) -> SimpleNamespace:
    return SimpleNamespace(
        student_id=student_id or uuid.uuid4(),
        first_name=first_name,
        last_name=last_name,
        attempt_id=attempt_id or uuid.uuid4(),
        overall_score=score,
        status=status or "COMPLETED",
        completed_at=completed_at,
    )


def _make_topic_row(
    topic_name: str,
    subtopic_name: str,
    correct: int,
    total: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        topic_name=topic_name,
        subtopic_name=subtopic_name,
        correct_count=correct,
        total_count=total,
    )


@pytest.mark.asyncio
async def test_get_assessment_results_when_responses_exist_then_topic_breakdown_populated(
    service: AssessmentService, mock_db: MagicMock
) -> None:
    """topic_breakdown must contain per-topic aggregated correct/total counts."""
    school_id = uuid.uuid4()
    assessment = _make_assessment(school_id=school_id)
    class_ = _make_class(school_id=school_id)

    mock_db.get.side_effect = [assessment, class_]

    enrollment_row = _make_enrollment_row(score=0.8, status="COMPLETED")
    mock_enrollments_result = MagicMock()
    mock_enrollments_result.all.return_value = [enrollment_row]

    # Two topic rows: same topic "Algebra", two subtopics
    topic_rows = [
        _make_topic_row("Algebra", "Linear Equations", correct=8, total=10),
        _make_topic_row("Algebra", "Quadratic Equations", correct=3, total=5),
    ]
    mock_topic_result = MagicMock()
    mock_topic_result.all.return_value = topic_rows

    mock_db.execute.side_effect = [mock_enrollments_result, mock_topic_result]

    result = await service.get_assessment_results(
        assessment_id=assessment.id,
        school_id=school_id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.SCHOOL_ADMIN,
    )

    assert len(result.topic_breakdown) == 1
    topic = result.topic_breakdown[0]
    assert topic.topic_name == "Algebra"
    assert topic.correct_count == 11  # 8 + 3
    assert topic.total_count == 15  # 10 + 5
    # avg = 11/15 ≈ 0.733
    assert abs(topic.avg_score - 11 / 15) < 0.001


@pytest.mark.asyncio
async def test_get_assessment_results_when_multiple_topics_then_sorted_by_avg_score_ascending(
    service: AssessmentService, mock_db: MagicMock
) -> None:
    """Weakest topics first so teacher attention flows naturally to gaps."""
    school_id = uuid.uuid4()
    assessment = _make_assessment(school_id=school_id)
    class_ = _make_class(school_id=school_id)

    mock_db.get.side_effect = [assessment, class_]
    mock_enrollments_result = MagicMock()
    mock_enrollments_result.all.return_value = [_make_enrollment_row()]
    topic_rows = [
        _make_topic_row("Statistics", "Probability", correct=2, total=10),  # 20%
        _make_topic_row("Algebra", "Linear Equations", correct=9, total=10),  # 90%
        _make_topic_row("Geometry", "Circles", correct=5, total=10),  # 50%
    ]
    mock_topic_result = MagicMock()
    mock_topic_result.all.return_value = topic_rows
    mock_db.execute.side_effect = [mock_enrollments_result, mock_topic_result]

    result = await service.get_assessment_results(
        assessment_id=assessment.id,
        school_id=school_id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.SCHOOL_ADMIN,
    )

    names = [t.topic_name for t in result.topic_breakdown]
    assert names == ["Statistics", "Geometry", "Algebra"]


@pytest.mark.asyncio
async def test_get_assessment_results_when_no_responses_then_topic_breakdown_empty(
    service: AssessmentService, mock_db: MagicMock
) -> None:
    """No responses → empty breakdown, not an error."""
    school_id = uuid.uuid4()
    assessment = _make_assessment(school_id=school_id)
    class_ = _make_class(school_id=school_id)

    mock_db.get.side_effect = [assessment, class_]
    mock_enrollments_result = MagicMock()
    mock_enrollments_result.all.return_value = []
    mock_topic_result = MagicMock()
    mock_topic_result.all.return_value = []
    mock_db.execute.side_effect = [mock_enrollments_result, mock_topic_result]

    result = await service.get_assessment_results(
        assessment_id=assessment.id,
        school_id=school_id,
        requesting_user_id=uuid.uuid4(),
        requesting_user_role=UserRole.SCHOOL_ADMIN,
    )

    assert result.topic_breakdown == []
