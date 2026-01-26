"""remove_profile_completed_column

Revision ID: bf1675fa2dd4
Revises: 71bfcaf277f8
Create Date: 2026-01-26 08:46:07.006893

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = 'bf1675fa2dd4'
down_revision = '71bfcaf277f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First, ensure all profiles with profile_completed=True have registration_completed_at set
    op.execute(
        """
        UPDATE student_profiles
        SET registration_completed_at = COALESCE(registration_completed_at, NOW())
        WHERE profile_completed = TRUE
        """
    )

    # Then drop the profile_completed column
    op.drop_column('student_profiles', 'profile_completed')


def downgrade() -> None:
    # Add back the profile_completed column
    op.add_column('student_profiles', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default='FALSE'))

    # Set profile_completed based on registration_completed_at
    op.execute(
        """
        UPDATE student_profiles
        SET profile_completed = TRUE
        WHERE registration_completed_at IS NOT NULL
        """
    )
