"""Integration tests for SQLAlchemy models.

These tests verify that models can be written to and read from the database,
and that constraints are properly enforced.
"""

import random
import uuid
from datetime import datetime

import pytest
from sqlalchemy import delete, select
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
    LearningObjective,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from app.models.gap import GapState
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment, School
from app.models.study_plan import StudyPlan
from app.models.user import (
    AuthToken,
    AuthTokenType,
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
        """Test StudentProfile model can be written and read.

        Note: onboarding_diagnostic_status moved to class_enrollments in v2.1.
        """
        profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=test_user.id,
        )
        db_session.add(profile)
        await db_session.commit()

        result = await db_session.execute(select(StudentProfile).where(StudentProfile.id == profile.id))
        fetched = result.scalar_one()
        # StudentProfile no longer has onboarding_diagnostic_status (now in class_enrollments)
        assert fetched.user_id == test_user.id

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
            academic_year="2025-2026",
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

    async def test_assessment_crud(
        self, db_session: AsyncSession, test_class: Class, test_teacher: User, test_school: School
    ) -> None:
        """Test Assessment model can be written and read."""
        assessment = Assessment(
            id=uuid.uuid4(),
            school_id=test_school.id,
            class_id=test_class.id,
            created_by=test_teacher.id,
            title="Math Diagnostic",
            assessment_type="DIAGNOSTIC",
        )
        db_session.add(assessment)
        await db_session.commit()

        result = await db_session.execute(select(Assessment).where(Assessment.id == assessment.id))
        fetched = result.scalar_one()
        assert fetched.title == "Math Diagnostic"
        assert fetched.created_by is not None

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
        test_grade: Grade,
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

        # Use existing test_grade fixture to avoid unique constraint violations
        grade = test_grade

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
        test_grade: Grade,
    ) -> None:
        """Test StudyPlan model can be written and read."""
        # Use existing test_grade fixture to avoid unique constraint violations
        subject = Subject(
            id=uuid.uuid4(),
            name="Math",
            code=f"M{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
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
            grade_id=test_grade.id,
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
            end_date=datetime.utcnow(),
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


@pytest.mark.asyncio
class TestLearningObjectiveLayer:
    """Integration tests for the LO layer introduced by the v2 curriculum remap.

    These assert database-enforced behaviour (uniqueness, RESTRICT, CASCADE, CHECK)
    that model-level unit tests cannot prove.
    """

    async def _make_subtopic(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        topic: Topic,
        name: str = "Test Subtopic",
    ) -> Subtopic:
        # curriculum_topics is UNIQUE on (curriculum, subject, grade, topic), so reuse
        # the pivot row — several subtopics legitimately hang off the same placement.
        existing = await db_session.execute(
            select(CurriculumTopic).where(
                CurriculumTopic.curriculum_id == test_curriculum.id,
                CurriculumTopic.subject_id == test_subject.id,
                CurriculumTopic.grade_id == test_grade.id,
                CurriculumTopic.topic_id == topic.id,
            )
        )
        ct = existing.scalar_one_or_none()
        if ct is None:
            ct = CurriculumTopic(
                id=uuid.uuid4(),
                curriculum_id=test_curriculum.id,
                subject_id=test_subject.id,
                grade_id=test_grade.id,
                topic_id=topic.id,
                sequence_order=1,
                is_required=True,
            )
            db_session.add(ct)
            await db_session.flush()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name=name,
            canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
            learning_objective=f"Objective for {name}.",
            is_active=True,
        )
        db_session.add(subtopic)
        await db_session.commit()
        return subtopic

    @staticmethod
    def _make_lo(topic_id: uuid.UUID, code: str | None = None) -> LearningObjective:
        return LearningObjective(
            id=uuid.uuid4(),
            canonical_code=code or f"MATH-LO-{uuid.uuid4().hex[:8]}",
            name="Using negative numbers",
            learning_objective="Order and use negative numbers in practical contexts.",
            topic_id=topic_id,
            bloom_taxonomy_level="Apply",
            is_active=True,
        )

    async def test_learning_objective_when_persisted_then_reads_back(
        self, db_session: AsyncSession, test_topic: Topic
    ) -> None:
        lo = self._make_lo(test_topic.id)
        db_session.add(lo)
        await db_session.commit()

        result = await db_session.execute(select(LearningObjective).where(LearningObjective.id == lo.id))
        fetched = result.scalar_one()
        assert fetched.topic_id == test_topic.id
        assert fetched.is_active is True
        assert fetched.embedding is None

    async def test_canonical_code_when_duplicated_then_raises_integrity_error(
        self, db_session: AsyncSession, test_topic: Topic
    ) -> None:
        code = f"MATH-DUP-{uuid.uuid4().hex[:8]}"
        db_session.add(self._make_lo(test_topic.id, code))
        await db_session.commit()

        db_session.add(self._make_lo(test_topic.id, code))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_topic_when_deleted_with_objectives_then_restrict_blocks_delete(
        self, db_session: AsyncSession, test_topic: Topic
    ) -> None:
        """Topics are shared across grades/curricula — the wipe must never cascade them away."""
        db_session.add(self._make_lo(test_topic.id))
        await db_session.commit()

        # The FK is checked at statement time, not at COMMIT — so the raise must
        # wrap the DELETE itself.
        with pytest.raises(IntegrityError):
            await db_session.execute(delete(Topic).where(Topic.id == test_topic.id))
        await db_session.rollback()

    async def test_bridge_when_one_subtopic_has_two_objectives_then_both_persist(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        subtopic = await self._make_subtopic(db_session, test_curriculum, test_subject, test_grade, test_topic)
        lo_a, lo_b = self._make_lo(test_topic.id), self._make_lo(test_topic.id)
        db_session.add_all([lo_a, lo_b])
        await db_session.flush()
        db_session.add_all(
            [
                SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=lo_a.id),
                SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=lo_b.id),
            ]
        )
        await db_session.commit()

        result = await db_session.execute(select(SubtopicObjective).where(SubtopicObjective.subtopic_id == subtopic.id))
        assert {r.learning_objective_id for r in result.scalars()} == {lo_a.id, lo_b.id}

    async def test_bridge_when_one_objective_shared_by_two_subtopics_then_both_persist(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        """This is the case that makes the bank curriculum-agnostic: the same concept
        taught at two placements resolves to a single objective."""
        st_a = await self._make_subtopic(
            db_session, test_curriculum, test_subject, test_grade, test_topic, "Ordering decimals G6"
        )
        st_b = await self._make_subtopic(
            db_session, test_curriculum, test_subject, test_grade, test_topic, "Ordering decimals G7"
        )
        lo = self._make_lo(test_topic.id)
        db_session.add(lo)
        await db_session.flush()
        db_session.add_all(
            [
                SubtopicObjective(subtopic_id=st_a.id, learning_objective_id=lo.id),
                SubtopicObjective(subtopic_id=st_b.id, learning_objective_id=lo.id),
            ]
        )
        await db_session.commit()

        result = await db_session.execute(
            select(SubtopicObjective).where(SubtopicObjective.learning_objective_id == lo.id)
        )
        assert {r.subtopic_id for r in result.scalars()} == {st_a.id, st_b.id}

    async def test_subtopic_when_deleted_then_bridge_cascades_but_objective_survives(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        """Exactly the scoped-wipe path: placement is removed, the concept is kept."""
        subtopic = await self._make_subtopic(db_session, test_curriculum, test_subject, test_grade, test_topic)
        lo = self._make_lo(test_topic.id)
        db_session.add(lo)
        await db_session.flush()
        db_session.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=lo.id))
        await db_session.commit()

        await db_session.execute(delete(Subtopic).where(Subtopic.id == subtopic.id))
        await db_session.commit()

        bridge = await db_session.execute(
            select(SubtopicObjective).where(SubtopicObjective.learning_objective_id == lo.id)
        )
        assert bridge.scalars().all() == []
        surviving = await db_session.execute(select(LearningObjective).where(LearningObjective.id == lo.id))
        assert surviving.scalar_one().id == lo.id

    async def test_objective_when_deleted_while_bridged_then_restrict_blocks_delete(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        subtopic = await self._make_subtopic(db_session, test_curriculum, test_subject, test_grade, test_topic)
        lo = self._make_lo(test_topic.id)
        db_session.add(lo)
        await db_session.flush()
        db_session.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=lo.id))
        await db_session.commit()

        with pytest.raises(IntegrityError):
            await db_session.execute(delete(LearningObjective).where(LearningObjective.id == lo.id))
        await db_session.rollback()

    async def test_subtopic_tier_when_not_specified_then_defaults_to_both(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        subtopic = await self._make_subtopic(db_session, test_curriculum, test_subject, test_grade, test_topic)
        await db_session.refresh(subtopic)
        assert subtopic.tier == "BOTH"

    async def test_subtopic_tier_when_given_invalid_value_then_check_constraint_rejects(
        self,
        db_session: AsyncSession,
        test_curriculum: Curriculum,
        test_subject: Subject,
        test_grade: Grade,
        test_topic: Topic,
    ) -> None:
        subtopic = await self._make_subtopic(db_session, test_curriculum, test_subject, test_grade, test_topic)
        subtopic.tier = "PREMIUM"
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_question_when_bound_to_objective_only_then_null_subtopic_is_allowed(
        self, db_session: AsyncSession, test_topic: Topic
    ) -> None:
        """The post-remap steady state: selection runs off the LO, not the subtopic."""
        lo = self._make_lo(test_topic.id)
        db_session.add(lo)
        await db_session.flush()

        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=None,
            learning_objective_id=lo.id,
            question_text="What is -3 + 5?",
            question_type="MCQ",
            options=[{"key": "A", "text": "2"}, {"key": "B", "text": "-8"}],
            correct_answer="A",
            canonical_form="-3+5",
            problem_signature={"op": "add"},
            difficulty_level=2.0,
            source="bank",
            is_active=True,
        )
        db_session.add(question)
        await db_session.commit()

        result = await db_session.execute(select(QuestionBank).where(QuestionBank.id == question.id))
        fetched = result.scalar_one()
        assert fetched.subtopic_id is None
        assert fetched.learning_objective_id == lo.id
