"""Mini-course generation service.

All business logic for generating interest-personalised subtopic explanations.
Called exclusively from the generate_topic_mini_course Celery task.

Architecture:
- Queries topic → curriculum_topic → subtopic chain.
- For each (subtopic, interest_category) pair, calls LLM via router.py.
- Upserts SubtopicContent rows: skips if non-rejected row already exists;
  creates new row if absent; updates rejected rows.
- Uses Jinja2 to render the mini_course_explanation prompt template.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes as orm_attrs

from app.ai.providers import router as llm_router
from app.models.curriculum import CurriculumTopic, Grade, QuestionBank, Subject, Subtopic, Topic
from app.models.interest_category import InterestCategory
from app.models.subtopic_content import SubtopicContent

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

_QUIZ_QUESTION_TARGET = 5
_QUIZ_DIFFICULTY_LEVEL = 3.0  # medium-hard, within the 3–5 range per user requirement


def _parse_quiz_response(raw: str) -> list[dict[str, Any]]:
    """Parse LLM JSON output into a list of question dicts.

    Strips optional markdown code fences, validates required fields.
    Raises ValueError on malformed output.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        questions = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    if not isinstance(questions, list) or len(questions) < 1:
        raise ValueError(f"Expected a JSON array of questions, got: {type(questions)}")

    for i, q in enumerate(questions):
        for field in ("question_text", "options", "correct_answer"):
            if field not in q:
                raise ValueError(f"Question {i} missing field '{field}'")
        if len(q["options"]) != 4:
            raise ValueError(f"Question {i} must have exactly 4 options, got {len(q['options'])}")
        option_keys = {opt["key"] for opt in q["options"]}
        if q["correct_answer"] not in option_keys:
            raise ValueError(f"Question {i} correct_answer '{q['correct_answer']}' not in option keys {option_keys}")

    return questions


# Interest categories: (db_name, human_label, interest_key)
# db_name must match interest_category_enum values in PostgreSQL.
INTEREST_CATEGORIES: list[tuple[str, str, str]] = [
    ("sports_movement", "Sports & Fitness", "sports_movement"),
    ("tech_gaming", "Technology & Innovation", "tech_gaming"),
    ("nature_animals", "Nature & Science", "nature_animals"),
    ("arts_culture", "Music & Arts", "arts_culture"),
]


class TopicNotFoundError(Exception):
    pass


