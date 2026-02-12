"""remove unnecessary field from question_bank table

Revision ID: 749be2eb6620
Revises: b10d7cca7994
Create Date: 2026-02-12 10:24:42.081753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '749be2eb6620'
down_revision = 'b10d7cca7994'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("question_bank", "times_used")
    op.drop_column("question_bank", "average_score")


def downgrade() -> None:
    op.add_column("question_bank", sa.Column("times_used", sa.Integer, default=0))
    op.add_column("question_bank", sa.Column("average_score", sa.Float, nullable=True))

