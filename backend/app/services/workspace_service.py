"""Workspace rules: who owns a workspace and what a workspace may contain.

A workspace is a `schools` row whose type is TEACHER_WORKSPACE or FAMILY. It is owned by
exactly one user, who has role TEACHER, and who may act as the operator of that workspace
(create classes, create and manage students). All existing `school_id` isolation is unchanged.

The invariant that keeps isolation sound: a workspace contains its owner plus students and
nothing else. No second teacher, no SCHOOL_ADMIN, no PARENT. `assert_role_allowed_in_school`
is the single place that rule lives, and every user-creating service path calls it.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School, SchoolType
from app.models.user import User, UserRole


class WorkspaceRestrictionError(Exception):
    """Raised when an action is not allowed inside a workspace. Routes map this to HTTP 403."""


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


async def assert_role_allowed_in_school(db: AsyncSession, school_id: uuid.UUID, role: str) -> None:
    """Enforce the one-operator invariant.

    A real school accepts any role. A workspace accepts students only: its single teacher is
    the owner, created by workspace signup, never through the user-creation paths.
    """
    school_type = await db.scalar(select(School.type).where(School.id == school_id))
    # A missing school is not this rule's concern: every caller looks the school up itself
    # and reports it (404 or ValueError). Returning here keeps one owner for that error.
    if school_type is None or school_type == SchoolType.SCHOOL:
        return
    if role != UserRole.STUDENT:
        raise WorkspaceRestrictionError("A workspace can only contain its owner and students.")


async def assert_class_teacher_allowed(db: AsyncSession, school_id: uuid.UUID, teacher_id: uuid.UUID) -> None:
    """In a workspace, every class is taught by the owner. A real school accepts any of its teachers."""
    school = await db.scalar(select(School).where(School.id == school_id))
    # Same as assert_role_allowed_in_school: a missing school is reported by the caller.
    # ClassService only reaches this after finding the teacher in `school_id`, so the school
    # exists on that path.
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
    # No such user in this workspace: possibly another tenant's user. Stays 403, not 404, so
    # the response does not reveal whether the id exists elsewhere (CONSTITUTION section 7).
    if target_role is None:
        raise WorkspaceRestrictionError("No such student in this workspace.")
    if target_role != UserRole.STUDENT:
        raise WorkspaceRestrictionError("A workspace owner may only manage students.")
