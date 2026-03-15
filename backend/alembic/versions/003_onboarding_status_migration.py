"""Migrate onboarding_diagnostic_status and add learning profile completion flag

Revision ID: 003_onboarding_status_migration
Revises: 002_nullable_created_by
Create Date: 2026-03-14

This migration:
1. Moves the onboarding diagnostic status tracking from the global student_profiles
   table to class_enrollments. This allows tracking onboarding status per-class,
   rather than globally per-student.
2. Adds is_learning_profile_complete boolean column to student_profiles to track
   whether the student has completed the learning profile questionnaire.

A student is considered fully onboarded when they complete the learning profile
questionnaire (is_learning_profile_complete = TRUE). The diagnostic status in
class_enrollments tracks per-class diagnostic assessment completion.
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
    # Step 1: Add onboarding_diagnostic_status column to class_enrollments
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
    # Use CONCURRENTLY to avoid table locks on large datasets
    op.create_index(
        "idx_enrollments_onboarding_status",
        "class_enrollments",
        ["student_id", "onboarding_diagnostic_status"],
        postgresql_concurrently=True,
    )

    # Remove onboarding_diagnostic_status column from student_profiles
    # First, we need to drop the column - the default will handle existing rows
    op.drop_column("student_profiles", "onboarding_diagnostic_status")

    # Step 2: Add is_learning_profile_complete to student_profiles
    op.add_column(
        "student_profiles",
        sa.Column(
            "is_learning_profile_complete",
            sa.Boolean(),
            nullable=False,
            server_default="FALSE",
        ),
    )


def downgrade() -> None:
    # Step 1: Remove is_learning_profile_complete
    op.drop_column("student_profiles", "is_learning_profile_complete")

    # Step 2: Add back onboarding_diagnostic_status to student_profiles
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
    # Use CONCURRENTLY to avoid table locks on large datasets
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_enrollments_onboarding_status")
    op.drop_column("class_enrollments", "onboarding_diagnostic_status")
