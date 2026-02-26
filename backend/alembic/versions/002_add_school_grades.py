"""Add school grades table

Revision ID: 002
Revises: 001
Create Date: 2026-02-26 14:56:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create school_grades table
    op.create_table('school_grades',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('grade_id', sa.UUID(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_id', 'grade_id')
    )

    op.create_index('idx_sg_school_id', 'school_grades', ['school_id'])


def downgrade() -> None:
    # Drop school_grades table
    op.drop_index('idx_sg_school_id', table_name='school_grades')
    op.drop_table('school_grades')