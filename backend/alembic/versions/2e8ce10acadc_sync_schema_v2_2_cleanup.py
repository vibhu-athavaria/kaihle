"""sync_schema_v2_2_cleanup — SUPERSEDED

This migration was replaced by schema_v2_2_sync.
It is kept as a no-op to preserve the revision chain.

Revision ID: 2e8ce10acadc
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15 07:52:27.435427

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "2e8ce10acadc"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op — superseded by schema_v2_2_sync."""
    pass


def downgrade() -> None:
    """No-op — superseded by schema_v2_2_sync."""
    pass
