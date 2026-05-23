"""add scope and school_id to subtopic_content

Revision ID: 324975e5c767
Revises: a00c6f3018c6
Create Date: 2026-05-23 06:12:46.588845

Architecture:
- scope='curriculum': KaihleAdmin-owned global content (school_id=NULL)
- scope='school': Teacher-generated content for a specific school (school_id set)

The old uq_subtopic_content_type unique constraint (subtopic_id, content_type)
is replaced with two partial unique indexes that enforce the right uniqueness rule
per scope, allowing both a curriculum row and a school row to coexist for the same
(subtopic_id, content_type) pair.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "324975e5c767"
down_revision: str | Sequence[str] | None = "a00c6f3018c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add scope + school_id columns; replace old unique constraint with partial indexes."""
    # Create enum type before adding column.
    # DO block catches duplicate_object so this is safe to run on a DB that already has the type.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE subtopic_content_scope_enum AS ENUM ('curriculum', 'school');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.add_column(
        "subtopic_content",
        sa.Column(
            "scope",
            sa.Enum("curriculum", "school", name="subtopic_content_scope_enum", create_type=False),
            server_default="curriculum",
            nullable=False,
        ),
    )
    op.add_column(
        "subtopic_content",
        sa.Column("school_id", sa.UUID(), nullable=True),
    )

    # Replace old (subtopic_id, content_type) unique constraint with partial indexes.
    op.drop_constraint("uq_subtopic_content_type", "subtopic_content", type_="unique")

    # Drop the per-category explanation index from dadba0b9d91d — its role is superseded
    # by the two curriculum partial indexes below.
    op.drop_index("uq_subtopic_content_explanation_per_category", table_name="subtopic_content")

    # Curriculum generic rows (video, quiz, practice — interest_category_id IS NULL):
    # one row per (subtopic_id, content_type).
    op.create_index(
        "uq_subtopic_content_curriculum_generic",
        "subtopic_content",
        ["subtopic_id", "content_type"],
        unique=True,
        postgresql_where="scope = 'curriculum' AND interest_category_id IS NULL",
    )
    # Curriculum personalised explanation rows (interest_category_id IS NOT NULL):
    # one row per (subtopic_id, content_type, interest_category_id).
    op.create_index(
        "uq_subtopic_content_curriculum_personalised",
        "subtopic_content",
        ["subtopic_id", "content_type", "interest_category_id"],
        unique=True,
        postgresql_where="scope = 'curriculum' AND interest_category_id IS NOT NULL",
    )
    op.create_index(
        "uq_subtopic_content_school",
        "subtopic_content",
        ["subtopic_id", "content_type", "school_id"],
        unique=True,
        postgresql_where="scope = 'school'",
    )

    # Regular indexes for filtering
    op.create_index("ix_subtopic_content_scope", "subtopic_content", ["scope"], unique=False)
    op.create_index("ix_subtopic_content_school_id", "subtopic_content", ["school_id"], unique=False)

    # Foreign key to schools (nullable — NULL for curriculum-scope rows)
    op.create_foreign_key(
        "fk_subtopic_content_school_id",
        "subtopic_content",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Restore original unique constraint; drop scope + school_id columns."""
    op.drop_constraint("fk_subtopic_content_school_id", "subtopic_content", type_="foreignkey")
    op.drop_index("ix_subtopic_content_school_id", table_name="subtopic_content")
    op.drop_index("ix_subtopic_content_scope", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_school", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_curriculum_personalised", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_curriculum_generic", table_name="subtopic_content")

    # Restore the per-category explanation index that was active before this migration.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subtopic_content_explanation_per_category
        ON subtopic_content (subtopic_id, content_type, interest_category_id)
        WHERE (content_type = 'explanation' AND is_active = true AND is_archived = false)
        """
    )

    op.create_unique_constraint("uq_subtopic_content_type", "subtopic_content", ["subtopic_id", "content_type"])

    op.drop_column("subtopic_content", "school_id")
    op.drop_column("subtopic_content", "scope")

    op.execute("DROP TYPE IF EXISTS subtopic_content_scope_enum")
