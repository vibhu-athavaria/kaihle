"""Assessment API routes.

Two logical sections:
1. Class-scoped list — GET /classes/{class_id}/assessments
   (teacher sees assessments for their class dashboard)
2. Assessment-scoped operations — /assessments/{assessment_id}/...
   (operate on a specific assessment by ID)
"""

from datetime import datetime
from typing import cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.assessment import Assessment
from app.models.curriculum import Subtopic
from app.models.user import UserRole
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentCreateResponse,
    AssessmentQuestionWithAnswer,
    AssessmentResponse,
    AssessmentResultsSummary,
    AssessmentWithClassResponse,
    DesignTier1DiagnosticRequest,
    QuestionOption,
    TopicAvailability,
    TopicAvailabilityRequest,
)
from app.schemas.common import Page
from app.services.assessment_service import (
    AssessmentAccessDeniedError,
    AssessmentService,
    InsufficientQuestionsError,
    TeacherNotClassOwnerError,
)

logger = structlog.get_logger()

router = APIRouter(tags=["assessments"])


class PublishRequest(BaseModel):
    deadline: datetime | None = None


def _assessment_to_response(assessment: Assessment) -> AssessmentResponse:
    """Convert an Assessment ORM model to AssessmentResponse schema.

    Note: topic_ids is not stored directly on the Assessment model — it is stored
    in the request body at creation time but not persisted as a top-level column.
    We return an empty list here as the schema requires the field but the model
    does not carry it; a future task (M1-3-T*) may add a persisted topics column.
    """
    return AssessmentResponse(
        id=assessment.id,
        class_id=assessment.class_id,
        title=assessment.title,
        assessment_type=assessment.assessment_type,
        status=assessment.status,
        topic_ids=[],  # populated from assessment_topic_config in T2
        question_count=assessment.question_count,
        questions_per_topic=assessment.questions_per_topic,
        minimum_difficulty=assessment.minimum_difficulty,
        maximum_difficulty=assessment.maximum_difficulty,
        question_types=assessment.question_types,
        time_limit_minutes=assessment.time_limit_minutes,
        created_at=assessment.created_at,
        published_at=assessment.published_at,
        deadline=assessment.deadline,
    )


# ── Class-scoped list ─────────────────────────────────────────────────────────


