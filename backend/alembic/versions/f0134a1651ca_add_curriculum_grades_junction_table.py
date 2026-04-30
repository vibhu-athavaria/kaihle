"""add curriculum_grades junction table

Revision ID: f0134a1651ca
Revises: c52a75bcdfcf
Create Date: 2026-04-30 17:55:51.252960

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f0134a1651ca"
down_revision: str | Sequence[str] | None = "c52a75bcdfcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_grades",
        sa.Column("curriculum_id", sa.UUID(), nullable=False),
        sa.Column("grade_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["curriculum_id"], ["curricula.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grade_id"], ["grades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("curriculum_id", "grade_id"),
    )

    # Secondary index for fast DELETE by grade_id during full-replace updates
    op.create_index("idx_curriculum_grades_grade_id", "curriculum_grades", ["grade_id"])

    # Backfill from curriculum_topics — derives existing grade–curriculum associations
    # from real topic placements. Pure SQL, no service calls (Constitution Rule 9).
    # Subquery deduplicates (curriculum_id, grade_id) pairs first so ROW_NUMBER()
    # is applied to the clean distinct set, not to individual topic rows.
    op.execute("""
        INSERT INTO curriculum_grades (curriculum_id, grade_id, sort_order)
        SELECT
            curriculum_id,
            grade_id,
            ROW_NUMBER() OVER (PARTITION BY curriculum_id ORDER BY grade_level) AS sort_order
        FROM (
            SELECT DISTINCT ct.curriculum_id, ct.grade_id, g.level AS grade_level
            FROM curriculum_topics ct
            JOIN grades g ON g.id = ct.grade_id
        ) distinct_pairs
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_curriculum_grades_grade_id", table_name="curriculum_grades")
    op.drop_table("curriculum_grades")
