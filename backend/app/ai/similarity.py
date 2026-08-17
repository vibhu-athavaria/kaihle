"""Embedding and similarity helpers shared by services and offline scripts.

These originally lived in scripts/create_learning_objectives.py. They moved here once
the review service needed them: a service importing from scripts/ inverts the
dependency direction — scripts are allowed to depend on the app, not the reverse.
"""

import re
import unicodedata
from typing import Any, cast

import structlog

from app.ai.providers.router import embed_batch

logger = structlog.get_logger()

# Provider-sized batches, so one oversized request cannot fail a whole run.
EMBED_BATCH_SIZE = 96


def normalise_text(value: str) -> str:
    """Fold an objective to a comparison key: casing, accents, punctuation, spacing.

    The exact-match half of learning-objective de-duplication, paired with the cosine
    half below. It catches the common case of the same objective restated verbatim at
    a different grade.

    This is the single definition on purpose. The value is persisted to
    learning_objectives.normalised_objective and constrained by
    UNIQUE (topic_id, grade_id, normalised_objective) — so if the de-duplicator and
    the backfill ever computed it differently, the constraint would stop matching what
    the de-duplicator considers a duplicate. Importing beats copying.

    Not expressible as a Postgres generated column: the NFKD accent folding needs
    unaccent(), which is not IMMUTABLE and is rejected in generated columns and index
    expressions alike.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.lower()
    without_punct = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", without_punct).strip()


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
