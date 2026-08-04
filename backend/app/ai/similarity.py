"""Embedding and similarity helpers shared by services and offline scripts.

These originally lived in scripts/create_learning_objectives.py. They moved here once
the review service needed them: a service importing from scripts/ inverts the
dependency direction — scripts are allowed to depend on the app, not the reverse.
"""

from typing import Any, cast

import structlog

from app.ai.providers.router import embed_batch

logger = structlog.get_logger()

# Provider-sized batches, so one oversized request cannot fail a whole run.
EMBED_BATCH_SIZE = 96


def parse_vector(raw: object) -> list[float] | None:
    """Coerce a pgvector value to a plain list of floats.

    Read through raw SQL, pgvector arrives as its text form ('[0.1,0.2,...]') rather
    than a sequence — list() on it would yield single characters and every similarity
    would silently be garbage. The ORM path returns a real sequence, so both are
    handled here.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return [float(x) for x in raw.strip().lstrip("[").rstrip("]").split(",") if x.strip()]
    return [float(x) for x in cast("list[Any]", raw)]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity without pulling numpy into the request path."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


async def embed_all(texts: list[str]) -> list[list[float]]:
    """Embed in provider-sized batches, preserving input order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        chunk = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(await embed_batch(chunk))
        logger.info("embedded_batch", done=min(start + EMBED_BATCH_SIZE, len(texts)), total=len(texts))
    return vectors
