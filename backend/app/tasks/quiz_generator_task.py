"""Quiz Generator Celery Task — M3-1-T2.

Celery task wrapping the quiz_generator module.
Queue: ai-tasks | Broker: Redis | Hard timeout: 60s | Max retries: 1
"""

from __future__ import annotations

from uuid import UUID

import structlog
from celery import Task

from app.ai.quiz_generator import GeneratedQuiz, QuizGenerationError, generate_quiz
from app.core.database import async_session
from app.models import Student, Subtopic
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()

# Celery task configuration
QUEUE = "ai-tasks"
MAX_RETRIES = 1
HARD_TIME_LIMIT = 60  # seconds


@celery_app.task(
    bind=True,
    max_retries=MAX_RETRIES,
    time_limit=HARD_TIME_LIMIT,
    hard_time_limit=HARD_TIME_LIMIT,
    queue=QUEUE,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=30,
)
def generate_quiz_task(
    self: Task,
    subtopic_id: UUID | str,
    student_id: UUID | str,
) -> dict:
    """Generate a 5-MCQ practice quiz for a student's subtopic.

    Args:
        subtopic_id: UUID of the Subtopic to generate questions for.
        student_id: UUID of the student (owner of the gap).

    Returns:
        dict: Serialised GeneratedQuiz (see GeneratedQuiz.to_dict()).

    Raises:
        ValueError: If subtopic or student is not found.
        QuizGenerationError: If LLM call fails or output is invalid after retry.
    """
    subtopic_uuid = UUID(str(subtopic_id))
    student_uuid = UUID(str(student_id))

    logger.info(
        "quiz_generation_task_started",
        task_id=self.request.id,
        subtopic_id=str(subtopic_uuid),
        student_id=str(student_uuid),
    )

    try:
        async with async_session() as db:
            # Validate subtopic exists
            subtopic = await db.get(Subtopic, subtopic_uuid)
            if not subtopic:
                raise ValueError(f"Subtopic {subtopic_uuid} not found")

            # Validate student exists
            student = await db.get(Student, student_uuid)
            if not student:
                raise ValueError(f"Student {student_uuid} not found")

            # Load student mastery from onboarding profile
            from app.models import StudentLearningProfile

            profile = await db.get(StudentLearningProfile, student_uuid)
            # Default to 0.5 if no profile yet
            student_mastery = 0.5
            if profile and profile.mastery_levels:
                mastery_data = profile.mastery_levels
                # Try to get mastery for this subtopic
                if isinstance(mastery_data, dict):
                    student_mastery = float(mastery_data.get(str(subtopic_uuid), 0.5))

            # Generate quiz
            quiz: GeneratedQuiz = await generate_quiz(
                subtopic=subtopic,
                student_mastery=student_mastery,
                student_id=student_uuid,
                db=db,
            )

            result = quiz.to_dict()

            logger.info(
                "quiz_generation_task_completed",
                task_id=self.request.id,
                subtopic_id=str(subtopic_uuid),
                student_id=str(student_uuid),
                question_count=len(quiz.questions),
            )

            return result

    except QuizGenerationError:
        # LLM failures — log CRITICAL and re-raise
        logger.critical(
            "quiz_generation_task_failed",
            task_id=self.request.id,
            subtopic_id=str(subtopic_uuid),
            student_id=str(student_uuid),
            error=str(QuizGenerationError.__cause__),
        )
        raise

    except Exception as exc:
        logger.critical(
            "quiz_generation_task_failed",
            task_id=self.request.id,
            subtopic_id=str(subtopic_uuid),
            student_id=str(student_uuid),
            error=str(exc),
        )
        raise
