"""add mastery_priors table

Revision ID: abda19793b5e
Revises: 8736f78616b6
Create Date: 2026-09-09 12:23:41.795167

MLH-T3-2. The hierarchical Bayesian prior a subtopic's mastery estimate shrinks toward.

Note for reviewers: `alembic revision --autogenerate` again proposed dropping table
comments from 33 unrelated tables — the same pre-existing ORM/schema drift documented in
MLH-T2's migration (models do not declare `comment=`; the database has comments from the
original SQL schema). Trimmed by hand for the same reason: applying it here would delete
schema documentation for reasons unrelated to this table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "abda19793b5e"
down_revision: str | Sequence[str] | None = "8736f78616b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create mastery_priors."""
    op.create_table(
        "mastery_priors",
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("alpha", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("beta", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("source_level", sa.String(length=10), nullable=False),
        sa.Column("source_n", sa.Integer(), nullable=False),
        sa.Column("fitted_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("alpha > 0", name="chk_mastery_prior_alpha_positive"),
        sa.CheckConstraint("beta > 0", name="chk_mastery_prior_beta_positive"),
        sa.CheckConstraint(
            "source_level IN ('SUBTOPIC', 'TOPIC', 'SUBJECT', 'GLOBAL')",
            name="chk_mastery_prior_source_level",
        ),
        sa.CheckConstraint("source_n >= 0", name="chk_mastery_prior_source_n_non_negative"),
        # CASCADE: a mastery_priors row has no meaning once its subtopic is gone, and
        # nothing else references it.
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subtopic_id"),
    )
    op.create_table_comment(
        "mastery_priors",
        "Hierarchical Bayesian prior per subtopic, fitted offline by "
        "calibrate_mastery_prior.py and read by GapService at write time.",
        schema=None,
    )


def downgrade() -> None:
    """Drop mastery_priors.

    Derived data only — recomputable in full from student_responses via
    scripts.calibrate_mastery_prior. Dropping loses no source-of-truth information.
    """
    op.drop_table("mastery_priors")
