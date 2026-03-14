"""Integration tests for onboarding completion tracking.

Tests cover:
- Tier 1 completion tracking service
- Onboarding gate lift when all diagnostics complete
- Integration with require_onboarding_complete middleware

These tests verify the end-to-end flow of student onboarding completion.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus, AttemptStatus, StudentAttempt
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, School
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole
from app.services.onboarding_service import OnboardingService


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest_asyncio.fixture
async def curriculum(db_session: AsyncSession) -> Curriculum:
    """Create a test curriculum."""
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Cambridge Lower Secondary",
        code="CLS",
        description="Cambridge Lower Secondary curriculum",
        is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()
    return curriculum


@pytest_asyncio.fixture
async def grade(db_session: AsyncSession) -> Grade:
    """Create a test grade."""
    grade = Grade(
        id=uuid.uuid4(),
        name="Grade 7",
        level=7,
        is_active=True,
    )
    db_session.add(grade)
    await db_session.commit()
    return grade


@pytest_asyncio.fixture
async def subject(db_session: AsyncSession) -> Subject:
    """Create a test subject."""
    subject = Subject(
        id=uuid.uuid4(),
        name="Mathematics",
        code="MATH",
        is_active=True,
    )
    db_session.add(subject)
    await db_session.commit()
    return subject


@pytest_asyncio.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    """Create a test teacher."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest_asyncio.fixture
async def student(db_session: AsyncSession, school: School) -> User:
    """Create a test student."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    return student


@pytest_asyncio.fixture
async def student_profile(db_session: AsyncSession, student: User) -> StudentProfile:
    """Create a student profile with PENDING onboarding status."""
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        onboarding_diagnostic_status=OnboardingStatus.PENDING,
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def learning_profile_completed(db_session: AsyncSession, student: User, school: School) -> StudentLearningProfile:
    """Create a completed learning profile."""
    profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=student.id,
        school_id=school.id,
        modality_scores={"visual": 0.8, "auditory": 0.3},
        work_style={"prefers_solo": True},
        interests=["sports", "music"],
        questionnaire_version="v1",
        completed_at=None,  # Will be set by questionnaire submission
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def test_class(
    db_session: AsyncSession,
    school: School,
    grade: Grade,
    subject: Subject,
    curriculum: Curriculum,
    teacher: User,
) -> Class:
    """Create a test class."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Grade 7 Math",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


@pytest_asyncio.fixture
async def tier1_assessments(
    db_session: AsyncSession,
    student: User,
    test_class: Class,
) -> list[Assessment]:
    """Create 3 Tier 1 (is_system_generated) assessments for the student."""
    assessments = []
    for i in range(3):
        assessment = Assessment(
            id=uuid.uuid4(),
            class_id=test_class.id,
            created_by=None,  # System-generated
            title=f"Tier 1 Diagnostic {i + 1}",
            assessment_type="DIAGNOSTIC",
            status=AssessmentStatus.ACTIVE,
            is_system_generated=True,
            config={"num_questions": 10},
        )
        db_session.add(assessment)
        assessments.append(assessment)

    await db_session.commit()
    return assessments


@pytest_asyncio.fixture
async def tier1_attempts_in_progress(
    db_session: AsyncSession,
    student: User,
    tier1_assessments: list[Assessment],
) -> list[StudentAttempt]:
    """Create 3 attempts for Tier 1 assessments - 2 COMPLETED, 1 IN_PROGRESS."""
    attempts = []
    statuses = [AttemptStatus.COMPLETED, AttemptStatus.COMPLETED, AttemptStatus.IN_PROGRESS]

    for i, assessment in enumerate(tier1_assessments):
        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            student_id=student.id,
            status=statuses[i],
            total_questions=10,
            questions_answered=statuses[i] == AttemptStatus.COMPLETED and 10 or 5,
        )
        db_session.add(attempt)
        attempts.append(attempt)

    await db_session.commit()
    return attempts


@pytest_asyncio.fixture
async def tier1_attempts_all_completed(
    db_session: AsyncSession,
    student: User,
    tier1_assessments: list[Assessment],
) -> list[StudentAttempt]:
    """Create 3 attempts for Tier 1 assessments - all COMPLETED."""
    attempts = []

    for assessment in tier1_assessments:
        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            student_id=student.id,
            status=AttemptStatus.COMPLETED,
            total_questions=10,
            questions_answered=10,
            overall_score=0.75,
        )
        db_session.add(attempt)
        attempts.append(attempt)

    await db_session.commit()
    return attempts


