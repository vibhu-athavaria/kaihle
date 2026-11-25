"""Integration tests for workspaces: school type, ownership and the operator guard.

A workspace is a `schools` row of type TEACHER_WORKSPACE or FAMILY, owned by one TEACHER.
These tests cover the model constraints and the S2 authorization changes (CONSTITUTION Rule 20).
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, School, SchoolCurriculum, SchoolType
from app.models.user import StudentProfile, User, UserRole
from app.tests.integration.conftest import make_auth_header


async def _make_workspace(db: AsyncSession, kind: str = SchoolType.TEACHER_WORKSPACE) -> tuple[School, User]:
    """Create a workspace school and its owner (role TEACHER) in one transaction."""
    school = School(
        id=uuid.uuid4(),
        name="Workspace",
        slug=f"ws-{uuid.uuid4().hex[:8]}",
        status="active",
        type=kind,
    )
    db.add(school)
    await db.flush()
    owner = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"owner-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Owner",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(owner)
    await db.flush()
    school.owner_user_id = owner.id
    await db.commit()
    return school, owner


async def _make_student(db: AsyncSession, school: School) -> User:
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        username=f"kid-{uuid.uuid4().hex[:8]}",
        first_name="Kid",
        last_name="Learner",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(student)
    await db.commit()
    return student


@pytest_asyncio.fixture
async def workspace_a(db_session: AsyncSession) -> tuple[School, User]:
    return await _make_workspace(db_session)


@pytest_asyncio.fixture
async def workspace_b(db_session: AsyncSession) -> tuple[School, User]:
    return await _make_workspace(db_session)


def _student_body(grade: Grade) -> dict[str, object]:
    return {
        "first_name": "New",
        "last_name": "Student",
        "username": f"new-{uuid.uuid4().hex[:8]}",
        "password": "a-long-enough-pass",
        "role": "STUDENT",
        "age": 12,
        "grade_id": str(grade.id),
    }


# ── Model constraints ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_school_when_type_not_given_then_defaults_to_school(db_session: AsyncSession) -> None:
    school = School(id=uuid.uuid4(), name="Plain", slug=f"plain-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(school)
    await db_session.commit()
    await db_session.refresh(school)

    assert school.type == SchoolType.SCHOOL
    assert school.owner_user_id is None


@pytest.mark.asyncio
async def test_school_when_type_invalid_then_integrity_error(db_session: AsyncSession) -> None:
    db_session.add(
        School(id=uuid.uuid4(), name="Bad", slug=f"bad-{uuid.uuid4().hex[:8]}", status="active", type="MALL")
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_school_when_user_owns_two_workspaces_then_integrity_error(
    db_session: AsyncSession, workspace_a: tuple[School, User]
) -> None:
    _, owner = workspace_a
    db_session.add(
        School(
            id=uuid.uuid4(),
            name="Second",
            slug=f"ws-{uuid.uuid4().hex[:8]}",
            status="active",
            type=SchoolType.FAMILY,
            owner_user_id=owner.id,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ── require_school_operator ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_direct_when_teacher_in_real_school_then_403(
    client: AsyncClient, school: School, teacher: User, test_grade: Grade
) -> None:
    response = await client.post(
        f"/api/v1/schools/{school.id}/users/create",
        json=_student_body(test_grade),
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_user_direct_when_workspace_owner_and_role_student_then_creates_in_own_workspace(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_a: tuple[School, User],
    test_grade: Grade,
) -> None:
    workspace, owner = workspace_a
    body = _student_body(test_grade)

    response = await client.post(
        f"/api/v1/schools/{workspace.id}/users/create",
        json=body,
        headers=make_auth_header(owner),
    )

    assert response.status_code == 201
    created = await db_session.scalar(select(User).where(User.username == body["username"]))
    assert created is not None
    assert created.school_id == workspace.id
    assert created.role == UserRole.STUDENT
    profile = await db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == created.id))
    assert profile is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["TEACHER", "PARENT", "SCHOOL_ADMIN"])
async def test_create_user_direct_when_workspace_owner_and_non_student_role_then_403(
    client: AsyncClient, workspace_a: tuple[School, User], role: str
) -> None:
    workspace, owner = workspace_a

    response = await client.post(
        f"/api/v1/schools/{workspace.id}/users/create",
        json={
            "first_name": "Extra",
            "last_name": "Person",
            "email": f"extra-{uuid.uuid4().hex[:8]}@test.com",
            "password": "a-long-enough-pass",
            "role": role,
        },
        headers=make_auth_header(owner),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_user_direct_when_owner_targets_another_workspace_then_403(
    client: AsyncClient,
    workspace_a: tuple[School, User],
    workspace_b: tuple[School, User],
    test_grade: Grade,
) -> None:
    _, owner_a = workspace_a
    other_workspace, _ = workspace_b

    response = await client.post(
        f"/api/v1/schools/{other_workspace.id}/users/create",
        json=_student_body(test_grade),
        headers=make_auth_header(owner_a),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_invite_user_when_school_is_workspace_then_403(
    client: AsyncClient, kaihle_admin: User, workspace_a: tuple[School, User]
) -> None:
    workspace, _ = workspace_a

    response = await client.post(
        f"/api/v1/schools/{workspace.id}/users",
        json={
            "email": f"second-{uuid.uuid4().hex[:8]}@test.com",
            "role": "TEACHER",
            "first_name": "Second",
            "last_name": "Teacher",
        },
        headers=make_auth_header(kaihle_admin),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_when_school_is_workspace_and_role_teacher_then_403(
    client: AsyncClient, workspace_a: tuple[School, User]
) -> None:
    workspace, _ = workspace_a

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"sneaky-{uuid.uuid4().hex[:8]}@test.com",
            "password": "a-long-enough-pass",
            "role": "TEACHER",
            "school_id": str(workspace.id),
            "first_name": "Sneaky",
            "last_name": "Teacher",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_when_workspace_owner_then_only_own_workspace_users(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_a: tuple[School, User],
    workspace_b: tuple[School, User],
) -> None:
    workspace, owner = workspace_a
    other_workspace, _ = workspace_b
    mine = await _make_student(db_session, workspace)
    theirs = await _make_student(db_session, other_workspace)

    own = await client.get(f"/api/v1/schools/{workspace.id}/users", headers=make_auth_header(owner))
    foreign = await client.get(f"/api/v1/schools/{other_workspace.id}/users", headers=make_auth_header(owner))

    assert own.status_code == 200
    ids = {u["id"] for u in own.json()["users"]}
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids
    assert foreign.status_code == 403


@pytest.mark.asyncio
async def test_update_user_when_owner_edits_own_account_then_403(
    client: AsyncClient, workspace_a: tuple[School, User]
) -> None:
    workspace, owner = workspace_a

    response = await client.patch(
        f"/api/v1/schools/{workspace.id}/users/{owner.id}",
        json={"is_active": False},
        headers=make_auth_header(owner),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_when_owner_deactivates_student_then_204(
    client: AsyncClient, db_session: AsyncSession, workspace_a: tuple[School, User]
) -> None:
    workspace, owner = workspace_a
    student = await _make_student(db_session, workspace)

    response = await client.delete(
        f"/api/v1/schools/{workspace.id}/users/{student.id}",
        headers=make_auth_header(owner),
    )

    assert response.status_code == 204
    await db_session.refresh(student)
    assert student.is_active is False


@pytest.mark.asyncio
async def test_deactivate_user_when_owner_targets_self_then_403(
    client: AsyncClient, workspace_a: tuple[School, User]
) -> None:
    workspace, owner = workspace_a

    response = await client.delete(
        f"/api/v1/schools/{workspace.id}/users/{owner.id}",
        headers=make_auth_header(owner),
    )

    assert response.status_code == 403


# ── Classes ──────────────────────────────────────────────────────────────────


def _class_body(teacher: User, grade: Grade, subject: Subject, curriculum: Curriculum) -> dict[str, object]:
    return {
        "name": "Maths A",
        "grade_id": str(grade.id),
        "subject_id": str(subject.id),
        "curriculum_id": str(curriculum.id),
        "teacher_id": str(teacher.id),
        "academic_year": "2026-2027",
    }


@pytest.mark.asyncio
async def test_create_class_when_workspace_owner_then_201_and_owner_is_teacher(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_a: tuple[School, User],
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    workspace, owner = workspace_a
    db_session.add(SchoolCurriculum(school_id=workspace.id, curriculum_id=test_curriculum.id, is_primary=True))
    await db_session.commit()

    response = await client.post(
        f"/api/v1/schools/{workspace.id}/classes",
        json=_class_body(owner, test_grade, test_subject, test_curriculum),
        headers=make_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["teacher_id"] == str(owner.id)
    created = await db_session.scalar(select(Class).where(Class.id == uuid.UUID(response.json()["id"])))
    assert created is not None
    assert created.school_id == workspace.id


@pytest.mark.asyncio
async def test_create_class_when_owner_targets_another_workspace_then_403(
    client: AsyncClient,
    workspace_a: tuple[School, User],
    workspace_b: tuple[School, User],
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    _, owner_a = workspace_a
    other_workspace, owner_b = workspace_b

    response = await client.post(
        f"/api/v1/schools/{other_workspace.id}/classes",
        json=_class_body(owner_b, test_grade, test_subject, test_curriculum),
        headers=make_auth_header(owner_a),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_class_when_teacher_in_real_school_then_403(
    client: AsyncClient,
    school: School,
    teacher: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    response = await client.post(
        f"/api/v1/schools/{school.id}/classes",
        json=_class_body(teacher, test_grade, test_subject, test_curriculum),
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_class_when_owner_requests_class_in_other_workspace_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_a: tuple[School, User],
    workspace_b: tuple[School, User],
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    _, owner_a = workspace_a
    other_workspace, owner_b = workspace_b
    other_class = Class(
        id=uuid.uuid4(),
        school_id=other_workspace.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=owner_b.id,
        name="Private class",
        academic_year="2026-2027",
        is_active=True,
    )
    db_session.add(other_class)
    await db_session.commit()

    response = await client.get(f"/api/v1/classes/{other_class.id}", headers=make_auth_header(owner_a))

    assert response.status_code == 403


# ── /users/me ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [SchoolType.TEACHER_WORKSPACE, SchoolType.FAMILY])
async def test_get_me_when_workspace_owner_then_returns_workspace_type(
    client: AsyncClient, db_session: AsyncSession, kind: SchoolType
) -> None:
    workspace, owner = await _make_workspace(db_session, kind)

    response = await client.get(f"/api/v1/schools/{workspace.id}/users/me", headers=make_auth_header(owner))

    assert response.status_code == 200
    assert response.json()["workspace_type"] == kind.value
    assert response.json()["is_workspace_owner"] is True


@pytest.mark.asyncio
async def test_get_me_when_teacher_in_real_school_then_no_workspace(
    client: AsyncClient, school: School, teacher: User
) -> None:
    response = await client.get(f"/api/v1/schools/{school.id}/users/me", headers=make_auth_header(teacher))

    assert response.status_code == 200
    assert response.json()["workspace_type"] is None
    assert response.json()["is_workspace_owner"] is False
