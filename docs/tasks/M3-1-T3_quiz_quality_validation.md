# M3-1-T3 — Quiz Quality Validation
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-1 — Content & Quiz Generation
**Task ID:** M3-1-T3
**Depends on:** M3-1-T2 (QuizGenerator exists), M1-2-T2 (subtopic embeddings in pgvector)
**Blocks:** Nothing — M3-1-T2 runs first; this adds a validation layer on top
**Estimated effort:** 3–4 hours
**Executor:** Coding agent

> **Why this task exists:**
> LLM-generated quiz questions have no quality gate. A question could be factually wrong,
> reference an incorrect syllabus concept, or be at the wrong difficulty level for the
> student's grade. In a Cambridge school context, an incorrect question appearing in a
> student's study plan is a serious credibility issue. This task adds a semantic
> similarity check using pgvector and a word count check before any generated
> question reaches a student.
>
> **What the automated gate catches:** questions semantically misaligned with the
> subtopic's learning objective (cosine similarity < 0.55), and questions too long
> for Grades 6–10 (> 120 words).
>
> **What it cannot catch:** factual errors and bad MCQ distractors require human
> judgment. Those are handled by Vibhu's pre-launch review tracked in M6-3-T5.

---

## Kramer — Implementation

### Architecture: Validation Pipeline

Add a `QuizValidator` class that `QuizGenerator.generate_quiz()` calls before returning:

```
QuizGenerator.generate_quiz()
  → LLM generates raw questions
  → QuizValidator.validate_batch(questions, subtopic_id)
    → For each question:
        semantic_score = pgvector_similarity(question.text, subtopic.embedding)
        if semantic_score < SIMILARITY_THRESHOLD: discard + log
        if passes_content_safety(question.text): keep
        else: discard + log
  → If < 5 valid questions remain:
      retry_once → re-generate rejected questions
      if still < 5 after retry: raise QuizGenerationError("Insufficient quality")
  → Return validated questions
```

### Semantic Similarity Check

Uses the same pgvector infrastructure already in place for RAG retrieval:

```python
# backend/app/services/quiz_validator.py

"""Quiz question quality validation using pgvector semantic similarity.

Ensures LLM-generated quiz questions are semantically aligned with the
target subtopic's curriculum content before they reach students.
"""

import structlog
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import numpy as np

from app.models.curriculum import Subtopic
from app.ai.rag.embedder import embed_text  # existing embedder from M1-2-T2

logger = structlog.get_logger()

# Minimum semantic similarity between question text and subtopic embedding.
# Below this threshold, the question is likely off-topic or misaligned.
# Set at 0.55 — calibrated to reject clearly off-topic questions without
# being too strict on questions that use different vocabulary from the textbook.
SIMILARITY_THRESHOLD = 0.55

# Maximum tokens in a question before it's flagged as too complex for Gr.6-10.
MAX_QUESTION_TOKENS = 120

class QuizValidator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_question(
        self,
        question_text: str,
        subtopic_id: UUID,
        grade_level: int,
    ) -> tuple[bool, str]:
        """Validate a single question against the target subtopic.

        Returns:
            (is_valid: bool, rejection_reason: str | "")
        """
        # Gate 1: Semantic similarity
        subtopic = await self.db.scalar(
            select(Subtopic).where(Subtopic.id == subtopic_id)
        )
        if subtopic is None or subtopic.embedding is None:
            # Cannot validate without embedding — pass through
            logger.warning(
                "quiz_validation_skipped_no_embedding",
                subtopic_id=str(subtopic_id),
            )
            return True, ""

        question_embedding = await embed_text(question_text)
        similarity = float(np.dot(question_embedding, subtopic.embedding) /
                           (np.linalg.norm(question_embedding) * np.linalg.norm(subtopic.embedding)))

        if similarity < SIMILARITY_THRESHOLD:
            logger.warning(
                "quiz_question_rejected_low_similarity",
                subtopic_id=str(subtopic_id),
                similarity=round(similarity, 3),
                threshold=SIMILARITY_THRESHOLD,
                question_preview=question_text[:80],
            )
            return False, f"Low semantic similarity: {similarity:.3f} < {SIMILARITY_THRESHOLD}"

        # Gate 2: Length/complexity heuristic
        word_count = len(question_text.split())
        if word_count > MAX_QUESTION_TOKENS:
            logger.warning(
                "quiz_question_rejected_too_complex",
                word_count=word_count,
                max=MAX_QUESTION_TOKENS,
                question_preview=question_text[:80],
            )
            return False, f"Question too long ({word_count} words > {MAX_QUESTION_TOKENS})"

        return True, ""

    async def validate_batch(
        self,
        questions: list[dict],
        subtopic_id: UUID,
        grade_level: int,
    ) -> list[dict]:
        """Validate a batch of generated questions.

        Returns only questions that pass all validation gates.
        Logs rejected questions with reasons.
        """
        validated = []
        rejected_count = 0

        for q in questions:
            is_valid, reason = await self.validate_question(
                question_text=q["question_text"],
                subtopic_id=subtopic_id,
                grade_level=grade_level,
            )
            if is_valid:
                validated.append(q)
            else:
                rejected_count += 1
                logger.info(
                    "quiz_question_rejected",
                    subtopic_id=str(subtopic_id),
                    reason=reason,
                )

        if rejected_count > 0:
            logger.info(
                "quiz_validation_complete",
                total=len(questions),
                passed=len(validated),
                rejected=rejected_count,
            )

        return validated
```

### Integrate into QuizGenerator

Update `backend/app/ai/quiz_generator.py` (from M3-1-T2):

