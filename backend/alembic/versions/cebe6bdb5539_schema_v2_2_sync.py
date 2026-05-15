"""schema_v2_2_sync — VOIDED, replaced by schema_v2_2_final

Revision ID: cebe6bdb5539
Revises: 2e8ce10acadc
Create Date: 2026-05-15 08:10:05.014050

"""

from collections.abc import Sequence

revision: str = "cebe6bdb5539"
down_revision: str | Sequence[str] | None = "2e8ce10acadc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
