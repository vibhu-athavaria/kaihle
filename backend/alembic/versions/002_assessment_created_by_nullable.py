"""Make assessments.created_by nullable for system-generated Tier 1 diagnostics.

System-generated assessments (is_system_generated=TRUE, Tier 1 onboarding diagnostics)
are created by the Celery task trigger_onboarding_diagnostics() on student enrollment.
They have no teacher owner. created_by NULL explicitly means system-created.
NULL is only valid when is_system_generated=TRUE; enforced at service layer.

Revision ID: 002_assessment_created_by_nullable
Revises: 001_initial_schema
Create Date: 2026-03-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_assessment_created_by_nullable"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make assessments.created_by nullable.

    Required for Tier 1 system-generated onboarding diagnostics, which have
    no teacher owner. NULL created_by is only valid when is_system_generated=TRUE.
    """
    op.alter_column("assessments", "created_by", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    """Revert assessments.created_by to NOT NULL.

    WARNING: This will fail if any rows have created_by=NULL (i.e. system-generated assessments exist).
    Ensure all system-generated assessment rows are removed before running downgrade.
    """
    op.alter_column("assessments", "created_by", existing_type=sa.UUID(), nullable=False)
