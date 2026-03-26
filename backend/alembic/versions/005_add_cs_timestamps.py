"""Add timestamp columns to curriculum_subjects

Revision ID: 005_add_timestamps_to_curriculum_subjects
Revises: 004_user_school_id_nullable
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "005_add_cs_timestamps"
down_revision = "004_user_school_id_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add created_at column to curriculum_subjects
    op.add_column(
        "curriculum_subjects",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Add updated_at column to curriculum_subjects
    op.add_column(
        "curriculum_subjects",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("curriculum_subjects", "updated_at")
    op.drop_column("curriculum_subjects", "created_at")
