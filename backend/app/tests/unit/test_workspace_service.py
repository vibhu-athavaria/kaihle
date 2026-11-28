"""Unit tests for workspace_service and the require_school_operator guard.

A workspace is a `schools` row of type TEACHER_WORKSPACE or FAMILY, owned by one TEACHER.
The database is mocked: each test sets what `db.scalar` returns for the query under test.
"""

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_school_operator
from app.models.school import School, SchoolCurriculum, SchoolType
from app.models.user import TeacherProfile, User, UserRole
from app.schemas.workspace import WorkspaceSignupRequest
from app.services.workspace_service import (
    HANDLE_MAX_ATTEMPTS,
    HANDLE_SUFFIX_ALPHABET,
    StudentHandleUnavailableError,
    WorkspaceRestrictionError,
    WorkspaceSignupError,
    add_user_with_generated_handle,
    assert_class_teacher_allowed,
    assert_operator_may_manage_user,
    assert_role_allowed_in_school,
    create_workspace,
    generate_student_handle,
    get_workspace_context,
    is_workspace_owner,
    is_workspace_school,
    sign_up_workspace,
)


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=_assign_ids(session))
    return session


def _assign_ids(session: MagicMock) -> Any:
    """Make flush() give every added School or User an id, as the database would."""

    async def flush() -> None:
        for call in session.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, (School, User)) and obj.id is None:
                obj.id = uuid.uuid4()

    return flush


def _signup(**overrides: Any) -> WorkspaceSignupRequest:
    data: dict[str, Any] = {
        "kind": "teacher",
        "first_name": "Ana",
        "last_name": "Lim",
        "email": "ana@example.com",
        "country": "Singapore",
        "timezone": "Asia/Singapore",
        "curriculum_id": uuid.uuid4(),
    }
    data.update(overrides)
    return WorkspaceSignupRequest(**data)


def _added(session: MagicMock, kind: type) -> list[Any]:
    return [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], kind)]


def _school(kind: str, owner_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), type=kind, owner_user_id=owner_id)


def _user(role: str, school_id: uuid.UUID | None) -> Any:
    return SimpleNamespace(id=uuid.uuid4(), role=role, school_id=school_id)