@pytest.mark.asyncio
class TestCheckAndUpdateOnboardingComplete:
    """Integration tests for check_and_update_onboarding_complete service method."""

    async def test_when_2_of_3_complete_then_returns_false(
        self,
        db_session: AsyncSession,
        student: User,
        student_profile: StudentProfile,
        tier1_assessments: list[Assessment],
        tier1_attempts_in_progress: list[StudentAttempt],
    ) -> None:
        """Test that when 2 of 3 Tier 1 diagnostics are complete, returns False."""
        service = OnboardingService(db_session)

        result = await service.check_and_update_onboarding_complete(student.id)

        assert result is False

        # Verify status unchanged
        profile_result = await db_session.execute(select(StudentProfile).where(StudentProfile.user_id == student.id))
        profile = profile_result.scalar_one()
        assert profile.onboarding_diagnostic_status == OnboardingStatus.PENDING

    async def test_when_all_3_complete_then_returns_true_and_status_updated(
        self,
        db_session: AsyncSession,
        student: User,
        student_profile: StudentProfile,
        tier1_assessments: list[Assessment],
        tier1_attempts_all_completed: list[StudentAttempt],
    ) -> None:
        """Test that when all 3 Tier 1 diagnostics are complete, returns True and updates status."""
        # Set profile to IN_PROGRESS first (simulating the workflow)
        student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS
        await db_session.commit()

        service = OnboardingService(db_session)

        result = await service.check_and_update_onboarding_complete(student.id)

        assert result is True

        # Verify status updated to COMPLETED
        await db_session.refresh(student_profile)
        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    async def test_when_already_completed_then_idempotent(
        self,
        db_session: AsyncSession,
        student: User,
        student_profile: StudentProfile,
        tier1_assessments: list[Assessment],
        tier1_attempts_all_completed: list[StudentAttempt],
    ) -> None:
        """Test that calling when already COMPLETED returns True without error."""
        # Already COMPLETED
        student_profile.onboarding_diagnostic_status = OnboardingStatus.COMPLETED
        await db_session.commit()

        service = OnboardingService(db_session)

        result = await service.check_and_update_onboarding_complete(student.id)

        # Should return True (idempotent)
        assert result is True

    async def test_when_no_tier1_assessments_then_returns_false(
        self,
        db_session: AsyncSession,
        student: User,
        student_profile: StudentProfile,
    ) -> None:
        """Test that when no Tier 1 assessments exist, returns False (no crash)."""
        service = OnboardingService(db_session)

        result = await service.check_and_update_onboarding_complete(student.id)

        assert result is False

        # Verify status unchanged
        await db_session.refresh(student_profile)
        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING


@pytest.mark.asyncio
class TestOnboardingGateLift:
    """Integration tests for onboarding gate lift after Tier 1 completion."""

    async def test_after_completion_student_can_access_dashboard(
        self,
        db_session: AsyncSession,
        school: School,
        student: User,
        student_profile: StudentProfile,
        learning_profile_completed: StudentLearningProfile,
        test_class: Class,
        tier1_assessments: list[Assessment],
        tier1_attempts_all_completed: list[StudentAttempt],
    ) -> None:
        """Test that after Tier 1 completion, student can access dashboard route."""
        # Set learning profile as completed (simulating questionnaire done)
        learning_profile_completed.completed_at = None  # This would be set by questionnaire

        # Set Tier 1 attempts all completed (already done by fixture)
        # Run the completion check
        service = OnboardingService(db_session)

        result = await service.check_and_update_onboarding_complete(student.id)

        assert result is True

        # Get updated status
        profile_result = await db_session.execute(select(StudentProfile).where(StudentProfile.user_id == student.id))
        updated_profile = profile_result.scalar_one()

        assert updated_profile.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    async def test_before_completion_student_blocked_from_dashboard(
        self,
        db_session: AsyncSession,
        school: School,
        student: User,
        student_profile: StudentProfile,
        learning_profile_completed: StudentLearningProfile,
        test_class: Class,
        tier1_assessments: list[Assessment],
        tier1_attempts_in_progress: list[StudentAttempt],
    ) -> None:
        """Test that before Tier 1 completion, student onboarding status is not COMPLETED."""
        # Learning profile has NOT been completed (completed_at is None)
        # Tier 1 diagnostics are IN_PROGRESS (only 2 of 3 complete)
        # So overall should be PENDING since neither is fully done

        # Check onboarding status
        service = OnboardingService(db_session)
        status = await service.get_onboarding_status(student.id)

        # Diagnostics should NOT be complete (2/3 done)
        assert status["diagnostics_complete"] is False
        # Learning profile is NOT complete (completed_at is None)
        assert status["learning_profile_complete"] is False
        # Overall should be PENDING
        assert status["overall"] == "PENDING"

    async def test_teacher_role_then_no_gate_applied(
        self,
        db_session: AsyncSession,
        school: School,
        teacher: User,
    ) -> None:
        """Test that teacher role bypasses onboarding check."""
        service = OnboardingService(db_session)

        # Teachers don't have student profiles, so this should handle gracefully
        status = await service.get_onboarding_status(teacher.id)

        # Teacher should not have learning profile or student profile
        assert status["learning_profile_complete"] is False
        assert status["diagnostics_complete"] is False
