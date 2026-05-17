"""fix_subtopic_content_unique_constraint_add_interest_category

Mini-course generation creates 4 explanation rows per subtopic (one per interest
category). The existing unique index only covered (subtopic_id, content_type),
preventing insertion of the 2nd–4th rows. This migration adds interest_category_id
to the constraint so all four variants can coexist.

Revision ID: dadba0b9d91d
Revises: 9d1eb1706729
Create Date: 2026-05-17 13:01:18.777021

"""

from collections.abc import Sequence

from alembic import op


revision: str = "dadba0b9d91d"
down_revision: str | Sequence[str] | None = "9d1eb1706729"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_subtopic_content_active_explanation_per_subtopic")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subtopic_content_explanation_per_category
        ON subtopic_content (subtopic_id, content_type, interest_category_id)
        WHERE (content_type = 'explanation' AND is_active = true AND is_archived = false)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_subtopic_content_explanation_per_category")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subtopic_content_active_explanation_per_subtopic
        ON subtopic_content (subtopic_id, content_type)
        WHERE (content_type = 'explanation' AND is_active = true AND is_archived = false)
        """
    )
