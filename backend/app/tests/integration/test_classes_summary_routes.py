"""Integration tests for class summary endpoints.

Tests verify the optimized single-call endpoint:
- GET /api/v1/schools/{school_id}/classes?include_summary=true

Run with: pytest backend/app/tests/integration/test_classes_summary_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    Subject,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_class_for_teacher(
    db: AsyncSession,
    school: School,
    teacher: User,
    class_name: str,
    level: int = 8,
) -> Class:
    """Create a class for a teacher."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Subject-{uuid.uuid4().hex[:4]}",
        code=f"S{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name=f"Grade {class_name}", level=level, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Curriculum-{uuid.uuid4().hex[:4]}",
        code=f"C{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add_all([subject, grade, curriculum])
    await db.flush()

    topic = Topic(id=uuid.uuid4(), name="Topic 1", is_active=True)
    db.add(topic)
    await db.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=True,
    )
    db.add(ct)
    await db.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name=class_name,
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()
    return class_


# ---------------------------------------------------------------------------
# list_classes with include_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_teacher_has_classes_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher listing classes with include_summary gets enriched data."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    await _create_class_for_teacher(db_session, school, teacher, "Math 8A", level=8)
    await _create_class_for_teacher(db_session, school, teacher, "Science 8B", level=9)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    for item in data:
        assert "grade_name" in item
        assert "subject_name" in item
        assert "avg_mastery" in item
        assert "student_count" in item
        assert "students_below_threshold" in item


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_no_classes_then_returns_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher with no classes gets empty list."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-empty-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_classes_include_summary_false_then_returns_basic(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher listing classes without include_summary gets basic data."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-basic-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    await _create_class_for_teacher(db_session, school, teacher, "Math 8A")
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{school.id}/classes",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

    item = data[0]
    assert "grade_name" not in item
    assert "subject_name" not in item


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_school_admin_then_returns_all(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """SchoolAdmin can see all classes with summary."""
    school_admin = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"sadmin-{uuid.uuid4().hex[:8]}@test.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(school_admin)
    await db_session.flush()

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    await _create_class_for_teacher(db_session, school, teacher, "Math 8A", level=10)
    await _create_class_for_teacher(db_session, school, teacher, "Science 8B", level=11)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(school_admin),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_other_school_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """Teacher from other school gets 403."""
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(other_teacher),
    )

    assert response.status_code == 403
