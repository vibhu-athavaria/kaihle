"""Integration tests for has_teacher and teacher_name fields in ClassWithSummary.

Tests verify that GET /api/v1/schools/{school_id}/classes?include_summary=true
returns the new has_teacher (bool) and teacher_name (str | None) fields correctly.

Note: The DB schema enforces teacher_id NOT NULL on the classes table.
Therefore has_teacher is always True for any persisted class. The has_teacher=False
path is a schema-level protection that cannot be triggered via the real DB; it is
covered at the service unit-test level.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, School
from app.models.user import User, UserRole
from app.tests.integration.conftest import make_auth_header


async def _make_class(
    db: AsyncSession,
    school: School,
    teacher: User,
    name: str,
    grade_level: int = 7,
) -> Class:
    """Create a minimal class with all required FK dependencies."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Subject-{uuid.uuid4().hex[:4]}",
        code=f"SC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name=f"Grade {grade_level}", level=grade_level, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Curriculum-{uuid.uuid4().hex[:4]}",
        code=f"CU{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add_all([subject, grade, curriculum])
    await db.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name=name,
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()
    return class_


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_class_has_teacher_then_has_teacher_is_true(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin requests include_summary=true; class has a teacher assigned.

    Asserts has_teacher is True and teacher_name matches the teacher's full name.
    """
    # Arrange
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-ht-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Alice",
        last_name="Walker",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    await _make_class(db_session, school, teacher, "Math 7A", grade_level=7)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["has_teacher"] is True
    assert item["teacher_name"] == "Alice Walker"


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_class_has_teacher_then_teacher_name_is_full_name(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """teacher_name is the concatenation of first_name and last_name (no extra whitespace).

    Verifies the exact format produced by the route: f"{first_name} {last_name}".strip().
    """
    # Arrange
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-fn-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Bob",
        last_name="Chen",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    await _make_class(db_session, school, teacher, "Science 8B", grade_level=8)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["teacher_name"] == "Bob Chen"
    assert data[0]["has_teacher"] is True


@pytest.mark.asyncio
async def test_list_classes_include_summary_when_multiple_classes_then_each_has_teacher_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """All returned classes include has_teacher and teacher_name fields."""
    # Arrange
    teacher_a = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-a-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Carol",
        last_name="Diaz",
        role=UserRole.TEACHER,
        is_active=True,
    )
    teacher_b = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-b-{uuid.uuid4().hex[:8]}@test.com",
        first_name="David",
        last_name="Evans",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add_all([teacher_a, teacher_b])
    await db_session.flush()

    await _make_class(db_session, school, teacher_a, "Math 7A", grade_level=7)
    await _make_class(db_session, school, teacher_b, "Science 8B", grade_level=8)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/schools/{school.id}/classes?include_summary=true",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    teacher_names = {item["teacher_name"] for item in data}
    assert "Carol Diaz" in teacher_names
    assert "David Evans" in teacher_names

    for item in data:
        assert "has_teacher" in item
        assert item["has_teacher"] is True
        assert "teacher_name" in item
        assert item["teacher_name"] is not None
