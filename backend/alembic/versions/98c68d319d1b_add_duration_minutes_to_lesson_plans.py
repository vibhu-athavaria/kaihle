"""add_duration_minutes_to_lesson_plans

Revision ID: 98c68d319d1b
Revises: ef92da49ff49
Create Date: 2026-05-08 06:10:28.067716

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "98c68d319d1b"
down_revision: str | Sequence[str] | None = "ef92da49ff49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lesson_plans",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="45"),
    )


def downgrade() -> None:
    op.drop_column("lesson_plans", "duration_minutes")
