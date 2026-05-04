"""Integration tests for gap map routes — real implementation (M2-1-T2).

These tests exercise the real GapService implementation against a live test DB,
unlike the stub-era tests in test_gap_map.py which used random UUIDs.

Run with: pytest backend/app/tests/integration/test_gap_map_routes.py -v
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Local fixtures (supplement conftest — avoid duplicating what already exists)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def second_student(db_session: AsyncSession, school: School) -> User:
    """A second student in the same school — used to test cross-student 403."""
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student2-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def subject_for_enrollment(db_session: AsyncSession) -> Subject:
    """Dedicated subject used when we need a real enrollment."""
    s = Subject(
        id=uuid.uuid4(),
        name=f"Math-{uuid.uuid4().hex[:6]}",
        code=f"M{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def grade_for_enrollment(db_session: AsyncSession) -> Grade:
    import random

    g = Grade(
        id=uuid.uuid4(),
        name="Grade 8",
        level=random.randint(1, 13),  # must be 1–13 per grades_level_range constraint
        is_active=True,
    )
    db_session.add(g)
    await db_session.commit()
    return g


@pytest_asyncio.fixture
async def curriculum_for_enrollment(db_session: AsyncSession) -> Curriculum:
    c = Curriculum(
        id=uuid.uuid4(),
        name=f"Curriculum-{uuid.uuid4().hex[:6]}",
        code=f"C{uuid.uuid4().hex[:6]}",
        description="Test curriculum",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest_asyncio.fixture
async def class_with_teacher(
    db_session: AsyncSession,
    school: School,
    teacher: User,
    subject_for_enrollment: Subject,
    grade_for_enrollment: Grade,
    curriculum_for_enrollment: Curriculum,
) -> Class:
    """A real Class owned by the `teacher` fixture in the `school` fixture."""
    c = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade_for_enrollment.id,
        subject_id=subject_for_enrollment.id,
        curriculum_id=curriculum_for_enrollment.id,
        teacher_id=teacher.id,
        name="Gap Map Test Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest_asyncio.fixture
async def enrolled_student(
    db_session: AsyncSession,
    student: User,
    class_with_teacher: Class,
) -> User:
    """Student enrolled in class_with_teacher — needed to get 200 from me/gap-map."""
    enrollment = ClassEnrollment(
        class_id=class_with_teacher.id,
        student_id=student.id,
        is_active=True,
        onboarding_diagnostic_status="COMPLETED",
    )
    db_session.add(enrollment)
    await db_session.commit()
    return student


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassGapMapMissingSubjectId:
    @pytest.mark.asyncio
    async def test_class_gap_map_when_missing_subject_id_then_422(
        self,
        client: AsyncClient,
        teacher: User,
        class_with_teacher: Class,
    ) -> None:
        """Missing required subject_id query param returns 422 Unprocessable Entity."""
        headers = make_auth_header(teacher)
        response = await client.get(
            f"/api/v1/classes/{class_with_teacher.id}/gap-map",
            headers=headers,
        )
        assert response.status_code == 422


class TestClassGapMapStudentRole:
    @pytest.mark.asyncio
    async def test_class_gap_map_when_student_role_then_403(
        self,
        client: AsyncClient,
        student: User,
        class_with_teacher: Class,
    ) -> None:
        """Student JWT is rejected with 403 — route requires TEACHER/SCHOOL_ADMIN/KAIHLE_ADMIN."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(student)
        response = await client.get(
            f"/api/v1/classes/{class_with_teacher.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )
        assert response.status_code == 403


class TestClassGapMapTeacherOwnsClass:
    @pytest.mark.asyncio
    async def test_class_gap_map_when_teacher_owns_class_then_200(
        self,
        client: AsyncClient,
        teacher: User,
        class_with_teacher: Class,
        subject_for_enrollment: Subject,
    ) -> None:
        """Teacher requesting gap map for their own class returns 200 with nodes key."""
        headers = make_auth_header(teacher)
        response = await client.get(
            f"/api/v1/classes/{class_with_teacher.id}/gap-map?subject_id={subject_for_enrollment.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert data["class_id"] == str(class_with_teacher.id)
        assert data["subject_id"] == str(subject_for_enrollment.id)


class TestClassSummaryTeacherOwnsClass:
    @pytest.mark.asyncio
    async def test_class_summary_when_teacher_owns_class_then_200(
        self,
        client: AsyncClient,
        teacher: User,
        class_with_teacher: Class,
    ) -> None:
        """Teacher requesting class summary for their own class returns 200 with student_count key."""
        headers = make_auth_header(teacher)
        response = await client.get(
            f"/api/v1/classes/{class_with_teacher.id}/summary",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "student_count" in data
        assert data["class_id"] == str(class_with_teacher.id)
        assert data["avg_mastery"] is None  # no gap states yet
        assert data["assessed_student_count"] == 0


class TestMyGapMapAuthenticatedStudent:
    @pytest.mark.asyncio
    async def test_my_gap_map_when_authenticated_student_then_200(
        self,
        client: AsyncClient,
        enrolled_student: User,
        class_with_teacher: Class,
        subject_for_enrollment: Subject,
    ) -> None:
        """Enrolled student requesting their own gap map returns 200 with scores key."""
        headers = make_auth_header(enrolled_student)
        response = await client.get(
            f"/api/v1/students/me/gap-map?subject_id={subject_for_enrollment.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == str(enrolled_student.id)
        assert "scores" in data


class TestStudentGapMapDifferentStudent:
    @pytest.mark.asyncio
    async def test_student_gap_map_when_different_student_then_403(
        self,
        client: AsyncClient,
        student: User,
        second_student: User,
    ) -> None:
        """Student requesting another student's gap map returns 403 Forbidden."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(student)
        response = await client.get(
            f"/api/v1/students/{second_student.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )
        assert response.status_code == 403
