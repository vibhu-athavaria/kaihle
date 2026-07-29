"""Add replaces_question_id to question_bank

Revision ID: 5d1bdf1ec743
Revises: dc843fdf3ba3
Create Date: 2026-07-28 22:23:13.617060

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5d1bdf1ec743"
down_revision: str | Sequence[str] | None = "dc843fdf3ba3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_bank",
        sa.Column(
            "replaces_question_id",
            sa.UUID(),
            sa.ForeignKey("question_bank.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_question_bank_replaces_question_id",
        "question_bank",
        ["replaces_question_id"],
        postgresql_where=sa.text("replaces_question_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_question_bank_replaces_question_id")
    op.drop_column("question_bank", "replaces_question_id")
