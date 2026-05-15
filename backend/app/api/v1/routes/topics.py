"""Topics API routes.

Routes:
  POST /topics/{topic_id}/generate-course  - Enqueue mini-course generation for a topic
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import CurriculumTopic, Topic
from app.models.user import UserRole

router = APIRouter(tags=["topics"])


@router.post(
    "/topics/{topic_id}/generate-course",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_topic_mini_course(
    topic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Enqueue mini-course content generation for all subtopics of a topic.

    Validates the topic exists in the curriculum (school-agnostic curriculum
    layer — no school_id filter on curriculum tables per CONSTITUTION).
    Returns the Celery task ID immediately; generation runs in background.

    Returns:
        {"task_id": "<celery_task_id>", "status": "queued"}
    """
    # Validate topic exists in the curriculum layer
    result = await db.execute(select(Topic.id).where(Topic.id == topic_id, Topic.is_active.is_(True)))
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic {topic_id} not found or inactive",
        )

    # Validate topic has at least one curriculum_topic entry
    ct_result = await db.execute(select(CurriculumTopic.id).where(CurriculumTopic.topic_id == topic_id).limit(1))
    if ct_result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic {topic_id} has no curriculum mapping",
        )

    # Enqueue the generation task — thin handler, no business logic here
    from app.tasks.mini_course_tasks import generate_topic_mini_course as celery_task

    school_id = str(current_user.school_id) if current_user.school_id else ""
    task = celery_task.delay(topic_id=str(topic_id), school_id=school_id)

    return {"task_id": task.id, "status": "queued"}
