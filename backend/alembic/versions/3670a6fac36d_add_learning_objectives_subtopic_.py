"""add learning_objectives, subtopic_objectives, subtopic tier, qb.learning_objective_id

Revision ID: 3670a6fac36d
Revises: 8a1b2c3d4e5f
Create Date: 2026-08-02 17:17:27.430157

Introduces the learning-objective (LO) layer that makes the question bank
curriculum-agnostic:

  subtopics (curriculum PLACEMENT)
      -> subtopic_objectives (M:N bridge)
          -> learning_objectives (the CONCEPT)
              -> question_bank.learning_objective_id (the stable binding)

question_bank.subtopic_id becomes nullable and is retained for legacy/audit only.
Questions are transiently NULL on both FKs between the scoped curriculum wipe and
their re-mapping to learning objectives.

The ivfflat index on learning_objectives.embedding is deliberately NOT created here
— ivfflat must be built after the vectors are populated, or its lists are trained on
an empty table. It ships in a follow-up migration once the LOs are seeded.

NOTE: autogenerate additionally emitted ~40 drop_table_comment() calls caused by
pre-existing drift between model docstrings and DB table comments. Those are
unrelated to this change and have been removed.
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3670a6fac36d"
down_revision: str | Sequence[str] | None = "8a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("learning_objective", sa.Text(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("bloom_taxonomy_level", sa.String(length=50), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_learning_objectives_topic_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_code", name="uq_learning_objectives_canonical_code"),
    )
    op.create_index(
        op.f("ix_learning_objectives_topic_id"),
        "learning_objectives",
        ["topic_id"],
        unique=False,
    )

    op.create_table(
        "subtopic_objectives",
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("learning_objective_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subtopic_id"],
            ["subtopics.id"],
            name="fk_subtopic_objectives_subtopic_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learning_objective_id"],
            ["learning_objectives.id"],
            name="fk_subtopic_objectives_learning_objective_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("subtopic_id", "learning_objective_id"),
    )

    # server_default backfills every existing row to 'BOTH', which is correct:
    # tiering only applies to IGCSE, and no IGCSE tier data exists yet.
    op.add_column(
        "subtopics",
        sa.Column("tier", sa.String(length=10), server_default="BOTH", nullable=False),
    )
    # CHECK constraints are never emitted by autogenerate — added by hand to match
    # the chk_subtopic_tier constraint declared on the Subtopic model.
    op.create_check_constraint(
        "chk_subtopic_tier",
        "subtopics",
        "tier IN ('CORE', 'EXTENDED', 'BOTH')",
    )

    op.add_column("question_bank", sa.Column("learning_objective_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_question_bank_learning_objective_id"),
        "question_bank",
        ["learning_objective_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_question_bank_learning_objective_id",
        "question_bank",
        "learning_objectives",
        ["learning_objective_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column(
        "question_bank",
        "subtopic_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    Restoring question_bank.subtopic_id to NOT NULL will fail if any question has
    been orphaned by the scoped curriculum wipe. That is intentional — a silent
    backfill would invent data. Restore from the pre-remap pg_dump instead.
    """
    op.alter_column(
        "question_bank",
        "subtopic_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_constraint("fk_question_bank_learning_objective_id", "question_bank", type_="foreignkey")
    op.drop_index(op.f("ix_question_bank_learning_objective_id"), table_name="question_bank")
    op.drop_column("question_bank", "learning_objective_id")

    op.drop_constraint("chk_subtopic_tier", "subtopics", type_="check")
    op.drop_column("subtopics", "tier")

    op.drop_table("subtopic_objectives")
    op.drop_index(op.f("ix_learning_objectives_topic_id"), table_name="learning_objectives")
    op.drop_table("learning_objectives")
