"""Integration tests for GET /api/v1/parents/{parent_id}.

Tests the parent detail endpoint accessible to SCHOOL_ADMIN and KAIHLE_ADMIN.

Response shape:
    id, first_name, last_name, email, is_active,
    linked_students: [{student_id, first_name, last_name, worst_mastery, class_count}]
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.user import ParentStudent, User, UserRole
from app.tests.integration.conftest import make_auth_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_parent(db: AsyncSession, school: School, first_name: str = "Pat") -> User:
    parent = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"parent-pd-{uuid.uuid4().hex[:8]}@test.com",
        first_name=first_name,
        last_name="Rivera",
        role=UserRole.PARENT,
        is_active=True,
    )
    db.add(parent)
    await db.flush()
    return parent


async def _make_student(db: AsyncSession, school: School, first_name: str = "Chris") -> User:
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-pd-{uuid.uuid4().hex[:8]}@test.com",
        first_name=first_name,
        last_name="Rivera",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(student)
    await db.flush()
    return student


async def _link_parent_student(db: AsyncSession, parent: User, student: User) -> None:
    link = ParentStudent(parent_id=parent.id, student_id=student.id)
    db.add(link)
    await db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_parent_detail_when_unauthenticated_then_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unauthenticated request returns 401."""
    # Arrange
    parent_id = uuid.uuid4()

    # Act
    response = await client.get(f"/api/v1/parents/{parent_id}")

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_parent_detail_when_school_admin_views_parent_in_own_school_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin can fetch full detail for a parent in their school.

    Asserts 200, correct id/first_name/email, and linked_students with one entry
    containing the correct student first_name.
    """
    # Arrange
    parent = await _make_parent(db_session, school, first_name="Linda")
    student = await _make_student(db_session, school, first_name="Marco")
    await _link_parent_student(db_session, parent, student)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/parents/{parent.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(parent.id)
    assert data["first_name"] == "Linda"
    assert data["last_name"] == "Rivera"
    assert data["email"] == parent.email
    assert data["is_active"] is True

    assert len(data["linked_students"]) == 1
    student_data = data["linked_students"][0]
    assert student_data["first_name"] == "Marco"
    assert str(student_data["student_id"]) == str(student.id)
    assert isinstance(student_data["class_count"], int)


@pytest.mark.asyncio
async def test_get_parent_detail_when_parent_has_no_linked_students_then_200_with_empty_list(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Parent with no ParentStudent links returns 200 with empty linked_students list."""
    # Arrange
    parent = await _make_parent(db_session, school, first_name="Hiro")
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/parents/{parent.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(parent.id)
    assert data["linked_students"] == []


@pytest.mark.asyncio
async def test_get_parent_detail_when_school_admin_views_parent_from_other_school_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin from school A cannot view a parent in school B; returns 403."""
    # Arrange — parent belongs to other_school
    other_parent = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"parent-other-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Yuki",
        last_name="Tanaka",
        role=UserRole.PARENT,
        is_active=True,
    )
    db_session.add(other_parent)
    await db_session.commit()

    # Act — school_admin belongs to school (not other_school)
    response = await client.get(
        f"/api/v1/parents/{other_parent.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_parent_detail_when_student_role_accesses_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A STUDENT user cannot call the parent detail endpoint; returns 403."""
    # Arrange
    student_requester = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-req-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Ivy",
        last_name="Nguyen",
        role=UserRole.STUDENT,
        is_active=True,
    )
    target_parent = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"parent-tgt-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Jean",
        last_name="Nguyen",
        role=UserRole.PARENT,
        is_active=True,
    )
    db_session.add_all([student_requester, target_parent])
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/parents/{target_parent.id}",
        headers=make_auth_header(student_requester),
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_parent_detail_when_nonexistent_id_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin: User,
) -> None:
    """Non-existent parent_id returns 404."""
    # Arrange
    nonexistent_id = uuid.uuid4()

    # Act
    response = await client.get(
        f"/api/v1/parents/{nonexistent_id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_parent_detail_when_parent_has_multiple_students_then_all_returned(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Parent linked to multiple students has all of them in linked_students."""
    # Arrange
    parent = await _make_parent(db_session, school, first_name="Dana")
    student_a = await _make_student(db_session, school, first_name="Aria")
    student_b = await _make_student(db_session, school, first_name="Bruno")
    await _link_parent_student(db_session, parent, student_a)
    await _link_parent_student(db_session, parent, student_b)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/parents/{parent.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["linked_students"]) == 2
    names = {s["first_name"] for s in data["linked_students"]}
    assert "Aria" in names
    assert "Bruno" in names
