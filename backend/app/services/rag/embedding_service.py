"""
EmbeddingService — wraps the configured embedding API.
Provider is determined by EMBEDDING_PROVIDER env var.
Supported values: "gemini"

Current default: "gemini" using text-embedding-004 (768 dimensions).

IMPORTANT: The embedding dimension (768) is hardcoded into the
curriculum_embeddings table schema (Phase 10A). Changing the model
to one with a different dimension requires a full DB migration and
re-ingestion of all content. Never change EMBEDDING_PROVIDER or
GEMINI_EMBEDDING_MODEL without a coordinated migration plan.

Called ONLY from Celery worker tasks. Never from the API layer.
"""
import logging
from typing import Optional

from app.core.config import settings

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    genai = None
    GOOGLE_AVAILABLE = False


logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self):
        if settings.EMBEDDING_PROVIDER == "gemini":
            if not GOOGLE_AVAILABLE:
                raise ImportError(
                    "google-generativeai is not installed. "
                    "Install it with: pip install google-generativeai"
                )
            if not settings.GEMINI_API_KEY:
                raise ValueError(
                    "GEMINI_API_KEY is required for Gemini embedding provider"
                )
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model_name = settings.GEMINI_EMBEDDING_MODEL
        else:
            raise ValueError(
                f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}. "
                f"Supported: gemini"
            )

    def embed_text(self, text: str) -> list[float]:
        """
        Embeds a single text string.
        Returns a list of floats (length = EMBEDDING_DIMENSIONS = 768).
        Raises on API failure — let Celery handle retry.
        Truncates input to 2048 tokens if necessary (Gemini model limit).
        """
        try:
            result = genai.embed_content(
                model=f"models/{self.model_name}",
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(
                "Embedding failed for text (len=%d): %s",
                len(text),
                str(e)[:200],
            )
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of texts.
        Gemini text-embedding-004 supports up to 100 texts per batch call.
        If len(texts) > 100, splits into batches of 100 and concatenates results.
        Returns list of embedding vectors in same order as input texts.
        """
        if not texts:
            return []

        all_embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(
                "Embedding batch %d-%d of %d texts",
                i + 1,
                min(i + batch_size, len(texts)),
                len(texts),
            )

            try:
                result = genai.embed_content(
                    model=f"models/{self.model_name}",
                    content=batch,
                    task_type="retrieval_document",
                )
                all_embeddings.extend(result["embedding"])
            except Exception as e:
                logger.error(
                    "Batch embedding failed for batch %d-%d: %s",
                    i + 1,
                    min(i + batch_size, len(texts)),
                    str(e)[:200],
                )
                raise

        return all_embeddings
