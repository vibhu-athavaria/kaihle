"""Make full_name nullable

Revision ID: 005
Revises: 004
Create Date: 2026-02-26 15:29:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make full_name column nullable
    op.alter_column('users', 'full_name', nullable=True)


def downgrade() -> None:
    # Make full_name column not nullable
    op.alter_column('users', 'full_name', nullable=False)