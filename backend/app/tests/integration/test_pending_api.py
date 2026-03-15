"""Integration tests for pending onboarding students endpoint.

Tests cover:
- GET /api/v1/onboarding/students/pending
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole


def auth_header(user: User) -> dict[str, str]:
    """Create auth header for user."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def kaihle_admin(db_session: AsyncSession, test_school: School) -> User:
    """Create a KaihleAdmin user.

    Note: KaihleAdmin technically should have no school_id but the model requires it,
    so we use a test school for fixture creation. The actual API endpoint handles
    KaihleAdmin without school_id filter.
    """
    admin = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def school_admin(db_session: AsyncSession, test_school: School) -> User:
    """Create a school admin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"school-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def teacher(db_session: AsyncSession, test_school: School) -> User:
    """Create a teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest.fixture
async def student_with_pending_onboarding(db_session: AsyncSession, test_school: School) -> User:
    """Create a student with pending onboarding (learning profile not complete)."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"pending-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Pending",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest.fixture
async def student_with_completed_onboarding(db_session: AsyncSession, test_school: School) -> User:
    """Create a student with completed onboarding (learning profile complete)."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"completed-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Completed",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest.fixture
async def class_with_pending_student(
    # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    test_school: School,
    teacher: User,
    student_with_pending_onboarding: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> Class:
    """Create a class with a pending student enrolled."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Test Class with Pending Student",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_pending_onboarding.id,
        is_active=True,
    )
    db_session.add(enrollment)
    await db_session.commit()

    return class_


@pytest.fixture
async def class_with_completed_student(
    # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    test_school: School,
    teacher: User,
    student_with_completed_onboarding: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> Class:
    """Create a class with a completed student enrolled."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Test Class with Completed Student",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_completed_onboarding.id,
        is_active=True,
    )
    db_session.add(enrollment)
    await db_session.commit()

    return class_


