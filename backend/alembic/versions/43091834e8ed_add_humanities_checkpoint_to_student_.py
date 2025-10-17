"""add humanities_checkpoint to student_profiles

Revision ID: 43091834e8ed
Revises: 1dd7942039cb
Create Date: 2025-10-13 16:33:52.369331

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43091834e8ed'
down_revision = '1dd7942039cb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "student_profiles",
        sa.Column("humanities_checkpoint", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("student_profiles", "humanities_checkpoint")
