"""Integration tests for GET /api/v1/teachers/{teacher_id}.

Tests the teacher detail endpoint accessible to SCHOOL_ADMIN and KAIHLE_ADMIN.

Response shape:
    id, first_name, last_name, email, is_active,
    assigned_classes: [{class_id, class_name, subject_name, grade_level,
                        student_count, avg_mastery}]
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, School
from app.models.user import User, UserRole
from app.tests.integration.conftest import make_auth_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_teacher_in_school(db: AsyncSession, school: School, first_name: str = "Raj") -> User:
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-td-{uuid.uuid4().hex[:8]}@test.com",
        first_name=first_name,
        last_name="Patel",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()
    return teacher


async def _make_class_for_teacher(
    db: AsyncSession,
    school: School,
    teacher: User,
    class_name: str = "Math 7A",
    grade_level: int = 7,
) -> tuple[Class, Subject, Grade]:
    """Create a class assigned to the given teacher."""
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
        name=class_name,
        academic_year="2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()
    return class_, subject, grade


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_teacher_detail_when_unauthenticated_then_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unauthenticated request returns 401."""
    # Arrange
    teacher_id = uuid.uuid4()

    # Act
    response = await client.get(f"/api/v1/teachers/{teacher_id}")

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_teacher_detail_when_school_admin_views_teacher_in_own_school_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin can fetch teacher detail for a teacher in their school.

    Asserts 200, correct id/first_name/email/is_active, and one assigned class
    with correct class_name and subject_name.
    """
    # Arrange
    teacher = await _make_teacher_in_school(db_session, school, first_name="Raj")
    class_, subject, _ = await _make_class_for_teacher(db_session, school, teacher, "Math 7A", grade_level=7)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/teachers/{teacher.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(teacher.id)
    assert data["first_name"] == "Raj"
    assert data["last_name"] == "Patel"
    assert data["email"] == teacher.email
    assert data["is_active"] is True

    assert len(data["assigned_classes"]) == 1
    cls_data = data["assigned_classes"][0]
    assert cls_data["class_name"] == "Math 7A"
    assert cls_data["subject_name"] == subject.name
    assert str(cls_data["class_id"]) == str(class_.id)
    assert isinstance(cls_data["grade_level"], int)
    assert cls_data["grade_level"] == 7


@pytest.mark.asyncio
async def test_get_teacher_detail_when_teacher_has_no_classes_then_200_with_empty_assigned_classes(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Teacher with no classes assigned returns 200 with empty assigned_classes list."""
    # Arrange
    teacher = await _make_teacher_in_school(db_session, school)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/teachers/{teacher.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_classes"] == []


@pytest.mark.asyncio
async def test_get_teacher_detail_when_school_admin_views_teacher_from_other_school_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin from school A cannot view a teacher in school B; returns 404."""
    # Arrange — teacher belongs to other_school
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"teacher-other-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Mei",
        last_name="Zhao",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    # Act — school_admin belongs to school (not other_school)
    response = await client.get(
        f"/api/v1/teachers/{other_teacher.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_teacher_detail_when_student_role_accesses_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A STUDENT user cannot call the teacher detail endpoint; returns 403."""
    # Arrange
    student_requester = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-req-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Finn",
        last_name="Taylor",
        role=UserRole.STUDENT,
        is_active=True,
    )
    target_teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-tgt-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Grace",
        last_name="Martin",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add_all([student_requester, target_teacher])
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/teachers/{target_teacher.id}",
        headers=make_auth_header(student_requester),
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_teacher_detail_when_nonexistent_id_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin: User,
) -> None:
    """Non-existent teacher_id returns 404."""
    # Arrange
    nonexistent_id = uuid.uuid4()

    # Act
    response = await client.get(
        f"/api/v1/teachers/{nonexistent_id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_teacher_detail_when_multiple_classes_then_all_returned(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Teacher assigned to multiple classes has all of them in assigned_classes."""
    # Arrange
    teacher = await _make_teacher_in_school(db_session, school, first_name="Sam")
    await _make_class_for_teacher(db_session, school, teacher, "Math 7A", grade_level=7)
    await _make_class_for_teacher(db_session, school, teacher, "Math 8B", grade_level=8)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/teachers/{teacher.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["assigned_classes"]) == 2
    class_names = {cls["class_name"] for cls in data["assigned_classes"]}
    assert "Math 7A" in class_names
    assert "Math 8B" in class_names
