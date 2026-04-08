# ~~M1-2-T2 — Curriculum PDF Ingestion & Embeddings~~ — RETIRED

> **RETIRED — DO NOT IMPLEMENT**
> **Retired by:** Vibhu Athavaria
> **Date:** April 2026
> **Reason:** PDF ingestion abandoned. Kaihle does not ingest Cambridge PDFs.
> LLM-generated explanations stored in `subtopic_content` table replace
> curriculum_chunks as the content source for quiz generation and lesson
> planning. pgvector embeddings on subtopics are not needed for MVP.
>
> **Replacement architecture:** See `M3-0-T1_subtopic_content_migration_and_seed.md`
> for the new content pipeline.
>
> **Impact on downstream tasks:**
> - `M3-1-T1_content_curator.md` — updated, no longer depends on this task
> - `M3-1-T2_quiz_generator.md` — updated, no longer depends on this task
> - `M4-1-T1_lesson_plan_celery_task.md` — updated, RAG context replaced
>
> This file is preserved for historical reference only.
> No coding agent should implement this task.

---

# M1-2-T2 — Curriculum PDF Ingestion & Embeddings (ORIGINAL — ARCHIVED)
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-2 — Curriculum Graph & RAG Ingestion
**Task:** T2 of 2 in this epic

---

## Context

This script ingests Cambridge curriculum PDFs, chunks them, embeds each chunk, and stores them in `curriculum_chunks`. It also populates `subtopics.embedding` (VECTOR(768)) for each touched subtopic. These embeddings power the RAG context used by question generation, quiz generation, and lesson planning.

**Depends on:** M1-2-T1 (curriculum graph seeded — needs `subtopics` rows to exist)
**Unlocks:** M3-1-T1 (content curator uses `subtopics.embedding` for cosine similarity)

---

## Files to Create

```
CREATE  backend/scripts/ingest_curriculum.py
CREATE  backend/app/ai/rag/embedder.py
CREATE  backend/app/ai/rag/retriever.py
CREATE  backend/tests/unit/test_ingest_curriculum.py
CREATE  backend/tests/integration/test_rag_retriever.py
```

---

## Database Tables Written

```sql
-- curriculum_chunks (write)
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
subtopic_id       UUID REFERENCES subtopics(id)   -- may be NULL if unresolvable
curriculum_id     UUID REFERENCES curricula(id)
subject_id        UUID REFERENCES subjects(id)
chunk_text        TEXT NOT NULL
chunk_index       INT NOT NULL                    -- position within source doc
source_pdf        VARCHAR(500)                    -- original filename
token_count       INT
embedding         VECTOR(768)

-- subtopics (update embedding column)
embedding         VECTOR(768)   -- populated per subtopic from mean of its chunks
```

---

## Script Logic (`ingest_curriculum.py`)

```
Usage: python ingest_curriculum.py --pdf-dir ./data/pdfs/cambridge/
```

### Step 1 — PDF Text Extraction
- Use `pdfplumber` to extract text page by page
- Concatenate pages with `\n\n` separator
- Filename → derive `curriculum_code` and `subject_code` from filename convention:
  `cambridge_lower_math_grade7.pdf` → `curriculum_code=cambridge_lower`, `subject_code=MATH`, `grade_level=7`

### Step 2 — Chunking
- Use `tiktoken` (model `cl100k_base`) to count tokens
- Chunk size: **500 tokens**, overlap: **50 tokens**
- Each chunk = a `curriculum_chunks` row

### Step 3 — Subtopic Resolution
- For each chunk, attempt to resolve `subtopic_id`:
  - Look for subtopic names from the seeded graph in the chunk text (fuzzy match with `difflib.get_close_matches`, cutoff=0.8)
  - If matched → set `subtopic_id`
  - If no match → set `subtopic_id = NULL`, log warning

### Step 4 — Embedding
- Embed in batches of 100 chunks using `text-embedding-004` (Google)
- API: `google.generativeai.embed_content(model="models/text-embedding-004", content=texts, task_type="RETRIEVAL_DOCUMENT")`
- Store `embedding VECTOR(768)` on each `curriculum_chunks` row

