"""Integration tests for workspaces: school type, ownership and the operator guard.

A workspace is a `schools` row of type TEACHER_WORKSPACE or FAMILY, owned by one TEACHER.
These tests cover the model constraints and the S2 authorization changes (CONSTITUTION Rule 20).
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.lesson_plan import LessonPlan, LessonPlanStatus
from app.models.school import Class, ClassEnrollment, School, SchoolCurriculum, SchoolType
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
@pytest.mark.parametrize("role", ["TEACHER", "PARENT"])
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
async def test_create_user_direct_when_workspace_owner_and_role_school_admin_then_422(
    client: AsyncClient, workspace_a: tuple[School, User]
) -> None:
    # UserDirectCreate never accepts SCHOOL_ADMIN, so the body is rejected before the workspace rule runs.
    workspace, owner = workspace_a

    response = await client.post(
        f"/api/v1/schools/{workspace.id}/users/create",
        json={
            "first_name": "Extra",
            "last_name": "Admin",
            "email": f"extra-{uuid.uuid4().hex[:8]}@test.com",
            "password": "a-long-enough-pass",
            "role": "SCHOOL_ADMIN",
        },
        headers=make_auth_header(owner),
    )

    assert response.status_code == 422


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
    client: AsyncClient,
    workspace_a: tuple[School, User],
    kaihle_admin: User,
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
        headers=make_auth_header(kaihle_admin),
    )

    assert response.status_code == 403
    # Called as KAIHLE_ADMIN, so the 403 comes from the workspace rule, not the route guard.
    assert "workspace" in response.json()["detail"]


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


# ── Cross-tenant sweep ───────────────────────────────────────────────────────
#
# Owner A must not read or change anything in workspace B. 404 is accepted next to 403 because
# routes that look a resource up inside the caller's own school cannot tell "missing" from
# "someone else's". What must never happen is a 2xx.


@pytest_asyncio.fixture
async def workspace_b_content(
    db_session: AsyncSession,
    workspace_b: tuple[School, User],
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> dict[str, uuid.UUID]:
    """Workspace B with one class, one enrolled student, one assessment and one lesson plan."""
    workspace, owner = workspace_b
    student = await _make_student(db_session, workspace)
    class_ = Class(
        id=uuid.uuid4(),
        school_id=workspace.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=owner.id,
        name="B Maths",
        academic_year="2026-2027",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.flush()
    db_session.add(ClassEnrollment(class_id=class_.id, student_id=student.id))
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=workspace.id,
        class_id=class_.id,
        created_by=owner.id,
        title="B Assessment",
        assessment_type="DIAGNOSTIC",
        status="DRAFT",
    )
    plan = LessonPlan(
        id=uuid.uuid4(),
        class_id=class_.id,
        teacher_id=owner.id,
        status=LessonPlanStatus.GENERATED,
        generated_at=datetime.now(UTC),
    )
    db_session.add_all([assessment, plan])
    await db_session.commit()
    return {
        "class": class_.id,
        "student": student.id,
        "assessment": assessment.id,
        "plan": plan.id,
        "subject": test_subject.id,
    }


CROSS_TENANT_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/classes/{class}"),
    ("GET", "/api/v1/classes/{class}/assessments"),
    ("GET", "/api/v1/assessments/{assessment}"),
    ("GET", "/api/v1/assessments/{assessment}/results"),
    ("GET", "/api/v1/assessments/{assessment}/preview"),
    ("PATCH", "/api/v1/assessments/{assessment}"),
    ("POST", "/api/v1/assessments/{assessment}/publish"),
    ("POST", "/api/v1/assessments/{assessment}/close"),
    ("DELETE", "/api/v1/assessments/{assessment}"),
    ("GET", "/api/v1/classes/{class}/gap-map?subject_id={subject}"),
    ("GET", "/api/v1/classes/{class}/summary"),
    ("GET", "/api/v1/students/{student}/gap-map?subject_id={subject}"),
    ("GET", "/api/v1/students/{student}/info"),
    ("GET", "/api/v1/classes/{class}/lesson-plans"),
    ("GET", "/api/v1/lesson-plans/{plan}"),
    ("PATCH", "/api/v1/lesson-plans/{plan}"),
    ("POST", "/api/v1/lesson-plans/{plan}/regenerate"),
    ("PATCH", "/api/v1/lesson-plans/{plan}/status"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), CROSS_TENANT_ROUTES)
async def test_cross_tenant_when_owner_a_targets_workspace_b_resource_then_403_or_404(
    client: AsyncClient,
    workspace_a: tuple[School, User],
    workspace_b_content: dict[str, uuid.UUID],
    method: str,
    path: str,
) -> None:
    _, owner_a = workspace_a
    url = path.format(**{key: str(value) for key, value in workspace_b_content.items()})
    body = {"status": "ARCHIVED", "title": "hijacked"} if method in ("PATCH", "POST") else None

    response = await client.request(method, url, json=body, headers=make_auth_header(owner_a))

    assert response.status_code in (403, 404), f"{method} {url} returned {response.status_code}"


@pytest.mark.asyncio
async def test_update_class_when_owner_assigns_teacher_from_another_workspace_then_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    workspace_a: tuple[School, User],
    workspace_b: tuple[School, User],
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    # update_class used to copy teacher_id from the body unchecked, so a class could point at
    # a teacher in another tenant. The teacher must now be an active TEACHER in the same school.
    workspace, owner_a = workspace_a
    _, owner_b = workspace_b
    class_ = Class(
        id=uuid.uuid4(),
        school_id=workspace.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=owner_a.id,
        name="A Maths",
        academic_year="2026-2027",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/classes/{class_.id}",
        json={"teacher_id": str(owner_b.id)},
        headers=make_auth_header(owner_a),
    )

    assert response.status_code == 404
    await db_session.refresh(class_)
    assert class_.teacher_id == owner_a.id
