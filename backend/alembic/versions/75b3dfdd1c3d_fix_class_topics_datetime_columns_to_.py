"""fix class_topics datetime columns to timestamptz

Revision ID: 75b3dfdd1c3d
Revises: 6c27f332953a
Create Date: 2026-05-02 15:47:29.159657

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "75b3dfdd1c3d"
down_revision: str | Sequence[str] | None = "6c27f332953a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "class_topics",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "class_topics",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "class_topics",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "class_topics",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
