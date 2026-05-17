"""AI Smoke Test endpoints — manual verification of LLM features.

KAIHLE_ADMIN only. These endpoints call production services in-process with
real DB data so admins can verify LLM output quality and end-to-end wiring
without running automated tests that would hit real LLMs in CI.

Routes:
    POST /smoke-tests/concept-explanation
    POST /smoke-tests/mini-course
    POST /smoke-tests/lesson-plan
    POST /smoke-tests/practice-quiz
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import router as llm_router
from app.ai.quiz_generator import generate_quiz
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import Grade, Subject, Subtopic, Topic
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment
from app.models.user import UserRole
from app.services.concept_guide_service import (
    _get_dominant_modality,
    _parse_mcq,
)
from app.services.mini_course_generation_service import MiniCourseGenerationService
from app.tasks.lesson_plan_tasks import _compute_class_context, _try_validate

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/smoke-tests", tags=["smoke-tests"])

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ConceptExplanationRequest(BaseModel):
    subtopic_id: str
    student_id: str | None = None
    question: str | None = None


class ConceptExplanationResult(BaseModel):
    subtopic_name: str
    modality_used: str
    has_profile: bool
    explanation: str
    check_question: dict[str, Any] | None
    duration_ms: int


class MiniCourseRequest(BaseModel):
    topic_id: str
    school_id: str
    dry_run: bool = True


class MiniCourseResult(BaseModel):
    topic_name: str | None
    subtopics_found: int
    subtopics_processed: int
    explanations_written: int
    dry_run: bool
    dry_run_results: list[dict[str, Any]] = Field(default_factory=list)
    duration_ms: int


class LessonPlanRequest(BaseModel):
    class_id: str
    focus_subtopic_ids: list[str] = Field(default_factory=list)
    duration_minutes: int = 60
    dry_run: bool = True


class LessonPlanResult(BaseModel):
    class_name: str
    subject_name: str
    grade_name: str
    student_count: int
    modality_distribution: dict[str, float]
    top_interests: list[str]
    validation_passed: bool
    generated_plan: dict[str, Any] | None
    raw_llm_output: str | None
    error: str | None
    llm_calls: int
    duration_ms: int


class PracticeQuizRequest(BaseModel):
    subtopic_id: str
    mastery_score: float = Field(ge=0.0, le=1.0, default=0.5)
    student_id: str | None = None


class QuizQuestionResult(BaseModel):
    question_text: str
    options: list[dict[str, str]]
    correct_answer: str
    explanation: str


class PracticeQuizResult(BaseModel):
    subtopic_name: str
    difficulty_label: str
    interests_used: list[str]
    explanation_context_found: bool
    question_count: int
    questions: list[dict[str, Any]]
    duration_ms: int


# ---------------------------------------------------------------------------
# 1. Concept Explanation
# ---------------------------------------------------------------------------


@router.post("/concept-explanation", response_model=ConceptExplanationResult)
async def smoke_test_concept_explanation(
    request: ConceptExplanationRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ConceptExplanationResult:
    """Smoke test: call generate_concept_explanation() with real DB data."""
    t0 = time.monotonic()

    subtopic_result = await db.execute(
        select(Subtopic).where(Subtopic.id == UUID(request.subtopic_id), Subtopic.is_active.is_(True))
    )
    subtopic = subtopic_result.scalar_one_or_none()
    if subtopic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtopic {request.subtopic_id} not found")

    profile: StudentLearningProfile | None = None
    if request.student_id:
        profile_result = await db.execute(
            select(StudentLearningProfile).where(
                StudentLearningProfile.student_id == UUID(request.student_id),
                StudentLearningProfile.completed_at.is_not(None),
            )
        )
        profile = profile_result.scalar_one_or_none()

    modality_scores: dict[str, float] = profile.modality_scores if profile else {}
    work_style: dict[str, Any] = profile.work_style if profile else {}
    interests: list[str] = (profile.interests or []) if profile else []
    dominant_modality = _get_dominant_modality(modality_scores)

    template = _jinja_env.get_template("concept_guide.jinja2")
    prompt = template.render(
        subtopic_name=subtopic.name,
        description=subtopic.description,
        learning_objective=subtopic.learning_objective,
        keywords=subtopic.keywords,
        dominant_modality=dominant_modality,
        interests=interests[:2],
        work_style=work_style,
        question=request.question,
    )

    raw = await llm_router.complete(
        task="concept_guide",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=600,
    )

    explanation, check_question = _parse_mcq(raw)
    duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "smoke_test_concept_explanation_completed",
        subtopic_id=request.subtopic_id,
        has_profile=profile is not None,
        has_check_question=check_question is not None,
        duration_ms=duration_ms,
    )

    return ConceptExplanationResult(
        subtopic_name=subtopic.name,
        modality_used=dominant_modality,
        has_profile=profile is not None,
        explanation=explanation,
        check_question=check_question,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# 2. Mini-Course Generation
# ---------------------------------------------------------------------------


@router.post("/mini-course", response_model=MiniCourseResult)
async def smoke_test_mini_course(
    request: MiniCourseRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MiniCourseResult:
    """Smoke test: generate mini-course explanations for a topic.

    With dry_run=True (default), generates all LLM responses but does not
    write to DB. Returns generated texts inline for quality review.
    """
    t0 = time.monotonic()

    # Resolve topic name for display
    topic_result = await db.execute(select(Topic).where(Topic.id == UUID(request.topic_id)))
    topic = topic_result.scalar_one_or_none()
    topic_name = topic.name if topic else None

    service = MiniCourseGenerationService(db)
    result = await service.generate_for_topic(
        topic_id=request.topic_id,
        school_id=request.school_id,
        dry_run=request.dry_run,
    )

    duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "smoke_test_mini_course_completed",
        topic_id=request.topic_id,
        dry_run=request.dry_run,
        subtopics_found=result["subtopics_found"],
        explanations_written=result["explanations_written"],
        duration_ms=duration_ms,
    )

    return MiniCourseResult(
        topic_name=topic_name,
        subtopics_found=result["subtopics_found"],
        subtopics_processed=result["subtopics_processed"],
        explanations_written=result["explanations_written"],
        dry_run=request.dry_run,
        dry_run_results=result.get("dry_run_results", []),
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# 3. Lesson Plan (in-process, no LessonPlan DB row created)
# ---------------------------------------------------------------------------


@router.post("/lesson-plan", response_model=LessonPlanResult)
async def smoke_test_lesson_plan(
    request: LessonPlanRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResult:
    """Smoke test: generate a lesson plan preview without creating a DB row.

    Calls the full prompt-render + LLM + validation pipeline inline.
    No LessonPlan row is created or modified regardless of dry_run flag.
    """
    t0 = time.monotonic()
    llm_calls = 0

    class_result = await db.execute(select(Class).where(Class.id == UUID(request.class_id)))
    cls = class_result.scalar_one_or_none()
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Class {request.class_id} not found")

    grade = await db.get(Grade, cls.grade_id) if cls.grade_id else None
    subject = await db.get(Subject, cls.subject_id) if cls.subject_id else None
    grade_name = grade.name if grade else "Unknown Grade"
    subject_name = subject.name if subject else "Unknown Subject"

    enrolled_result = await db.execute(
        select(ClassEnrollment.student_id).where(ClassEnrollment.class_id == UUID(request.class_id))
    )
    student_ids = [row[0] for row in enrolled_result.all()]

    profiles: list[StudentLearningProfile] = []
    if student_ids:
        profiles_result = await db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id.in_(student_ids))
        )
        profiles = list(profiles_result.scalars().all())

    class_context = _compute_class_context(profiles)

    subtopic_uuids = [UUID(s) for s in request.focus_subtopic_ids if s]
    subtopics_for_prompt: list[dict[str, str]] = []
    if subtopic_uuids:
        sub_result = await db.execute(select(Subtopic).where(Subtopic.id.in_(subtopic_uuids)))
        for sub in sub_result.scalars().all():
            subtopics_for_prompt.append({"name": sub.name, "learning_objective": sub.learning_objective or ""})

    template = _jinja_env.get_template("lesson_plan.jinja2")
    prompt_text = template.render(
        class_name=cls.name,
        subject_name=subject_name,
        grade_name=grade_name,
        student_count=class_context["student_count"],
        duration_minutes=request.duration_minutes,
        subtopics=subtopics_for_prompt,
        modality_distribution=class_context["modality_distribution"],
        top_interests=class_context["top_interests"],
    )

    try:
        response_text = await llm_router.complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=4000,
            stream=True,
        )
        llm_calls += 1
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return LessonPlanResult(
            class_name=cls.name,
            subject_name=subject_name,
            grade_name=grade_name,
            student_count=class_context["student_count"],
            modality_distribution=class_context["modality_distribution"],
            top_interests=class_context["top_interests"],
            validation_passed=False,
            generated_plan=None,
            raw_llm_output=None,
            error=f"LLM call failed: {exc}",
            llm_calls=llm_calls,
            duration_ms=duration_ms,
        )

    parsed, error = _try_validate(response_text)

    # One correction retry if first attempt fails
    if parsed is None:
        _CORRECTION_PROMPT = (
            "Your previous response could not be parsed as valid JSON matching the required schema.\n\n"
            f"Error: {error}\n\n"
            f"Previous response (first 500 chars):\n{response_text[:500]}\n\n"
            "Return ONLY valid JSON matching the exact schema. No markdown fences, no prose."
        )
        try:
            retry_text = await llm_router.complete(
                task="lesson_plan",
                messages=[
                    {"role": "user", "content": prompt_text},
                    {"role": "assistant", "content": response_text},
                    {"role": "user", "content": _CORRECTION_PROMPT},
                ],
                max_tokens=4000,
                stream=True,
            )
            llm_calls += 1
            parsed, error = _try_validate(retry_text)
            if parsed is not None:
                response_text = retry_text
        except Exception as exc:
            error = f"Correction LLM error: {exc}"
            parsed = None

    duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "smoke_test_lesson_plan_completed",
        class_id=request.class_id,
        dry_run=request.dry_run,
        validation_passed=parsed is not None,
        llm_calls=llm_calls,
        duration_ms=duration_ms,
    )

    return LessonPlanResult(
        class_name=cls.name,
        subject_name=subject_name,
        grade_name=grade_name,
        student_count=class_context["student_count"],
        modality_distribution=class_context["modality_distribution"],
        top_interests=class_context["top_interests"],
        validation_passed=parsed is not None,
        generated_plan=parsed,
        raw_llm_output=response_text,
        error=error if parsed is None else None,
        llm_calls=llm_calls,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# 4. Practice Quiz
# ---------------------------------------------------------------------------


@router.post("/practice-quiz", response_model=PracticeQuizResult)
async def smoke_test_practice_quiz(
    request: PracticeQuizRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PracticeQuizResult:
    """Smoke test: generate a practice quiz for a subtopic.

    Also surfaces whether the approved explanation context was found
    (diagnoses the db.get(SubtopicContent, subtopic_id) PK mismatch risk).
    """
    t0 = time.monotonic()

    subtopic_result = await db.execute(
        select(Subtopic).where(Subtopic.id == UUID(request.subtopic_id), Subtopic.is_active.is_(True))
    )
    subtopic = subtopic_result.scalar_one_or_none()
    if subtopic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtopic {request.subtopic_id} not found")

    # Use provided student_id for interest personalisation; fall back to nil UUID
    # (generate_quiz will find no profile and use empty interests — valid smoke test path)
    student_id = UUID(request.student_id) if request.student_id else UUID(int=0)

    quiz = await generate_quiz(
        subtopic=subtopic,
        student_mastery=request.mastery_score,
        student_id=student_id,
        db=db,
    )

    # Check whether explanation context was found (diagnoses potential PK bug)
    from app.models.subtopic_content import SubtopicContent

    explanation_result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic.id,
            SubtopicContent.content_type == "explanation",
            SubtopicContent.review_status == "approved",
        )
    )
    explanation_context_found = explanation_result.scalar_one_or_none() is not None

    from app.ai.quiz_generator import _mastery_to_difficulty_label

    difficulty_label = _mastery_to_difficulty_label(request.mastery_score)
    duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "smoke_test_practice_quiz_completed",
        subtopic_id=request.subtopic_id,
        mastery_score=request.mastery_score,
        question_count=len(quiz.questions),
        explanation_context_found=explanation_context_found,
        duration_ms=duration_ms,
    )

    return PracticeQuizResult(
        subtopic_name=subtopic.name,
        difficulty_label=difficulty_label,
        interests_used=quiz.interests_used,
        explanation_context_found=explanation_context_found,
        question_count=len(quiz.questions),
        questions=[q.to_dict() for q in quiz.questions],
        duration_ms=duration_ms,
    )
