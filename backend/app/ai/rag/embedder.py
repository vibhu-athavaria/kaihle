"""RAG embedding utilities for curriculum content.

Provides batch embedding via LiteLLM router (text-embedding-004 by default)
and fallback subtopic embedding using learning_objectives.
"""

import structlog

from app.ai.providers.router import embed as litellm_embed
from app.models.curriculum import Subtopic

logger = structlog.get_logger()


class CurriculumEmbedder:
    """Handles embedding generation for curriculum chunks and subtopics."""

    def __init__(self) -> None:
        self._embedding_dim = 768

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts using text-embedding-004 via LiteLLM.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 768-dimensional embedding vectors, one per input text.

        Raises:
            ValueError: If texts list is empty.
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        logger.info("batch_embedding_started", batch_size=len(texts))

        embeddings: list[list[float]] = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._embed_batch(batch)
            embeddings.extend(batch_embeddings)
            logger.debug(
                "batch_embedding_progress",
                processed=i + len(batch),
                total=len(texts),
            )

        logger.info(
            "batch_embedding_completed",
            batch_size=len(texts),
            embedding_dim=len(embeddings[0]) if embeddings else 0,
        )

        return embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a single batch of texts (up to 100)."""
        all_embeddings: list[list[float]] = []
        for text in texts:
            embedding = await litellm_embed(text)
            all_embeddings.append(embedding)
        return all_embeddings

    async def embed_subtopic(self, subtopic: Subtopic) -> list[float]:
        """Embed subtopic learning_objectives as fallback when no chunks exist.

        Uses the subtopic's name, learning_objective, and description concatenated
        to create a representative embedding.

        Args:
            subtopic: Subtopic model instance with learning_objective attribute.

        Returns:
            768-dimensional embedding vector.
        """
        text_parts = [subtopic.name]
        if hasattr(subtopic, "learning_objective") and subtopic.learning_objective:
            text_parts.append(subtopic.learning_objective)
        if hasattr(subtopic, "description") and subtopic.description:
            text_parts.append(subtopic.description)

        text = " ".join(text_parts)
        logger.debug("subtopic_embedding_fallback", subtopic_id=str(subtopic.id), text_length=len(text))

        return await litellm_embed(text)

    def compute_mean_embedding(self, embeddings: list[list[float]]) -> list[float]:
        """Compute element-wise mean of a list of embedding vectors.

        Args:
            embeddings: List of 768-dim embedding vectors.

        Returns:
            Mean vector as a 768-dim list of floats.
        """
        if not embeddings:
            raise ValueError("Cannot compute mean of empty embedding list")

        if len(embeddings) == 1:
            return embeddings[0]

        n_dims = len(embeddings[0])
        mean: list[float] = [0.0] * n_dims

        for embedding in embeddings:
            for i, val in enumerate(embedding):
                mean[i] += val

        n = len(embeddings)
        mean = [val / n for val in mean]

        return mean