```python
# In QuizGenerator.generate_quiz() — add after LLM response parsing:

from app.services.quiz_validator import QuizValidator

# ... existing LLM call and parsing ...
raw_questions = self._parse_llm_response(llm_response)

# Validate
validator = QuizValidator(self.db)
valid_questions = await validator.validate_batch(
    questions=raw_questions,
    subtopic_id=subtopic_id,
    grade_level=grade_level,
)

# If fewer than 5 valid questions, retry once
if len(valid_questions) < 5:
    logger.warning(
        "quiz_insufficient_valid_questions_retrying",
        subtopic_id=str(subtopic_id),
        valid_count=len(valid_questions),
    )
    # Re-generate the number of missing questions
    needed = 5 - len(valid_questions)
    retry_response = await self._call_llm(
        subtopic_id=subtopic_id,
        num_questions=needed + 2,  # ask for 2 extra to account for possible rejection
        student_profile=student_profile,
    )
    retry_questions = self._parse_llm_response(retry_response)
    retry_valid = await validator.validate_batch(
        questions=retry_questions,
        subtopic_id=subtopic_id,
        grade_level=grade_level,
    )
    valid_questions.extend(retry_valid)

if len(valid_questions) < 3:
    # Cannot produce a viable quiz — degraded state
    raise QuizGenerationError(
        f"Insufficient valid questions after retry: {len(valid_questions)}/5"
    )

# Take first 5 valid questions
return GeneratedQuiz(
    subtopic_id=subtopic_id,
    questions=valid_questions[:5],
    generated_at=datetime.utcnow(),
    interests_used=top_2_interests,
)
```

---

## Files to Create / Modify

```
backend/app/services/quiz_validator.py                ← CREATE
backend/app/ai/quiz_generator.py                      ← MODIFY: add validator call
backend/scripts/quiz_quality_review.py                ← CREATE (review harness)
backend/data/quiz_review/                             ← CREATE directory (gitignored)
backend/app/tests/unit/test_quiz_validator.py         ← CREATE
```

Add `backend/data/quiz_review/` to `.gitignore`.

---

## Unit Tests

```python
# test_quiz_validator.py

class TestQuizValidator:
    async def test_validate_question_when_high_similarity_then_passes(
        self, db_session, seeded_subtopic_with_embedding
    ):
        validator = QuizValidator(db_session)
        # Question is clearly about the subtopic topic
        on_topic_question = "What is the formula for calculating the area of a circle?"
        is_valid, reason = await validator.validate_question(
            question_text=on_topic_question,
            subtopic_id=seeded_subtopic_with_embedding.id,
            grade_level=8,
        )
        assert is_valid is True
        assert reason == ""

    async def test_validate_question_when_no_embedding_then_passes_through(
        self, db_session, seeded_subtopic_without_embedding
    ):
        # Cannot validate without embedding — should not block
        validator = QuizValidator(db_session)
        is_valid, reason = await validator.validate_question(
            question_text="Any question text",
            subtopic_id=seeded_subtopic_without_embedding.id,
            grade_level=8,
        )
        assert is_valid is True  # pass-through, not rejection

    async def test_validate_question_when_too_long_then_rejected(
        self, db_session, seeded_subtopic_with_embedding
    ):
        validator = QuizValidator(db_session)
        very_long_question = "word " * 150  # 150 words — exceeds MAX_QUESTION_TOKENS
        is_valid, reason = await validator.validate_question(
            question_text=very_long_question,
            subtopic_id=seeded_subtopic_with_embedding.id,
            grade_level=8,
        )
        assert is_valid is False
        assert "too long" in reason.lower()

    async def test_validate_batch_when_all_valid_then_all_returned(
        self, db_session, seeded_subtopic_with_embedding
    ):
        validator = QuizValidator(db_session)
        questions = [{"question_text": f"Valid question about topic {i}"} for i in range(5)]
        result = await validator.validate_batch(
            questions=questions,
            subtopic_id=seeded_subtopic_with_embedding.id,
            grade_level=8,
        )
        assert len(result) == 5

    async def test_validate_batch_when_some_invalid_then_only_valid_returned(
        self, db_session, seeded_subtopic_with_embedding
    ):
        validator = QuizValidator(db_session)
        questions = [
            {"question_text": "valid relevant question for this subtopic"},
            {"question_text": "completely unrelated question about unrelated topic X Y Z"},
        ]
        # Mock similarity to return 0.8 for first, 0.2 for second
        with mock.patch.object(validator, 'validate_question',
                                side_effect=[(True, ""), (False, "Low similarity: 0.2")]):
            result = await validator.validate_batch(questions, seeded_subtopic_with_embedding.id, 8)
        assert len(result) == 1
```

---

## Acceptance Criteria

- [ ] `QuizValidator.validate_question()` returns `(False, reason)` for questions with similarity < 0.55
- [ ] `QuizValidator.validate_question()` returns `(True, "")` for on-topic questions
- [ ] Questions with subtopics that have no embedding pass through without rejection
- [ ] `QuizGenerator.generate_quiz()` calls validator before returning
- [ ] Retry logic triggers when fewer than 5 valid questions returned
- [ ] Quiz degrades gracefully (< 3 valid → `QuizGenerationError`, not crash)
- [ ] All rejected questions logged at WARNING level with similarity score
- [ ] Pre-launch quiz review is tracked in M6-3-T5 pre-launch checklist (not part of this coding task)
- [ ] All unit tests pass
- [ ] `mypy app/` passes with zero errors

---

## Calibration Note on `SIMILARITY_THRESHOLD = 0.55`

This threshold was chosen conservatively. After running the pilot school's first
100 quiz sessions, analyze the rejection rate:
- If rejection rate > 30%: lower threshold to 0.45 (too many false rejections)
- If acceptance rate includes clearly wrong questions: raise threshold to 0.65

Update the constant and this document when threshold is adjusted post-pilot.
