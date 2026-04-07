"""Add curriculum_id and subject_id to curriculum_chunks

Revision ID: 006_add_curriculum_subject_to_chunks
Revises: 005_add_cs_timestamps
Create Date: 2026-04-07

Required for efficient RAG retrieval filtering without joining through subtopics.
These columns enable direct filtering by curriculum_id and subject_id in
similarity_search(), as required by M3-1-T1 content curator.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "006_add_curriculum_subject_to_chunks"
down_revision = "005_add_cs_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curriculum_chunks",
        sa.Column(
            "curriculum_id",
            UUID(as_uuid=True),
            sa.ForeignKey("curricula.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "curriculum_chunks",
        sa.Column(
            "subject_id",
            UUID(as_uuid=True),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_chunks_curriculum",
        "curriculum_chunks",
        ["curriculum_id"],
        unique=False,
    )
    op.create_index(
        "idx_chunks_subject",
        "curriculum_chunks",
        ["subject_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_chunks_subject", table_name="curriculum_chunks")
    op.drop_index("idx_chunks_curriculum", table_name="curriculum_chunks")
    op.drop_column("curriculum_chunks", "subject_id")
    op.drop_column("curriculum_chunks", "curriculum_id")
