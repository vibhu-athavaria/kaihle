"""add subtopic_explanation_suggestions table

Revision ID: 6b9d2df42b5d
Revises: 324975e5c767
Create Date: 2026-05-23 08:32:33.245705

Teacher-submitted text improvement suggestions for KaihleAdmin-managed personalised explanations.
Captures a snapshot of the original text for diff display.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6b9d2df42b5d"
down_revision: str | Sequence[str] | None = "324975e5c767"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create subtopic_explanation_suggestions table."""
    op.create_table(
        "subtopic_explanation_suggestions",
        sa.Column("subtopic_content_id", sa.UUID(), nullable=False),
        sa.Column("suggested_by_id", sa.UUID(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                "accepted_with_edits",
                name="suggestion_status_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subtopic_content_id"], ["subtopic_content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suggested_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subtopic_explanation_suggestions_status"),
        "subtopic_explanation_suggestions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subtopic_explanation_suggestions_subtopic_content_id"),
        "subtopic_explanation_suggestions",
        ["subtopic_content_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subtopic_explanation_suggestions_suggested_by_id"),
        "subtopic_explanation_suggestions",
        ["suggested_by_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop subtopic_explanation_suggestions table."""
    op.drop_index(
        op.f("ix_subtopic_explanation_suggestions_suggested_by_id"),
        table_name="subtopic_explanation_suggestions",
    )
    op.drop_index(
        op.f("ix_subtopic_explanation_suggestions_subtopic_content_id"),
        table_name="subtopic_explanation_suggestions",
    )
    op.drop_index(
        op.f("ix_subtopic_explanation_suggestions_status"),
        table_name="subtopic_explanation_suggestions",
    )
    op.drop_table("subtopic_explanation_suggestions")
    sa.Enum(name="suggestion_status_enum").drop(op.get_bind(), checkfirst=False)
