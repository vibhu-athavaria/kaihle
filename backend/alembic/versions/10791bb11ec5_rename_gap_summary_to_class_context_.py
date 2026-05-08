"""rename_gap_summary_to_class_context_snapshot

Revision ID: 10791bb11ec5
Revises: 98c68d319d1b
Create Date: 2026-05-08 08:42:03.346288

"""

from alembic import op

revision: str = "10791bb11ec5"
down_revision = "98c68d319d1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("lesson_plans", "gap_summary", new_column_name="class_context_snapshot")


def downgrade() -> None:
    op.alter_column("lesson_plans", "class_context_snapshot", new_column_name="gap_summary")
