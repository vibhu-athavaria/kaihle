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

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.core.deps import CurrentUser, get_current_user

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
