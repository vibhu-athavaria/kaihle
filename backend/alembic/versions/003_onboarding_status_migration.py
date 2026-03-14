"""Migrate onboarding_diagnostic_status from student_profiles to class_enrollments

Revision ID: 003_onboarding_status_migration
Revises: 002_nullable_created_by
Create Date: 2026-03-14

This migration moves the onboarding diagnostic status tracking from the global
student_profiles table to class_enrollments. This allows tracking onboarding
status per-class, rather than globally per-student.

A student is considered fully onboarded when ALL active class_enrollments rows
have onboarding_diagnostic_status = 'COMPLETED'.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003_onboarding_status_migration"
down_revision: str | None = "002_nullable_created_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add onboarding_diagnostic_status column to class_enrollments
    # Use the existing onboarding_status enum type
    op.add_column(
        "class_enrollments",
        sa.Column(
            "onboarding_diagnostic_status",
            sa.Enum("PENDING", "IN_PROGRESS", "COMPLETED", name="onboarding_status"),
            nullable=False,
            server_default="PENDING",
        ),
    )

    # Create index for efficient gate checks on onboarding status
    op.create_index(
        "idx_enrollments_onboarding_status",
        "class_enrollments",
        ["student_id", "onboarding_diagnostic_status"],
    )

    # Remove onboarding_diagnostic_status column from student_profiles
    # First, we need to drop the column - the default will handle existing rows
    op.drop_column("student_profiles", "onboarding_diagnostic_status")


def downgrade() -> None:
    # Add back onboarding_diagnostic_status to student_profiles
    op.add_column(
        "student_profiles",
        sa.Column(
            "onboarding_diagnostic_status",
            sa.Enum("PENDING", "IN_PROGRESS", "COMPLETED", name="onboarding_status"),
            nullable=False,
            server_default="PENDING",
        ),
    )

    # Remove the column from class_enrollments
    op.drop_index("idx_enrollments_onboarding_status", table_name="class_enrollments")
    op.drop_column("class_enrollments", "onboarding_diagnostic_status")
