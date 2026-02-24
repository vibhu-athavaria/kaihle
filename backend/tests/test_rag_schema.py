"""
Tests for Phase 10A - RAG Schema and Models.

Tests:
- CurriculumContent model creation and constraints
- CurriculumEmbedding model creation and constraints
- pgvector extension availability
- IVFFlat index creation
- EMBEDDING_DIMENSION consistency between config and schema
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from app.models.rag import CurriculumContent, CurriculumEmbedding, EMBEDDING_DIMENSION
from app.core.config import settings


class TestEmbeddingDimensionConsistency:
    """Tests to ensure embedding dimension is consistent across config and schema."""

    def test_embedding_dimension_matches_config(self):
        """Test that model EMBEDDING_DIMENSION matches settings.EMBEDDING_DIMENSIONS."""
        assert EMBEDDING_DIMENSION == settings.EMBEDDING_DIMENSIONS, (
            f"Model EMBEDDING_DIMENSION ({EMBEDDING_DIMENSION}) must match "
            f"settings.EMBEDDING_DIMENSIONS ({settings.EMBEDDING_DIMENSIONS})"
        )


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

    def test_curriculum_content_nullable_subtopic_id(self):
        """Test CurriculumContent can be created with subtopic_id=None for unmapped chunks."""
        content = CurriculumContent(
            id=uuid4(),
            subtopic_id=None,
            chunk_index=0,
            content_source="test_unmapped",
            content_text="Unmapped content",
            token_count=50,
            created_at=datetime.now(timezone.utc),
        )

        assert content.subtopic_id is None

    def test_curriculum_content_default_chunk_index(self):
        """Test chunk_index has default of 0 in model."""
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
            embedding=[0.1] * EMBEDDING_DIMENSION,
            model_name="text-embedding-004",
            created_at=datetime.now(timezone.utc),
        )

        assert embedding.content_id == content_id
        assert embedding.model_name == "text-embedding-004"
        assert len(embedding.embedding) == EMBEDDING_DIMENSION


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

    def test_curriculum_content_no_redundant_columns(self, db_session):
        """Test that curriculum_content does NOT have redundant FK columns."""
        result = db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'curriculum_content'
            """)
        ).fetchall()

        column_names = [row[0] for row in result]

        assert "topic_id" not in column_names, "topic_id is redundant - derive from subtopic"
        assert "subject_id" not in column_names, "subject_id is redundant - derive from subtopic"
        assert "grade_id" not in column_names, "grade_id is redundant - derive from subtopic"

    def test_curriculum_content_chunk_index_server_default(self, db_session):
        """Test chunk_index has server_default of 0 at DB level."""
        row_id = uuid4()
        subtopic_id = uuid4()

        db_session.execute(
            text("""
                INSERT INTO curriculum_content (
                    id, subtopic_id, content_source, content_text, created_at
                ) VALUES (:id, :subtopic_id, :content_source, :content_text, :created_at)
            """),
            {
                "id": row_id,
                "subtopic_id": subtopic_id,
                "content_source": "test_server_default",
                "content_text": "test content",
                "created_at": datetime.now(timezone.utc),
            },
        )

        result = db_session.execute(
            text("SELECT chunk_index FROM curriculum_content WHERE id = :id"),
            {"id": row_id},
        ).scalar_one()

        db_session.execute(
            text("DELETE FROM curriculum_content WHERE id = :id"),
            {"id": row_id},
        )
        db_session.commit()

        assert result == 0, "chunk_index server_default should be 0"

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
        """Test that embedding column is vector(EMBEDDING_DIMENSION) type."""
        result = db_session.execute(
            text("""
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'curriculum_embeddings'
                  AND column_name = 'embedding'
            """)
        ).fetchone()

        assert result is not None
        data_type, udt_name = result
        assert data_type == "USER-DEFINED"
        assert udt_name == "vector"

        type_result = db_session.execute(
            text("""
                SELECT format_type(a.atttypid, a.atttypmod) AS formatted_type
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                WHERE c.relname = 'curriculum_embeddings'
                  AND a.attname = 'embedding'
            """)
        ).fetchone()

        assert type_result is not None
        expected_type = f"vector({EMBEDDING_DIMENSION})"
        assert type_result[0] == expected_type, (
            f"Embedding column should be {expected_type}, got {type_result[0]}"
        )

    def test_db_embedding_dimension_matches_config(self, db_session):
        """Test that the actual DB vector dimension matches settings.EMBEDDING_DIMENSIONS."""
        type_result = db_session.execute(
            text("""
                SELECT format_type(a.atttypid, a.atttypmod) AS formatted_type
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                WHERE c.relname = 'curriculum_embeddings'
                  AND a.attname = 'embedding'
            """)
        ).fetchone()

        assert type_result is not None
        db_dimension = int(type_result[0].split("(")[1].rstrip(")"))
        assert db_dimension == settings.EMBEDDING_DIMENSIONS, (
            f"DB embedding dimension ({db_dimension}) must match "
            f"settings.EMBEDDING_DIMENSIONS ({settings.EMBEDDING_DIMENSIONS})"
        )

    def test_ivfflat_index_exists(self, db_session):
        """Test that IVFFlat index exists with expected configuration."""
        result = db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'curriculum_embeddings'
                AND indexname = 'idx_ce_embedding_ivfflat'
            """)
        ).fetchone()

        assert result is not None, "IVFFlat index should exist"

        index_def_lower = result[1].lower()

        assert "ivfflat" in index_def_lower, "IVFFlat index method should be used"
        assert "vector_cosine_ops" in index_def_lower, (
            "IVFFlat index should be configured with vector_cosine_ops"
        )
        assert "lists = 100" in index_def_lower, (
            "IVFFlat index should be configured with lists = 100"
        )

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
