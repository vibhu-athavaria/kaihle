"""Add user role column

Revision ID: 001
Revises: phase10a_rag_schema
Create Date: 2026-02-26 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = 'phase10a_rag_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column to users table
    op.execute("CREATE TYPE userrole AS ENUM ('parent', 'student', 'teacher', 'school_admin', 'super_admin')")
    op.add_column('users', sa.Column('role', sa.Enum('parent', 'student', 'teacher', 'school_admin', 'super_admin', name='userrole'), nullable=True))

    # Set default role for existing users
    # Since we don't have a way to determine the role of existing users, we'll set them as 'student' for now
    # In a real scenario, this would need to be updated based on business logic
    op.execute("UPDATE users SET role = 'student'")

    # Make role column not nullable
    op.alter_column('users', 'role', nullable=False)


def downgrade() -> None:
    # Remove role column
    op.drop_column('users', 'role')

    # Drop enum type
    op.execute("DROP TYPE userrole")

    # Drop enum type
    op.execute("DROP TYPE userrole")