"""add_password_reset_auth_token_type

Revision ID: 4d34a27f17df
Revises: 75b3dfdd1c3d
Create Date: 2026-05-06 11:11:28.545622

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4d34a27f17df"
down_revision: str | Sequence[str] | None = "75b3dfdd1c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add PASSWORD_RESET to the auth_token_type PG ENUM."""
    op.execute("ALTER TYPE auth_token_type ADD VALUE IF NOT EXISTS 'PASSWORD_RESET'")


def downgrade() -> None:
    # PG ENUM values cannot be removed without rebuilding the table.
    # Downgrade is a no-op; remove rows with type='PASSWORD_RESET' manually if needed.
    pass
