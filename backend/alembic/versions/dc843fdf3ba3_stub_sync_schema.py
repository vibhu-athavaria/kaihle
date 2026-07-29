"""stub: sync schema (school_id, submitted_by, review_status)

This migration was applied directly to the database on a different branch.
This stub preserves the revision chain without re-applying the changes.

Revision ID: dc843fdf3ba3
Revises: f892502b0975
Create Date: 2026-07-28 22:23:13.617060

"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "dc843fdf3ba3"
down_revision: str | Sequence[str] | None = "f892502b0975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Already applied to the database."""
    pass


def downgrade() -> None:
    """No-op — the original migration would need to reverse school_id, submitted_by, review_status."""
    pass
