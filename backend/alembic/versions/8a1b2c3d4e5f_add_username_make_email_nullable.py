"""add username column, make email nullable

Revision ID: 8a1b2c3d4e5f
Revises: f892502b0975
Create Date: 2026-07-29 16:00:00.000000

Adds a nullable unique username column to users table.
Makes email column nullable (drops NOT NULL, keeps UNIQUE).
Adds a unique index on username for fast lookups.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "3aa9ab53e687"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable username column
    op.add_column("users", sa.Column("username", sa.String(100), nullable=True))
    op.create_unique_constraint("users_username_unique", "users", ["username"])
    op.create_index("idx_users_username", "users", ["username"])

    # Make email nullable — drop NOT NULL, keep UNIQUE constraint
    op.alter_column("users", "email", nullable=True)


def downgrade() -> None:
    # Revert email to NOT NULL
    op.alter_column("users", "email", nullable=False)

    # Remove username column
    op.drop_index("idx_users_username", table_name="users")
    op.drop_constraint("users_username_unique", "users", type_="unique")
    op.drop_column("users", "username")
