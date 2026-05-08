"""add_raw_llm_output_to_lesson_plans

Revision ID: ef92da49ff49
Revises: 7d0507c70479
Create Date: 2026-05-08 03:45:47.030652

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef92da49ff49"
down_revision: str | Sequence[str] | None = "7d0507c70479"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lesson_plans", sa.Column("raw_llm_output", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_plans", "raw_llm_output")
