"""Convert grade_level to integer

Revision ID: 1dd7942039cb
Revises: 44788560034a
Create Date: 2025-10-12 08:23:49.372986

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1dd7942039cb'
down_revision = '44788560034a'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'student_profiles',
        'grade_level',
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=True
    )

def downgrade():
    op.alter_column(
        'student_profiles',
        'grade_level',
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=True
    )

