"""add username column, make email nullable

Revision ID: 8a1b2c3d4e5f
Revises: 3aa9ab53e687
Create Date: 2026-07-29 16:00:00.000000

Adds a nullable unique username column to users table.
Makes email column nullable (drops NOT NULL, keeps UNIQUE).
Creates username index using CONCURRENTLY to avoid write locks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "3aa9ab53e687"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable username column — metadata-only operation, no table rewrite
    op.add_column("users", sa.Column("username", sa.String(100), nullable=True))
    op.create_unique_constraint("users_username_unique", "users", ["username"])

    # Make email nullable — metadata-only operation
    op.alter_column("users", "email", nullable=True)

    # Create index with CONCURRENTLY — autocommit_block commits the outer
    # transaction so CREATE INDEX CONCURRENTLY runs outside it,
    # preventing write locks on the table during the index build.
    with op.get_context().autocommit_block():
        op.create_index(
            "idx_users_username",
            "users",
            ["username"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    # Drop index (brief ACCESS EXCLUSIVE lock on the index)
    op.drop_index("idx_users_username", table_name="users")

    # Revert email to NOT NULL
    op.alter_column("users", "email", nullable=False)

    # Remove username column
    op.drop_constraint("users_username_unique", "users", type_="unique")
    op.drop_column("users", "username")
