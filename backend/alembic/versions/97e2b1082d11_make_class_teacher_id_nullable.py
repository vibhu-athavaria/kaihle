"""make class teacher_id nullable

Revision ID: 97e2b1082d11
Revises: c1156cdb4c15
Create Date: 2026-04-24 18:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97e2b1082d11"
down_revision: str | Sequence[str] | None = "c1156cdb4c15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make teacher_id nullable on classes table."""
    op.alter_column(
        "classes",
        "teacher_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Make teacher_id non-nullable on classes table."""
    op.alter_column(
        "classes",
        "teacher_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