### Step 5 — Subtopic Embedding
- For each subtopic that has at least 1 chunk with an embedding:
  - Compute mean vector across all chunk embeddings for that subtopic
  - Store on `subtopics.embedding`
- For subtopics with no chunks: embed `learning_objectives` text directly as a fallback

### Step 6 — Resumable
- Skip any `curriculum_chunks` row where `embedding IS NOT NULL`
- Skip any `subtopics` row where `embedding IS NOT NULL`
- Script can be interrupted and resumed safely

---

## `embedder.py`

```python
class CurriculumEmbedder:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts using text-embedding-004. Returns list of 768-dim vectors."""

    async def embed_subtopic(self, subtopic: Subtopic) -> list[float]:
        """Embed subtopic learning_objectives as fallback when no chunks exist."""
```

---

## `retriever.py`

```python
class CurriculumRetriever:
    async def get_relevant_chunks(
        self,
        subtopic_id: UUID,
        top_k: int = 3
    ) -> list[CurriculumChunk]:
        """
        Return top_k curriculum_chunks most similar to the given subtopic's embedding.
        Uses pgvector cosine similarity: embedding <=> subtopic.embedding
        Filters to same curriculum + subject as subtopic.
        """

    async def similarity_search(
        self,
        query_text: str,
        curriculum_id: UUID,
        subject_id: UUID,
        top_k: int = 5,
        threshold: float = 0.72
    ) -> list[CurriculumChunk]:
        """Embed query_text and find similar chunks. Used by content curation in M3."""
```

SQL for cosine similarity search:
```sql
SELECT *, 1 - (embedding <=> :query_embedding) AS similarity
FROM curriculum_chunks
WHERE curriculum_id = :curriculum_id
  AND subject_id = :subject_id
  AND embedding IS NOT NULL
ORDER BY embedding <=> :query_embedding
LIMIT :top_k;
```

---

## Acceptance Criteria

### Unit Tests (`test_ingest_curriculum.py`)

- [ ] `test_chunking_when_500_token_text_then_single_chunk_produced`

- [ ] `test_chunking_when_1100_token_text_then_three_chunks_with_overlap`
  - Chunk 1: tokens 0–499, Chunk 2: tokens 450–949, Chunk 3: tokens 900–1099

- [ ] `test_subtopic_resolution_when_text_contains_subtopic_name_then_subtopic_id_set`

- [ ] `test_subtopic_resolution_when_no_match_then_subtopic_id_null_and_warning_logged`

- [ ] `test_resumable_when_chunk_already_has_embedding_then_skipped`

### Integration Tests (`test_rag_retriever.py`)

- [ ] `test_get_relevant_chunks_when_valid_subtopic_then_returns_3_chunks`
  - Seed 5 chunks with embeddings → retriever returns top 3

- [ ] `test_similarity_search_when_query_algebraic_equations_then_similarity_above_0_7`
  - Requires real embeddings — mark as `@pytest.mark.slow` and skip in fast CI

- [ ] `test_similarity_search_when_below_threshold_then_filtered_out`

### Manual Verification

- [ ] Script processes a 50-page Cambridge Math PDF without errors
- [ ] Chunks average 450–550 tokens
- [ ] Every `curriculum_chunk` has non-null `embedding` after run
- [ ] Every touched `subtopic` has non-null `embedding`
- [ ] Cosine similarity search on "quadratic equations" returns chunks with similarity > 0.7

---

## Output of This Task

- `ingest_curriculum.py` script
- `embedder.py` with batch embedding + subtopic embedding fallback
- `retriever.py` with cosine similarity search used by M3 content curation and M4 lesson planning
- All unit + integration tests passing

**Unlocks:** M3-1-T1 (content curator uses `retriever.similarity_search`), M4-1-T1 (lesson plan uses `retriever.get_relevant_chunks`)
