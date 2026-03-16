"""Make users.school_id nullable for KaihleAdmin users.

KaihleAdmin is a platform-level role with no school affiliation.
All other roles (STUDENT, TEACHER, SCHOOL_ADMIN, PARENT) must have school_id.
Enforced by CHECK constraint.

Revision ID: 004_user_school_id_nullable
Revises: 003_onboarding_status_migration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_user_school_id_nullable"
down_revision: str | None = "003_onboarding_status_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "school_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_constraint("users_school_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_school_id_fkey",
        "users",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "chk_user_school_id_required",
        "users",
        "role = 'KAIHLE_ADMIN' OR school_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("chk_user_school_id_required", "users", type_="check")
    op.drop_constraint("users_school_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_school_id_fkey",
        "users",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "users",
        "school_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
