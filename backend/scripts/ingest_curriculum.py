"""Curriculum PDF ingestion script.

Ingests Cambridge curriculum PDFs, chunks them, embeds each chunk, and stores
them in curriculum_chunks. Also populates subtopics.embedding for each touched
subtopic from the mean of its chunk embeddings (fallback: embed learning_objectives).

Usage:
    # With Docker running:
    docker compose exec backend python -m scripts.ingest_curriculum \
        --pdf-dir ./data/pdfs/cambridge/

    # Outside Docker (requires DATABASE_URL in env):
    cd backend
    python -m scripts.ingest_curriculum --pdf-dir ../data/pdfs/cambridge/

Depends on: M1-2-T1 (curriculum graph seeded — needs subtopics rows to exist)
Unlocks: M3-1-T1 (content curator uses subtopic embeddings for cosine similarity)
"""

import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pdfplumber
import structlog
import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.rag.embedder import CurriculumEmbedder  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.curriculum import (  # noqa: E402
    Curriculum,
    CurriculumChunk,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
EMBEDDING_BATCH_SIZE = 100
FUZZY_MATCH_CUTOFF = 0.8

SUBTOPIC_NAME_MAP: dict[str, uuid.UUID] = {}
CURRICULUM_ID_MAP: dict[str, uuid.UUID] = {}
SUBJECT_ID_MAP: dict[str, uuid.UUID] = {}
GRADE_LEVEL_MAP: dict[int, uuid.UUID] = {}


class Stats:
    def __init__(self) -> None:
        self.pdfs_processed = 0
        self.pdfs_failed = 0
        self.chunks_created = 0
        self.chunks_skipped = 0
        self.subtopics_embedded = 0
        self.subtopics_fallback = 0
        self.warnings: list[str] = []

    def report(self) -> None:
        log.info(
            "ingestion_complete",
            pdfs_processed=self.pdfs_processed,
            pdfs_failed=self.pdfs_failed,
            chunks_created=self.chunks_created,
            chunks_skipped=self.chunks_skipped,
            subtopics_embedded=self.subtopics_embedded,
            subtopics_fallback=self.subtopics_fallback,
        )
        if self.warnings:
            log.warning("ingestion_warnings", count=len(self.warnings))


def parse_filename(filename: str) -> tuple[str, str, int] | None:
    """Parse Cambridge PDF filename to extract curriculum_code, subject_code, grade_level.

    Expected format: cambridge_{curriculum}_{subject}_grade{grade}.pdf
    Examples:
        cambridge_lower_math_grade7.pdf -> curriculum=cambridge_lower, subject=MATH, grade=7
        cambridge_igcse_biology_grade9.pdf -> curriculum=cambridge_igcse, subject=BIO, grade=9

    Returns:
        Tuple of (curriculum_code, subject_code, grade_level) or None if parsing fails.
    """
    filename = filename.lower()
    if not filename.endswith(".pdf"):
        return None

    filename = filename[:-4]

    match = re.match(r"cambridge_(.+?)_(.+?)_grade(\d+)", filename)
    if not match:
        return None

    curriculum_part = match.group(1)
    subject_part = match.group(2)
    grade = int(match.group(3))

    curriculum_map = {
        "lower": "cambridge_lower",
        "igcse": "cambridge_igcse",
        "as_a": "cambridge_as_a",
    }
    curriculum_code = curriculum_map.get(curriculum_part, f"cambridge_{curriculum_part}")

    subject_map: dict[str, str] = {
        "math": "MATH",
        "science": "SCI",
        "bio": "BIO",
        "biology": "BIO",
        "chem": "CHEM",
        "chemistry": "CHEM",
        "phy": "PHY",
        "physics": "PHY",
        "eng": "ENG",
        "english": "ENG",
        "engl": "ENGL",
        "literature": "ENGL",
    }
    subject_code = subject_map.get(subject_part.lower(), subject_part.upper())

    return curriculum_code, subject_code, grade


def extract_pdf_text(pdf_path: Path) -> tuple[list[str], list[int]]:
    """Extract text from PDF page by page.

    Returns:
        Tuple of (list of page texts, list of page numbers)
    """
    pages: list[str] = []
    page_numbers: list[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
                page_numbers.append(i + 1)

    return pages, page_numbers


def tokenize_text(text: str, encoder: tiktoken.Encoding) -> list[int]:
    """Tokenize text using cl100k_base encoder."""
    return encoder.encode(text)


def chunk_text_by_tokens(text: str, encoder: tiktoken.Encoding, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    """Split text into chunks of specified token size with overlap.

    Args:
        text: Full text to chunk.
        encoder: tiktoken encoder.
        chunk_size: Target tokens per chunk.
        overlap: Token overlap between chunks.

    Returns:
        List of dicts with 'text', 'start_token', 'end_token' keys.
    """
    tokens = tokenize_text(text, encoder)
    chunks: list[dict[str, Any]] = []

    if not tokens:
        return chunks

    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]

        chunk_text = encoder.decode(chunk_tokens)
        chunks.append(
            {
                "text": chunk_text,
                "start_token": start,
                "end_token": end,
            }
        )

        if end >= len(tokens):
            break

        start = end - overlap

    return chunks


def resolve_subtopic(
    chunk_text: str,
    subtopic_names: list[str],
    subtopic_name_to_id: dict[str, uuid.UUID],
) -> uuid.UUID | None:
    """Resolve subtopic ID from chunk text using fuzzy matching.

    Args:
        chunk_text: Text from a chunk.
        subtopic_names: List of subtopic names to match against.
        subtopic_name_to_id: Mapping of subtopic name to UUID.

    Returns:
        Subtopic UUID if match found, None otherwise.
    """
    import difflib

    chunk_text_lower = chunk_text.lower()

    matches = difflib.get_close_matches(
        chunk_text_lower,
        subtopic_names,
        n=1,
        cutoff=FUZZY_MATCH_CUTOFF,
    )

    if matches:
        matched_name = matches[0]
        for name, name_lower in [(n, n.lower()) for n in subtopic_names]:
            if name_lower == matched_name:
                return subtopic_name_to_id.get(name)

    for name, st_id in subtopic_name_to_id.items():
        if name.lower() in chunk_text_lower:
            return st_id

    return None


def resolve_subtopic_with_logging(
    chunk_text: str,
    subtopic_names: list[str],
    subtopic_name_to_id: dict[str, uuid.UUID],
    chunk_index: int,
    filename: str,
) -> uuid.UUID | None:
    """Resolve subtopic ID with warning log when no match found.

    This wrapper adds warning logging for chunks that can't be matched to a subtopic.
    """
    result = resolve_subtopic(chunk_text, subtopic_names, subtopic_name_to_id)
    if result is None:
        log.warning(
            "subtopic_not_resolved",
            chunk_index=chunk_index,
            source_file=filename,
            chunk_text_preview=chunk_text[:100] if len(chunk_text) > 100 else chunk_text,
        )
    return result


class CurriculumIngester:
    """Handles PDF ingestion, chunking, embedding, and storage."""

    def __init__(self, db: AsyncSession, embedder: CurriculumEmbedder, stats: Stats) -> None:
        self.db = db
        self.embedder = embedder
        self.stats = stats
        self.encoder = tiktoken.get_encoding("cl100k_base")

    async def load_curriculum_data(self) -> None:
        """Load curriculum lookup maps from database."""
        result = await self.db.execute(select(Curriculum))
        for curr in result.scalars().all():
            CURRICULUM_ID_MAP[curr.code] = curr.id

        result = await self.db.execute(select(Subject))
        for subject in result.scalars().all():
            SUBJECT_ID_MAP[subject.code] = subject.id

        result = await self.db.execute(select(Grade))
        all_grades = result.scalars().all()
        for grade_obj in all_grades:
            GRADE_LEVEL_MAP[grade_obj.level] = grade_obj.id  # type: ignore[attr-defined]

        result = await self.db.execute(select(Subtopic))
        for st in result.scalars().all():
            SUBTOPIC_NAME_MAP[st.name] = st.id

        log.info(
            "curriculum_data_loaded",
            curricula=len(CURRICULUM_ID_MAP),
            subjects=len(SUBJECT_ID_MAP),
            subtopics=len(SUBTOPIC_NAME_MAP),
        )

    async def get_subtopics_for_curriculum(
        self, curriculum_id: uuid.UUID, subject_id: uuid.UUID, grade_id: uuid.UUID
    ) -> list[Subtopic]:
        """Get all subtopics for a given curriculum, subject, and grade."""
        result = await self.db.execute(
            select(Subtopic)
            .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .where(CurriculumTopic.curriculum_id == curriculum_id)
            .where(CurriculumTopic.subject_id == subject_id)
            .where(CurriculumTopic.grade_id == grade_id)
        )
        return list(result.scalars().all())

    async def ingest_pdf(self, pdf_path: Path) -> None:
        """Ingest a single PDF file."""
        filename = pdf_path.name
        parsed = parse_filename(filename)

        if not parsed:
            self.stats.warnings.append(f"Could not parse filename: {filename}")
            log.warning("filename_parse_failed", filename=filename)
            return

        curriculum_code, subject_code, grade_level = parsed

        curriculum_id = CURRICULUM_ID_MAP.get(curriculum_code)
        subject_id = SUBJECT_ID_MAP.get(subject_code)
        grade_id = GRADE_LEVEL_MAP.get(grade_level)

        if not curriculum_id or not subject_id or not grade_id:
            self.stats.warnings.append(f"Curriculum data not found for {curriculum_code}/{subject_code}/G{grade_level}")
            log.warning(
                "curriculum_data_missing",
                filename=filename,
                curriculum=curriculum_code,
                subject=subject_code,
                grade=grade_level,
            )
            return

        subtopics = await self.get_subtopics_for_curriculum(curriculum_id, subject_id, grade_id)
        subtopic_name_to_id: dict[str, uuid.UUID] = {st.name: st.id for st in subtopics}
        subtopic_names = list(subtopic_name_to_id.keys())

        result_existing = await self.db.execute(
            select(CurriculumChunk).where(
                CurriculumChunk.source_file == filename,
                CurriculumChunk.embedding.isnot(None),
            )
        )
        existing_chunks = {c.chunk_index: c for c in result_existing.scalars().all()}

        if existing_chunks:
            log.info("resuming_pdf", filename=filename, existing_chunks=len(existing_chunks))

        pages, page_numbers = extract_pdf_text(pdf_path)
        full_text = "\n\n".join(pages)

        chunks = chunk_text_by_tokens(full_text, self.encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        log.info(
            "pdf_chunks_created",
            filename=filename,
            total_chunks=len(chunks),
            existing=len(existing_chunks),
        )

        chunks_to_embed: list[dict[str, Any]] = []
        chunk_objects: list[CurriculumChunk] = []

        for i, chunk_info in enumerate(chunks):
            if i in existing_chunks:
                self.stats.chunks_skipped += 1
                continue

            chunk_text = chunk_info["text"]
            token_count = chunk_info["end_token"] - chunk_info["start_token"]

            subtopic_id = resolve_subtopic_with_logging(chunk_text, subtopic_names, subtopic_name_to_id, i, filename)

            chunk = CurriculumChunk(
                id=uuid.uuid4(),
                subtopic_id=subtopic_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                curriculum_id=curriculum_id,
                subject_id=subject_id,
                content=chunk_text,
                chunk_index=i,
                token_count=token_count,
                source_file=filename,
                page_number=self._get_page_for_chunk(chunks, i, page_numbers) if page_numbers else None,
                embedding=None,
            )
            chunk_objects.append(chunk)
            chunks_to_embed.append({"chunk": chunk, "text": chunk_text})

        if chunks_to_embed:
            self.db.add_all(chunk_objects)
            await self.db.flush()

            texts_to_embed = [c["text"] for c in chunks_to_embed]
            embeddings = await self.embedder.embed_texts(texts_to_embed)

            for chunk_info, embedding in zip(chunks_to_embed, embeddings):
                chunk_info["chunk"].embedding = embedding
                self.stats.chunks_created += 1

            await self.db.commit()

        self.stats.pdfs_processed += 1
        log.info("pdf_ingested", filename=filename, chunks_created=len(chunks_to_embed))

    def _get_page_for_chunk(
        self, chunks: list[dict[str, Any]], chunk_index: int, page_numbers: list[int]
    ) -> int | None:
        """Determine which page number a chunk belongs to based on position."""
        if not page_numbers:
            return None

        total_pages = len(page_numbers)
        chunks_per_page = len(chunks) / total_pages if total_pages > 0 else 1

        page_idx = min(int(chunk_index / chunks_per_page), total_pages - 1)
        return page_numbers[page_idx] if page_idx < len(page_numbers) else None

    async def compute_subtopic_embeddings(self) -> None:
        """Compute and store mean embedding for each subtopic that has chunks."""
        result = await self.db.execute(select(Subtopic).where(Subtopic.embedding.is_(None)))
        subtopics_without_embedding = list(result.scalars().all())

        if not subtopics_without_embedding:
            log.info("all_subtopics_have_embeddings")
            return

        log.info("computing_subtopic_embeddings", count=len(subtopics_without_embedding))

        subtopic_chunks: dict[uuid.UUID, list[list[float]]] = {}

        for subtopic in subtopics_without_embedding:
            result = await self.db.execute(
                select(CurriculumChunk).where(
                    CurriculumChunk.subtopic_id == subtopic.id,
                    CurriculumChunk.embedding.isnot(None),
                )
            )
            chunks_with_embedding = [c.embedding for c in result.scalars().all() if c.embedding]

            if chunks_with_embedding:
                subtopic_chunks[subtopic.id] = chunks_with_embedding

        for subtopic_id, embeddings in subtopic_chunks.items():
            mean_embedding = self.embedder.compute_mean_embedding(embeddings)
            result = await self.db.execute(select(Subtopic).where(Subtopic.id == subtopic_id))
            subtopic = result.scalar_one_or_none()
            if subtopic:
                subtopic.embedding = mean_embedding
                self.stats.subtopics_embedded += 1
                log.debug("subtopic_embedded_from_chunks", subtopic_id=str(subtopic_id))

        await self.db.commit()

        subtopics_with_chunks = set(subtopic_chunks.keys())
        subtopics_needing_fallback = [s for s in subtopics_without_embedding if s.id not in subtopics_with_chunks]

        for subtopic in subtopics_needing_fallback:
            try:
                embedding = await self.embedder.embed_subtopic(subtopic)
                subtopic.embedding = embedding
                self.stats.subtopics_fallback += 1
                log.debug("subtopic_embedded_fallback", subtopic_id=str(subtopic.id))
            except Exception as e:
                self.stats.warnings.append(f"Failed to embed subtopic {subtopic.name}: {e}")
                log.warning("subtopic_embedding_failed", subtopic_id=str(subtopic.id), error=str(e))

        await self.db.commit()


async def main(pdf_dir: Path) -> int:
    """Main entry point."""
    log.info("ingestion_start", pdf_dir=str(pdf_dir))

    if not pdf_dir.exists():
        log.error("pdf_dir_not_found", path=str(pdf_dir))
        return 1

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        log.warning("no_pdf_files_found", path=str(pdf_dir))
        return 0

    log.info("pdf_files_found", count=len(pdf_files))

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    stats = Stats()
    embedder = CurriculumEmbedder()

    try:
        async with async_session() as db:
            ingester = CurriculumIngester(db, embedder, stats)
            await ingester.load_curriculum_data()

            for pdf_path in pdf_files:
                try:
                    await ingester.ingest_pdf(pdf_path)
                except Exception as e:
                    stats.pdfs_failed += 1
                    stats.warnings.append(f"Failed to process {pdf_path.name}: {e}")
                    log.error("pdf_processing_failed", filename=pdf_path.name, error=str(e))

            await ingester.compute_subtopic_embeddings()

    except Exception as exc:
        log.error("ingestion_failed", error=str(exc), exc_info=True)
        await engine.dispose()
        return 1

    await engine.dispose()
    stats.report()

    if stats.warnings:
        log.warning("completed_with_warnings", warning_count=len(stats.warnings))

    log.info("ingestion_done")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Cambridge curriculum PDFs and generate embeddings.")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        required=True,
        help="Directory containing Cambridge curriculum PDF files",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(pdf_dir=args.pdf_dir))
    sys.exit(exit_code)
