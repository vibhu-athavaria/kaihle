"""add prompt and response text to llm usage events

Revision ID: a6ef5a235401
Revises: 3529927733b8
Create Date: 2026-09-09 20:47:21.115702

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6ef5a235401"
down_revision: str | Sequence[str] | None = "3529927733b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("llm_usage_events", sa.Column("prompt_text", sa.Text(), nullable=True))
    op.add_column("llm_usage_events", sa.Column("response_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("llm_usage_events", "response_text")
    op.drop_column("llm_usage_events", "prompt_text")
