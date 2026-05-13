"""assessment_schema_v2_replace_config_with_typed_columns

Replaces the config JSONB blob and dead columns (is_system_generated,
diagnostic_topic_ids, curriculum_topic_id) with properly-typed columns.
Adds assessment_topic_config junction table for per-assessment topic selection.

Revision ID: 4a43084e7ad5
Revises: 10791bb11ec5
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4a43084e7ad5"
down_revision: str | Sequence[str] | None = "10791bb11ec5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. Add new typed columns (nullable first so existing rows are valid) ──

    op.add_column(
        "assessments",
        sa.Column("questions_per_topic", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("minimum_difficulty", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("maximum_difficulty", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column(
            "question_types",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "assessments",
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
    )

    # ── 2. Backfill from config JSONB before dropping it ──────────────────────

    op.execute("""
        UPDATE assessments
        SET minimum_difficulty = COALESCE(
            ((config->'difficulty_range'->>0)::int),
            1
        )
        WHERE config IS NOT NULL
    """)

    op.execute("""
        UPDATE assessments
        SET maximum_difficulty = COALESCE(
            ((config->'difficulty_range'->>1)::int),
            5
        )
        WHERE config IS NOT NULL
    """)

    op.execute("""
        UPDATE assessments
        SET question_types = ARRAY(
            SELECT jsonb_array_elements_text(config->'question_types')
        )
        WHERE config IS NOT NULL
          AND config ? 'question_types'
          AND jsonb_array_length(config->'question_types') > 0
    """)

    op.execute("""
        UPDATE assessments
        SET time_limit_minutes = COALESCE(
            NULLIF(config->>'time_limit_minutes', 'null')::int,
            0
        )
        WHERE config IS NOT NULL
    """)

    # Default any rows that still have NULL (e.g. config was NULL or empty)
    op.execute("UPDATE assessments SET minimum_difficulty = 1 WHERE minimum_difficulty IS NULL")
    op.execute("UPDATE assessments SET maximum_difficulty = 5 WHERE maximum_difficulty IS NULL")
    op.execute("UPDATE assessments SET question_types = ARRAY['MCQ','TRUE_FALSE'] WHERE question_types IS NULL")
    op.execute("UPDATE assessments SET time_limit_minutes = 0 WHERE time_limit_minutes IS NULL")
    op.execute("UPDATE assessments SET questions_per_topic = 2 WHERE questions_per_topic IS NULL")

    # ── 3. Create assessment_topic_config and backfill from diagnostic_topic_ids

    op.create_table(
        "assessment_topic_config",
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_topic_id"],
            ["curriculum_topics.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["grade_id"],
            ["grades.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("assessment_id", "curriculum_topic_id"),
    )
    op.create_index("idx_atc_assessment", "assessment_topic_config", ["assessment_id"])

    op.execute("""
        INSERT INTO assessment_topic_config (assessment_id, curriculum_topic_id, grade_id)
        SELECT
            a.id,
            t.topic_id,
            ct.grade_id
        FROM assessments a
        CROSS JOIN LATERAL UNNEST(a.diagnostic_topic_ids) AS t(topic_id)
        JOIN curriculum_topics ct ON ct.id = t.topic_id
        WHERE a.diagnostic_topic_ids IS NOT NULL
          AND array_length(a.diagnostic_topic_ids, 1) > 0
        ON CONFLICT DO NOTHING
    """)

    # ── 4. Make new columns NOT NULL and add constraints ──────────────────────

    op.alter_column("assessments", "questions_per_topic", nullable=False)
    op.alter_column("assessments", "minimum_difficulty", nullable=False)
    op.alter_column("assessments", "maximum_difficulty", nullable=False)
    op.alter_column("assessments", "question_types", nullable=False)
    op.alter_column("assessments", "time_limit_minutes", nullable=False)

    op.create_check_constraint("chk_assessment_min_diff", "assessments", "minimum_difficulty >= 1")
    op.create_check_constraint("chk_assessment_max_diff", "assessments", "maximum_difficulty <= 5")
    op.create_check_constraint("chk_assessment_qpt", "assessments", "questions_per_topic >= 1")
    op.create_check_constraint("chk_assessment_time_limit", "assessments", "time_limit_minutes >= 0")

    # ── 5. Drop dead columns ──────────────────────────────────────────────────

    op.drop_constraint("assessments_curriculum_topic_id_fkey", "assessments", type_="foreignkey")
    op.drop_column("assessments", "config")
    op.drop_column("assessments", "is_system_generated")
    op.drop_column("assessments", "diagnostic_topic_ids")
    op.drop_column("assessments", "curriculum_topic_id")


def downgrade() -> None:
    # Restore dropped columns as nullable (data loss on downgrade is intentional)
    op.add_column(
        "assessments",
        sa.Column("config", postgresql.JSONB(), nullable=True, server_default="{}"),
    )
    op.add_column(
        "assessments",
        sa.Column("is_system_generated", sa.Boolean(), nullable=True, server_default="false"),
    )
    op.add_column(
        "assessments",
        sa.Column(
            "diagnostic_topic_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
    )
    op.add_column(
        "assessments",
        sa.Column(
            "curriculum_topic_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Drop new columns and table
    op.drop_constraint("chk_assessment_min_diff", "assessments", type_="check")
    op.drop_constraint("chk_assessment_max_diff", "assessments", type_="check")
    op.drop_constraint("chk_assessment_qpt", "assessments", type_="check")
    op.drop_constraint("chk_assessment_time_limit", "assessments", type_="check")
    op.drop_column("assessments", "questions_per_topic")
    op.drop_column("assessments", "minimum_difficulty")
    op.drop_column("assessments", "maximum_difficulty")
    op.drop_column("assessments", "question_types")
    op.drop_column("assessments", "time_limit_minutes")
    op.drop_index("idx_atc_assessment", table_name="assessment_topic_config")
    op.drop_table("assessment_topic_config")
