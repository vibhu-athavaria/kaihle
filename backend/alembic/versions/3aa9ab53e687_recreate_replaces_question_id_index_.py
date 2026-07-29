"""Recreate replaces_question_id index CONCURRENTLY

Prior migration created the index with a SHARE lock. This migration drops
and recreates it using CONCURRENTLY to avoid blocking writes on a
populated production table.

Revision ID: 3aa9ab53e687
Revises: cf3123e3e24a
Create Date: 2026-07-29 16:49:46.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3aa9ab53e687"
down_revision: str | Sequence[str] | None = "cf3123e3e24a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old index (brief ACCESS EXCLUSIVE lock on the index)
    op.drop_index("ix_question_bank_replaces_question_id")

    # Recreate with CONCURRENTLY — autocommit_block commits the outer
    # transaction so CREATE INDEX CONCURRENTLY runs outside it,
    # preventing write locks on the table during the index build.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_question_bank_replaces_question_id",
            "question_bank",
            ["replaces_question_id"],
            postgresql_where=sa.text("replaces_question_id IS NOT NULL"),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    op.drop_index("ix_question_bank_replaces_question_id")
    op.create_index(
        "ix_question_bank_replaces_question_id",
        "question_bank",
        ["replaces_question_id"],
        postgresql_where=sa.text("replaces_question_id IS NOT NULL"),
    )
