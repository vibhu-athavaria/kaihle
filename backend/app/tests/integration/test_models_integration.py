"""Integration tests for SQLAlchemy models.

These tests verify that models can be written to and read from the database,
and that constraints are properly enforced.
"""

import random
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, StudentAttempt
from app.models.billing import (
    SchoolSubscription,
    SubscriptionPlan,
)
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.models.gap import GapState
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment, School
from app.models.study_plan import StudyPlan
from app.models.user import (
    AuthToken,
    AuthTokenType,
    OnboardingStatus,
    ParentStudent,
    StudentProfile,
    TeacherProfile,
    User,
    UserRole,
)


class TestModelCRUD:
    """Test that all models can be created and read from the database."""

    async def test_school_crud(self, db_session: AsyncSession) -> None:
        """Test School model can be written and read."""
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-school-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
        await db_session.commit()

        result = await db_session.execute(select(School).where(School.id == school.id))
        fetched = result.scalar_one()
        assert fetched.name == "Test School"

    async def test_user_crud(self, db_session: AsyncSession, test_school: School) -> None:
        """Test User model can be written and read."""
        user = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
            role=UserRole.STUDENT,
        )
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        fetched = result.scalar_one()
        assert fetched.email == user.email
        assert fetched.role == UserRole.STUDENT

    async def test_student_profile_crud(self, db_session: AsyncSession, test_user: User) -> None:
        """Test StudentProfile model can be written and read."""
        profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=test_user.id,
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )
        db_session.add(profile)
        await db_session.commit()

        result = await db_session.execute(select(StudentProfile).where(StudentProfile.id == profile.id))
        fetched = result.scalar_one()
        assert fetched.onboarding_diagnostic_status == OnboardingStatus.PENDING

    async def test_teacher_profile_crud(self, db_session: AsyncSession, test_teacher: User) -> None:
        """Test TeacherProfile model can be written and read."""
        profile = TeacherProfile(
            id=uuid.uuid4(),
            user_id=test_teacher.id,
            bio="Experienced math teacher",
            experience_years=5,
        )
        db_session.add(profile)
        await db_session.commit()

        result = await db_session.execute(select(TeacherProfile).where(TeacherProfile.id == profile.id))
        fetched = result.scalar_one()
        assert fetched.bio == "Experienced math teacher"

    async def test_auth_token_crud(self, db_session: AsyncSession, test_user: User) -> None:
        """Test AuthToken model can be written and read."""
        token = AuthToken(
            id=uuid.uuid4(),
            user_id=test_user.id,
            token_hash=f"hash-{uuid.uuid4().hex}",
            type=AuthTokenType.REFRESH,
            expires_at=datetime.utcnow(),
        )
        db_session.add(token)
        await db_session.commit()

        result = await db_session.execute(select(AuthToken).where(AuthToken.id == token.id))
        fetched = result.scalar_one()
        assert fetched.type == AuthTokenType.REFRESH

    async def test_parent_student_crud(self, db_session: AsyncSession, test_school: School) -> None:
        """Test ParentStudent model can be written and read."""
        parent = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=f"parent-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Parent",
            last_name="Test",
            role=UserRole.PARENT,
        )
        student = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=f"student-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Student",
            last_name="Test",
            role=UserRole.STUDENT,
        )
        db_session.add_all([parent, student])
        await db_session.commit()

        link = ParentStudent(
            parent_id=parent.id,
            student_id=student.id,
        )
        db_session.add(link)
        await db_session.commit()

        result = await db_session.execute(select(ParentStudent).where(ParentStudent.parent_id == parent.id))
        fetched = result.scalar_one()
        assert fetched.student_id == student.id

    async def test_learning_profile_crud(self, db_session: AsyncSession, test_user: User, test_school: School) -> None:
        """Test StudentLearningProfile model can be written and read."""
        profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=test_user.id,
            school_id=test_school.id,
            modality_scores={"visual": 0.8, "auditory": 0.3},
            work_style={"prefers_solo": True},
            interests=["football", "music"],
        )
        db_session.add(profile)
        await db_session.commit()

        result = await db_session.execute(select(StudentLearningProfile).where(StudentLearningProfile.id == profile.id))
        fetched = result.scalar_one()
        assert fetched.modality_scores == {"visual": 0.8, "auditory": 0.3}
        assert fetched.interests == ["football", "music"]

    async def test_curriculum_crud(self, db_session: AsyncSession) -> None:
        """Test Curriculum model can be written and read."""
        curriculum = Curriculum(
            id=uuid.uuid4(),
            name="Cambridge Lower Secondary",
            code=f"cambridge-{uuid.uuid4().hex[:6]}",
            description="International curriculum",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.commit()

        result = await db_session.execute(select(Curriculum).where(Curriculum.id == curriculum.id))
        fetched = result.scalar_one()
        assert fetched.code == curriculum.code

    async def test_subject_crud(self, db_session: AsyncSession) -> None:
        """Test Subject model can be written and read."""
        subject = Subject(
            id=uuid.uuid4(),
            name="Mathematics",
            code=f"MATH-{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.commit()

        result = await db_session.execute(select(Subject).where(Subject.id == subject.id))
        fetched = result.scalar_one()
        assert fetched.name == "Mathematics"

    async def test_grade_crud(self, db_session: AsyncSession) -> None:
        """Test Grade model can be written and read."""
        # Use a unique level to avoid constraint violations
        level = random.randint(1, 13)
        grade = Grade(
            id=uuid.uuid4(),
            name=f"Grade {level}",
            level=level,
            is_active=True,
        )
        db_session.add(grade)
        await db_session.commit()

        result = await db_session.execute(select(Grade).where(Grade.id == grade.id))
        fetched = result.scalar_one()
        assert fetched.level == level

    async def test_topic_crud(self, db_session: AsyncSession) -> None:
        """Test Topic model can be written and read."""
        topic = Topic(
            id=uuid.uuid4(),
            name="Algebra",
            canonical_code=f"ALG-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(topic)
        await db_session.commit()

        result = await db_session.execute(select(Topic).where(Topic.id == topic.id))
        fetched = result.scalar_one()
        assert fetched.name == "Algebra"

    async def test_curriculum_topic_crud(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        """Test CurriculumTopic model can be written and read."""
        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=test_curriculum.id,
            subject_id=test_subject.id,
            grade_id=test_grade.id,
            topic_id=test_topic.id,
            sequence_order=1,
            is_required=True,
        )
        db_session.add(ct)
        await db_session.commit()

        result = await db_session.execute(select(CurriculumTopic).where(CurriculumTopic.id == ct.id))
        fetched = result.scalar_one()
        assert fetched.sequence_order == 1

    async def test_subtopic_crud(self, db_session: AsyncSession, test_curriculum: Curriculum) -> None:
        """Test Subtopic model can be written and read."""
        # First need a curriculum_topic
        subject = Subject(
            id=uuid.uuid4(),
            name="Math",
            code=f"M{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.commit()

        level = random.randint(1, 13)
        grade = Grade(
            id=uuid.uuid4(),
            name=f"Grade {level}",
            level=level,
            is_active=True,
        )
        db_session.add(grade)
        await db_session.commit()

        topic = Topic(
            id=uuid.uuid4(),
            name="Algebra",
            canonical_code=f"ALG-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(topic)
        await db_session.commit()

        cs = CurriculumSubject(
            curriculum_id=test_curriculum.id,
            subject_id=subject.id,
            is_core=True,
        )
        db_session.add(cs)
        await db_session.commit()

        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=test_curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
        )
        db_session.add(ct)
        await db_session.commit()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name="Linear Equations",
            learning_objective="Solve linear equations",
            sequence_order=1,
        )
        db_session.add(subtopic)
        await db_session.commit()

        result = await db_session.execute(select(Subtopic).where(Subtopic.id == subtopic.id))
        fetched = result.scalar_one()
        assert fetched.name == "Linear Equations"

    async def test_class_crud(
        self,
        db_session: AsyncSession,
        test_school: School,
        test_grade: Grade,
        test_subject: Subject,
        test_curriculum: Curriculum,
        test_teacher: User,
    ) -> None:
        """Test Class model can be written and read."""
        class_ = Class(
            id=uuid.uuid4(),
            school_id=test_school.id,
            grade_id=test_grade.id,
            subject_id=test_subject.id,
            curriculum_id=test_curriculum.id,
            teacher_id=test_teacher.id,
            name="Grade 7 Math A",
            academic_year="2026",
        )
        db_session.add(class_)
        await db_session.commit()

        result = await db_session.execute(select(Class).where(Class.id == class_.id))
        fetched = result.scalar_one()
        assert fetched.name == "Grade 7 Math A"

    async def test_class_enrollment_crud(self, db_session: AsyncSession, test_class: Class, test_user: User) -> None:
        """Test ClassEnrollment model can be written and read."""
        enrollment = ClassEnrollment(
            class_id=test_class.id,
            student_id=test_user.id,
            is_active=True,
        )
        db_session.add(enrollment)
        await db_session.commit()

        result = await db_session.execute(select(ClassEnrollment).where(ClassEnrollment.class_id == test_class.id))
        fetched = result.scalar_one()
        assert fetched.student_id == test_user.id

    async def test_assessment_crud(self, db_session: AsyncSession, test_class: Class, test_teacher: User) -> None:
        """Test Assessment model can be written and read."""
        assessment = Assessment(
            id=uuid.uuid4(),
            class_id=test_class.id,
            created_by=test_teacher.id,
            title="Math Diagnostic",
            assessment_type="DIAGNOSTIC",
            is_system_generated=False,
            config={"num_questions": 10},
        )
        db_session.add(assessment)
        await db_session.commit()

        result = await db_session.execute(select(Assessment).where(Assessment.id == assessment.id))
        fetched = result.scalar_one()
        assert fetched.title == "Math Diagnostic"
        assert fetched.is_system_generated is False

    async def test_student_attempt_crud(
        self,
        db_session: AsyncSession,
        test_assessment: Assessment,
        test_user: User,
    ) -> None:
        """Test StudentAttempt model can be written and read."""
        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=test_assessment.id,
            student_id=test_user.id,
            total_questions=10,
            questions_answered=0,
        )
        db_session.add(attempt)
        await db_session.commit()

        result = await db_session.execute(select(StudentAttempt).where(StudentAttempt.id == attempt.id))
        fetched = result.scalar_one()
        assert fetched.total_questions == 10

    async def test_gap_state_crud(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_class: Class,
    ) -> None:
        """Test GapState model can be written and read."""
        # Need a subtopic first
        subject = Subject(
            id=uuid.uuid4(),
            name="Math",
            code=f"M{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.commit()

        level = random.randint(1, 13)
        grade = Grade(
            id=uuid.uuid4(),
            name=f"Grade {level}",
            level=level,
            is_active=True,
        )
        db_session.add(grade)
        await db_session.commit()

        topic = Topic(
            id=uuid.uuid4(),
            name="Algebra",
            canonical_code=f"ALG-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(topic)
        await db_session.commit()

        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Test Curriculum {uuid.uuid4().hex[:8]}",
            code=f"TC-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.commit()

        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
        )
        db_session.add(ct)
        await db_session.commit()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name="Linear Equations",
            learning_objective="Solve linear equations",
        )
        db_session.add(subtopic)
        await db_session.commit()

        gap = GapState(
            id=uuid.uuid4(),
            student_id=test_user.id,
            subtopic_id=subtopic.id,
            class_id=test_class.id,
            mastery_score=0.5,
            confidence=0.3,
        )
        db_session.add(gap)
        await db_session.commit()

        result = await db_session.execute(select(GapState).where(GapState.id == gap.id))
        fetched = result.scalar_one()
        assert fetched.mastery_score == 0.5

    async def test_study_plan_crud(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_class: Class,
        test_teacher: User,
    ) -> None:
        """Test StudyPlan model can be written and read."""
        # Need a subtopic first
        subject = Subject(
            id=uuid.uuid4(),
            name="Math",
            code=f"M{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.commit()

        level = random.randint(1, 13)
        grade = Grade(
            id=uuid.uuid4(),
            name=f"Grade {level}",
            level=level,
            is_active=True,
        )
        db_session.add(grade)
        await db_session.commit()

        topic = Topic(
            id=uuid.uuid4(),
            name="Algebra",
            canonical_code=f"ALG-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(topic)
        await db_session.commit()

        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Test Curriculum {uuid.uuid4().hex[:8]}",
            code=f"TC-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.commit()

        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
        )
        db_session.add(ct)
        await db_session.commit()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name="Linear Equations",
            learning_objective="Solve linear equations",
        )
        db_session.add(subtopic)
        await db_session.commit()

        plan = StudyPlan(
            id=uuid.uuid4(),
            student_id=test_user.id,
            subtopic_id=subtopic.id,
            class_id=test_class.id,
            assigned_by=test_teacher.id,
            assigned_at=datetime.utcnow(),
        )
        db_session.add(plan)
        await db_session.commit()

        result = await db_session.execute(select(StudyPlan).where(StudyPlan.id == plan.id))
        fetched = result.scalar_one()
        assert fetched.student_id == test_user.id

    async def test_subscription_plan_crud(self, db_session: AsyncSession) -> None:
        """Test SubscriptionPlan model can be written and read."""
        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            tier="STARTER",
            name="Starter Plan",
            price_per_student_annual=75.00,
            max_students=100,
            max_curricula=1,
            features={"parent_portal": True},
        )
        db_session.add(plan)
        await db_session.commit()

        result = await db_session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan.id))
        fetched = result.scalar_one()
        assert fetched.tier == "STARTER"

    async def test_school_subscription_crud(self, db_session: AsyncSession, test_school: School) -> None:
        """Test SchoolSubscription model can be written and read."""
        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            tier="STARTER",
            name="Starter Plan",
            price_per_student_annual=75.00,
            max_students=100,
        )
        db_session.add(plan)
        await db_session.commit()

        subscription = SchoolSubscription(
            id=uuid.uuid4(),
            school_id=test_school.id,
            plan_id=plan.id,
            student_count=50,
            total_amount=3750.00,
            start_date=datetime.utcnow(),
        )
        db_session.add(subscription)
        await db_session.commit()

        result = await db_session.execute(select(SchoolSubscription).where(SchoolSubscription.id == subscription.id))
        fetched = result.scalar_one()
        assert fetched.student_count == 50


class TestConstraints:
    """Test database constraints are properly enforced."""

    async def test_learning_profile_unique_student_id(
        self, db_session: AsyncSession, test_user: User, test_school: School
    ) -> None:
        """Test that StudentLearningProfile unique constraint on student_id raises IntegrityError."""
        profile1 = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=test_user.id,
            school_id=test_school.id,
            modality_scores={"visual": 0.8},
        )
        db_session.add(profile1)
        await db_session.commit()

        # Attempt to insert duplicate
        profile2 = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=test_user.id,  # Same student_id
            school_id=test_school.id,
            modality_scores={"auditory": 0.5},
        )
        db_session.add(profile2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()
