"""Unit tests for SQLAlchemy models."""

import uuid

from app.models.assessment import Assessment, AssessmentStatus
from app.models.onboarding import StudentLearningProfile
from app.models.school import ClassEnrollment
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole


class TestUser:
    """Tests for User model."""

    def test_user_model_has_check_constraint(self) -> None:
        """Test that User model has the school_id check constraint defined."""
        from sqlalchemy import Table

        table: Table = User.__table__  # type: ignore[assignment]
        constraints = table.constraints
        constraint_names = [c.name for c in constraints]
        assert "chk_user_school_id_required" in constraint_names

    def test_user_school_id_is_nullable(self) -> None:
        """Test that school_id column is nullable."""
        col = User.__table__.c.school_id
        assert col.nullable is True

    def test_kaihle_admin_role_can_have_null_school_id(self) -> None:
        """Test that KAIHLE_ADMIN role can be instantiated with None school_id."""
        user = User(
            email="admin@kaihle.com",
            hashed_password="hashed",
            role=UserRole.KAIHLE_ADMIN,
            school_id=None,
            first_name="Admin",
            last_name="User",
            is_active=True,
        )
        assert user.school_id is None
        assert user.role == UserRole.KAIHLE_ADMIN

    def test_teacher_can_have_school_id(self) -> None:
        """Test that TEACHER role can be instantiated with a school_id."""
        school_id = uuid.uuid4()
        user = User(
            email="teacher@test.com",
            hashed_password="hashed",
            role=UserRole.TEACHER,
            school_id=school_id,
            first_name="Teacher",
            last_name="User",
            is_active=True,
        )
        assert user.school_id == school_id
        assert user.role == UserRole.TEACHER


class TestStudentLearningProfile:
    """Tests for StudentLearningProfile model."""

    def test_instantiation_with_required_fields(self) -> None:
        """Test that StudentLearningProfile can be instantiated with required fields."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()

        profile = StudentLearningProfile(
            student_id=student_id,
            school_id=school_id,
            modality_scores={"visual": 0.8, "auditory": 0.3},
            work_style={"prefers_solo": True},
        )

        assert profile.student_id == student_id
        assert profile.school_id == school_id
        assert profile.modality_scores == {"visual": 0.8, "auditory": 0.3}
        assert profile.work_style == {"prefers_solo": True}
        assert profile.completed_at is None
        assert profile.interests is None

    def test_questionnaire_version_column_default(self) -> None:
        """Test that questionnaire_version column has correct server_default."""
        # Check column definition
        col = StudentLearningProfile.__table__.c.questionnaire_version
        assert col.default is not None
        assert col.default.arg == "v1"


class TestAssessment:
    """Tests for Assessment model."""

    def test_is_system_generated_column_default(self) -> None:
        """Test that is_system_generated column defaults to False at DB level."""
        col = Assessment.__table__.c.is_system_generated
        # The default should be the SQL false() construct
        assert col.default is not None

    def test_explicit_is_system_generated_true(self) -> None:
        """Test that is_system_generated can be set to True."""
        assessment = Assessment(
            class_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            title="Test Assessment",
            assessment_type="DIAGNOSTIC",
            is_system_generated=True,
        )

        assert assessment.is_system_generated is True

    def test_status_column_default(self) -> None:
        """Test that status column defaults to DRAFT."""
        col = Assessment.__table__.c.status
        assert col.default is not None
        assert col.default.arg == AssessmentStatus.DRAFT


class TestStudentProfile:
    """Tests for StudentProfile model."""

    def test_grade_id_nullable(self) -> None:
        """Test that grade_id is nullable."""
        col = StudentProfile.__table__.c.grade_id
        assert col.nullable is True


class TestClassEnrollment:
    """Tests for ClassEnrollment model (v2.1)."""

    def test_onboarding_status_column_has_server_default(self) -> None:
        """Test that onboarding_diagnostic_status column has server_default PENDING."""
        col = ClassEnrollment.__table__.c.onboarding_diagnostic_status
        assert col.server_default is not None
        assert col.server_default.arg == "PENDING"

    def test_explicit_onboarding_status(self) -> None:
        """Test that onboarding_diagnostic_status can be explicitly set."""
        enrollment = ClassEnrollment(
            class_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        assert enrollment.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    def test_column_is_not_nullable(self) -> None:
        """Test that onboarding_diagnostic_status is NOT NULL."""
        col = ClassEnrollment.__table__.c.onboarding_diagnostic_status
        assert col.nullable is False
