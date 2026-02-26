"""Update schools table with additional fields

Revision ID: 004
Revises: 003
Create Date: 2026-02-26 14:58:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create school status enum
    op.execute("CREATE TYPE schoolstatus AS ENUM ('pending_approval', 'active', 'suspended')")

    # Create plan tier enum
    op.execute("CREATE TYPE plantier AS ENUM ('trial', 'starter', 'growth', 'scale')")

    # Add columns to schools table
    op.add_column('schools', sa.Column('slug', sa.String(length=100), nullable=True))
    op.add_column('schools', sa.Column('school_code', sa.String(length=8), nullable=True))
    op.add_column('schools', sa.Column('curriculum_id', sa.UUID(), nullable=True))
    op.add_column('schools', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('schools', sa.Column('timezone', sa.String(length=64), nullable=True, default='Asia/Makassar'))
    op.add_column('schools', sa.Column('status', sa.Enum('pending_approval', 'active', 'suspended', name='schoolstatus'), nullable=True, default='pending_approval'))
    op.add_column('schools', sa.Column('plan_tier', sa.Enum('trial', 'starter', 'growth', 'scale', name='plantier'), nullable=True, default='trial'))
    op.add_column('schools', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('schools', sa.Column('approved_by', sa.UUID(), nullable=True))
    op.add_column('schools', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
    op.add_column('schools', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key('schools_curriculum_id_fkey', 'schools', 'curricula', ['curriculum_id'], ['id'])
    op.create_foreign_key('schools_approved_by_fkey', 'schools', 'users', ['approved_by'], ['id'])

    # Add unique constraints
    op.create_unique_constraint('uq_schools_slug', 'schools', ['slug'])
    op.create_unique_constraint('uq_schools_school_code', 'schools', ['school_code'])

    # Add indexes
    op.create_index('idx_schools_status', 'schools', ['status'])
    op.create_index('idx_schools_admin_id', 'schools', ['admin_id'])

    # Set default values for existing rows
    op.execute("UPDATE schools SET slug = LOWER(REPLACE(name, ' ', '-')), timezone = 'Asia/Makassar', status = 'pending_approval', plan_tier = 'trial', is_active = true")

    # Make columns not nullable where required
    op.alter_column('schools', 'slug', nullable=False)
    op.alter_column('schools', 'timezone', nullable=False)
    op.alter_column('schools', 'status', nullable=False)
    op.alter_column('schools', 'plan_tier', nullable=False)
    op.alter_column('schools', 'is_active', nullable=False)


def downgrade() -> None:
    # Remove columns from schools table
    op.drop_constraint('uq_schools_school_code', 'schools', type_='unique')
    op.drop_constraint('uq_schools_slug', 'schools', type_='unique')
    op.drop_constraint('schools_approved_by_fkey', 'schools', type_='foreignkey')
    op.drop_constraint('schools_curriculum_id_fkey', 'schools', type_='foreignkey')

    op.drop_index('idx_schools_admin_id', table_name='schools')
    op.drop_index('idx_schools_status', table_name='schools')

    op.drop_column('schools', 'updated_at')
    op.drop_column('schools', 'is_active')
    op.drop_column('schools', 'approved_by')
    op.drop_column('schools', 'approved_at')
    op.drop_column('schools', 'plan_tier')
    op.drop_column('schools', 'status')
    op.drop_column('schools', 'timezone')
    op.drop_column('schools', 'country')
    op.drop_column('schools', 'curriculum_id')
    op.drop_column('schools', 'school_code')
    op.drop_column('schools', 'slug')

    # Drop enums
    op.execute("DROP TYPE plantier")
    op.execute("DROP TYPE schoolstatus")