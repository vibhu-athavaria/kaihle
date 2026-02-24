"""Add pgvector extension and RAG curriculum tables

Revision ID: phase10a_rag_schema
Revises: phase2_difficulty
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'phase10a_rag_schema'
down_revision = 'phase2_difficulty'
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 768
assert isinstance(EMBEDDING_DIMENSION, int) and EMBEDDING_DIMENSION > 0, (
    "EMBEDDING_DIMENSION must be a positive integer"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "curriculum_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subtopic_id", UUID(as_uuid=True),
                  sa.ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_source", sa.String(255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_cc_subtopic_id", "curriculum_content", ["subtopic_id"])

    op.create_table(
        "curriculum_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("content_id", UUID(as_uuid=True),
                  sa.ForeignKey("curriculum_content.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("subtopic_id", UUID(as_uuid=True),
                  sa.ForeignKey("subtopics.id"), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        sa.text(
            "ALTER TABLE curriculum_embeddings ADD COLUMN embedding vector(:dim) NOT NULL"
        ).bindparams(dim=EMBEDDING_DIMENSION)
    )
    op.create_index("idx_ce_subtopic_id", "curriculum_embeddings", ["subtopic_id"])

    op.execute("""
        CREATE INDEX idx_ce_embedding_ivfflat
        ON curriculum_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ce_embedding_ivfflat")
    op.drop_table("curriculum_embeddings")
    op.drop_table("curriculum_content")
    result = op.get_bind().execute(
        sa.text("""
            SELECT COUNT(*) FROM pg_depend
            WHERE objid = (SELECT oid FROM pg_extension WHERE extname = 'vector')
            AND deptype = 'e'
        """)
    ).scalar()
    if result == 1:
        op.execute("DROP EXTENSION IF EXISTS vector")
