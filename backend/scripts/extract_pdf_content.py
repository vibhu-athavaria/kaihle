"""
PDF Content Extraction Pipeline

Usage:
    docker-compose exec api python scripts/extract_pdf_content.py \
        --file grade8_math_textbook.pdf \
        --dry-run

    docker-compose exec api python scripts/extract_pdf_content.py \
        --file grade8_math_textbook.pdf

    docker-compose exec api python scripts/extract_pdf_content.py \
        --all   # processes all PDFs in /app/data/textbooks/

Arguments:
    --file      Single PDF filename (must be in /app/data/textbooks/)
    --all       Process all PDF files in /app/data/textbooks/
    --dry-run   Print extracted chunks without writing to DB
    --force     Re-process already-ingested files (default: skip if content_source exists)

Exit codes:
    0 = success
    1 = file not found
    2 = PDF parse error
    3 = subtopic mapping error (no matching subtopic found)

Chunking strategy:
    1. Extract full text per page using PyMuPDF (fitz.open)
    2. Split text into paragraphs on double newline
    3. Group paragraphs into chunks targeting RAG_CHUNK_SIZE_TOKENS tokens
       with RAG_CHUNK_OVERLAP_TOKENS overlap between adjacent chunks
    4. Skip chunks with fewer than 50 tokens (noise/headers)
    5. Attempt subtopic mapping: match chunk text against subtopic names
       using fuzzy keyword match (no LLM call — purely string matching)
    6. Insert CurriculumContent rows; print summary

Output per run:
    Processed: grade8_math_textbook.pdf
    Pages read: 312
    Chunks extracted: 847
    Chunks inserted: 823 (24 skipped — below min token threshold)
    Subtopics mapped: 18/20
    Unmapped chunks written with subtopic_id=NULL (review manually)

NOTE: Chunks with subtopic_id=NULL are inserted but will be EXCLUDED
from embedding ingestion and RAG queries until manually mapped.
A summary of unmapped chunks is printed at script end.
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import fitz
import tiktoken
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.curriculum import Grade, Subtopic, CurriculumTopic
from app.models.subject import Subject
from app.models.rag import CurriculumContent


PDF_DIR = settings.PDF_STORAGE_PATH
MIN_CHUNK_TOKENS = 50

GRADE_CODES = {
    "grade5": 5,
    "grade6": 6,
    "grade7": 7,
    "grade8": 8,
    "grade9": 9,
    "grade10": 10,
    "grade11": 11,
    "grade12": 12,
}

SUBJECT_CODES = {
    "math": "Math",
    "science": "Science",
    "english": "English",
    "humanities": "Humanities",
}


def parse_filename(filename: str) -> tuple[str, str, str]:
    """
    Parses '{grade_code}_{subject_code}_{content_type}.pdf'.
    Returns (grade_code, subject_code, content_type).
    Raises ValueError on invalid format.
    """
    basename = os.path.basename(filename)
    if not basename.endswith(".pdf"):
        raise ValueError(f"File must be a PDF: {basename}")

    parts = basename[:-4].split("_")
    if len(parts) < 3:
        raise ValueError(
            f"Invalid filename format: {basename}. "
            f"Expected: {{grade_code}}_{{subject_code}}_{{content_type}}.pdf"
        )

    grade_code = parts[0].lower()
    subject_code = parts[1].lower()
    content_type = "_".join(parts[2:])

    if grade_code not in GRADE_CODES:
        raise ValueError(
            f"Invalid grade_code: {grade_code}. "
            f"Valid codes: {', '.join(GRADE_CODES.keys())}"
        )

    if subject_code not in SUBJECT_CODES:
        raise ValueError(
            f"Invalid subject_code: {subject_code}. "
            f"Valid codes: {', '.join(SUBJECT_CODES.keys())}"
        )

    return grade_code, subject_code, content_type


def extract_pages(pdf_path: str) -> list[str]:
    """Uses fitz.open to extract text per page. Returns list of page strings."""
    pages = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                pages.append(text)
        doc.close()
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF {pdf_path}: {e}") from e
    return pages


def chunk_text(
    pages: list[str],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> list[tuple[str, int]]:
    """
    Groups paragraphs into chunks.
    Uses tiktoken cl100k_base encoder for token counting.
    Respects chunk_size_tokens target with overlap_tokens sliding window.

    Returns list of (chunk_text, token_count) tuples.
    """
    enc = tiktoken.get_encoding("cl100k_base")

    all_paragraphs = []
    for page in pages:
        paragraphs = page.split("\n\n")
        for p in paragraphs:
            p = p.strip()
            if p:
                all_paragraphs.append(p)

    chunks = []
    current_chunk = []
    current_tokens = 0
    overlap_buffer = []

    for para in all_paragraphs:
        para_tokens = len(enc.encode(para))

        if current_tokens + para_tokens > chunk_size_tokens and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append((chunk_text, current_tokens))

            overlap_text = "\n\n".join(current_chunk[-2:]) if len(current_chunk) >= 2 else "\n\n".join(current_chunk)
            overlap_tokens_count = len(enc.encode(overlap_text))
            overlap_buffer = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[:]
            current_chunk = overlap_buffer[:]
            current_tokens = overlap_tokens_count

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append((chunk_text, current_tokens))

    return chunks


def normalize_text(text: str) -> set[str]:
    """Normalize text for keyword matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "must", "shall",
                  "can", "need", "dare", "ought", "used", "to", "of", "in",
                  "for", "on", "with", "at", "by", "from", "as", "into",
                  "through", "during", "before", "after", "above", "below",
                  "between", "under", "again", "further", "then", "once", "and",
                  "but", "or", "nor", "so", "yet", "both", "either", "neither",
                  "not", "only", "own", "same", "than", "too", "very", "just"}
    return set(w for w in words if w not in stop_words and len(w) > 2)


