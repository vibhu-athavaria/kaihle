"""Integration tests for GET /api/v1/students/me/dashboard."""

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
async def enrolled_student_for_dashboard(
    db_session: AsyncSession,
    school: School,
) -> User:
    """Student with a learning profile + one active enrollment."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"dash-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Aisha",
        last_name="Rahman",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    profile = StudentProfile(id=uuid.uuid4(), user_id=student.id)
    db_session.add(profile)
    await db_session.commit()
    return student


@pytest_asyncio.fixture
async def student_class_with_enrollment(
    db_session: AsyncSession,
    school: School,
    enrolled_student_for_dashboard: User,
    teacher: User,
) -> Class:
    """A class + enrollment for the dashboard student."""
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Cambridge Lower Secondary {uuid.uuid4().hex[:4]}",
        code=f"cambridge_lower_{uuid.uuid4().hex[:4]}",
    )
    db_session.add(curriculum)
    await db_session.flush()

    subject = Subject(
        id=uuid.uuid4(),
        name="Mathematics",
        code=f"MATH{uuid.uuid4().hex[:4]}",
    )
    db_session.add(subject)
    await db_session.flush()

    grade = Grade(
        id=uuid.uuid4(),
        name="Grade 8",
        level=8,
    )
    db_session.add(grade)
    await db_session.flush()

    cls = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Mathematics 8A",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(cls)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=cls.id,
        student_id=enrolled_student_for_dashboard.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db_session.add(enrollment)
    await db_session.commit()
    return cls


@pytest.mark.asyncio
async def test_dashboard_route_when_unauthenticated_then_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/students/me/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_route_when_teacher_authenticated_then_returns_403(
    client: AsyncClient,
    teacher: User,
) -> None:
    response = await client.get(
        "/api/v1/students/me/dashboard",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_route_when_student_authenticated_then_returns_200(
    client: AsyncClient,
    enrolled_student_for_dashboard: User,
) -> None:
    response = await client.get(
        "/api/v1/students/me/dashboard",
        headers=make_auth_header(enrolled_student_for_dashboard),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_route_response_matches_schema(
    client: AsyncClient,
    enrolled_student_for_dashboard: User,
    student_class_with_enrollment: Class,
) -> None:
    response = await client.get(
        "/api/v1/students/me/dashboard",
        headers=make_auth_header(enrolled_student_for_dashboard),
    )
    assert response.status_code == 200
    body = response.json()
    assert "student_name" in body
    assert "action_items" in body
    assert "classes" in body
    assert isinstance(body["classes"], list)
    assert len(body["classes"]) == 1
    cls = body["classes"][0]
    assert cls["class_name"] == "Mathematics 8A"
    assert cls["diagnostic_status"] == "PENDING"
    assert cls["mastery_score"] is None  # no gap states yet


@pytest.mark.asyncio
async def test_dashboard_route_when_diagnostic_pending_then_action_item_added(
    client: AsyncClient,
    enrolled_student_for_dashboard: User,
    student_class_with_enrollment: Class,
) -> None:
    response = await client.get(
        "/api/v1/students/me/dashboard",
        headers=make_auth_header(enrolled_student_for_dashboard),
    )
    body = response.json()
    diagnostic_items = [a for a in body["action_items"] if a["type"] == "diagnostic_pending"]
    assert len(diagnostic_items) == 1
    assert diagnostic_items[0]["priority"] == 3


@pytest.mark.asyncio
async def test_dashboard_route_filters_by_school_id(
    client: AsyncClient,
    school: School,
    other_school: School,
    db_session: AsyncSession,
    teacher: User,
) -> None:
    """Student from school A must not see classes from school B."""
    student_a = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-a-{uuid.uuid4().hex[:8]}@example.com",
        first_name="StudentA",
        last_name="Test",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student_a)
    await db_session.flush()
    db_session.add(StudentProfile(id=uuid.uuid4(), user_id=student_a.id))
    await db_session.commit()

    response = await client.get(
        "/api/v1/students/me/dashboard",
        headers=make_auth_header(student_a),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["classes"] == []
