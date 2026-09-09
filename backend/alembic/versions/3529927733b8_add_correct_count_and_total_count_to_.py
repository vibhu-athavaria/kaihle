"""add correct_count and total_count to student_attempt_subtopic_scores

Revision ID: 3529927733b8
Revises: abda19793b5e
Create Date: 2026-09-09 12:43:30.924376

MLH-T3-3. A proportion alone cannot recover the counts a Beta-Binomial posterior needs
(3/5 and 30/50 are both 0.6). These columns are what mastery_model.estimate() actually
consumes going forward.

NULLABLE on purpose: rows written before this migration predate the columns and cannot be
backfilled from `score` alone — the proportion does not determine the counts it came from.
Every new write populates both; MLH-T3-4's rebuild backfills existing rows where the
underlying responses can still be attributed via student_responses. A NULL pair means
"counts unknown", not zero, and such rows are excluded from mastery_model's observations
rather than treated as zero evidence (see GapService.calculate_gap_states_for_attempt).

Note for reviewers: `alembic revision --autogenerate` again proposed dropping table
comments from 33 unrelated tables (the same pre-existing drift documented in MLH-T2 and
MLH-T3-2's migrations) — trimmed by hand for the same reason. Autogenerate also did NOT
detect the three CHECK constraints added to StudentAttemptSubtopicScore.__table_args__ (a
known limitation: reflection-based diffing of CHECK constraint bodies is unreliable) —
added here explicitly rather than left silently missing from the schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3529927733b8"
down_revision: str | Sequence[str] | None = "abda19793b5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add correct_count/total_count and their integrity constraints."""
    op.add_column("student_attempt_subtopic_scores", sa.Column("correct_count", sa.Integer(), nullable=True))
    op.add_column("student_attempt_subtopic_scores", sa.Column("total_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "chk_sats_counts_both_or_neither",
        "student_attempt_subtopic_scores",
        "(correct_count IS NULL) = (total_count IS NULL)",
    )
    op.create_check_constraint(
        "chk_sats_correct_le_total",
        "student_attempt_subtopic_scores",
        "correct_count IS NULL OR correct_count <= total_count",
    )
    op.create_check_constraint(
        "chk_sats_correct_non_negative",
        "student_attempt_subtopic_scores",
        "correct_count IS NULL OR correct_count >= 0",
    )


def downgrade() -> None:
    """Drop the columns and their constraints.

    Loses no source-of-truth data: correct_count/total_count are always re-derivable from
    student_responses via the same resolution GapService.calculate_gap_states_for_attempt
    already performs.
    """
    op.drop_constraint("chk_sats_correct_non_negative", "student_attempt_subtopic_scores", type_="check")
    op.drop_constraint("chk_sats_correct_le_total", "student_attempt_subtopic_scores", type_="check")
    op.drop_constraint("chk_sats_counts_both_or_neither", "student_attempt_subtopic_scores", type_="check")
    op.drop_column("student_attempt_subtopic_scores", "total_count")
    op.drop_column("student_attempt_subtopic_scores", "correct_count")
