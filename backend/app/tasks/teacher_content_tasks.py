"""Celery tasks for teacher-requested school-scoped content generation.

When a teacher calls POST /{subtopic_id}/{content_type}/generate, the route
creates a school-scoped placeholder row and enqueues this task. The task
performs the actual LLM/YouTube generation and updates the placeholder so the
teacher can review and approve it.

Supported content_types:
  - quiz        → LLM-generated MCQs saved to quiz_questions
  - explanation → LLM-generated explanation saved to explanation_text
  - video       → YouTube search saved as video candidates (JSONB array)
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import attributes as orm_attrs

from app.ai.providers import router as llm_router
from app.core.config import settings
from app.core.database import CeleryAsyncSessionLocal
from app.models.curriculum import CurriculumTopic, Grade, Subject, Subtopic
from app.models.subtopic_content import SubtopicContent
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_QUIZ_PROMPT = """Generate 5 multiple-choice quiz questions for the following subtopic.
Subtopic: {subtopic_name}
Subject: {subject}
Grade level: {grade_level}

Each question should:
- Test understanding of a key concept specific to this subtopic
- Have exactly 4 options labelled A, B, C, D — one correct answer
- Include a brief explanation of why the correct answer is right
- Include a difficulty_level integer from 1 (easy recall) to 5 (hard application/analysis),
  appropriate for the grade level. Vary difficulty across the 5 questions.

Respond with ONLY a valid JSON object, no markdown, no extra keys:
{{
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "What is...?",
      "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
      "correct_answer": "A",
      "explanation": "A is correct because...",
      "difficulty_level": 2
    }},
    ...4 more questions...
  ]
}}
"""

_EXPLANATION_PROMPT = """Write a clear, concise educational explanation for the following subtopic.
Subtopic: {subtopic_name}
Subject: {subject}
Grade level: {grade_level}
Learning objective: {learning_objective}

Requirements:
- 150-250 words
- Use plain language appropriate for Grade {grade_level} students
- Cover the core concept directly
- Do not use bullet points — write in flowing prose

Respond with plain text only, no markdown.
"""


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)  # type: ignore[misc]
def generate_teacher_requested_content(
    self: object,
    subtopic_id: str,
    content_type: str,
    school_id: str,
) -> dict[str, object]:
    """Generate school-scoped content on behalf of a teacher request.

    Updates the existing placeholder SubtopicContent row created by the route handler.
    Sets is_active=True on success so the teacher can see and review the generated content.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _run_generate(
                task=self,
                subtopic_id=subtopic_id,
                content_type=content_type,
                school_id=school_id,
            )
        )
    finally:
        loop.close()


