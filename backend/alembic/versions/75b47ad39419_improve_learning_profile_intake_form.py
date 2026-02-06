"""Improve learning profile intake form

Revision ID: 75b47ad39419
Revises: 5390a3b99f42
Create Date: 2026-02-05 15:12:24.700622

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75b47ad39419'
down_revision = '5390a3b99f42'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("student_profiles", "learning_style", new_column_name="learning_profile")

    op.drop_column("student_profiles", "motivation_profile")
    op.drop_column("student_profiles", "interests")
    op.drop_column("student_profiles", "preferred_format")
    op.drop_column("student_profiles", "preferred_session_length")

    op.add_column(
        "student_profiles",
        sa.Column("learning_profile_version", sa.String(length=10), nullable=True)
    )
    op.add_column(
        "student_profiles",
        sa.Column("learning_profile_updated_at", sa.DateTime(timezone=True), nullable=True)
    )

def downgrade():
    op.alter_column('student_profiles', 'learning_profile', new_column_name='learning_style')

    op.add_column("student_profiles", sa.Column("motivation_profile", sa.JSONB, nullable=True))
    op.add_column("student_profiles", sa.Column("interests", sa.JSONB, nullable=True))
    op.add_column("student_profiles", sa.Column("preferred_format", sa.String(length=50), nullable=True))
    op.add_column("student_profiles", sa.Column("preferred_session_length", sa.Integer, nullable=True))

    op.drop_column("student_profiles", "learning_profile_version")
    op.drop_column("student_profiles", "learning_profile_updated_at")