class MiniCourseGenerationService:
    """Generates interest-personalised explanations for all subtopics under a topic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_for_topic(self, topic_id: str, school_id: str, dry_run: bool = False) -> dict[str, Any]:
        """Generate mini-course explanations for all subtopics of a topic.

        Idempotent: skips (subtopic_id, interest_category_id) pairs that
        already have a non-rejected row (pending or approved).

        Args:
            topic_id: UUID string of the Topic.
            school_id: UUID string of the requesting school (logged only).
            dry_run: When True, generate LLM responses but do not write to DB.
                     Returns generated texts inline in the result dict.

        Returns:
            Dict with subtopics_found, subtopics_processed, explanations_written.
            When dry_run=True, also includes a 'dry_run_results' list.

        Raises:
            TopicNotFoundError: If topic_id does not exist.
        """
        topic_uuid = uuid.UUID(topic_id)

        # 1. Fetch topic context (name, subject, grade) via CurriculumTopic
        topic_row = await self._fetch_topic_context(topic_uuid)
        if topic_row is None:
            raise TopicNotFoundError(f"Topic {topic_id} not found")

        topic_name, subject_name, grade_level = topic_row

        # 2. Fetch all subtopics for this topic (via any CurriculumTopic)
        subtopics = await self._fetch_subtopics(topic_uuid)

        # Rule 17: log WARNING and exit early if no subtopics
        if not subtopics:
            logger.warning(
                "generate_topic_mini_course_no_subtopics",
                topic_id=topic_id,
                school_id=school_id,
            )
            return {
                "subtopics_found": 0,
                "subtopics_processed": 0,
                "explanations_written": 0,
            }

        # 3. Resolve interest category IDs from DB
        category_id_map = await self._resolve_interest_category_ids()

        # 4. Batch-fetch all existing non-rejected (subtopic_id, category_id) pairs
        #    for this topic in one query — avoids N+1 point-lookups inside the loop.
        subtopic_ids = [s.id for s in subtopics]
        existing_pairs = await self._fetch_existing_content_pairs(subtopic_ids)

        # 5. Batch-fetch existing llm question counts per subtopic (one query)
        existing_question_counts = await self._fetch_existing_question_counts(subtopic_ids)

        # 6. Generate for each subtopic × interest_category (explanations) + quiz questions
        explanations_written = 0
        questions_written = 0
        subtopics_processed = 0
        dry_run_results: list[dict[str, Any]] = []

        for subtopic in subtopics:
            subtopic_written = 0
            for db_name, human_label, interest_key in INTEREST_CATEGORIES:
                category_id = category_id_map.get(db_name)
                if category_id is None:
                    logger.warning(
                        "interest_category_not_found_in_db",
                        category_name=db_name,
                        topic_id=topic_id,
                    )
                    continue

                # Skip if a non-rejected row already exists (in-memory set lookup)
                if not dry_run and (subtopic.id, category_id) in existing_pairs:
                    logger.info(
                        "mini_course_content_already_exists_skipping",
                        subtopic_id=str(subtopic.id),
                        interest_category=db_name,
                    )
                    continue

                explanation = await self._call_llm_explanation(
                    subtopic_name=subtopic.name,
                    topic_name=topic_name,
                    subject_name=subject_name,
                    grade_level=grade_level,
                    interest_category=human_label,
                    interest_key=interest_key,
                )

                if dry_run:
                    dry_run_results.append(
                        {
                            "subtopic_name": subtopic.name,
                            "interest_category": db_name,
                            "interest_label": human_label,
                            "explanation_text": explanation,
                        }
                    )
                else:
                    await self._upsert_content(
                        subtopic_id=subtopic.id,
                        interest_category_id=category_id,
                        explanation_text=explanation,
                    )
                subtopic_written += 1

            explanations_written += subtopic_written
            if subtopic_written > 0:
                subtopics_processed += 1

            # Generate quiz questions if fewer than target exist (idempotent)
            existing_count = existing_question_counts.get(subtopic.id, 0)
            if existing_count < _QUIZ_QUESTION_TARGET:
                written = await self._generate_quiz_questions(
                    subtopic_id=subtopic.id,
                    subtopic_name=subtopic.name,
                    topic_name=topic_name,
                    subject_name=subject_name,
                    grade_level=grade_level,
                    dry_run=dry_run,
                )
                questions_written += written

        if not dry_run:
            await self.db.commit()

        result: dict[str, Any] = {
            "subtopics_found": len(subtopics),
            "subtopics_processed": subtopics_processed,
            "explanations_written": explanations_written,
            "questions_written": questions_written,
        }
        if dry_run:
            result["dry_run_results"] = dry_run_results
        return result

    async def _fetch_topic_context(self, topic_id: uuid.UUID) -> tuple[str, str, int] | None:
        """Return (topic_name, subject_name, grade_level) for a topic.

        Joins through CurriculumTopic to get Subject and Grade.
        """
        result = await self.db.execute(
            select(
                Topic.name.label("topic_name"),
                Subject.name.label("subject_name"),
                Grade.level.label("grade_level"),
            )
            .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
            .join(Subject, Subject.id == CurriculumTopic.subject_id)
            .join(Grade, Grade.id == CurriculumTopic.grade_id)
            .where(Topic.id == topic_id)
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        return (row.topic_name, row.subject_name, row.grade_level)

    async def _fetch_subtopics(self, topic_id: uuid.UUID) -> list[Subtopic]:
        """Return all active subtopics for a topic via curriculum_topics."""
        result = await self.db.execute(
            select(Subtopic)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(
                CurriculumTopic.topic_id == topic_id,
                Subtopic.is_active.is_(True),
            )
            .order_by(Subtopic.sequence_order)
        )
        return list(result.scalars().all())

    async def _resolve_interest_category_ids(self) -> dict[str, uuid.UUID]:
        """Return {category_name: id} for all interest categories in DB."""
        result = await self.db.execute(select(InterestCategory))
        categories = result.scalars().all()
        return {cat.name: cat.id for cat in categories}

    async def _fetch_existing_content_pairs(self, subtopic_ids: list[uuid.UUID]) -> set[tuple[uuid.UUID, uuid.UUID]]:
        """Return set of (subtopic_id, interest_category_id) pairs that already have
        a non-rejected explanation row. One query for the whole topic batch."""
        if not subtopic_ids:
            return set()
        result = await self.db.execute(
            select(SubtopicContent.subtopic_id, SubtopicContent.interest_category_id).where(
                SubtopicContent.subtopic_id.in_(subtopic_ids),
                SubtopicContent.content_type == "explanation",
                SubtopicContent.review_status != "rejected",
                SubtopicContent.is_archived.is_(False),
            )
        )
        return {(row.subtopic_id, row.interest_category_id) for row in result.all()}

    async def _fetch_existing_question_counts(self, subtopic_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Return {subtopic_id: count} of active llm questions per subtopic. One query."""
        if not subtopic_ids:
            return {}
        result = await self.db.execute(
            select(QuestionBank.subtopic_id, func.count().label("cnt"))
            .where(
                QuestionBank.subtopic_id.in_(subtopic_ids),
                QuestionBank.is_active.is_(True),
            )
            .group_by(QuestionBank.subtopic_id)
        )
        return {row.subtopic_id: row.cnt for row in result.all()}

    async def _generate_quiz_questions(
        self,
        subtopic_id: uuid.UUID,
        subtopic_name: str,
        topic_name: str,
        subject_name: str,
        grade_level: int,
        dry_run: bool,
    ) -> int:
        """Generate and stage quiz questions for one subtopic. Returns count written.

        Self-gating: fetches the existing active staging row before calling the LLM.
        Returns 0 immediately if the row already has >= _QUIZ_QUESTION_TARGET questions,
        so callers do not need to perform their own sufficiency check.
        """
        # Fetch once; reused for both the gate check and the write below.
        # Skipped in dry_run — dry_run never touches the DB.
        quiz_content = None
        if not dry_run:
            existing_result = await self.db.execute(
                select(SubtopicContent).where(
                    SubtopicContent.subtopic_id == subtopic_id,
                    SubtopicContent.content_type == "quiz",
                    SubtopicContent.is_archived == False,  # noqa: E712
                )
            )
            quiz_content = existing_result.scalars().first()
            if quiz_content is not None and (quiz_content.quiz_questions_count or 0) >= _QUIZ_QUESTION_TARGET:
                return 0

        template = _jinja_env.get_template("mini_course_quiz.jinja2")
        prompt_text = template.render(
            subtopic_name=subtopic_name,
            topic_name=topic_name,
            subject_name=subject_name,
            grade_level=grade_level,
        )
        messages = [{"role": "user", "content": prompt_text}]
        raw = await llm_router.complete(
            task="mini_course_explanation",
            messages=messages,
            temperature=0.5,
            max_tokens=1500,
        )

        try:
            questions = _parse_quiz_response(raw)
        except ValueError:
            logger.warning(
                "mini_course_quiz_parse_failed",
                subtopic_id=str(subtopic_id),
                raw_preview=raw[:200],
            )
            return 0

        if dry_run:
            return len(questions)

        # Write to subtopic_content staging (not question_bank directly).
        # KaihleAdmin reviews and approves the batch, which then publishes to question_bank.
        existing_result = await self.db.execute(
            select(SubtopicContent).where(
                SubtopicContent.subtopic_id == subtopic_id,
                SubtopicContent.content_type == "quiz",
                SubtopicContent.is_archived == False,  # noqa: E712
            )
        )
        quiz_content = existing_result.scalars().first()

        normalized = [
            {
                "question_id": str(uuid.uuid4()),
                "question_text": q["question_text"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation"),
                "difficulty_level": _QUIZ_DIFFICULTY_LEVEL,
            }
            for q in questions
        ]

        if quiz_content is not None:
            quiz_content.quiz_questions = normalized
            quiz_content.quiz_questions_count = len(normalized)
            quiz_content.review_status = "pending"
            quiz_content.is_archived = False
            orm_attrs.flag_modified(quiz_content, "quiz_questions")
        else:
            quiz_content = SubtopicContent(
                subtopic_id=subtopic_id,
                content_type="quiz",
                quiz_questions=normalized,
                quiz_questions_count=len(normalized),
                review_status="pending",
                is_archived=False,
            )
            self.db.add(quiz_content)

        logger.info(
            "mini_course_quiz_questions_staged",
            subtopic_id=str(subtopic_id),
            count=len(questions),
        )
        return len(questions)

    async def _call_llm_explanation(
        self,
        subtopic_name: str,
        topic_name: str,
        subject_name: str,
        grade_level: int,
        interest_category: str,
        interest_key: str,
    ) -> str:
        """Render prompt and call LLM via router. Returns explanation text."""
        template = _jinja_env.get_template("mini_course_explanation.jinja2")
        prompt_text = template.render(
            subtopic_name=subtopic_name,
            topic_name=topic_name,
            subject_name=subject_name,
            grade_level=grade_level,
            interest_category=interest_category,
            interest_key=interest_key,
        )
        messages = [{"role": "user", "content": prompt_text}]
        return await llm_router.complete(
            task="mini_course_explanation",
            messages=messages,
            temperature=0.7,
            max_tokens=600,
        )

    async def _upsert_content(
        self,
        subtopic_id: uuid.UUID,
        interest_category_id: uuid.UUID,
        explanation_text: str,
    ) -> None:
        """Insert a new SubtopicContent row (or update a rejected one).

        Strategy: check for existing rejected row first — update in place.
        Otherwise insert fresh. This avoids needing a DB-level unique constraint
        while remaining idempotent when the task is retried.
        """
        result = await self.db.execute(
            select(SubtopicContent).where(
                SubtopicContent.subtopic_id == subtopic_id,
                SubtopicContent.interest_category_id == interest_category_id,
                SubtopicContent.content_type == "explanation",
                SubtopicContent.review_status == "rejected",
                SubtopicContent.is_archived.is_(False),
            )
        )
        existing_rejected = result.scalar_one_or_none()

        if existing_rejected is not None:
            existing_rejected.explanation_text = explanation_text
            existing_rejected.review_status = "pending"
            existing_rejected.rejection_reason = None
            existing_rejected.rejection_teacher_note = None
            logger.info(
                "mini_course_content_updated_rejected_row",
                subtopic_id=str(subtopic_id),
                interest_category_id=str(interest_category_id),
            )
        else:
            content = SubtopicContent(
                subtopic_id=subtopic_id,
                content_type="explanation",
                explanation_text=explanation_text,
                interest_category_id=interest_category_id,
                review_status="pending",
            )
            self.db.add(content)
            logger.info(
                "mini_course_content_created",
                subtopic_id=str(subtopic_id),
                interest_category_id=str(interest_category_id),
            )
