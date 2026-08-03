"""add curriculum_migrations artifact tracking

Alembic tracks schema migrations; nothing tracked which curriculum remap ARTIFACTS an
environment had applied. import_remap_artifact now records each application here and
refuses to apply the same artifact twice.

The counts are stored so a later audit can distinguish a full application from a
partial one — the failure mode that let production drift go unnoticed.

Revision ID: 15712dea893f
Revises: ac17bc4d7df0
Create Date: 2026-08-03 15:15:29.351986

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "15712dea893f"
down_revision: str | Sequence[str] | None = "ac17bc4d7df0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "curriculum_migrations",
        sa.Column("artifact_name", sa.String(length=200), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("objectives_created", sa.Integer(), nullable=False),
        sa.Column("placements_linked", sa.Integer(), nullable=False),
        sa.Column("questions_bound", sa.Integer(), nullable=False),
        sa.Column("groups_unresolved", sa.Integer(), nullable=False),
        sa.Column("applied_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("curriculum_migrations")
