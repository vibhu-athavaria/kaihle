"""Update chk_qb_source to allow llm-correction, widen source column

Revision ID: cf3123e3e24a
Revises: 5d1bdf1ec743
Create Date: 2026-07-29 09:54:31.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "cf3123e3e24a"
down_revision: str | Sequence[str] | None = "5d1bdf1ec743"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Widen column to accommodate 'llm-correction' (14 chars)
    op.alter_column(
        "question_bank",
        "source",
        type_=sa.String(20),
        existing_type=sa.String(10),
        nullable=False,
    )
    # Update constraint to allow the new value
    op.execute("ALTER TABLE question_bank DROP CONSTRAINT IF EXISTS chk_qb_source")
    op.execute(
        "ALTER TABLE question_bank ADD CONSTRAINT chk_qb_source CHECK (source IN ('bank', 'llm', 'llm-correction'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE question_bank DROP CONSTRAINT IF EXISTS chk_qb_source")
    op.execute("ALTER TABLE question_bank ADD CONSTRAINT chk_qb_source CHECK (source IN ('bank', 'llm'))")
    op.alter_column(
        "question_bank",
        "source",
        type_=sa.String(10),
        existing_type=sa.String(20),
        nullable=False,
    )
