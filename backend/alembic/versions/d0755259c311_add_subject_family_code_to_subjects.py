"""add subject_family_code to subjects

Revision ID: d0755259c311
Revises: 4a43084e7ad5
Create Date: 2026-05-14 09:12:14.524410

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0755259c311"
down_revision: str | Sequence[str] | None = "4a43084e7ad5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column("subject_family_code", sa.String(20), nullable=True),
    )
    op.create_index("idx_subjects_family_code", "subjects", ["subject_family_code"])
    # Backfill: group subjects by knowledge domain across curriculum boundaries.
    # SCI (Lower Secondary Integrated Science) and BIO/CHEM/PHY (IGCSE) share one family.
    # ENGL (English Literature) is a specialisation of ENG — same family.
    op.execute("UPDATE subjects SET subject_family_code = 'SCI' WHERE code IN ('SCI', 'BIO', 'CHEM', 'PHY')")
    op.execute("UPDATE subjects SET subject_family_code = 'MATH' WHERE code = 'MATH'")
    op.execute("UPDATE subjects SET subject_family_code = 'ENG' WHERE code IN ('ENG', 'ENGL')")


def downgrade() -> None:
    op.drop_index("idx_subjects_family_code", table_name="subjects")
    op.drop_column("subjects", "subject_family_code")