# ── is_workspace_owner ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_workspace_owner_when_school_id_is_none_then_false_without_query(mock_db: MagicMock) -> None:
    assert await is_workspace_owner(mock_db, uuid.uuid4(), None) is False
    mock_db.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_is_workspace_owner_when_user_owns_workspace_then_true(mock_db: MagicMock) -> None:
    user_id = uuid.uuid4()
    mock_db.scalar.return_value = user_id

    assert await is_workspace_owner(mock_db, user_id, uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_is_workspace_owner_when_other_user_owns_workspace_then_false(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = uuid.uuid4()

    assert await is_workspace_owner(mock_db, uuid.uuid4(), uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_is_workspace_owner_when_real_school_or_no_owner_then_false(mock_db: MagicMock) -> None:
    # The query excludes type SCHOOL, so a real school returns no row.
    mock_db.scalar.return_value = None

    assert await is_workspace_owner(mock_db, uuid.uuid4(), uuid.uuid4()) is False


# ── get_workspace_context ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_workspace_context_when_user_has_no_school_then_not_a_workspace(mock_db: MagicMock) -> None:
    context = await get_workspace_context(mock_db, _user(UserRole.KAIHLE_ADMIN, None))

    assert context.workspace_type is None
    assert context.is_owner is False
    mock_db.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_workspace_context_when_real_school_then_not_a_workspace(mock_db: MagicMock) -> None:
    school = _school(SchoolType.SCHOOL)
    mock_db.get.return_value = school

    context = await get_workspace_context(mock_db, _user(UserRole.TEACHER, school.id))

    assert context.workspace_type is None
    assert context.is_owner is False


@pytest.mark.asyncio
async def test_get_workspace_context_when_school_missing_then_not_a_workspace(mock_db: MagicMock) -> None:
    mock_db.get.return_value = None

    context = await get_workspace_context(mock_db, _user(UserRole.TEACHER, uuid.uuid4()))

    assert context.workspace_type is None


@pytest.mark.asyncio
async def test_get_workspace_context_when_owner_of_family_workspace_then_family_and_owner(mock_db: MagicMock) -> None:
    owner = _user(UserRole.TEACHER, None)
    school = _school(SchoolType.FAMILY, owner.id)
    owner.school_id = school.id
    mock_db.get.return_value = school

    context = await get_workspace_context(mock_db, owner)

    assert context.workspace_type == SchoolType.FAMILY
    assert context.is_owner is True


@pytest.mark.asyncio
async def test_get_workspace_context_when_student_in_workspace_then_type_but_not_owner(mock_db: MagicMock) -> None:
    school = _school(SchoolType.TEACHER_WORKSPACE, uuid.uuid4())
    mock_db.get.return_value = school

    context = await get_workspace_context(mock_db, _user(UserRole.STUDENT, school.id))

    assert context.workspace_type == SchoolType.TEACHER_WORKSPACE
    assert context.is_owner is False


# ── assert_role_allowed_in_school ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PARENT, UserRole.STUDENT])
async def test_assert_role_allowed_in_school_when_real_school_then_any_role_allowed(
    mock_db: MagicMock, role: str
) -> None:
    mock_db.scalar.return_value = SchoolType.SCHOOL

    await assert_role_allowed_in_school(mock_db, uuid.uuid4(), role)


@pytest.mark.asyncio
async def test_assert_role_allowed_in_school_when_school_missing_then_no_error(mock_db: MagicMock) -> None:
    # The caller reports the missing school (404); this rule has nothing to add.
    mock_db.scalar.return_value = None

    await assert_role_allowed_in_school(mock_db, uuid.uuid4(), UserRole.TEACHER)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [SchoolType.TEACHER_WORKSPACE, SchoolType.FAMILY])
async def test_assert_role_allowed_in_school_when_workspace_and_student_then_allowed(
    mock_db: MagicMock, kind: str
) -> None:
    mock_db.scalar.return_value = kind

    await assert_role_allowed_in_school(mock_db, uuid.uuid4(), UserRole.STUDENT)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PARENT])
async def test_invite_user_when_school_is_workspace_and_role_teacher_then_raises(mock_db: MagicMock, role: str) -> None:
    # Name from the plan; covers every non-student role the invite and create paths could pass.
    mock_db.scalar.return_value = SchoolType.TEACHER_WORKSPACE

    with pytest.raises(WorkspaceRestrictionError):
        await assert_role_allowed_in_school(mock_db, uuid.uuid4(), role)