def map_subtopic(
    chunk_text: str,
    grade_id: UUID,
    subject_id: UUID,
    subtopics: list[Subtopic],
) -> UUID | None:
    """
    Attempts to match chunk to a subtopic by keyword overlap.
    Returns subtopic_id or None if no confident match (confidence < 0.4).
    Does NOT call any LLM.
    """
    chunk_words = normalize_text(chunk_text)

    if not chunk_words:
        return None

    best_match = None
    best_score = 0.0

    for subtopic in subtopics:
        subtopic_words = normalize_text(subtopic.name)
        if subtopic.keywords:
            subtopic_words.update(normalize_text(" ".join(subtopic.keywords)))

        if not subtopic_words:
            continue

        intersection = chunk_words & subtopic_words
        union = chunk_words | subtopic_words

        if not union:
            continue

        jaccard = len(intersection) / len(union)

        if jaccard > best_score:
            best_score = jaccard
            best_match = subtopic

    if best_score >= 0.15:
        return best_match.id if best_match else None

    return None


def get_grade_and_subject(
    db: Session,
    grade_code: str,
    subject_code: str,
) -> tuple[Grade | None, Subject | None]:
    """Look up Grade and Subject by codes."""
    grade_level = GRADE_CODES.get(grade_code)
    subject_name = SUBJECT_CODES.get(subject_code)

    if grade_level is None or subject_name is None:
        return None, None

    grade = db.execute(
        select(Grade).where(Grade.level == grade_level)
    ).scalar_one_or_none()

    subject = db.execute(
        select(Subject).where(Subject.name == subject_name)
    ).scalar_one_or_none()

    return grade, subject


def get_subtopics_for_grade_subject(
    db: Session,
    grade_id: UUID,
    subject_id: UUID,
) -> list[Subtopic]:
    """Get all subtopics for a grade and subject combination."""
    result = db.execute(
        select(Subtopic)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .where(
            and_(
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.subject_id == subject_id,
            )
        )
    ).scalars().all()

    return list(result)


