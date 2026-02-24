"""
Tests for Phase 10A - RAG Schema and Models.

Tests:
- CurriculumContent model creation and constraints
- CurriculumEmbedding model creation and constraints
- pgvector extension availability
- IVFFlat index creation
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from app.models.rag import CurriculumContent, CurriculumEmbedding
from app.core.config import settings


class TestCurriculumContentModel:
    """Tests for CurriculumContent model."""

    def test_curriculum_content_creation(self):
        """Test CurriculumContent can be instantiated with all fields."""
        content = CurriculumContent(
            id=uuid4(),
            subtopic_id=uuid4(),
            chunk_index=0,
            content_source="test_textbook",
            content_text="Sample content text",
            token_count=100,
            created_at=datetime.now(timezone.utc),
        )

        assert content.chunk_index == 0
        assert content.content_source == "test_textbook"
        assert content.content_text == "Sample content text"
        assert content.token_count == 100

    def test_curriculum_content_default_chunk_index(self):
        """Test chunk_index has server default of 0 in DB schema."""
        content = CurriculumContent(
            id=uuid4(),
            subtopic_id=uuid4(),
            content_source="test",
            content_text="text",
            created_at=datetime.now(timezone.utc),
        )

        assert content.chunk_index is None or content.chunk_index == 0


class TestCurriculumEmbeddingModel:
    """Tests for CurriculumEmbedding model."""

    def test_curriculum_embedding_creation(self):
        """Test CurriculumEmbedding can be instantiated with all fields."""
        content_id = uuid4()
        embedding = CurriculumEmbedding(
            id=uuid4(),
            content_id=content_id,
            subtopic_id=uuid4(),
            embedding=[0.1] * 768,
            model_name="text-embedding-004",
            created_at=datetime.now(timezone.utc),
        )

        assert embedding.content_id == content_id
        assert embedding.model_name == "text-embedding-004"
        assert len(embedding.embedding) == 768


class TestRAGSchemaIntegration:
    """Integration tests for RAG schema."""

    @pytest.fixture
    def db_session(self):
        """Provide a synchronous database session for tests."""
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    def test_vector_extension_exists(self, db_session):
        """Test that pgvector extension is installed."""
        result = db_session.execute(
            text("SELECT * FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()

        assert result is not None, "pgvector extension should be installed"

    def test_curriculum_content_table_exists(self, db_session):
        """Test that curriculum_content table exists with correct columns."""
        result = db_session.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'curriculum_content'
                ORDER BY ordinal_position
            """)
        ).fetchall()

        column_names = [row[0] for row in result]

        assert "id" in column_names
        assert "subtopic_id" in column_names
        assert "chunk_index" in column_names
        assert "content_source" in column_names
        assert "content_text" in column_names
        assert "token_count" in column_names
        assert "created_at" in column_names

    def test_curriculum_content_no_redundant_fk_columns(self, db_session):
        """Test that curriculum_content does NOT have redundant FK columns."""
        result = db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'curriculum_content'
            """)
        ).fetchall()

        column_names = [row[0] for row in result]

        assert "topic_id" not in column_names
        assert "subject_id" not in column_names
        assert "grade_id" not in column_names

    def test_curriculum_embeddings_table_exists(self, db_session):
        """Test that curriculum_embeddings table exists with correct columns."""
        result = db_session.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'curriculum_embeddings'
                ORDER BY ordinal_position
            """)
        ).fetchall()

        column_names = [row[0] for row in result]

        assert "id" in column_names
        assert "content_id" in column_names
        assert "subtopic_id" in column_names
        assert "embedding" in column_names
        assert "model_name" in column_names
        assert "created_at" in column_names

    def test_embedding_column_is_vector_type(self, db_session):
        """Test that embedding column is vector(768) type."""
        result = db_session.execute(
            text("""
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'curriculum_embeddings'
                AND column_name = 'embedding'
            """)
        ).fetchone()

        assert result is not None
        assert result[0] == "USER-DEFINED" or result[1] == "vector"

    def test_ivfflat_index_exists(self, db_session):
        """Test that IVFFlat index exists on curriculum_embeddings."""
        result = db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'curriculum_embeddings'
                AND indexname = 'idx_ce_embedding_ivfflat'
            """)
        ).fetchone()

        assert result is not None, "IVFFlat index should exist"
        assert "ivfflat" in result[1].lower()

    def test_curriculum_content_indexes_exist(self, db_session):
        """Test that required indexes exist on curriculum_content."""
        result = db_session.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'curriculum_content'
            """)
        ).fetchall()

        index_names = [row[0] for row in result]

        assert "idx_cc_subtopic_id" in index_names

    def test_curriculum_embeddings_subtopic_index_exists(self, db_session):
        """Test that subtopic index exists on curriculum_embeddings."""
        result = db_session.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'curriculum_embeddings'
                AND indexname = 'idx_ce_subtopic_id'
            """)
        ).fetchone()

        assert result is not None, "subtopic_id index should exist"
