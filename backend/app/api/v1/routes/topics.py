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

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import CurriculumTopic, Topic
from app.models.subtopic_content import SubtopicContent
from app.models.user import UserRole
from app.schemas.mini_course import CourseStatusResponse, VideoCoverage
from app.services.mini_course_generation_service import (
    compute_gap_count,
    compute_video_coverage,
    fetch_active_subtopic_ids,
)
from app.tasks.mini_course_tasks import generate_topic_mini_course as celery_mini_course_task

logger = structlog.get_logger()

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
    response_model=CourseStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_topic_course_status(
    topic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CourseStatusResponse:
    """Return the mini-course generation status for a topic.

    status="partial" means some explanations/quizzes generated but not all — gaps_count
    reports how many are still missing, recomputed live from current content state
    (MCR-T3), not from a stored value that could drift.
    """
    topic_result = await db.execute(
        select(Topic.mini_course_status).where(Topic.id == topic_id, Topic.is_active.is_(True))
    )
    topic_row = topic_result.first()
    if topic_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Topic {topic_id} not found")

    # Fetched once and shared — compute_gap_count and compute_video_coverage both used
    # to independently re-run this identical join query on every request.
    subtopic_ids = await fetch_active_subtopic_ids(db, topic_id)
    subtopic_count = len(subtopic_ids)

    # KAIHLE_ADMIN has no school_id — None is the explicit Rule-12 bypass, counting
    # across all schools rather than scoping to one.
    caller_school_id = current_user.school_id if current_user.role == UserRole.TEACHER else None

    # Only computed for "partial" — a "ready"/"none"/"generating"/"failed" topic has
    # nothing to report and this is two extra queries, not a free check.
    # Sequential, not asyncio.gather: both share this one AsyncSession, and SQLAlchemy's
    # async session does not support concurrent operations on the same instance — the
    # win here is eliminating the redundant subtopic_ids re-fetch above, not concurrency.
    gaps_count = 0
    if topic_row.mini_course_status == "partial":
        gaps_count = await compute_gap_count(db, subtopic_ids, caller_school_id)
    covered, total = await compute_video_coverage(db, subtopic_ids)

    return CourseStatusResponse(
        status=topic_row.mini_course_status,
        subtopic_count=subtopic_count,
        gaps_count=gaps_count,
        video_coverage=VideoCoverage(covered=covered, total=total),
    )


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

    # Explicit KAIHLE_ADMIN bypass (CONSTITUTION Rule 12) — written as its own branch,
    # not left implicit via "only fires when role==TEACHER", so a future edit to the
    # teacher-side condition can't silently start blocking admins too.
    if current_user.role == UserRole.KAIHLE_ADMIN:
        pass
    elif sc.scope == "school" and sc.school_id != current_user.school_id:
        # A teacher may review a curriculum-scope row (claiming it for their school, per
        # the comment below) or their OWN school's row — never another school's row.
        # Without this, a teacher could point this endpoint at any content_id and both
        # approve/reject it AND (via the scope reassignment below) reassign a row that
        # already belongs to another school onto their own (CONSTITUTION Rule 3 — a
        # write takeover, not just a leak).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This content belongs to another school")

    sc.review_status = review_status
    sc.reviewed_at = datetime.now(UTC)
    sc.reviewed_by_id = current_user.id

    # When a teacher approves, ensure the row is school-scoped with the correct
    # school_id. This corrects rows generated before the scope fix (which defaulted
    # to scope="curriculum") and is also correct semantically: teacher approval
    # claims content for their school.
    #
    # Guarded: uq_subtopic_content_school is unique on (subtopic_id, content_type,
    # school_id, interest_category_id) for scope='school' rows. If this school already
    # has a school-scope row occupying that exact slot — e.g. a school-specific variant
    # generated separately from this (still scope='curriculum') row — blindly
    # reassigning sc onto the same slot violates that constraint and previously crashed
    # this endpoint with an unhandled 500 on commit. The review itself (status, note,
    # edited text) is independent of the ownership takeover, so it still applies even
    # when the takeover has to be skipped.
    if (
        current_user.role == UserRole.TEACHER
        and current_user.school_id is not None
        and not (sc.scope == "school" and sc.school_id == current_user.school_id)
    ):
        conflict_result = await db.execute(
            select(SubtopicContent.id).where(
                SubtopicContent.id != sc.id,
                SubtopicContent.subtopic_id == sc.subtopic_id,
                SubtopicContent.content_type == sc.content_type,
                SubtopicContent.interest_category_id == sc.interest_category_id,
                SubtopicContent.scope == "school",
                SubtopicContent.school_id == current_user.school_id,
            )
        )
        if conflict_result.first() is not None:
            logger.warning(
                "subtopic_content_review_scope_takeover_skipped_duplicate_slot",
                content_id=str(sc.id),
                subtopic_id=str(sc.subtopic_id),
                content_type=sc.content_type,
                interest_category_id=str(sc.interest_category_id) if sc.interest_category_id else None,
                school_id=str(current_user.school_id),
            )
        else:
            sc.scope = "school"
            sc.school_id = current_user.school_id

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
