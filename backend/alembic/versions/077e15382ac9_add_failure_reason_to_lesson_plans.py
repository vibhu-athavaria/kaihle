"""add failure_reason to lesson_plans

Revision ID: 077e15382ac9
Revises: bc39ab8bf954
Create Date: 2026-05-07

"""

from alembic import op
import sqlalchemy as sa

revision = "077e15382ac9"
down_revision = "bc39ab8bf954"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lesson_plans",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lesson_plans", "failure_reason")
