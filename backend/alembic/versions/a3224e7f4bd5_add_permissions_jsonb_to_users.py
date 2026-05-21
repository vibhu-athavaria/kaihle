"""add permissions jsonb to users

Revision ID: a3224e7f4bd5
Revises: dadba0b9d91d
Create Date: 2026-05-21 00:00:00.000000

NULL = all permission defaults apply (open by default, restrict explicitly).
No backfill needed — NULL is handled by has_permission() as full access.
Adding a nullable column is a metadata-only operation in PostgreSQL (no table rewrite).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3224e7f4bd5"
down_revision: str | Sequence[str] | None = "dadba0b9d91d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("permissions", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "permissions")
