"""Topics API routes.

Routes:
  POST  /topics/{topic_id}/generate-course                          - Enqueue mini-course generation
  GET   /topics/{topic_id}/course-status                            - Poll generation status + subtopic count
  PATCH /topics/{topic_id}/variants/{content_id}/review             - Approve or reject a variant
  GET   /classes/{class_id}/topics/{topic_id}/course-detail         - 4-variant grid + student assignments
  POST  /classes/{class_id}/topics/{topic_id}/student-overrides     - Set interest override for student
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import CurriculumTopic, Subtopic, Topic
from app.models.subtopic_content import SubtopicContent
from app.models.user import UserRole
from app.tasks.mini_course_tasks import generate_topic_mini_course as celery_mini_course_task

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

    Two-path: if content already exists, schedules a 30s delayed email to the teacher
    (simulating on-demand generation). Otherwise runs full LLM pipeline.

    Returns:
        {"task_id": "<celery_task_id>", "status": "queued"}
    """
    result = await db.execute(select(Topic.id).where(Topic.id == topic_id, Topic.is_active.is_(True)))
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic {topic_id} not found or inactive",
        )

    ct_result = await db.execute(select(CurriculumTopic.id).where(CurriculumTopic.topic_id == topic_id).limit(1))
    if ct_result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic {topic_id} has no curriculum mapping",
        )

    school_id = str(current_user.school_id) if current_user.school_id else ""
    teacher_id = str(current_user.id)

    task = celery_mini_course_task.delay(
        topic_id=str(topic_id),
        school_id=school_id,
        teacher_id=teacher_id,
    )

    return {"task_id": task.id, "status": "queued"}


@router.get(
    "/topics/{topic_id}/course-status",
    status_code=status.HTTP_200_OK,
)
async def get_topic_course_status(
    topic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return the mini-course generation status for a topic.

    Returns:
        {
          "status": "none" | "generating" | "ready" | "failed",
          "subtopic_count": int
        }
    """
    topic_result = await db.execute(
        select(Topic.mini_course_status).where(Topic.id == topic_id, Topic.is_active.is_(True))
    )
    topic_row = topic_result.first()
    if topic_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Topic {topic_id} not found")

    subtopic_count_result = await db.execute(
        select(Subtopic.id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .where(CurriculumTopic.topic_id == topic_id, Subtopic.is_active.is_(True))
    )
    subtopic_count = len(subtopic_count_result.all())

    return {
        "status": topic_row.mini_course_status,
        "subtopic_count": subtopic_count,
    }


@router.patch(
    "/topics/{topic_id}/variants/{content_id}/review",
    status_code=status.HTTP_200_OK,
)
async def review_topic_variant(
    topic_id: uuid.UUID,
    content_id: uuid.UUID,
    body: dict[str, str],
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Approve or reject a specific interest-category variant (SubtopicContent row).

    Body: {"review_status": "approved" | "rejected", "teacher_note": "<optional>"}
    """
    review_status = body.get("review_status")
    if review_status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="review_status must be 'approved' or 'rejected'",
        )

    result = await db.execute(select(SubtopicContent).where(SubtopicContent.id == content_id))
    sc = result.scalar_one_or_none()
    if sc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    sc.review_status = review_status
    sc.reviewed_at = datetime.now(UTC)
    sc.reviewed_by_id = current_user.id
    if body.get("teacher_note"):
        sc.rejection_teacher_note = body["teacher_note"]
    if body.get("edited_text"):
        sc.teacher_explanation = body["edited_text"]
        sc.teacher_explanation_author_id = current_user.id

    await db.commit()
    return {"status": "ok", "review_status": review_status}


@router.get(
    "/classes/{class_id}/topics/{topic_id}/course-detail",
    status_code=status.HTTP_200_OK,
)
async def get_topic_course_detail(
    class_id: uuid.UUID,
    topic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return 4-variant course detail for a topic: all subtopics with interest-category content.

    Also returns enrolled students with their auto-assigned and teacher-overridden
    interest categories. Used by the Course Detail page.
    """
    from app.services.mini_course_service import MiniCourseService

    school_id = current_user.school_id
    if school_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No school associated")

    service = MiniCourseService(db)
    return await service.get_course_detail_for_teacher(
        topic_id=topic_id,
        class_id=class_id,
        school_id=school_id,
    )


@router.post(
    "/classes/{class_id}/topics/{topic_id}/student-overrides",
    status_code=status.HTTP_200_OK,
)
async def set_student_interest_override(
    class_id: uuid.UUID,
    topic_id: uuid.UUID,
    body: dict[str, str],
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Set or update the interest-category override for a student on a topic.

    Body: {"student_id": "<uuid>", "interest_category_id": "<uuid>"}
    Pass interest_category_id = null to clear the override.
    """
    from app.services.mini_course_service import MiniCourseService

    school_id = current_user.school_id
    if school_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No school associated")

    student_id_str = body.get("student_id")
    interest_category_id_str = body.get("interest_category_id")

    if not student_id_str:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="student_id is required")

    service = MiniCourseService(db)
    await service.set_student_override(
        topic_id=topic_id,
        student_id=uuid.UUID(student_id_str),
        school_id=school_id,
        teacher_id=current_user.id,
        interest_category_id=uuid.UUID(interest_category_id_str) if interest_category_id_str else None,
    )
    return {"status": "ok"}
