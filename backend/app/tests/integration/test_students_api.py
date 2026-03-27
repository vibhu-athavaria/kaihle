"""Integration tests for students API routes.

Tests cover:
- GET /api/v1/students/{student_id}/info - student info retrieval
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole
from app.tests.integration.conftest import make_auth_header


@pytest_asyncio.fixture
async def enrolled_student(
    db_session: AsyncSession,
    test_school: School,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
    test_teacher: User,
) -> User:
    """Create a test student with an active class enrollment."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"enrolled-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Enrolled",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
    )
    db_session.add(profile)
    await db_session.commit()

    # Create a class and enroll the student
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=test_teacher.id,
        name="Test Class for Student",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        id=uuid.uuid4(),
        class_id=class_.id,
        student_id=student.id,
        is_active=True,
    )
    db_session.add(enrollment)
    await db_session.commit()

    return student


@pytest_asyncio.fixture
async def unenrolled_student(
    db_session: AsyncSession,
    test_school: School,
) -> User:
    """Create a test student without any class enrollment."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"unenrolled-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Unenrolled",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


class TestGetStudentInfo:
    """Tests for GET /api/v1/students/{student_id}/info."""

    @pytest.mark.asyncio
    async def test_get_student_info_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
        enrolled_student: User,
    ) -> None:
        """Test that unauthenticated requests return 401."""
        response = await client.get(
            f"/api/v1/students/{enrolled_student.id}/info",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_student_info_when_student_views_own_enrolled_info_then_200(
        self,
        client: AsyncClient,
        enrolled_student: User,
        test_grade: Grade,
        test_curriculum: Curriculum,
    ) -> None:
        """Test that enrolled student can view their own info and gets grade/curriculum."""
        auth_headers = make_auth_header(enrolled_student)
        response = await client.get(
            f"/api/v1/students/{enrolled_student.id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "Enrolled"
        assert data["gradeName"] == test_grade.name
        assert data["curriculumName"] == test_curriculum.name
        assert data["classId"] is not None
        assert data["streakDays"] is None

    @pytest.mark.asyncio
    async def test_get_student_info_when_student_views_own_unenrolled_info_then_200(
        self,
        client: AsyncClient,
        unenrolled_student: User,
    ) -> None:
        """Test that unenrolled student can view their own info with empty strings."""
        auth_headers = make_auth_header(unenrolled_student)
        response = await client.get(
            f"/api/v1/students/{unenrolled_student.id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "Unenrolled"
        assert data["gradeName"] == ""
        assert data["curriculumName"] == ""
        assert data["classId"] is None
        assert data["streakDays"] is None

    @pytest.mark.asyncio
    async def test_get_student_info_when_student_views_other_student_then_403(
        self,
        client: AsyncClient,
        enrolled_student: User,
        unenrolled_student: User,
    ) -> None:
        """Test that student cannot view another student's info."""
        auth_headers = make_auth_header(enrolled_student)
        response = await client.get(
            f"/api/v1/students/{unenrolled_student.id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_student_info_when_teacher_views_student_in_own_school_then_200(
        self,
        client: AsyncClient,
        enrolled_student: User,
        test_teacher: User,
        test_grade: Grade,
        test_curriculum: Curriculum,
    ) -> None:
        """Test that teacher can view student info within their school."""
        auth_headers = make_auth_header(test_teacher)
        response = await client.get(
            f"/api/v1/students/{enrolled_student.id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "Enrolled"
        assert data["gradeName"] == test_grade.name
        assert data["curriculumName"] == test_curriculum.name

    @pytest.mark.asyncio
    async def test_get_student_info_when_teacher_views_student_from_other_school_then_403(
        self,
        client: AsyncClient,
        test_teacher: User,
        other_school: School,
        db_session: AsyncSession,
    ) -> None:
        """Test that teacher cannot view student from another school."""
        # Create a student in a different school
        other_student = User(
            id=uuid.uuid4(),
            school_id=other_school.id,
            email=f"other-school-student-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Other",
            last_name="Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(other_student)
        await db_session.commit()

        auth_headers = make_auth_header(test_teacher)
        response = await client.get(
            f"/api/v1/students/{other_student.id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_student_info_when_student_not_found_then_404(
        self,
        client: AsyncClient,
        enrolled_student: User,
    ) -> None:
        """Test that 404 is returned when student doesn't exist."""
        auth_headers = make_auth_header(enrolled_student)
        nonexistent_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/students/{nonexistent_id}/info",
            headers=auth_headers,
        )

        assert response.status_code == 404
