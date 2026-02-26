"""Add student school registrations table

Revision ID: 003
Revises: 002
Create Date: 2026-02-26 14:57:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create registration status enum
    op.execute("CREATE TYPE registrationstatus AS ENUM ('pending', 'approved', 'rejected')")

    # Create student_school_registrations table
    op.create_table('student_school_registrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='registrationstatus'), nullable=False, default='pending'),
        sa.Column('grade_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_id', 'student_id')
    )

    op.create_index('idx_ssr_school_status', 'student_school_registrations', ['school_id', 'status'])


def downgrade() -> None:
    # Drop student_school_registrations table
    op.drop_index('idx_ssr_school_status', table_name='student_school_registrations')
    op.drop_table('student_school_registrations')

    # Drop registration status enum
    op.execute("DROP TYPE registrationstatus")