"""add_class_topics_diagnostic_topic_ids_lesson_plan_changes

Revision ID: 6c27f332953a
Revises: f0134a1651ca
Create Date: 2026-05-02 11:20:11.469367

Changes:
  1. Create class_topics table (teacher-configured topic list per class)
  2. Add diagnostic_topic_ids to assessments (teacher-designed Tier 1 topics)
  3. Make lesson_plans.week_start nullable + drop lp_class_week_unique constraint
     (on-demand generation replaces weekly auto-gen)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6c27f332953a"
down_revision: str | Sequence[str] | None = "f0134a1651ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create class_topics
    op.create_table(
        "class_topics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("curriculum_topic_id", sa.UUID(), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("is_covered", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curriculum_topic_id"], ["curriculum_topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "curriculum_topic_id", name="uq_class_topic"),
    )

    # 2. Add diagnostic_topic_ids to assessments
    op.add_column(
        "assessments",
        sa.Column("diagnostic_topic_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
    )

    # 3. lesson_plans: make week_start nullable + drop unique constraint
    op.alter_column("lesson_plans", "week_start", existing_type=sa.DATE(), nullable=True)
    op.drop_constraint("lp_class_week_unique", "lesson_plans", type_="unique")


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse lesson_plans changes (re-add constraint requires no NULL rows)
    op.create_unique_constraint("lp_class_week_unique", "lesson_plans", ["class_id", "week_start"])
    op.alter_column("lesson_plans", "week_start", existing_type=sa.DATE(), nullable=False)

    # Drop diagnostic_topic_ids
    op.drop_column("assessments", "diagnostic_topic_ids")

    # Drop class_topics
    op.drop_table("class_topics")