class TestGetPendingOnboardingStudents:
    """Tests for GET /api/v1/onboarding/students/pending."""

    @pytest.mark.asyncio
    async def test_pending_01_teacher_retrieves_pending_students_in_their_classes_returns_200(
        self,
        client: AsyncClient,
        teacher: User,
        class_with_pending_student: Class,
        student_with_pending_onboarding: User,
    ) -> None:
        """PENDING-01: Teacher retrieves pending students in their classes -> 200."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_pending_02_kaihle_admin_retrieves_all_pending_students_returns_200(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        student_with_pending_onboarding: User,
    ) -> None:
        """PENDING-02: KaihleAdmin retrieves all pending students -> 200."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_pending_03_teacher_with_no_students_returns_empty_list(
        self,
        client: AsyncClient,
        teacher: User,
        db_session: AsyncSession,
        test_school: School,
        test_grade: Grade,
        test_subject: Subject,
        test_curriculum: Curriculum,
    ) -> None:
        """PENDING-03: Teacher with no students -> 200, empty list."""
        # Create a class but don't enroll any students
        class_without_students = Class(
            id=uuid.uuid4(),
            school_id=test_school.id,
            grade_id=test_grade.id,
            subject_id=test_subject.id,
            curriculum_id=test_curriculum.id,
            teacher_id=teacher.id,
            name="Empty Class",
            academic_year="2026",
            is_active=True,
        )
        db_session.add(class_without_students)
        await db_session.commit()

        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_pending_04_pagination_limit_parameter_respects_limit(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        db_session: AsyncSession,
        test_school: School,
        test_grade: Grade,
        test_subject: Subject,
        test_curriculum: Curriculum,
    ) -> None:
        """PENDING-04: Pagination - limit parameter -> 200, respects limit."""
        # Create multiple pending students
        students = []
        for i in range(5):
            student = User(
                id=uuid.uuid4(),
                school_id=test_school.id,
                email=f"student-limit-{i}-{uuid.uuid4().hex[:8]}@example.com",
                first_name=f"Student{i}",
                last_name="Test",
                role=UserRole.STUDENT,
                is_active=True,
            )
            db_session.add(student)
            await db_session.commit()

            profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=student.id,
                is_learning_profile_complete=False,
            )
            db_session.add(profile)
            await db_session.commit()
            students.append(student)

        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=2",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_pending_05_pagination_offset_parameter_skips_offset(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        db_session: AsyncSession,
        test_school: School,
        test_grade: Grade,
        test_subject: Subject,
        test_curriculum: Curriculum,
    ) -> None:
        """PENDING-05: Pagination - offset parameter -> 200, skips offset."""
        # Create multiple pending students
        students = []
        for i in range(5):
            student = User(
                id=uuid.uuid4(),
                school_id=test_school.id,
                email=f"student-offset-{i}-{uuid.uuid4().hex[:8]}@example.com",
                first_name=f"Student{i}",
                last_name="Test",
                role=UserRole.STUDENT,
                is_active=True,
            )
            db_session.add(student)
            await db_session.commit()

            profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=student.id,
                is_learning_profile_complete=False,
            )
            db_session.add(profile)
            await db_session.commit()
            students.append(student)

        headers = auth_header(kaihle_admin)

        # Get first page
        response1 = await client.get(
            "/api/v1/onboarding/students/pending?limit=2&offset=0",
            headers=headers,
        )

        # Get second page
        response2 = await client.get(
            "/api/v1/onboarding/students/pending?limit=2&offset=2",
            headers=headers,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200
        data1 = response1.json()
        data2 = response2.json()
        assert isinstance(data1, list)
        assert isinstance(data2, list)
        # Both should have 2 items since we created 5 (5 - 2 offset = 3, but limit caps at 2)
        assert len(data1) == 2
        assert len(data2) == 2

    @pytest.mark.asyncio
    async def test_pending_06_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """PENDING-06: Unauthenticated -> 401."""
        response = await client.get("/api/v1/onboarding/students/pending")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pending_07_student_tries_to_access_returns_403(
        self,
        client: AsyncClient,
        student_with_pending_onboarding: User,
    ) -> None:
        """PENDING-07: Student tries to access -> 403."""
        headers = auth_header(student_with_pending_onboarding)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_pending_08_school_admin_tries_to_access_returns_403(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """PENDING-08: SCHOOL_ADMIN tries to access -> 403."""
        headers = auth_header(school_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_pending_09_invalid_limit_0_returns_422(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """PENDING-09: Invalid limit (0) -> 422."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=0",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pending_10_invalid_limit_over_100_returns_422(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """PENDING-10: Invalid limit (>100) -> 422."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=101",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pending_11_negative_offset_returns_422(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """PENDING-10: Negative offset -> 422."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending?offset=-1",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pending_12_teacher_does_not_see_completed_students(
        self,
        client: AsyncClient,
        teacher: User,
        class_with_pending_student: Class,
        class_with_completed_student: Class,
        student_with_completed_onboarding: User,
    ) -> None:
        """Teacher only sees pending students, not completed ones."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should only contain the pending student, not the completed one
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_pending_13_kaihle_admin_sees_all_pending_students(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        db_session: AsyncSession,
        test_school: School,
    ) -> None:
        """KaihleAdmin sees all pending students across all schools."""
        # Create pending student in first school
        student1 = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=f"kaihle-pending-1-{uuid.uuid4().hex[:8]}@example.com",
            first_name="KaihlePending1",
            last_name="Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student1)
        await db_session.commit()

        profile1 = StudentProfile(
            id=uuid.uuid4(),
            user_id=student1.id,
            is_learning_profile_complete=False,
        )
        db_session.add(profile1)
        await db_session.commit()

        # Create second school with pending student
        school2 = School(
            id=uuid.uuid4(),
            name="Second School",
            slug=f"second-school-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school2)
        await db_session.commit()

        student2 = User(
            id=uuid.uuid4(),
            school_id=school2.id,
            email=f"kaihle-pending-2-{uuid.uuid4().hex[:8]}@example.com",
            first_name="KaihlePending2",
            last_name="Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student2)
        await db_session.commit()

        profile2 = StudentProfile(
            id=uuid.uuid4(),
            user_id=student2.id,
            is_learning_profile_complete=False,
        )
        db_session.add(profile2)
        await db_session.commit()

        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should see both pending students from both schools
        assert len(data) == 2
