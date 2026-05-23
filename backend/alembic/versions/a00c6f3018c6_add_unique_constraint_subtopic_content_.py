"""add unique constraint subtopic content type

Revision ID: a00c6f3018c6
Revises: a3224e7f4bd5
Create Date: 2026-05-22 09:20:51.291301

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a00c6f3018c6"
down_revision: str | Sequence[str] | None = "a3224e7f4bd5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Delete duplicate rows, keeping the most recently updated one per (subtopic_id, content_type).
    op.execute(
        """
        DELETE FROM subtopic_content
        WHERE id NOT IN (
            SELECT DISTINCT ON (subtopic_id, content_type) id
            FROM subtopic_content
            ORDER BY subtopic_id, content_type, updated_at DESC NULLS LAST
        )
        """
    )
    op.create_unique_constraint("uq_subtopic_content_type", "subtopic_content", ["subtopic_id", "content_type"])


def downgrade() -> None:
    op.drop_constraint("uq_subtopic_content_type", "subtopic_content", type_="unique")
