"""lesson_plan_generating_status_nullable_week_start

Revision ID: bc39ab8bf954
Revises: 4d34a27f17df
Create Date: 2026-05-06 13:42:00.965037

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str | Sequence[str] = "bc39ab8bf954"
down_revision: str | Sequence[str] | None = "4d34a27f17df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add GENERATING value to the lesson_plan_status native PG enum.
    # ALTER TYPE ADD VALUE cannot run in the same transaction as a column default
    # that uses the new value — commit first, then alter the default.
    op.execute("ALTER TYPE lesson_plan_status ADD VALUE IF NOT EXISTS 'GENERATING'")
    op.execute("COMMIT")

    # Update the default from GENERATED to GENERATING for new rows.
    op.alter_column(
        "lesson_plans",
        "status",
        server_default=sa.text("'GENERATING'::lesson_plan_status"),
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values (no DROP VALUE).
    # Reset server default only.
    op.alter_column(
        "lesson_plans",
        "status",
        server_default=sa.text("'GENERATED'::lesson_plan_status"),
    )