def extract_and_ingest(
    filename: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Main entry point per file."""
    pdf_path = os.path.join(PDF_DIR, filename)

    if not os.path.exists(pdf_path):
        print(f"ERROR: File not found: {pdf_path}")
        return {"status": "error", "code": 1, "message": "File not found"}

    try:
        grade_code, subject_code, content_type = parse_filename(filename)
    except ValueError as e:
        print(f"ERROR: {e}")
        return {"status": "error", "code": 1, "message": str(e)}

    content_source = f"{grade_code}_{subject_code}_{content_type}"

    db = SessionLocal()
    try:
        grade, subject = get_grade_and_subject(db, grade_code, subject_code)
        if not grade:
            print(f"ERROR: Grade not found for code: {grade_code}")
            return {"status": "error", "code": 3, "message": f"Grade not found: {grade_code}"}
        if not subject:
            print(f"ERROR: Subject not found for code: {subject_code}")
            return {"status": "error", "code": 3, "message": f"Subject not found: {subject_code}"}

        existing = db.execute(
            select(CurriculumContent)
            .where(CurriculumContent.content_source == content_source)
            .limit(1)
        ).scalar_one_or_none()

        if existing and not force:
            print(f"SKIP: {filename} already ingested (use --force to re-process)")
            return {"status": "skipped", "message": "Already ingested"}

        if existing and force:
            db.execute(
                CurriculumContent.__table__.delete().where(
                    CurriculumContent.content_source == content_source
                )
            )
            db.commit()
            print(f"FORCE: Removed existing content for {content_source}")

        subtopics = get_subtopics_for_grade_subject(db, grade.id, subject.id)
        print(f"INFO: Found {len(subtopics)} subtopics for {grade_code}/{subject_code}")

        print(f"INFO: Extracting text from {filename}...")
        pages = extract_pages(pdf_path)
        print(f"INFO: Extracted {len(pages)} pages")

        print(f"INFO: Chunking text...")
        chunks = chunk_text(
            pages,
            settings.RAG_CHUNK_SIZE_TOKENS,
            settings.RAG_CHUNK_OVERLAP_TOKENS,
        )
        print(f"INFO: Created {len(chunks)} chunks")

        chunks_inserted = 0
        chunks_skipped = 0
        unmapped_chunks = []
        mapped_subtopics = set()

        for chunk_index, (chunk_text, token_count) in enumerate(chunks):
            if token_count < MIN_CHUNK_TOKENS:
                chunks_skipped += 1
                continue

            subtopic_id = map_subtopic(chunk_text, grade.id, subject.id, subtopics)

            if subtopic_id is None:
                unmapped_chunks.append({
                    "chunk_index": chunk_index,
                    "token_count": token_count,
                    "preview": chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text,
                })
            else:
                mapped_subtopics.add(subtopic_id)

            if dry_run:
                print(f"  DRY-RUN: chunk {chunk_index}: {token_count} tokens, subtopic={subtopic_id}")
            else:
                content = CurriculumContent(
                    subtopic_id=subtopic_id,
                    topic_id=None,
                    subject_id=subject.id,
                    grade_id=grade.id,
                    chunk_index=chunk_index,
                    content_source=content_source,
                    content_text=chunk_text,
                    token_count=token_count,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(content)
                chunks_inserted += 1

        if not dry_run:
            db.commit()

        print(f"\n{'=' * 60}")
        print(f"Processed: {filename}")
        print(f"Pages read: {len(pages)}")
        print(f"Chunks extracted: {len(chunks)}")
        print(f"Chunks inserted: {chunks_inserted} ({chunks_skipped} skipped — below min token threshold)")
        print(f"Subtopics mapped: {len(mapped_subtopics)}/{len(subtopics)}")
        print(f"Unmapped chunks: {len(unmapped_chunks)}")

        if unmapped_chunks and len(unmapped_chunks) <= 10:
            print("\nUnmapped chunks (subtopic_id=NULL):")
            for uc in unmapped_chunks[:10]:
                print(f"  - chunk {uc['chunk_index']}: {uc['preview']}")

        return {
            "status": "success",
            "pages": len(pages),
            "chunks": len(chunks),
            "inserted": chunks_inserted,
            "skipped": chunks_skipped,
            "mapped_subtopics": len(mapped_subtopics),
            "unmapped": len(unmapped_chunks),
        }

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        return {"status": "error", "code": 2, "message": str(e)}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="PDF Content Extraction Pipeline for RAG"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Single PDF filename (must be in /app/data/textbooks/)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all PDF files in /app/data/textbooks/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print extracted chunks without writing to DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process already-ingested files",
    )

    args = parser.parse_args()

    if not args.file and not args.all:
        parser.error("Must specify --file or --all")

    if args.all:
        pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")]
        if not pdf_files:
            print(f"No PDF files found in {PDF_DIR}")
            return

        print(f"Found {len(pdf_files)} PDF files to process")
        results = []
        for pdf_file in sorted(pdf_files):
            print(f"\n{'=' * 60}")
            result = extract_and_ingest(pdf_file, dry_run=args.dry_run, force=args.force)
            results.append({"file": pdf_file, **result})

        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        for r in results:
            print(f"  {r['file']}: {r['status']}")

    else:
        result = extract_and_ingest(args.file, dry_run=args.dry_run, force=args.force)
        if result.get("code"):
            sys.exit(result["code"])


if __name__ == "__main__":
    main()
