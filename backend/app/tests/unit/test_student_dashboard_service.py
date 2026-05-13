"""Unit tests for StudentDashboardService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import User
from app.services.student_dashboard_service import (
    StudentDashboardService,
    _mastery_label,
    _trend,
)

# -----------------------------------------------------------------------------
# Helper function tests
# -----------------------------------------------------------------------------


class TestMasteryLabel:
    """Tests for _mastery_label() helper."""

    def test_mastery_label_when_score_none_returns_not_assessed(self):
        """None score should return 'Not assessed'."""
        assert _mastery_label(None) == "Not assessed"

    def test_mastery_label_when_score_above_0_7_returns_strong(self):
        """Score > 0.7 should return 'Strong'."""
        assert _mastery_label(0.71) == "Strong"
        assert _mastery_label(1.0) == "Strong"
        assert _mastery_label(0.9) == "Strong"

    def test_mastery_label_when_score_between_0_4_and_0_7_returns_developing(self):
        """Score >= 0.4 and <= 0.7 should return 'Developing'."""
        assert _mastery_label(0.4) == "Developing"
        assert _mastery_label(0.5) == "Developing"
        assert _mastery_label(0.7) == "Developing"

    def test_mastery_label_when_score_below_0_4_returns_needs_work(self):
        """Score < 0.4 should return 'Needs Work'."""
        assert _mastery_label(0.39) == "Needs Work"
        assert _mastery_label(0.0) == "Needs Work"
        assert _mastery_label(0.1) == "Needs Work"


class TestTrend:
    """Tests for _trend() helper."""

    def test_trend_when_recent_none_returns_none(self):
        """None recent_avg should return 'none'."""
        assert _trend(None, 0.5) == "none"

    def test_trend_when_prev_none_returns_none(self):
        """None prev_avg should return 'none'."""
        assert _trend(0.5, None) == "none"

    def test_trend_when_diff_above_0_05_returns_up(self):
        """Diff > 0.05 should return 'up'."""
        assert _trend(0.6, 0.5) == "up"
        assert _trend(0.8, 0.2) == "up"

    def test_trend_when_diff_below_negative_0_05_returns_down(self):
        """Diff < -0.05 should return 'down'."""
        assert _trend(0.5, 0.6) == "down"
        assert _trend(0.2, 0.8) == "down"

    def test_trend_when_diff_within_0_05_returns_flat(self):
        """Diff between -0.05 and 0.05 should return 'flat'."""
        assert _trend(0.5, 0.52) == "flat"
        assert _trend(0.5, 0.48) == "flat"
        assert _trend(0.5, 0.5) == "flat"


# -----------------------------------------------------------------------------
# StudentDashboardService tests
# -----------------------------------------------------------------------------


def _make_student():
    """Create a test student user."""
    return User(
        id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        email="test@example.com",
        first_name="Test",
        last_name="Student",
        role="STUDENT",
        is_active=True,
    )


def _make_mock_row(**kwargs):
    """Create a mock row with attributes."""
    row = MagicMock()
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


def _make_profile_result(grade_name="Grade 8"):
    """Create a mock profile query result."""
    result = MagicMock()
    result.grade_name = grade_name
    return result


def _make_enrollment_row(
    class_id=None,
    class_name="Math 8A",
    subject_id=None,
    subject_name="Mathematics",
    teacher_first="Jane",
    teacher_last="Doe",
    diagnostic_status="PENDING",
):
    """Create a mock enrollment row."""
    return _make_mock_row(
        class_id=class_id or uuid.uuid4(),
        class_name=class_name,
        subject_id=subject_id or uuid.uuid4(),
        subject_name=subject_name,
        teacher_first=teacher_first,
        teacher_last=teacher_last,
        onboarding_diagnostic_status=diagnostic_status,
    )


class TestGetDashboard:
    """Tests for StudentDashboardService.get_dashboard()."""

    @pytest.mark.asyncio
    async def test_get_dashboard_when_no_enrollments_returns_empty_classes(self):
        """Student with no enrollments should get empty classes list."""
        student = _make_student()
        mock_db = AsyncMock()

        # Profile query returns result
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result("Grade 8")

        # Enrollments query returns empty
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[profile_mock, enrollments_mock])

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert result.student_name == "Test Student"
        assert result.grade == "Grade 8"
        assert result.classes == []
        assert result.action_items == []

    @pytest.mark.asyncio
    async def test_get_dashboard_when_no_profile_returns_empty_grade(self):
        """Student with no profile should have empty grade."""
        student = _make_student()
        mock_db = AsyncMock()

        # Profile query returns None
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = None

        # Enrollments query returns empty
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[profile_mock, enrollments_mock])

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert result.grade == ""
        assert result.curriculum == ""

    @pytest.mark.asyncio
    async def test_get_dashboard_when_has_enrollments_returns_class_summaries(self):
        """Student with enrollments should get class summaries."""
        student = _make_student()
        class_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result("Grade 8")

        # Enrollment query
        enrollment = _make_enrollment_row(
            class_id=class_id,
            class_name="Mathematics 8A",
            subject_name="Mathematics",
        )
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery query returns no results (no gap states yet)
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = []

        # Topics total query
        topics_mock = MagicMock()
        topics_mock.all.return_value = []

        # Assessed topics query
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Assessments query
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = []

        # Study plans query
        plans_mock = MagicMock()
        plans_mock.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert len(result.classes) == 1
        assert result.classes[0].class_name == "Mathematics 8A"
        assert result.classes[0].subject_name == "Mathematics"
        assert result.classes[0].teacher_name == "Jane Doe"
        assert result.classes[0].diagnostic_status == "PENDING"
        assert result.classes[0].mastery_score is None

    @pytest.mark.asyncio
    async def test_get_dashboard_when_has_mastery_scores(self):
        """Class summaries should include mastery scores from gap states."""
        student = _make_student()
        class_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query
        enrollment = _make_enrollment_row(class_id=class_id)
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery query returns average
        mastery_row = _make_mock_row(class_id=class_id, avg_mastery=0.75)
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = [mastery_row]

        # Topics queries
        topics_mock = MagicMock()
        topics_mock.all.return_value = []
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Action items queries
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = []
        plans_mock = MagicMock()
        plans_mock.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert result.classes[0].mastery_score == 0.75
        assert result.classes[0].mastery_label == "Strong"

    @pytest.mark.asyncio
    async def test_get_dashboard_when_has_topic_counts(self):
        """Class summaries should include topic counts."""
        student = _make_student()
        class_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query
        enrollment = _make_enrollment_row(class_id=class_id)
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery query
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = []

        # Topics total query
        topics_row = _make_mock_row(class_id=class_id, total=10)
        topics_mock = MagicMock()
        topics_mock.all.return_value = [topics_row]

        # Assessed topics query
        assessed_row = _make_mock_row(class_id=class_id, assessed=5)
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = [assessed_row]

        # Action items queries
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = []
        plans_mock = MagicMock()
        plans_mock.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert result.classes[0].topics_total == 10
        assert result.classes[0].topics_assessed == 5

    @pytest.mark.asyncio
    async def test_get_dashboard_when_has_assessments_creates_action_items(self):
        """Pending assessments should create action items."""
        student = _make_student()
        class_id = uuid.uuid4()
        assessment_id = uuid.uuid4()
        attempt_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query
        enrollment = _make_enrollment_row(class_id=class_id)
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery/topics queries return empty
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = []
        topics_mock = MagicMock()
        topics_mock.all.return_value = []
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Assessments query returns pending assessment
        assessment_row = _make_mock_row(
            id=assessment_id,
            deadline=None,
            class_id=class_id,
            title="Unit 1 Test",
            attempt_id=attempt_id,
            class_name="Mathematics 8A",
            subject_name="Mathematics",
        )
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = [assessment_row]

        # Study plans query returns empty
        plans_mock = MagicMock()
        plans_mock.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert len(result.action_items) == 1
        assert result.action_items[0].type == "assessment_due"
        assert result.action_items[0].title == "Unit 1 Test"
        assert result.action_items[0].action_url == f"/student/assessments/{attempt_id}/take"

    @pytest.mark.asyncio
    async def test_get_dashboard_when_has_study_plans_creates_action_items(self):
        """Active study plans should create action items."""
        student = _make_student()
        class_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query
        enrollment = _make_enrollment_row(class_id=class_id)
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery/topics queries return empty
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = []
        topics_mock = MagicMock()
        topics_mock.all.return_value = []
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Assessments query returns empty
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = []

        # Study plans query returns active plan
        plan_row = _make_mock_row(
            id=plan_id,
            class_id=class_id,
            class_name="Mathematics 8A",
            subject_name="Mathematics",
        )
        plans_mock = MagicMock()
        plans_mock.all.return_value = [plan_row]

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert len(result.action_items) == 1
        assert result.action_items[0].type == "study_plan_continue"
        assert result.action_items[0].action_url == f"/student/classes/{class_id}?tab=study-plan"

    @pytest.mark.asyncio
    async def test_get_dashboard_sorts_action_items_by_priority(self):
        """Action items should be sorted by priority."""
        student = _make_student()
        class_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query
        enrollment = _make_enrollment_row(class_id=class_id)
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment]

        # Mastery/topics queries return empty
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = []
        topics_mock = MagicMock()
        topics_mock.all.return_value = []
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Assessments query returns assessment (priority 1)
        assessment_row = _make_mock_row(
            id=uuid.uuid4(),
            deadline=None,
            class_id=class_id,
            title="Assessment",
            attempt_id=None,
            class_name="Math 8A",
            subject_name="Mathematics",
        )
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = [assessment_row]

        # Study plans query returns plan (priority 2)
        plan_row = _make_mock_row(
            id=uuid.uuid4(),
            class_id=class_id,
            class_name="Math 8A",
            subject_name="Mathematics",
        )
        plans_mock = MagicMock()
        plans_mock.all.return_value = [plan_row]

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        # Both action items present, assessment (priority 1) should come first
        assert len(result.action_items) == 2
        assert result.action_items[0].type == "assessment_due"
        assert result.action_items[1].type == "study_plan_continue"

    @pytest.mark.asyncio
    async def test_get_dashboard_with_multiple_classes(self):
        """Student with multiple classes should get all class summaries."""
        student = _make_student()
        class_id_1 = uuid.uuid4()
        class_id_2 = uuid.uuid4()
        mock_db = AsyncMock()

        # Profile query
        profile_mock = MagicMock()
        profile_mock.one_or_none.return_value = _make_profile_result()

        # Enrollment query returns two classes
        enrollment_1 = _make_enrollment_row(
            class_id=class_id_1,
            class_name="Mathematics 8A",
            subject_name="Mathematics",
        )
        enrollment_2 = _make_enrollment_row(
            class_id=class_id_2,
            class_name="Science 8A",
            subject_name="Integrated Science",
        )
        enrollments_mock = MagicMock()
        enrollments_mock.all.return_value = [enrollment_1, enrollment_2]

        # Mastery query returns different scores for each class
        mastery_row_1 = _make_mock_row(class_id=class_id_1, avg_mastery=0.85)
        mastery_row_2 = _make_mock_row(class_id=class_id_2, avg_mastery=0.45)
        mastery_mock = MagicMock()
        mastery_mock.all.return_value = [mastery_row_1, mastery_row_2]

        # Topics queries
        topics_mock = MagicMock()
        topics_mock.all.return_value = []
        assessed_mock = MagicMock()
        assessed_mock.all.return_value = []

        # Action items queries
        assessments_mock = MagicMock()
        assessments_mock.all.return_value = []
        plans_mock = MagicMock()
        plans_mock.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                profile_mock,
                enrollments_mock,
                mastery_mock,
                topics_mock,
                assessed_mock,
                assessments_mock,
                plans_mock,
            ]
        )

        service = StudentDashboardService(mock_db)
        result = await service.get_dashboard(student)

        assert len(result.classes) == 2
        # Find each class and verify its mastery
        math_class = next(c for c in result.classes if c.class_name == "Mathematics 8A")
        science_class = next(c for c in result.classes if c.class_name == "Science 8A")
        assert math_class.mastery_score == 0.85
        assert math_class.mastery_label == "Strong"
        assert science_class.mastery_score == 0.45
        assert science_class.mastery_label == "Developing"
