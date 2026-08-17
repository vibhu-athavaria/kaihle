"""add grade_id and normalised_objective to learning_objectives

Revision ID: 2a0f35d51c5c
Revises: b7c41f9d2ae8
Create Date: 2026-08-13 05:56:15.998977

ADR-003 — Grade-Scoped Learning Objectives, task T1.

Makes grade part of a learning objective's identity so a question's grade is
derivable without question_bank.subtopic_id, which wipe_curriculum.py NULLs on
every remap.

Both new columns are deliberately NULLABLE here. 12 objectives currently resolve
to more than one grade and cannot be assigned mechanically; forcing NOT NULL now
would mean inventing values. T3 splits them, T4 sets NOT NULL and adds
UNIQUE (topic_id, grade_id, normalised_objective).

NOTE ON AUTOGENERATE: `alembic revision --autogenerate` also emitted ~35
drop_table_comment() calls, because the ORM models do not declare the COMMENT ON
TABLE strings that the original schema created. Those were removed — they are
unrelated to this change and would strip documentation from every table. Do not
paste autogenerate output back in without re-reviewing for them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a0f35d51c5c"
down_revision: str | Sequence[str] | None = "b7c41f9d2ae8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Existing values plus OBJECTIVE_GRADE_SPLIT, which T3 uses to park questions whose
# grade cannot be inferred from a surviving subtopic_id.
_ITEM_TYPES_NEW = "'QUESTION_REMAP', 'QUESTION_REMAP_REMAINDER', 'OBJECTIVE_DEDUP', 'OBJECTIVE_GRADE_SPLIT'"
_ITEM_TYPES_OLD = "'QUESTION_REMAP', 'QUESTION_REMAP_REMAINDER', 'OBJECTIVE_DEDUP'"


def upgrade() -> None:
    """Upgrade schema."""
    # Grade becomes part of objective identity. RESTRICT matches topic_id: grades are
    # global and shared, so deleting one that still owns objectives is a hard error.
    op.add_column("learning_objectives", sa.Column("grade_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_learning_objectives_grade_id"),
        "learning_objectives",
        ["grade_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_learning_objectives_grade_id",
        "learning_objectives",
        "grades",
        ["grade_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Stored comparison key for de-duplication. Not a generated column: the Python
    # normalisation folds accents via NFKD, which Postgres can only reproduce through
    # unaccent(), and unaccent() is not IMMUTABLE so it is rejected in generated
    # columns and index expressions alike. Written by create_learning_objectives.py.
    op.add_column("learning_objectives", sa.Column("normalised_objective", sa.Text(), nullable=True))

    # T3 suffixes split objectives with -G{level}. Existing max length is 46, so
    # '-G6' fits at 49 but '-G10'..'-G13' would land exactly on the old 50 limit.
    op.alter_column(
        "learning_objectives",
        "canonical_code",
        existing_type=sa.String(length=50),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.drop_constraint("chk_lo_review_item_type", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_item_type",
        "lo_review_items",
        f"item_type IN ({_ITEM_TYPES_NEW})",
    )


def downgrade() -> None:
    """Downgrade schema.

    Reversible, with one caveat: rows using OBJECTIVE_GRADE_SPLIT must be resolved or
    removed first, or restoring the narrower CHECK constraint will fail. That is
    deliberate — silently deleting review decisions to make a downgrade succeed would
    discard human judgement.
    """
    op.drop_constraint("chk_lo_review_item_type", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_item_type",
        "lo_review_items",
        f"item_type IN ({_ITEM_TYPES_OLD})",
    )

    op.alter_column(
        "learning_objectives",
        "canonical_code",
        existing_type=sa.String(length=64),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.drop_column("learning_objectives", "normalised_objective")
    op.drop_constraint("fk_learning_objectives_grade_id", "learning_objectives", type_="foreignkey")
    op.drop_index(op.f("ix_learning_objectives_grade_id"), table_name="learning_objectives")
    op.drop_column("learning_objectives", "grade_id")
