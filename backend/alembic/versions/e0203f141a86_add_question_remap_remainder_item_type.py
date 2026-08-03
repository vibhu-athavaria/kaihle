"""add QUESTION_REMAP_REMAINDER item type

Splitting a group left its undecided questions with no presence in the queue. The
parent moved to SPLIT — a terminal status — while 88 questions across two groups still
needed decisions and were counted nowhere. A queue that under-reports outstanding work
is worse than none, because it says you are nearly finished when you are not.

The remainder now becomes its own PENDING item. It is typed separately because those
questions are heterogeneous by definition — whatever the model could not confidently
place — so offering them as one bindable group would invite exactly the batch
mis-binding the split existed to prevent. The UI reviews these one question at a time.

Revision ID: e0203f141a86
Revises: 9162e489f203
Create Date: 2026-08-03 21:13:03.235737

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e0203f141a86"
down_revision: str | Sequence[str] | None = "9162e489f203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("chk_lo_review_item_type", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_item_type",
        "lo_review_items",
        "item_type IN ('QUESTION_REMAP', 'QUESTION_REMAP_REMAINDER', 'OBJECTIVE_DEDUP')",
    )


def downgrade() -> None:
    """Downgrade schema.

    Remainder rows are retyped rather than deleted — their questions are real work and
    must not silently vanish from the queue.
    """
    op.execute("UPDATE lo_review_items SET item_type = 'QUESTION_REMAP' WHERE item_type = 'QUESTION_REMAP_REMAINDER'")
    op.drop_constraint("chk_lo_review_item_type", "lo_review_items", type_="check")
    op.create_check_constraint(
        "chk_lo_review_item_type",
        "lo_review_items",
        "item_type IN ('QUESTION_REMAP', 'OBJECTIVE_DEDUP')",
    )
