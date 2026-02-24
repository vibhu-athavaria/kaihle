# app/models/rag.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.config import settings
from app.core.database import Base
from app.crud.mixin import SerializerMixin


EMBEDDING_DIMENSION = settings.EMBEDDING_DIMENSIONS


class CurriculumContent(Base, SerializerMixin):
    """
    Raw educational text chunks extracted from Cambridge textbook PDFs.
    One row per chunk. A single subtopic may have multiple chunks.
    Populated by Phase 10B extraction pipeline.

    Note: Only subtopic_id FK is stored. Grade/subject/topic relationships
    are derived via Subtopic → CurriculumTopic FK chain.
    """
    __tablename__ = "curriculum_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="CASCADE"),
                         nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    content_source = Column(String(255), nullable=False)
    content_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_cc_subtopic_id", "subtopic_id"),
    )


class CurriculumEmbedding(Base, SerializerMixin):
    """
    pgvector embeddings for each CurriculumContent chunk.
    One row per CurriculumContent row — linked by content_id.
    Populated by Phase 10C ingestion task.
    
    Note: Embedding dimension is sourced from settings.EMBEDDING_DIMENSIONS.
    Changing dimension requires a full DB migration and re-ingestion.
    """
    __tablename__ = "curriculum_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True),
                        ForeignKey("curriculum_content.id", ondelete="CASCADE"),
                        nullable=False, unique=True)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id"), nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=False)
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ce_subtopic_id", "subtopic_id"),
    )