@router.get("/classes/{class_id}/assessments", response_model=Page[AssessmentResponse])
async def list_class_assessments(
    class_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN, UserRole.STUDENT)
    ),
    db: AsyncSession = Depends(get_db),
) -> Page[AssessmentResponse]:
    service = AssessmentService(db)
    try:
        items, total = await service.list_class_assessments(
            class_id=class_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this class.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return Page(
        data=[_assessment_to_response(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/teachers/me/assessments", response_model=list[AssessmentWithClassResponse])
async def list_teacher_assessments(
    status_filter: str | None = Query(None, alias="status"),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[AssessmentWithClassResponse]:
    """List all assessments across all classes owned by the current teacher.

    More efficient than fetching assessments per-class. Returns assessments
    with class name included for display.
    """
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school associated",
        )

    service = AssessmentService(db)
    assessments = await service.list_teacher_assessments(
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        status_filter=status_filter,
    )

    return [
        AssessmentWithClassResponse(
            id=a["id"],
            class_id=a["class_id"],
            class_name=a["class_name"],
            grade_name=a["grade_name"],
            title=a["title"],
            assessment_type=a["assessment_type"],
            status=a["status"],
            topic_ids=[],  # populated from assessment_topic_config in T2
            question_count=a["question_count"],
            questions_per_topic=a["questions_per_topic"],
            minimum_difficulty=a["minimum_difficulty"],
            maximum_difficulty=a["maximum_difficulty"],
            question_types=a["question_types"],
            time_limit_minutes=a["time_limit_minutes"],
            created_at=a["created_at"],
            published_at=a["published_at"],
            deadline=a["deadline"],
        )
        for a in assessments
    ]


@router.post(
    "/classes/{class_id}/assessments",
    response_model=AssessmentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    class_id: UUID,
    body: AssessmentCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentCreateResponse:
    service = AssessmentService(db)
    try:
        assessment = await service.create_assessment(
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            class_id=class_id,
            body=body,
        )
        await db.commit()
        _, question_bank_rows = await service.get_assessment(
            assessment_id=assessment.id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this class.",
        )
    except InsufficientQuestionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Insufficient questions in the question bank for this assessment.",
                "available": exc.available,
                "requested": exc.requested,
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Batch-fetch subtopic names to avoid N+1
    subtopic_ids = [q.subtopic_id for q in question_bank_rows]
    subtopic_result = await db.execute(select(Subtopic.id, Subtopic.name).where(Subtopic.id.in_(subtopic_ids)))
    subtopic_name_map: dict[str, str] = {str(row[0]): row[1] for row in subtopic_result.all()}

    questions = [
        AssessmentQuestionWithAnswer(
            question_id=q.id,
            question_text=q.question_text,
            question_type=q.question_type,
            options=[QuestionOption(key=o["key"], text=o["text"]) for o in cast(list[dict[str, str]], q.options or [])],
            difficulty_level=int(q.difficulty_level) if q.difficulty_level is not None else 0,
            subtopic_name=subtopic_name_map.get(str(q.subtopic_id), "Unknown"),
            correct_answer_key=q.correct_answer,
            explanation=None,
        )
        for q in question_bank_rows
    ]

    base = _assessment_to_response(assessment)
    return AssessmentCreateResponse(**base.model_dump(), questions=questions)


@router.post(
    "/classes/{class_id}/assessments/topic-availability",
    response_model=list[TopicAvailability],
)
async def check_topic_availability(
    class_id: UUID,
    body: TopicAvailabilityRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[TopicAvailability]:
    """Return per-topic question availability for a diagnostic configuration.

    Used by the wizard UI to warn teachers before they submit if a topic
    doesn't have enough questions to fulfil the requested questions_per_topic.
    """
    if current_user.school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no school")
    service = AssessmentService(db)
    return await service.check_topic_availability(
        class_id=class_id,
        school_id=current_user.school_id,
        topic_ids=body.topic_ids,
        questions_per_topic=body.questions_per_topic,
        minimum_difficulty=body.minimum_difficulty,
        maximum_difficulty=body.maximum_difficulty,
        question_types=body.question_types,
    )


@router.post(
    "/classes/{class_id}/diagnostics/tier1",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def design_tier1_diagnostic(
    class_id: UUID,
    body: DesignTier1DiagnosticRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    """Create (or replace DRAFT of) a teacher-designed Tier 1 diagnostic.

    The teacher picks which curriculum topics to include.
    Questions are sampled from the bank across those topics.
    The resulting assessment is in DRAFT status — teacher must publish it separately.
    """
    if current_user.school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no school")
    service = AssessmentService(db)
    try:
        assessment = await service.design_tier1_diagnostic(
            class_id=class_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            body=body,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this class.")
    except InsufficientQuestionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Insufficient questions for selected topics.",
                "available": exc.available,
                "requested": exc.requested,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _assessment_to_response(assessment)


# ── Assessment-scoped operations ──────────────────────────────────────────────


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.TEACHER,
            UserRole.SCHOOL_ADMIN,
            UserRole.KAIHLE_ADMIN,
            UserRole.STUDENT,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    service = AssessmentService(db)
    try:
        assessment, _questions = await service.get_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except AssessmentAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _assessment_to_response(assessment)


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentResponse)
async def publish_assessment(
    assessment_id: UUID,
    body: PublishRequest | None = Body(None),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    service = AssessmentService(db)
    deadline = body.deadline if body else None
    try:
        assessment = await service.publish_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            deadline=deadline,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to publish this assessment.",
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        # Status conflict (already ACTIVE/CLOSED)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    return _assessment_to_response(assessment)


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = AssessmentService(db)
    try:
        await service.delete_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this assessment.",
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


@router.get("/assessments/{assessment_id}/results", response_model=AssessmentResultsSummary)
async def get_assessment_results(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResultsSummary:
    """Return all student attempt summaries for an assessment (class overview).

    Distinct from GET /attempts/{id}/results which returns per-question breakdown
    for a single student attempt.
    """
    service = AssessmentService(db)
    try:
        return await service.get_assessment_results(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except AssessmentAccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/assessments/{assessment_id}/close", response_model=AssessmentResponse)
async def close_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    service = AssessmentService(db)
    try:
        assessment = await service.close_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to close this assessment.",
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        # Status conflict (not ACTIVE)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    return _assessment_to_response(assessment)
