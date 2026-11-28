"""Workspace rules: who owns a workspace and what a workspace may contain.

A workspace is a `schools` row whose type is TEACHER_WORKSPACE or FAMILY. It is owned by
exactly one user, who has role TEACHER, and who may act as the operator of that workspace
(create classes, create and manage students). All existing `school_id` isolation is unchanged.

The invariant that keeps isolation sound: a workspace contains its owner plus students and
nothing else. No second teacher, no SCHOOL_ADMIN, no PARENT. `assert_role_allowed_in_school`
is the single place that rule lives, and every user-creating service path calls it.
"""

import re
import secrets
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import mask_email
from app.core.security import create_magic_link_token, hash_password, hash_token, store_magic_link_token
from app.models.curriculum import Curriculum
from app.models.school import School, SchoolCurriculum, SchoolType
from app.models.user import TeacherProfile, User, UserRole
from app.schemas.workspace import WorkspaceSignupRequest
from app.services.email_service import EmailService

logger = structlog.get_logger()

# Same lifetime as an invite link (UserService.invite_user).
SIGNUP_LINK_EXPIRES_MINUTES = 72 * 60

_KIND_TO_TYPE: dict[str, SchoolType] = {
    "teacher": SchoolType.TEACHER_WORKSPACE,
    "family": SchoolType.FAMILY,
}

# Student handles (decision D3): usernames stay globally unique, so a workspace student gets
# a generated `firstname-xxxx` instead of a name the owner picks. The suffix alphabet leaves
# out 0, o, 1 and l, which children misread when typing their login.
HANDLE_NAME_MAX_LENGTH = 12
HANDLE_SUFFIX_LENGTH = 4
HANDLE_SUFFIX_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
HANDLE_FALLBACK_NAME = "student"
HANDLE_MAX_ATTEMPTS = 5
# Name of the unique constraint on users.username (migration 8a1b2c3d4e5f).
USERNAME_UNIQUE_CONSTRAINT = "users_username_unique"


class WorkspaceRestrictionError(Exception):
    """Raised when an action is not allowed inside a workspace. Routes map this to HTTP 403."""


class WorkspaceSignupError(Exception):
    """Raised when a signup request cannot be fulfilled (e.g. unknown curriculum). Routes map this to 400."""


class StudentHandleUnavailableError(ValueError):
    """Raised when every generated handle collided. Routes map ValueError to 409; the message is generic."""


@dataclass(frozen=True)
class WorkspaceContext:
    """What the UI needs to know about the caller's school."""

    workspace_type: str | None  # None for a real school
    is_owner: bool


async def is_workspace_owner(db: AsyncSession, user_id: uuid.UUID, school_id: uuid.UUID | None) -> bool:
    """True if `user_id` owns the workspace `school_id`. Always False for a real school."""
    if school_id is None:
        return False
    owner_id = await db.scalar(
        select(School.owner_user_id).where(
            School.id == school_id,
            School.type != SchoolType.SCHOOL,
        )
    )
    return owner_id is not None and owner_id == user_id


async def get_workspace_context(db: AsyncSession, user: User) -> WorkspaceContext:
    """Describe the caller's school for the /users/me response."""
    if user.school_id is None:
        return WorkspaceContext(workspace_type=None, is_owner=False)
    school = await db.get(School, user.school_id)
    if school is None or school.type == SchoolType.SCHOOL:
        return WorkspaceContext(workspace_type=None, is_owner=False)
    return WorkspaceContext(workspace_type=school.type, is_owner=school.owner_user_id == user.id)


async def is_workspace_school(db: AsyncSession, school_id: uuid.UUID) -> bool:
    """True if `school_id` is a workspace (TEACHER_WORKSPACE or FAMILY), False for a real or unknown school."""
    school_type = await db.scalar(select(School.type).where(School.id == school_id))
    return school_type is not None and school_type != SchoolType.SCHOOL


def generate_student_handle(first_name: str) -> str:
    """Return `slug(first_name)[:12]-xxxx` with a random suffix from HANDLE_SUFFIX_ALPHABET.

    Accents are folded to ASCII and everything but letters and digits is dropped. A name
    with nothing left (e.g. written only in a non-Latin script) uses HANDLE_FALLBACK_NAME.
    """
    folded = unicodedata.normalize("NFKD", first_name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]", "", folded.lower())[:HANDLE_NAME_MAX_LENGTH] or HANDLE_FALLBACK_NAME
    suffix = "".join(secrets.choice(HANDLE_SUFFIX_ALPHABET) for _ in range(HANDLE_SUFFIX_LENGTH))
    return f"{name}-{suffix}"


async def add_user_with_generated_handle(db: AsyncSession, build_user: Callable[[str], User], first_name: str) -> User:
    """Insert the user returned by `build_user(handle)`, retrying with a new handle on collision.

    Writes to the database. Each attempt runs in a savepoint, so a collision on
    users_username_unique rolls back only that insert and the caller's transaction stays
    usable. Any other integrity error (e.g. a taken email) is re-raised unchanged.
    """
    for attempt in range(1, HANDLE_MAX_ATTEMPTS + 1):
        user = build_user(generate_student_handle(first_name))
        try:
            async with db.begin_nested():
                db.add(user)
                await db.flush()
        except IntegrityError as exc:
            if USERNAME_UNIQUE_CONSTRAINT not in str(exc.orig):
                raise
            logger.info("student_handle_collision", school_id=str(user.school_id), attempt=attempt)
            continue
        logger.info("student_handle_generated", user_id=str(user.id), school_id=str(user.school_id), attempt=attempt)
        return user
    logger.error("student_handle_exhausted", school_id=str(user.school_id), attempts=HANDLE_MAX_ATTEMPTS)
    raise StudentHandleUnavailableError("Could not create the student. Please try again.")


