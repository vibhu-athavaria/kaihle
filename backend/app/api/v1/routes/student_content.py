"""Student class content API routes.

Endpoints for accessing class content (topics, resources, lesson plans, quizzes).
Content is NOT hard-gated behind diagnostic completion — students can access content
regardless of diagnostic status. The gap map shows a "diagnostic pending" state for
classes where the diagnostic has not been completed, but content remains accessible.

Routes:
- GET /api/v1/classes/{class_id}/topics - List topics for a class
- GET /api/v1/classes/{class_id}/topics/{topic_id} - Get specific topic
- GET /api/v1/classes/{class_id}/topics/{topic_id}/resources - Get resources
- GET /api/v1/classes/{class_id}/topics/{topic_id}/lesson-plan - Get lesson plan
- GET /api/v1/classes/{class_id}/topics/{topic_id}/quizzes - Get quizzes
- GET /api/v1/classes/{class_id}/diagnostic - Get diagnostic for class
"""

from typing import Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.class_topic import ClassTopic
from app.models.curriculum import Subtopic
from app.models.mini_course import SubtopicCourseProgress
from app.models.subtopic_content import SubtopicContent

logger = structlog.get_logger()

router = APIRouter(prefix="/classes", tags=["student-content"])


class TopicResponse(BaseModel):
    """Stub schema for topic response."""

    id: UUID
    name: str
    description: str | None = None


class ResourceResponse(BaseModel):
    """Stub schema for resource response."""

    id: UUID
    title: str
    resource_type: str
    url: str


class LessonPlanStubResponse(BaseModel):
    """Stub schema for lesson plan response."""

    id: UUID
    class_id: UUID
    status: str
    generated_plan: dict[str, Any] | None = None


class QuizStubResponse(BaseModel):
    """Stub schema for quiz response."""

    id: UUID
    title: str
    question_count: int


class DiagnosticStubResponse(BaseModel):
    """Stub schema for diagnostic response."""

    class_id: UUID
    status: str  # PENDING | IN_PROGRESS | COMPLETED
    assessment_id: UUID | None = None


