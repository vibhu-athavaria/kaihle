"""fix_subtopic_content_curriculum_indexes_schema_drift

Corrects schema drift introduced by migration a00c6f3018c6 + a stale T5 migration.

What happened:
1. Migration a00c6f3018c6 (2026-05-22) deleted 3 of 4 interest-category explanation
   variants per subtopic, then created uq_subtopic_content_type (subtopic_id, content_type).
2. The T5 migration 324975e5c767 was edited after being applied to the DB. The version
   that actually ran created uq_subtopic_content_curriculum — a partial unique index on
   (subtopic_id, content_type) WHERE scope='curriculum', which blocks insertion of more
   than one interest-category variant per subtopic for curriculum-scoped content.
3. The correctly-split indexes uq_subtopic_content_curriculum_generic and
   uq_subtopic_content_curriculum_personalised were never created in the live DB.
4. uq_subtopic_content_explanation_per_category (from dadba0b9d91d) was never dropped.

This migration corrects the live DB to match what the T5 migration file currently states:
  - Drops uq_subtopic_content_curriculum (the overly-strict one)
  - Drops uq_subtopic_content_explanation_per_category (stale, should have been removed by T5)
  - Creates uq_subtopic_content_curriculum_generic
  - Creates uq_subtopic_content_curriculum_personalised

After applying this, mini-course generation can insert all 4 interest-category variants
per subtopic without unique constraint violations.

Revision ID: 7ff9ea130a9e
Revises: 6b9d2df42b5d
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ff9ea130a9e"
down_revision: str | Sequence[str] | None = "6b9d2df42b5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace the wrong curriculum unique index with the correct split indexes."""
    # Drop the overly-strict index — blocks all interest-category variants beyond the first.
    op.execute("DROP INDEX IF EXISTS uq_subtopic_content_curriculum")

    # Drop the stale per-category explanation index left over from dadba0b9d91d.
    op.execute("DROP INDEX IF EXISTS uq_subtopic_content_explanation_per_category")

    # Curriculum generic rows (video, quiz, practice — interest_category_id IS NULL):
    # one row per (subtopic_id, content_type).
    # IF NOT EXISTS — safe on a fresh DB where T5 already created this index correctly.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_subtopic_content_curriculum_generic
        ON subtopic_content (subtopic_id, content_type)
        WHERE scope = 'curriculum' AND interest_category_id IS NULL
        """
    )

    # Curriculum personalised explanation rows (interest_category_id IS NOT NULL):
    # one row per (subtopic_id, content_type, interest_category_id).
    # Allows all 4 interest-category variants to coexist per subtopic.
    # IF NOT EXISTS — safe on a fresh DB where T5 already created this index correctly.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_subtopic_content_curriculum_personalised
        ON subtopic_content (subtopic_id, content_type, interest_category_id)
        WHERE scope = 'curriculum' AND interest_category_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Revert to the (wrong) curriculum index state from the stale T5 run."""
    op.drop_index("uq_subtopic_content_curriculum_personalised", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_curriculum_generic", table_name="subtopic_content")

    op.execute(
        """
        CREATE UNIQUE INDEX uq_subtopic_content_curriculum
        ON subtopic_content (subtopic_id, content_type)
        WHERE (scope = 'curriculum')
        """
    )