# ── assert_class_teacher_allowed ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assert_class_teacher_allowed_when_real_school_then_any_teacher_allowed(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = _school(SchoolType.SCHOOL)

    await assert_class_teacher_allowed(mock_db, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_assert_class_teacher_allowed_when_school_missing_then_no_error(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    await assert_class_teacher_allowed(mock_db, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_assert_class_teacher_allowed_when_workspace_and_teacher_is_owner_then_allowed(
    mock_db: MagicMock,
) -> None:
    owner_id = uuid.uuid4()
    mock_db.scalar.return_value = _school(SchoolType.TEACHER_WORKSPACE, owner_id)

    await assert_class_teacher_allowed(mock_db, uuid.uuid4(), owner_id)


@pytest.mark.asyncio
async def test_assert_class_teacher_allowed_when_workspace_and_teacher_not_owner_then_raises(
    mock_db: MagicMock,
) -> None:
    mock_db.scalar.return_value = _school(SchoolType.FAMILY, uuid.uuid4())

    with pytest.raises(WorkspaceRestrictionError):
        await assert_class_teacher_allowed(mock_db, uuid.uuid4(), uuid.uuid4())


# ── assert_operator_may_manage_user ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN])
async def test_assert_operator_may_manage_user_when_admin_then_no_workspace_checks(
    mock_db: MagicMock, role: str
) -> None:
    await assert_operator_may_manage_user(mock_db, role, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    mock_db.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_assert_operator_may_manage_user_when_teacher_not_owner_then_raises(mock_db: MagicMock) -> None:
    with patch("app.services.workspace_service.is_workspace_owner", new=AsyncMock(return_value=False)):
        with pytest.raises(WorkspaceRestrictionError):
            await assert_operator_may_manage_user(mock_db, UserRole.TEACHER, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_assert_operator_may_manage_user_when_owner_targets_student_then_allowed(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = UserRole.STUDENT

    with patch("app.services.workspace_service.is_workspace_owner", new=AsyncMock(return_value=True)):
        await assert_operator_may_manage_user(mock_db, UserRole.TEACHER, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("target_role", [UserRole.TEACHER, None])
async def test_assert_operator_may_manage_user_when_owner_targets_non_student_then_raises(
    mock_db: MagicMock, target_role: str | None
) -> None:
    # TEACHER is the owner themselves; None is a user outside this workspace.
    mock_db.scalar.return_value = target_role

    with patch("app.services.workspace_service.is_workspace_owner", new=AsyncMock(return_value=True)):
        with pytest.raises(WorkspaceRestrictionError):
            await assert_operator_may_manage_user(mock_db, UserRole.TEACHER, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


# ── require_school_operator ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN])
async def test_require_school_operator_when_admin_then_returns_user(mock_db: MagicMock, role: str) -> None:
    user = _user(role, uuid.uuid4())

    assert await require_school_operator(user, mock_db) is user


@pytest.mark.asyncio
async def test_require_school_operator_when_workspace_owner_then_returns_user(mock_db: MagicMock) -> None:
    user = _user(UserRole.TEACHER, uuid.uuid4())

    with patch("app.core.deps.is_workspace_owner", new=AsyncMock(return_value=True)):
        assert await require_school_operator(user, mock_db) is user


@pytest.mark.asyncio
async def test_require_school_operator_when_plain_teacher_in_real_school_then_403(mock_db: MagicMock) -> None:
    user = _user(UserRole.TEACHER, uuid.uuid4())

    with patch("app.core.deps.is_workspace_owner", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await require_school_operator(user, mock_db)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.PARENT])
async def test_require_school_operator_when_student_or_parent_then_403(mock_db: MagicMock, role: str) -> None:
    with pytest.raises(HTTPException) as exc:
        await require_school_operator(_user(role, uuid.uuid4()), mock_db)

    assert exc.value.status_code == 403


# ── create_workspace ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("curriculum_active", [None, False])
async def test_create_workspace_when_curriculum_missing_or_inactive_then_raises_and_adds_nothing(
    mock_db: MagicMock, curriculum_active: bool | None
) -> None:
    mock_db.scalar.return_value = curriculum_active

    with pytest.raises(WorkspaceSignupError):
        await create_workspace(mock_db, _signup())

    mock_db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "school_type", "name"),
    [
        ("teacher", SchoolType.TEACHER_WORKSPACE, "Ana Lim's classroom"),
        ("family", SchoolType.FAMILY, "Lim family"),
    ],
)
async def test_create_workspace_when_valid_then_school_owner_profile_and_curriculum_added(
    mock_db: MagicMock, kind: str, school_type: str, name: str
) -> None:
    mock_db.scalar.return_value = True
    data = _signup(kind=kind, city="Singapore")

    school, owner = await create_workspace(mock_db, data)

    assert school.type == school_type
    assert school.name == name
    assert school.slug.startswith("ws-")
    assert school.status == "active"
    assert (school.country, school.city, school.timezone) == ("Singapore", "Singapore", "Asia/Singapore")
    assert school.owner_user_id == owner.id
    assert owner.role == UserRole.TEACHER
    assert owner.school_id == school.id
    assert owner.is_active is True
    assert owner.hashed_password  # unusable random password until set via the magic link
    (profile,) = _added(mock_db, TeacherProfile)
    assert profile.user_id == owner.id
    (subscription,) = _added(mock_db, SchoolCurriculum)
    assert subscription.curriculum_id == data.curriculum_id
    assert subscription.is_primary is True


@pytest.mark.asyncio
async def test_create_workspace_when_name_given_then_used_verbatim(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = True

    school, _ = await create_workspace(mock_db, _signup(workspace_name="Maths with Ana"))

    assert school.name == "Maths with Ana"


@pytest.mark.asyncio
async def test_create_workspace_when_called_twice_then_slugs_differ(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = True

    first, _ = await create_workspace(mock_db, _signup())
    second, _ = await create_workspace(mock_db, _signup(email="other@example.com"))

    assert first.slug != second.slug


# ── sign_up_workspace ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sign_up_workspace_when_email_taken_then_creates_and_sends_nothing(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = uuid.uuid4()  # an existing user id

    with (
        patch("app.services.workspace_service.create_workspace", new=AsyncMock()) as create,
        patch("app.services.workspace_service.EmailService.send", new=AsyncMock()) as send,
    ):
        await sign_up_workspace(mock_db, _signup(), "http://api")

    create.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_up_workspace_when_new_email_then_stores_token_and_sends_welcome(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None
    owner = SimpleNamespace(id=uuid.uuid4(), first_name="Ana")

    with (
        patch("app.services.workspace_service.create_workspace", new=AsyncMock(return_value=(None, owner))),
        patch("app.services.workspace_service.store_magic_link_token", new=AsyncMock()) as store,
        patch("app.services.workspace_service.EmailService.send", new=AsyncMock()) as send,
    ):
        await sign_up_workspace(mock_db, _signup(kind="family"), "http://api")

    store.assert_awaited_once()
    assert store.await_args is not None
    assert store.await_args.args[1] == owner.id
    send.assert_awaited_once()
    assert send.await_args is not None
    kwargs = send.await_args.kwargs
    assert kwargs["to"] == "ana@example.com"
    assert kwargs["template"] == "workspace_welcome.html.jinja2"
    assert kwargs["ctx"]["kind"] == "family"
    assert str(kwargs["ctx"]["verify_url"]).startswith("http://api/api/v1/auth/magic-link/verify?token=")


@pytest.mark.asyncio
async def test_sign_up_workspace_when_email_send_fails_then_no_error_raised(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None
    owner = SimpleNamespace(id=uuid.uuid4(), first_name="Ana")

    with (
        patch("app.services.workspace_service.create_workspace", new=AsyncMock(return_value=(None, owner))),
        patch("app.services.workspace_service.store_magic_link_token", new=AsyncMock()),
        patch("app.services.workspace_service.EmailService.send", new=AsyncMock(side_effect=RuntimeError("down"))),
    ):
        await sign_up_workspace(mock_db, _signup(), "http://api")


@pytest.mark.asyncio
async def test_sign_up_workspace_when_curriculum_invalid_then_error_propagates(mock_db: MagicMock) -> None:
    mock_db.scalar.return_value = None

    with patch(
        "app.services.workspace_service.create_workspace",
        new=AsyncMock(side_effect=WorkspaceSignupError("Curriculum not available")),
    ):
        with pytest.raises(WorkspaceSignupError):
            await sign_up_workspace(mock_db, _signup(), "http://api")


# ── Student handles (decision D3) ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("school_type", "expected"),
    [(SchoolType.TEACHER_WORKSPACE, True), (SchoolType.FAMILY, True), (SchoolType.SCHOOL, False), (None, False)],
)
async def test_is_workspace_school_when_type_given_then_true_only_for_workspaces(
    mock_db: MagicMock, school_type: str | None, expected: bool
) -> None:
    mock_db.scalar.return_value = school_type

    assert await is_workspace_school(mock_db, uuid.uuid4()) is expected


@pytest.mark.parametrize(
    ("first_name", "expected_name"),
    [
        ("Emma", "emma"),
        ("José-María", "josemaria"),
        ("Mary Ann", "maryann"),
        ("Bartholomew-Alexander", "bartholomewa"),
        ("李明", "student"),
        ("  ", "student"),
    ],
)
def test_generate_student_handle_when_name_given_then_slug_plus_four_character_suffix(
    first_name: str, expected_name: str
) -> None:
    handle = generate_student_handle(first_name)

    name, suffix = handle.rsplit("-", 1)
    assert name == expected_name
    assert len(suffix) == 4
    assert set(suffix) <= set(HANDLE_SUFFIX_ALPHABET)


def test_generate_student_handle_when_generated_then_suffix_never_uses_ambiguous_characters() -> None:
    suffixes = "".join(generate_student_handle("Emma").rsplit("-", 1)[1] for _ in range(500))

    assert not set(suffixes) & set("0o1l")


def _username_collision() -> IntegrityError:
    return IntegrityError(
        "INSERT INTO users", {}, Exception('duplicate key value violates unique constraint "users_username_unique"')
    )


def _savepoints(mock_db: MagicMock) -> None:
    """Make db.begin_nested() an async context manager that lets exceptions through."""
    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock()
    savepoint.__aexit__ = AsyncMock(return_value=False)
    mock_db.begin_nested = MagicMock(return_value=savepoint)


def _build_student(school_id: uuid.UUID) -> Any:
    def build(username: str) -> User:
        return User(school_id=school_id, username=username, first_name="Emma", last_name="Lim", role=UserRole.STUDENT)

    return build


@pytest.mark.asyncio
async def test_add_user_with_generated_handle_when_no_collision_then_inserts_once(mock_db: MagicMock) -> None:
    _savepoints(mock_db)

    user = await add_user_with_generated_handle(mock_db, _build_student(uuid.uuid4()), "Emma")

    assert user.username is not None
    assert user.username.startswith("emma-")
    mock_db.add.assert_called_once_with(user)
    assert mock_db.begin_nested.call_count == 1


@pytest.mark.asyncio
async def test_add_user_with_generated_handle_when_handle_collides_then_retries_with_new_handle(
    mock_db: MagicMock,
) -> None:
    _savepoints(mock_db)
    mock_db.flush = AsyncMock(side_effect=[_username_collision(), None])

    user = await add_user_with_generated_handle(mock_db, _build_student(uuid.uuid4()), "Emma")

    assert mock_db.add.call_count == 2
    first, second = (call.args[0] for call in mock_db.add.call_args_list)
    assert second is user
    assert first is not second


@pytest.mark.asyncio
async def test_add_user_with_generated_handle_when_every_attempt_collides_then_raises_generic_error(
    mock_db: MagicMock,
) -> None:
    _savepoints(mock_db)
    mock_db.flush = AsyncMock(side_effect=[_username_collision() for _ in range(HANDLE_MAX_ATTEMPTS)])

    with pytest.raises(StudentHandleUnavailableError, match="Please try again") as raised:
        await add_user_with_generated_handle(mock_db, _build_student(uuid.uuid4()), "Emma")

    assert "emma" not in str(raised.value)
    assert mock_db.add.call_count == HANDLE_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_add_user_with_generated_handle_when_other_integrity_error_then_reraises_without_retry(
    mock_db: MagicMock,
) -> None:
    _savepoints(mock_db)
    email_taken = IntegrityError("INSERT INTO users", {}, Exception('unique constraint "users_email_unique"'))
    mock_db.flush = AsyncMock(side_effect=email_taken)

    with pytest.raises(IntegrityError):
        await add_user_with_generated_handle(mock_db, _build_student(uuid.uuid4()), "Emma")

    mock_db.add.assert_called_once()
