"""Lesson plan Celery tasks.

On-demand generation: teacher triggers via POST /classes/{class_id}/lesson-plans/generate.
No GapState queries here — lesson plans use StudentLearningProfile (modality + interests) only.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from uuid import UUID

import celery
import litellm
import resend  # type: ignore[import]
import structlog
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import router as llm_router
from app.core.config import settings
from app.core.database import CeleryAsyncSessionLocal
from app.models.curriculum import Grade, Subject, Subtopic
from app.models.lesson_plan import LessonPlan, LessonPlanFailureCode, LessonPlanStatus
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment
from app.models.user import User
from app.schemas.lesson_plan_content import LessonPlanContent
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

TASK_NAME = "lesson_plan_tasks.generate_lesson_plan"

_CORRECTION_PROMPT = (
    "Your previous response could not be parsed as valid JSON matching the required schema.\n\n"
    "Error: {error}\n\n"
    "Previous response (first 500 chars):\n{previous_response}\n\n"
    "Return ONLY valid JSON matching the exact schema. No markdown fences, no prose."
)


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------


def send_lesson_plan_ready_email(teacher_email: str, plan_id: str, class_name: str) -> None:
    """Send success email to teacher with BCC to kaihle-admin. Non-fatal — log on failure."""
    try:
        resend.api_key = settings.resend_api_key
        plan_url = f"{settings.teacher_app_url}/lesson-plans/{plan_id}"
        resend.Emails.send(
            {
                "from": settings.from_email,
                "to": [teacher_email],
                "bcc": [settings.kaihle_admin_email],
                "subject": f"Your lesson plan for {class_name} is ready",
                "html": (
                    f"<p>Your lesson plan for <strong>{class_name}</strong> has been generated.</p>"
                    f'<p><a href="{plan_url}">View lesson plan →</a></p>'
                ),
            }
        )
    except Exception as exc:
        logger.warning("lesson_plan_ready_email_failed", plan_id=plan_id, error=str(exc))


def send_lesson_plan_failed_email(plan_id: str, class_name: str, reason: str) -> None:
    """Send failure notification to kaihle-admin only. Non-fatal — log on failure."""
    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.from_email,
                "to": [settings.kaihle_admin_email],
                "subject": f"[ALERT] Lesson plan generation failed — {class_name}",
                "html": f"<p>Plan ID: {plan_id}<br>Class: {class_name}<br>Reason: {reason}</p>",
            }
        )
    except Exception as exc:
        logger.warning("lesson_plan_failed_email_failed", plan_id=plan_id, error=str(exc))


async def _fetch_teacher_email(teacher_id: str, db: AsyncSession) -> str | None:
    user = await db.get(User, UUID(teacher_id))
    return user.email if user else None


# ---------------------------------------------------------------------------
# Context building (learning styles only — never GapState)
# ---------------------------------------------------------------------------


def _compute_class_context(profiles: list) -> dict:
    """Aggregate modality scores and interests from StudentLearningProfile objects.

    Returns {modality_distribution, top_interests, student_count}.
    Never reads GapState — lesson plans use learning styles only.
    """
    if not profiles:
        return {"modality_distribution": {}, "top_interests": [], "student_count": 0}

    modality_keys = ["visual", "auditory", "reading_writing", "kinesthetic"]
    totals: dict[str, float] = defaultdict(float)
    interest_counts: dict[str, int] = defaultdict(int)

    for profile in profiles:
        for k in modality_keys:
            totals[k] += float((profile.modality_scores or {}).get(k, 0.0))
        for interest in profile.interests or []:
            interest_counts[interest] += 1

    n = len(profiles)
    modality_distribution = {k: round(totals[k] / n, 3) for k in modality_keys}
    top_interests = [i for i, _ in sorted(interest_counts.items(), key=lambda x: -x[1])[:5]]

    return {
        "modality_distribution": modality_distribution,
        "top_interests": top_interests,
        "student_count": n,
    }


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _try_validate(raw_text: str) -> tuple[dict | None, str]:
    """Parse and Pydantic-validate raw LLM text. Returns (parsed_dict, error_message)."""
    try:
        parsed = json.loads(raw_text.strip())
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    try:
        LessonPlanContent.model_validate(parsed)
        return parsed, ""
    except ValidationError as exc:
        return None, f"Schema validation error: {exc}"


# ---------------------------------------------------------------------------
# Core async generation logic
# ---------------------------------------------------------------------------


async def _generate(
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    duration_minutes: int,
    teacher_id: str,
    db: AsyncSession,
) -> None:
    """Core async generation. Called by both the Celery entry point and tests."""
    log = logger.bind(lesson_plan_id=lesson_plan_id, class_id=class_id)

    # ── Load plan ─────────────────────────────────────────────────────────────
    result = await db.execute(select(LessonPlan).where(LessonPlan.id == UUID(lesson_plan_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        log.error("lesson_plan_not_found")
        return

    if plan.status != LessonPlanStatus.GENERATING:
        log.warning("lesson_plan_not_generating", status=plan.status)
        return

    # ── Load class, grade, subject ────────────────────────────────────────────
    class_result = await db.execute(select(Class).where(Class.id == UUID(class_id)))
    cls = class_result.scalar_one_or_none()
    if not cls:
        log.error("lesson_plan_class_not_found")
        await _mark_archived(plan, db, LessonPlanFailureCode.CLASS_NOT_FOUND, "Class record not found.")
        send_lesson_plan_failed_email(lesson_plan_id, "Unknown class", "Class not found")
        return

    grade = await db.get(Grade, cls.grade_id) if cls.grade_id else None
    subject = await db.get(Subject, cls.subject_id) if cls.subject_id else None
    grade_name = grade.name if grade else "Unknown Grade"
    subject_name = subject.name if subject else "Unknown Subject"

    # ── Learning profiles (StudentLearningProfile only — no GapState) ─────────
    enrolled_result = await db.execute(
        select(ClassEnrollment.student_id).where(ClassEnrollment.class_id == UUID(class_id))
    )
    student_ids = [row[0] for row in enrolled_result.all()]

    if student_ids:
        profiles_result = await db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id.in_(student_ids))
        )
        profiles = list(profiles_result.scalars().all())
    else:
        profiles = []

    class_context = _compute_class_context(profiles)

    plan.class_context_snapshot = class_context
    log.info("lesson_plan_context_built", student_count=class_context["student_count"])

    # ── Fetch subtopic names from curriculum (no GapState) ────────────────────
    subtopic_uuids = [UUID(s) for s in focus_subtopic_ids if s]
    subtopics_for_prompt: list[dict] = []
    if subtopic_uuids:
        sub_result = await db.execute(select(Subtopic).where(Subtopic.id.in_(subtopic_uuids)))
        for sub in sub_result.scalars().all():
            subtopics_for_prompt.append({"name": sub.name, "learning_objective": sub.learning_objective or ""})

    # ── Render prompt ─────────────────────────────────────────────────────────
    template = _jinja_env.get_template("lesson_plan.jinja2")
    prompt_text = template.render(
        class_name=cls.name,
        subject_name=subject_name,
        grade_name=grade_name,
        student_count=class_context["student_count"],
        duration_minutes=duration_minutes,
        subtopics=subtopics_for_prompt,
        modality_distribution=class_context["modality_distribution"],
        top_interests=class_context["top_interests"],
    )

    # ── LLM call (streaming for reliability on long outputs) ──────────────────
    try:
        response_text = await llm_router.complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=4000,
            stream=True,
        )
    except litellm.AuthenticationError as exc:
        log.error("lesson_plan_llm_auth_failed", error=str(exc), exc_info=True)
        await _mark_archived(plan, db, LessonPlanFailureCode.LLM_AUTH_ERROR, "LLM authentication failed.")
        send_lesson_plan_failed_email(lesson_plan_id, cls.name, f"LLM auth error: {exc}")
        return
    except litellm.RateLimitError:
        # Transient — re-raise so Celery retries. Plan stays in GENERATING.
        log.warning("lesson_plan_llm_rate_limited_will_retry", exc_info=True)
        raise
    except Exception as exc:
        log.error("lesson_plan_llm_unexpected_error", error=str(exc), exc_info=True)
        await _mark_archived(plan, db, LessonPlanFailureCode.LLM_UNEXPECTED_ERROR, f"Unexpected LLM error: {exc}")
        send_lesson_plan_failed_email(lesson_plan_id, cls.name, f"Unexpected error: {exc}")
        return

    # Store raw output immediately — even if validation fails
    plan.raw_llm_output = response_text
    log.info("lesson_plan_llm_response_received", chars=len(response_text))

    # ── Validate — one correction retry ──────────────────────────────────────
    parsed, error = _try_validate(response_text)

    if parsed is None:
        log.warning("lesson_plan_validation_failed_first_attempt", error=error)
        correction_prompt = _CORRECTION_PROMPT.format(error=error, previous_response=response_text[:500])
        try:
            retry_text = await llm_router.complete(
                task="lesson_plan",
                messages=[
                    {"role": "user", "content": prompt_text},
                    {"role": "assistant", "content": response_text},
                    {"role": "user", "content": correction_prompt},
                ],
                max_tokens=4000,
                stream=True,
            )
            plan.raw_llm_output = retry_text
            parsed, error = _try_validate(retry_text)
        except Exception as exc:
            log.error("lesson_plan_correction_llm_error", error=str(exc), exc_info=True)
            error = f"Correction LLM error: {exc}"
            parsed = None

    if parsed is None:
        log.error("lesson_plan_validation_failed_after_retry", error=error)
        await _mark_archived(plan, db, LessonPlanFailureCode.JSON_PARSE_FAILED, error)
        send_lesson_plan_failed_email(lesson_plan_id, cls.name, f"Validation failed after retry: {error}")
        return

    # ── Success ───────────────────────────────────────────────────────────────
    # Fetch email before commit — session expires after commit in async SQLAlchemy
    teacher_email = await _fetch_teacher_email(teacher_id, db)

    plan.generated_plan = parsed
    plan.status = LessonPlanStatus.GENERATED
    await db.commit()
    log.info("lesson_plan_generation_completed")

    if teacher_email:
        send_lesson_plan_ready_email(teacher_email, lesson_plan_id, cls.name)
    else:
        log.warning("lesson_plan_teacher_email_not_found", teacher_id=teacher_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mark_archived(
    plan: LessonPlan,
    db: AsyncSession,
    failure_code: str,
    user_message: str | None = None,
) -> None:
    plan.status = LessonPlanStatus.ARCHIVED
    plan.failure_code = failure_code
    plan.failure_reason = user_message or failure_code
    await db.commit()
    logger.error(
        "lesson_plan_archived",
        plan_id=str(plan.id),
        failure_code=failure_code,
    )


# ---------------------------------------------------------------------------
# Celery task class (CONSTITUTION Rule 18 — CRITICAL log on final retry)
# ---------------------------------------------------------------------------


class GenerateLessonPlanTask(celery.Task):  # type: ignore[type-arg]
    """Emits CRITICAL log on final retry exhaustion (CONSTITUTION Rule 18)."""

    def on_failure(  # type: ignore[override]
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object
    ) -> None:
        # Only emit CRITICAL on true final exhaustion (Rule 18), not on each retry attempt
        if self.request.retries < self.max_retries:
            return
        lesson_plan_id = args[0] if args else kwargs.get("lesson_plan_id")
        class_id = args[1] if len(args) > 1 else kwargs.get("class_id")
        logger.critical(
            "generate_lesson_plan_permanently_failed",
            task_id=task_id,
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=GenerateLessonPlanTask,
    max_retries=2,
    name=TASK_NAME,
    queue="celery",
)
def generate_lesson_plan_task(
    self: GenerateLessonPlanTask,
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    duration_minutes: int = 45,
    teacher_id: str = "",
) -> None:
    """Celery entry point — runs async generation logic in a new event loop.

    Uses new_event_loop() per CONSTITUTION Rule (never asyncio.run inside Celery).
    max_retries=2 covers transient LLM rate limits. Permanent failures (auth, parse)
    are archived inside _generate and do not propagate here.
    """
    logger.info(
        "lesson_plan_task_started",
        lesson_plan_id=lesson_plan_id,
        class_id=class_id,
        duration_minutes=duration_minutes,
    )

    async def _run() -> None:
        async with CeleryAsyncSessionLocal() as session:
            await _generate(lesson_plan_id, class_id, focus_subtopic_ids, duration_minutes, teacher_id, session)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    except litellm.RateLimitError as exc:
        # Transient — Celery will retry (up to max_retries=2) with 60s back-off
        logger.warning(
            "lesson_plan_rate_limit_retry",
            lesson_plan_id=lesson_plan_id,
            retries=self.request.retries,
        )
        raise self.retry(exc=exc, countdown=60)
    except Exception as exc:
        # Unexpected exception that escaped _generate — CONSTITUTION Rule 18
        logger.critical(
            "generate_lesson_plan_permanently_failed",
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )

        # Best-effort: mark plan ARCHIVED so it doesn't stay stuck in GENERATING.
        # Open a fresh loop + session — the original may have already closed or errored.
        # Pass exc_message explicitly — nested async def can't close over `exc` reliably.
        exc_message = str(exc)

        async def _mark_failed_fallback() -> None:
            async with CeleryAsyncSessionLocal() as db:
                result = await db.execute(select(LessonPlan).where(LessonPlan.id == UUID(lesson_plan_id)))
                plan = result.scalar_one_or_none()
                if plan and plan.status == LessonPlanStatus.GENERATING:
                    plan.status = LessonPlanStatus.ARCHIVED
                    plan.failure_code = LessonPlanFailureCode.LLM_UNEXPECTED_ERROR
                    plan.failure_reason = f"Unexpected task error: {exc_message}"
                    await db.commit()
                    logger.error(
                        "lesson_plan_archived_by_fallback",
                        lesson_plan_id=lesson_plan_id,
                        error=exc_message,
                    )

        fallback_loop = asyncio.new_event_loop()
        try:
            fallback_loop.run_until_complete(_mark_failed_fallback())
        except Exception as fallback_exc:
            logger.warning(
                "lesson_plan_fallback_archive_failed",
                lesson_plan_id=lesson_plan_id,
                error=str(fallback_exc),
            )
        finally:
            fallback_loop.close()

        send_lesson_plan_failed_email(lesson_plan_id, "Unknown", f"Unexpected task error: {exc}")
        raise
    finally:
        loop.close()
