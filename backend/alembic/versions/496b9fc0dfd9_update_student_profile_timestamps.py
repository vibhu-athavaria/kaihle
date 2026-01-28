"""update student_profile timestamps

Revision ID: 496b9fc0dfd9
Revises: 792e00593eac
Create Date: 2026-01-28 12:17:33.175430

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '496b9fc0dfd9'
down_revision = '792e00593eac'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Remove old column
    op.drop_column("student_profiles", "profile_completed")

    # 2. Add new columns
    op.add_column(
        "student_profiles",
        sa.Column(
            "registration_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "student_profiles",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "student_profiles",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    # 1. Re-add removed column
    op.add_column(
        "student_profiles",
        sa.Column(
            "profile_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # 2. Remove newly added columns
    op.drop_column("student_profiles", "updated_at")
    op.drop_column("student_profiles", "created_at")
    op.drop_column("student_profiles", "registration_completed_at")