@router.get("/{class_id}/topics", response_model=list[TopicResponse])
async def list_class_topics(
    class_id: UUID = Path(..., description="Class ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TopicResponse]:
    """List all topics available for a class."""
    logger.debug(
        "class_topics_listed",
        user_id=str(current_user.id),
        class_id=str(class_id),
    )
    # TODO: Replace with actual topic listing from curriculum
    return []


@router.get("/{class_id}/topics/{topic_id}", response_model=TopicResponse)
async def get_class_topic(
    class_id: UUID = Path(..., description="Class ID"),
    topic_id: UUID = Path(..., description="Topic ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> TopicResponse:
    """Get a specific topic by ID."""
    logger.debug(
        "class_topic_retrieved",
        user_id=str(current_user.id),
        class_id=str(class_id),
        topic_id=str(topic_id),
    )
    # TODO: Replace with actual topic retrieval
    raise NotImplementedError("Topic retrieval not yet implemented")


@router.get(
    "/{class_id}/topics/{topic_id}/resources",
    response_model=list[ResourceResponse],
)
async def list_topic_resources(
    class_id: UUID = Path(..., description="Class ID"),
    topic_id: UUID = Path(..., description="Topic ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ResourceResponse]:
    """List all resources for a specific topic."""
    logger.debug(
        "topic_resources_listed",
        user_id=str(current_user.id),
        class_id=str(class_id),
        topic_id=str(topic_id),
    )
    # TODO: Replace with actual resource listing
    return []


@router.get(
    "/{class_id}/topics/{topic_id}/lesson-plan",
    response_model=LessonPlanStubResponse | None,
)
async def get_topic_lesson_plan(
    class_id: UUID = Path(..., description="Class ID"),
    topic_id: UUID = Path(..., description="Topic ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> LessonPlanStubResponse | None:
    """Get the lesson plan for a specific topic."""
    logger.debug(
        "topic_lesson_plan_retrieved",
        user_id=str(current_user.id),
        class_id=str(class_id),
        topic_id=str(topic_id),
    )
    # TODO: Replace with actual lesson plan retrieval
    return None


@router.get(
    "/{class_id}/topics/{topic_id}/quizzes",
    response_model=list[QuizStubResponse],
)
async def list_topic_quizzes(
    class_id: UUID = Path(..., description="Class ID"),
    topic_id: UUID = Path(..., description="Topic ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[QuizStubResponse]:
    """List all quizzes available for a specific topic."""
    logger.debug(
        "topic_quizzes_listed",
        user_id=str(current_user.id),
        class_id=str(class_id),
        topic_id=str(topic_id),
    )
    # TODO: Replace with actual quiz listing
    return []


class SubtopicProgressResponse(BaseModel):
    explanation_accessed: bool
    video_accessed: bool
    check_questions_score: float | None
    status: Literal["not_started", "in_progress", "completed"]


class SubtopicStudentResponse(BaseModel):
    id: UUID
    name: str
    order: int
    progress: SubtopicProgressResponse | None
    has_content: bool  # True when at least one approved SubtopicContent row exists


def _derive_subtopic_status(
    explanation_accessed: bool,
    video_accessed: bool,
    check_questions_score: float | None,
) -> Literal["not_started", "in_progress", "completed"]:
    if check_questions_score is not None:
        return "completed"
    if explanation_accessed or video_accessed:
        return "in_progress"
    return "not_started"


@router.get(
    "/{class_id}/topics/{class_topic_id}/subtopics",
    response_model=list[SubtopicStudentResponse],
)
async def list_class_topic_subtopics(
    class_id: UUID = Path(..., description="Class ID"),
    class_topic_id: UUID = Path(..., description="ClassTopic ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubtopicStudentResponse]:
    """List subtopics for a class topic with this student's progress, ordered by sequence_order."""
    result = await db.execute(
        select(ClassTopic).where(
            ClassTopic.id == class_topic_id,
            ClassTopic.class_id == class_id,
        )
    )
    class_topic = result.scalar_one_or_none()
    if class_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found in this class")

    # Correlated subquery: TRUE if at least one approved, non-archived content row exists
    content_exists_sq = (
        select(SubtopicContent.id)
        .where(
            SubtopicContent.subtopic_id == Subtopic.id,
            SubtopicContent.review_status == "approved",
            SubtopicContent.is_archived.is_(False),
        )
        .correlate(Subtopic)
        .exists()
        .label("has_content")
    )

    # Single query: subtopics + student progress (LEFT JOIN) + content availability (correlated EXISTS)
    joined = outerjoin(
        Subtopic,
        SubtopicCourseProgress,
        (SubtopicCourseProgress.subtopic_id == Subtopic.id) & (SubtopicCourseProgress.student_id == current_user.id),
    )
    subtopics_result = await db.execute(
        select(Subtopic, SubtopicCourseProgress, content_exists_sq)
        .select_from(joined)
        .where(
            Subtopic.curriculum_topic_id == class_topic.curriculum_topic_id,
            Subtopic.is_active.is_(True),
        )
        .order_by(Subtopic.sequence_order)
    )
    rows = subtopics_result.all()

    logger.info(
        "class_topic_subtopics_listed",
        user_id=str(current_user.id),
        class_id=str(class_id),
        class_topic_id=str(class_topic_id),
        count=len(rows),
    )

    responses = []
    for subtopic, progress, has_content in rows:
        progress_resp: SubtopicProgressResponse | None = None
        if progress is not None:
            progress_resp = SubtopicProgressResponse(
                explanation_accessed=progress.explanation_accessed,
                video_accessed=progress.video_accessed,
                check_questions_score=progress.check_questions_score,
                status=_derive_subtopic_status(
                    progress.explanation_accessed,
                    progress.video_accessed,
                    progress.check_questions_score,
                ),
            )
        responses.append(
            SubtopicStudentResponse(
                id=subtopic.id,
                name=subtopic.name,
                order=subtopic.sequence_order or 0,
                progress=progress_resp,
                has_content=bool(has_content),
            )
        )
    return responses