async def _run_generate(
    task: object,
    subtopic_id: str,
    content_type: str,
    school_id: str,
) -> dict[str, object]:
    subtopic_uuid = uuid.UUID(subtopic_id)
    school_uuid = uuid.UUID(school_id)

    async with CeleryAsyncSessionLocal() as db:
        # Load subtopic with curriculum metadata for prompt context
        result = await db.execute(
            select(Subtopic)
            .where(Subtopic.id == subtopic_uuid)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        )
        subtopic = result.scalar_one_or_none()
        if subtopic is None:
            logger.error("teacher_content_subtopic_not_found", subtopic_id=subtopic_id)
            return {"error": "subtopic_not_found"}

        ct_result = await db.execute(
            select(CurriculumTopic, Subject, Grade)
            .join(Subject, Subject.id == CurriculumTopic.subject_id)
            .join(Grade, Grade.id == CurriculumTopic.grade_id)
            .where(CurriculumTopic.id == subtopic.curriculum_topic_id)
        )
        row = ct_result.first()
        subject_name = row[1].name if row else "Mathematics"
        grade_level = row[2].level if row else 8
        learning_objective = subtopic.learning_objective or ""

        # Load the placeholder row to update
        placeholder_result = await db.execute(
            select(SubtopicContent).where(
                SubtopicContent.subtopic_id == subtopic_uuid,
                SubtopicContent.content_type == content_type,
                SubtopicContent.scope == "school",
                SubtopicContent.school_id == school_uuid,
                SubtopicContent.is_active.is_(False),
            )
        )
        placeholder = placeholder_result.scalar_one_or_none()
        if placeholder is None:
            logger.error(
                "teacher_content_placeholder_not_found",
                subtopic_id=subtopic_id,
                content_type=content_type,
                school_id=school_id,
            )
            return {"error": "placeholder_not_found"}

        now = datetime.now(UTC)

        if content_type == "quiz":
            questions = await _generate_quiz(subtopic.name, subject_name, grade_level)
            if not questions:
                logger.critical(
                    "teacher_quiz_generation_failed",
                    subtopic_id=subtopic_id,
                    school_id=school_id,
                    exc_info=True,
                )
                return {"error": "generation_failed"}
            placeholder.quiz_questions = questions
            orm_attrs.flag_modified(placeholder, "quiz_questions")
            placeholder.quiz_questions_count = len(questions)
            placeholder.is_active = True
            placeholder.updated_at = now

        elif content_type == "explanation":
            text = await _generate_explanation(subtopic.name, subject_name, grade_level, learning_objective)
            if not text:
                logger.critical(
                    "teacher_explanation_generation_failed",
                    subtopic_id=subtopic_id,
                    school_id=school_id,
                    exc_info=True,
                )
                return {"error": "generation_failed"}
            placeholder.explanation_text = text
            placeholder.is_active = True
            placeholder.updated_at = now

        elif content_type == "video":
            videos = await _search_videos(subtopic.name, subject_name, grade_level)
            if not videos:
                logger.warning(
                    "teacher_video_search_no_results",
                    subtopic_id=subtopic_id,
                    school_id=school_id,
                )
                # Not critical — teacher can add manually; keep placeholder inactive
                return {"status": "no_videos_found"}
            placeholder.videos = videos
            orm_attrs.flag_modified(placeholder, "videos")
            placeholder.is_active = True
            placeholder.updated_at = now

        await db.commit()

        logger.info(
            "teacher_content_generated",
            subtopic_id=subtopic_id,
            content_type=content_type,
            school_id=school_id,
        )
        return {"status": "ok", "content_type": content_type, "subtopic_id": subtopic_id}


async def _generate_quiz(subtopic_name: str, subject_name: str, grade_level: int) -> list[dict[str, Any]]:
    prompt = _QUIZ_PROMPT.format(
        subtopic_name=subtopic_name,
        subject=subject_name,
        grade_level=f"Grade {grade_level}",
    )
    try:
        raw = await llm_router.complete(
            task="content_seed",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        parsed: dict[str, Any] = json.loads(clean)
        questions: list[dict[str, Any]] = parsed.get("questions", [])
        return questions
    except Exception as exc:
        logger.error("teacher_quiz_llm_failed", error=str(exc))
        return []


async def _generate_explanation(
    subtopic_name: str, subject_name: str, grade_level: int, learning_objective: str
) -> str:
    prompt = _EXPLANATION_PROMPT.format(
        subtopic_name=subtopic_name,
        subject=subject_name,
        grade_level=grade_level,
        learning_objective=learning_objective or subtopic_name,
    )
    try:
        return await llm_router.complete(
            task="content_seed",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
        )
    except Exception as exc:
        logger.error("teacher_explanation_llm_failed", error=str(exc))
        return ""


async def _search_videos(subtopic_name: str, subject_name: str, grade_level: int) -> list[dict[str, Any]]:
    api_key = settings.youtube_data_api_key
    if not api_key:
        logger.warning("teacher_video_youtube_api_key_missing")
        return []

    from app.services.youtube_service import search_youtube_videos

    subtopic_dict = {
        "name": subtopic_name,
        "_strand_id": subject_name,
        "grade_level": f"Grade {grade_level}",
    }
    loop = asyncio.get_event_loop()
    candidates = await loop.run_in_executor(
        None,
        lambda: search_youtube_videos(subtopic_dict, api_key=api_key),
    )
    return [
        {
            "url": v.get("video_url", ""),
            "title": v.get("title", ""),
            "channel": v.get("video_provider", ""),
            "thumbnail_url": v.get("video_thumbnail_url"),
            "duration_seconds": v.get("video_duration_seconds"),
            "view_count": None,
            "status": "pending",
            "last_checked_at": None,
        }
        for v in candidates
    ]
