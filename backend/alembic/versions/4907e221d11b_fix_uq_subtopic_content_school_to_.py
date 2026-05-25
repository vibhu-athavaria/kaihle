"""fix uq_subtopic_content_school to include interest_category_id

Revision ID: 4907e221d11b
Revises: 7ff9ea130a9e
Create Date: 2026-05-25 05:25:51.030065

Background:
    The original uq_subtopic_content_school index was (subtopic_id, content_type, school_id)
    WHERE scope='school'. This prevented more than one school-scoped row per
    (subtopic_id, content_type) per school, which conflicts with the mini-course
    generation flow that creates 4 interest-category variants per subtopic.

    The fix:
    1. Drop the old partial unique index.
    2. Create a new one that includes interest_category_id.
    3. Backfill existing rows that were generated with scope='curriculum' due to
       the missing school_id write bug — set them to scope='school' with the
       correct school_id derived from the reviewing teacher's school.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4907e221d11b"
down_revision: str | Sequence[str] | None = "7ff9ea130a9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop old school-scoped unique index, create new one with interest_category_id.

    Also backfills existing rows that were generated with scope='curriculum'
    (school_id=NULL, interest_category_id IS NOT NULL, reviewed_by_id IS NOT NULL)
    by deriving the correct school_id from the reviewing teacher's school.
    """
    # 1. Drop the old partial unique index
    op.drop_index("uq_subtopic_content_school", table_name="subtopic_content")

    # 2. Create the new partial unique index including interest_category_id
    op.create_index(
        "uq_subtopic_content_school",
        "subtopic_content",
        ["subtopic_id", "content_type", "school_id", "interest_category_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'school'"),
    )

    # 3. Backfill rows that were created with scope='curriculum' by the
    #    mini-course generation bug (school_id=NULL, interest_category_id set,
    #    reviewed_by_id set — meaning a teacher approved them).
    #    Derive the correct school_id from the teacher's school.
    op.execute(
        sa.text("""
            UPDATE subtopic_content sc
            SET
                scope = 'school',
                school_id = u.school_id
            FROM users u
            WHERE
                sc.scope = 'curriculum'
                AND sc.school_id IS NULL
                AND sc.interest_category_id IS NOT NULL
                AND sc.reviewed_by_id IS NOT NULL
                AND u.id = sc.reviewed_by_id
                AND u.school_id IS NOT NULL
        """)
    )


def downgrade() -> None:
    """Revert to the original school-scoped unique index (without interest_category_id).

    Note: this does NOT undo the scope backfill — those rows remain school-scoped.
    """
    op.drop_index("uq_subtopic_content_school", table_name="subtopic_content")

    op.create_index(
        "uq_subtopic_content_school",
        "subtopic_content",
        ["subtopic_id", "content_type", "school_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'school'"),
    )
