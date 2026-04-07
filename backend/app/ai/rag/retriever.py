"""RAG retrieval utilities for curriculum content.

Provides cosine similarity search over curriculum_chunks using pgvector,
and subtopic-based chunk retrieval for lesson planning and content curation.
"""

import uuid

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import CurriculumChunk, Subtopic

logger = structlog.get_logger()


class CurriculumRetriever:
    """Retrieves relevant curriculum chunks using vector similarity."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_relevant_chunks(
        self,
        subtopic_id: uuid.UUID,
        top_k: int = 3,
    ) -> list[CurriculumChunk]:
        """Return top_k curriculum_chunks most similar to the given subtopic's embedding.

        Uses pgvector cosine similarity between chunk embeddings and the subtopic's
        embedding. Filters to chunks belonging to the same curriculum and subject
        as the target subtopic.

        Args:
            subtopic_id: UUID of the subtopic to find relevant chunks for.
            top_k: Maximum number of chunks to return (default 3).

        Returns:
            List of CurriculumChunk objects ordered by descending similarity.
        """
        logger.info("get_relevant_chunks_started", subtopic_id=str(subtopic_id), top_k=top_k)

        result_subtopic = await self.db.execute(select(Subtopic).where(Subtopic.id == subtopic_id))
        subtopic = result_subtopic.scalar_one_or_none()
        if not subtopic:
            logger.warning("subtopic_not_found", subtopic_id=str(subtopic_id))
            return []

        if subtopic.embedding is None:
            logger.warning("subtopic_has_no_embedding", subtopic_id=str(subtopic_id))
            return []

        query = text("""
            SELECT cc.*
            FROM curriculum_chunks cc
            JOIN subtopics s ON cc.subtopic_id = s.id
            JOIN curriculum_topics ct ON s.curriculum_topic_id = ct.id
            WHERE cc.embedding IS NOT NULL
              AND ct.curriculum_id = :curriculum_id
              AND ct.subject_id = :subject_id
            ORDER BY cc.embedding <=> :subtopic_embedding::vector
            LIMIT :top_k
        """)

        from app.models.curriculum import CurriculumTopic

        result_ct = await self.db.execute(
            select(CurriculumTopic).where(CurriculumTopic.id == subtopic.curriculum_topic_id)
        )
        ct = result_ct.scalar_one_or_none()
        if not ct:
            logger.warning("curriculum_topic_not_found", curriculum_topic_id=str(subtopic.curriculum_topic_id))
            return []

        embedding_list = subtopic.embedding
        embedding_str = "[" + ",".join(str(x) for x in embedding_list) + "]"

        result_chunks = await self.db.execute(
            query,
            {
                "curriculum_id": str(ct.curriculum_id),
                "subject_id": str(ct.subject_id),
                "subtopic_embedding": embedding_str,
                "top_k": top_k,
            },
        )
        rows = result_chunks.fetchall()

        chunk_ids = [row[0] for row in rows]
        if not chunk_ids:
            return []

        result_cc = await self.db.execute(select(CurriculumChunk).where(CurriculumChunk.id.in_(chunk_ids)))
        chunks_list = result_cc.scalars().all()
        chunks: list[CurriculumChunk] = [c for c in chunks_list]

        chunks_sorted = sorted(chunks, key=lambda c: chunk_ids.index(c.id))

        logger.info(
            "get_relevant_chunks_completed",
            subtopic_id=str(subtopic_id),
            chunks_returned=len(chunks),
        )
        return chunks_sorted

    async def similarity_search(
        self,
        query_text: str,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        top_k: int = 5,
        threshold: float = 0.72,
    ) -> list[CurriculumChunk]:
        """Embed query_text and find similar chunks within a curriculum and subject.

        Used by content curation in M3-1-T1 to find relevant curriculum material
        for a given query or learning objective.

        Args:
            query_text: Text to embed and search for.
            curriculum_id: UUID of the curriculum to search within.
            subject_id: UUID of the subject to search within.
            top_k: Maximum chunks to return (default 5).
            threshold: Minimum cosine similarity threshold (default 0.72).

        Returns:
            List of CurriculumChunk objects with similarity >= threshold,
            ordered by descending similarity.
        """
        from app.ai.providers.router import embed as litellm_embed

        logger.info(
            "similarity_search_started",
            curriculum_id=str(curriculum_id),
            subject_id=str(subject_id),
            query_length=len(query_text),
            top_k=top_k,
            threshold=threshold,
        )

        query_embedding = await litellm_embed(query_text)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        sql = text("""
            SELECT cc.*,
                   1 - (cc.embedding <=> :query_embedding::vector) AS similarity
            FROM curriculum_chunks cc
            WHERE cc.curriculum_id = :curriculum_id
              AND cc.subject_id = :subject_id
              AND cc.embedding IS NOT NULL
            ORDER BY cc.embedding <=> :query_embedding::vector
            LIMIT :top_k
        """)

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "curriculum_id": str(curriculum_id),
                "subject_id": str(subject_id),
                "top_k": top_k * 2,
            },
        )
        rows = result.fetchall()

        filtered_rows = [(row, row[-1]) for row in rows if row[-1] >= threshold]
        filtered_rows.sort(key=lambda x: x[1], reverse=True)
        filtered_rows = filtered_rows[:top_k]

        if not filtered_rows:
            logger.info("similarity_search_no_results", threshold=threshold)
            return []

        chunk_ids = [row[0][0] for row in filtered_rows]
        similarities = {row[0][0]: row[1] for row in filtered_rows}

        result_objs = await self.db.execute(select(CurriculumChunk).where(CurriculumChunk.id.in_(chunk_ids)))
        chunks = list(result_objs.scalars().all())

        chunks_sorted = sorted(chunks, key=lambda c: similarities.get(c.id, 0), reverse=True)

        logger.info(
            "similarity_search_completed",
            chunks_returned=len(chunks),
        )
        return chunks_sorted
