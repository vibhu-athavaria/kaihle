"""allow SPLIT status on lo_review_items

A single old subtopic could be broad enough to span several objectives in the newer,
more granular curriculum. MATH-NUM-G6-04 "Ratio and Proportion" is the clear case: its
objective reads "Write and simplify ratios; divide a quantity into a given ratio; solve
simple proportion problems using the unitary method" — three skills, now three separate
objectives, and 103 questions attached to it.

Binding all 103 to one of those three would mis-target most of them. That is not
pre-existing mis-filing being carried forward; it is mis-targeting the remap itself
would introduce, because the new curriculum splits what the old one merged.

SPLIT records that a group was resolved question-by-question instead of as a block.

Revision ID: 9162e489f203
Revises: 15712dea893f
Create Date: 2026-08-03 20:38:17.225661

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9162e489f203"
down_revision: str | Sequence[str] | None = "15712dea893f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("chk_lo_review_status", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_status",
        "lo_review_items",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'SPLIT')",
    )


def downgrade() -> None:
    """Downgrade schema.

    Any SPLIT rows are moved to REJECTED first, or the narrowed constraint could not be
    created. Their questions are already bound individually, so the row is only a
    record of how the decision was made.
    """
    op.execute("UPDATE lo_review_items SET status = 'REJECTED' WHERE status = 'SPLIT'")
    op.drop_constraint("chk_lo_review_status", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_status",
        "lo_review_items",
        "status IN ('PENDING', 'APPROVED', 'REJECTED')",
    )
