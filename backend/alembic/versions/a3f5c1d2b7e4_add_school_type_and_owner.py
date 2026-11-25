"""add schools.type and schools.owner_user_id

Revision ID: a3f5c1d2b7e4
Revises: 7bd6c759f6c6
Create Date: 2026-11-25 09:00:00.000000

Adds the workspace concept: every school row is a SCHOOL (all existing rows),
a TEACHER_WORKSPACE or a FAMILY. A workspace is owned by exactly one user.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f5c1d2b7e4"
down_revision: str | Sequence[str] | None = "7bd6c759f6c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills every existing row as a real school.
    op.add_column(
        "schools",
        sa.Column("type", sa.String(length=20), server_default="SCHOOL", nullable=False),
    )
    # Nullable on purpose: NULL for type SCHOOL, and for a workspace only until its owner is created.
    op.add_column(
        "schools",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "chk_school_type",
        "schools",
        "type IN ('SCHOOL', 'TEACHER_WORKSPACE', 'FAMILY')",
    )
    op.create_foreign_key(
        "fk_schools_owner_user_id",
        "schools",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_schools_type", "schools", ["type"], unique=False)
    op.create_index(
        "uq_schools_owner_user_id",
        "schools",
        ["owner_user_id"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Destructive for workspaces: dropping `type` makes any workspace look like a real school.
    Only downgrade before workspace signup has been enabled.
    """
    op.drop_index(
        "uq_schools_owner_user_id", table_name="schools", postgresql_where=sa.text("owner_user_id IS NOT NULL")
    )
    op.drop_index("idx_schools_type", table_name="schools")
    op.drop_constraint("fk_schools_owner_user_id", "schools", type_="foreignkey")
    op.drop_constraint("chk_school_type", "schools", type_="check")
    op.drop_column("schools", "owner_user_id")
    op.drop_column("schools", "type")