async def assert_role_allowed_in_school(db: AsyncSession, school_id: uuid.UUID, role: str) -> None:
    """Enforce the one-operator invariant.

    A real school accepts any role. A workspace accepts students only: its single teacher is
    the owner, created by workspace signup, never through the user-creation paths.
    """
    school_type = await db.scalar(select(School.type).where(School.id == school_id))
    if school_type is None or school_type == SchoolType.SCHOOL:
        return
    if role != UserRole.STUDENT:
        raise WorkspaceRestrictionError("A workspace can only contain its owner and students.")


async def assert_class_teacher_allowed(db: AsyncSession, school_id: uuid.UUID, teacher_id: uuid.UUID) -> None:
    """In a workspace, every class is taught by the owner. A real school accepts any of its teachers."""
    school = await db.scalar(select(School).where(School.id == school_id))
    if school is None or school.type == SchoolType.SCHOOL:
        return
    if school.owner_user_id != teacher_id:
        raise WorkspaceRestrictionError("A workspace class must be taught by the workspace owner.")


async def assert_operator_may_manage_user(
    db: AsyncSession,
    actor_role: str,
    actor_id: uuid.UUID,
    school_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> None:
    """A workspace owner may edit or deactivate students in their own workspace, nothing else.

    SCHOOL_ADMIN and KAIHLE_ADMIN are unaffected. The owner may not edit themselves through
    this path (role, activation), and may not touch any non-student.
    """
    if actor_role != UserRole.TEACHER:
        return
    if not await is_workspace_owner(db, actor_id, school_id):
        raise WorkspaceRestrictionError("Only a workspace owner may manage users here.")
    target_role = await db.scalar(select(User.role).where(User.id == target_user_id, User.school_id == school_id))
    if target_role != UserRole.STUDENT:
        raise WorkspaceRestrictionError("A workspace owner may only manage students.")


def _default_workspace_name(kind: Literal["teacher", "family"], first_name: str, last_name: str) -> str:
    if kind == "family":
        return f"{last_name} family"
    return f"{first_name} {last_name}'s classroom"


async def create_workspace(db: AsyncSession, data: WorkspaceSignupRequest) -> tuple[School, User]:
    """Create a workspace school, its owner and its curriculum subscription. Writes to the DB.

    Everything is flushed in the caller's transaction, so a failure leaves nothing behind.
    The owner is an active TEACHER with an unusable random password: they set a real one
    through the magic link (CONSTITUTION Rule 10).

    Raises:
        WorkspaceSignupError: If the curriculum does not exist or is not active.
    """
    curriculum_active = await db.scalar(select(Curriculum.is_active).where(Curriculum.id == data.curriculum_id))
    if not curriculum_active:
        raise WorkspaceSignupError("Curriculum not available")

    school = School(
        name=data.workspace_name or _default_workspace_name(data.kind, data.first_name, data.last_name),
        slug=f"ws-{secrets.token_hex(4)}",
        country=data.country,
        city=data.city,
        timezone=data.timezone,
        status="active",
        type=_KIND_TO_TYPE[data.kind],
    )
    db.add(school)
    await db.flush()

    owner = User(
        school_id=school.id,
        email=data.email,
        hashed_password=hash_password(secrets.token_hex(32)),
        role=UserRole.TEACHER,
        first_name=data.first_name,
        last_name=data.last_name,
        is_active=True,
        must_change_password=False,
    )
    db.add(owner)
    await db.flush()

    # The owner row exists now, so the workspace can point at it.
    school.owner_user_id = owner.id
    db.add(TeacherProfile(user_id=owner.id, qualifications={"subjects": []}))
    db.add(SchoolCurriculum(school_id=school.id, curriculum_id=data.curriculum_id, is_primary=True))
    await db.flush()

    logger.info(
        "workspace_created",
        school_id=str(school.id),
        owner_user_id=str(owner.id),
        workspace_type=school.type,
        email=mask_email(owner.email),
    )
    return school, owner


async def sign_up_workspace(db: AsyncSession, data: WorkspaceSignupRequest, base_url: str) -> None:
    """Self-serve signup: create the workspace and email the owner a password-setup link.

    Side effects: DB writes (via create_workspace and the magic-link token) and one email.
    An email that is already registered creates nothing and sends nothing, and the caller
    returns the same response as for a new signup, so the endpoint does not reveal accounts.

    Raises:
        WorkspaceSignupError: If the request cannot be fulfilled (see create_workspace).
    """
    existing = await db.scalar(select(User.id).where(User.email == data.email))
    if existing is not None:
        logger.info("workspace_signup_email_taken", email=mask_email(data.email))
        return

    _, owner = await create_workspace(db, data)

    token = create_magic_link_token(owner.id, expires_in_minutes=SIGNUP_LINK_EXPIRES_MINUTES)
    await store_magic_link_token(db, owner.id, hash_token(token), expires_minutes=SIGNUP_LINK_EXPIRES_MINUTES)
    verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"
    try:
        await EmailService().send(
            to=data.email,
            subject="Welcome to Kaihle: set up your account",
            template="workspace_welcome.html.jinja2",
            ctx={"first_name": owner.first_name, "verify_url": verify_url, "kind": data.kind},
        )
    except Exception as e:
        # Same policy as invites: the account stays, and the owner can request a new magic link.
        logger.error(
            "workspace_welcome_email_failed",
            user_id=str(owner.id),
            error_type=type(e).__name__,
            error_message=str(e),
        )
