"""Subtopic Content API — KaihleAdmin video review.

All endpoints require KAIHLE_ADMIN role.
Provides endpoints for reviewing YouTube video candidates per subtopic.

These endpoints handle the video review workflow:
1. GET /review-queue — list subtopics with pending video reviews
2. GET /{subtopic_id} — full detail for one subtopic
3. PATCH /{subtopic_id}/videos/{video_index} — approve/reject a video
4. POST /{subtopic_id}/videos — add a manual video entry
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.subtopic_content import SubtopicContent
from app.models.user import UserRole
from app.schemas.subtopic_content import (
    ManualVideoAddRequest,
    ReviewQueueItem,
    ReviewQueueResponse,
    SubtopicContentReviewResponse,
    VideoEntry,
    VideoStatusUpdateRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/subtopic-content", tags=["subtopic-content"])


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    subject: str | None = Query(None, description="Filter by subject code (e.g. MATH, SCI)"),
    grade: int | None = Query(None, description="Filter by grade level"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by review status: all | pending | complete",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ReviewQueueResponse:
    """Return paginated list of subtopics with pending video reviews.

    Only returns subtopics that have a subtopic_content row with video content type.
    """
    from app.models.curriculum import CurriculumTopic, Grade, Subject, Subtopic

    # Base query: join subtopic_content with subtopics
    # We want video content type only
    base_query = (
        select(SubtopicContent)
        .join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
        .where(SubtopicContent.content_type == "video")
    )

    # Count query for totals
    count_query = (
        select(func.count())
        .select_from(SubtopicContent)
        .join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
        .where(SubtopicContent.content_type == "video")
    )

    # Apply subject filter (need to join through curriculum_topic -> subject)
    if subject:
        base_query = (
            base_query.join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .join(Subject, CurriculumTopic.subject_id == Subject.id)
            .where(Subject.code == subject.upper())
        )
        count_query = (
            count_query.join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
            .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .join(Subject, CurriculumTopic.subject_id == Subject.id)
            .where(Subject.code == subject.upper())
        )

    # Apply grade filter
    if grade is not None:
        base_query = (
            base_query.join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .join(Grade, CurriculumTopic.grade_id == Grade.id)
            .where(Grade.level == grade)
        )
        count_query = (
            count_query.join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
            .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .join(Grade, CurriculumTopic.grade_id == Grade.id)
            .where(Grade.level == grade)
        )

    # Apply status filter
    if status_filter == "pending":
        base_query = base_query.where(SubtopicContent.review_status == "pending")
        count_query = count_query.where(SubtopicContent.review_status == "pending")
    elif status_filter == "complete":
        base_query = base_query.where(SubtopicContent.review_status == "approved")
        count_query = count_query.where(SubtopicContent.review_status == "approved")

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = base_query.offset(offset).limit(page_size)

    result = await db.execute(query)
    content_rows = result.unique().scalars().all()

    # Build response items
    items: list[ReviewQueueItem] = []
    pending_total = 0

    for content in content_rows:
        subtopic = content.subtopic  # type: ignore[attr-defined]
        ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
        subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
        grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]

        videos = content.videos or []
        pending_count = sum(1 for v in videos if v.get("status") == "pending")
        approved_count = sum(1 for v in videos if v.get("status") == "approved")
        pending_total += pending_count

        items.append(
            ReviewQueueItem(
                subtopic_id=subtopic.id,
                subtopic_name=subtopic.name,
                subject_code=subject_code,
                grade_level=grade_level,
                pending_video_count=pending_count,
                approved_video_count=approved_count,
            )
        )

    return ReviewQueueResponse(items=items, total=total, pending_total=pending_total)


@router.get("/{subtopic_id}", response_model=SubtopicContentReviewResponse)
async def get_subtopic_content(
    subtopic_id: uuid.UUID,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicContentReviewResponse:
    """Return full subtopic_content detail for video review."""
    from app.models.curriculum import CurriculumTopic, Subtopic

    # Get subtopic info with relationships
    subtopic_result = await db.execute(
        select(Subtopic)
        .where(Subtopic.id == subtopic_id)
        .options(
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.subject),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.grade),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.curriculum),
        )
    )
    subtopic = subtopic_result.scalar_one_or_none()
    if not subtopic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtopic not found",
        )

    # Get content row (video type only)
    content_result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = content_result.scalar_one_or_none()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No video content found for this subtopic",
        )

    # Build response
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]
    curriculum_code = ct.curriculum.code if ct.curriculum else "UNKNOWN"  # type: ignore[attr-defined]

    videos: list[VideoEntry] = []
    pending_count = 0
    approved_count = 0

    for v in content.videos or []:
        video_entry = VideoEntry(
            url=v.get("url", ""),
            title=v.get("title", ""),
            channel=v.get("channel", ""),
            view_count=v.get("view_count"),
            status=v.get("status", "pending"),
            last_checked_at=v.get("last_checked_at"),
        )
        videos.append(video_entry)
        if video_entry.status == "pending":
            pending_count += 1
        elif video_entry.status == "approved":
            approved_count += 1

    return SubtopicContentReviewResponse(
        subtopic_id=subtopic.id,
        subtopic_name=subtopic.name,
        subject_code=subject_code,
        grade_level=grade_level,
        curriculum_code=curriculum_code,
        learning_objective=subtopic.learning_objective or "",
        videos=videos,
        pending_count=pending_count,
        approved_count=approved_count,
        explanation_review_status="",  # Not needed for video review
    )


@router.patch("/{subtopic_id}/videos/{video_index}", response_model=SubtopicContentReviewResponse)
async def update_video_status(
    subtopic_id: uuid.UUID,
    video_index: int = Path(..., ge=0, description="Index of video in the JSONB array"),
    body: VideoStatusUpdateRequest | None = None,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicContentReviewResponse:
    """Update the status of one video entry in the JSONB array."""
    from app.models.curriculum import CurriculumTopic, Subtopic

    if body is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body is required",
        )

    # Get subtopic with relationships
    subtopic_result = await db.execute(
        select(Subtopic)
        .where(Subtopic.id == subtopic_id)
        .options(
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.subject),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.grade),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.curriculum),
        )
    )
    subtopic = subtopic_result.scalar_one_or_none()
    if not subtopic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtopic not found",
        )

    # Get content
    content_result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = content_result.scalar_one_or_none()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No video content found for this subtopic",
        )

    videos = content.videos or []
    if video_index < 0 or video_index >= len(videos):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video index {video_index} out of range (0-{len(videos) - 1})",
        )

    # Update the video status
    videos[video_index]["status"] = body.status
    content.videos = videos

    # Update overall review status based on videos
    pending_count = sum(1 for v in videos if v.get("status") == "pending")
    approved_count = sum(1 for v in videos if v.get("status") == "approved")

    if approved_count > 0 and pending_count == 0:
        content.review_status = "approved"
    elif pending_count > 0:
        content.review_status = "pending"
    else:
        content.review_status = "rejected"

    await db.commit()
    await db.refresh(content)

    # Build response
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]
    curriculum_code = ct.curriculum.code if ct.curriculum else "UNKNOWN"  # type: ignore[attr-defined]

    video_entries: list[VideoEntry] = []
    for v in videos:
        video_entries.append(
            VideoEntry(
                url=v.get("url", ""),
                title=v.get("title", ""),
                channel=v.get("channel", ""),
                view_count=v.get("view_count"),
                status=v.get("status", "pending"),
                last_checked_at=v.get("last_checked_at"),
            )
        )

    return SubtopicContentReviewResponse(
        subtopic_id=subtopic.id,
        subtopic_name=subtopic.name,
        subject_code=subject_code,
        grade_level=grade_level,
        curriculum_code=curriculum_code,
        learning_objective=subtopic.learning_objective or "",
        videos=video_entries,
        pending_count=pending_count,
        approved_count=approved_count,
        explanation_review_status="",
    )


@router.post("/{subtopic_id}/videos", response_model=SubtopicContentReviewResponse)
async def add_manual_video(
    subtopic_id: uuid.UUID,
    body: ManualVideoAddRequest,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicContentReviewResponse:
    """Add a new manual video entry to the subtopic's video array."""
    from app.models.curriculum import CurriculumTopic, Subtopic

    # Get subtopic with relationships
    subtopic_result = await db.execute(
        select(Subtopic)
        .where(Subtopic.id == subtopic_id)
        .options(
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.subject),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.grade),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.curriculum),
        )
    )
    subtopic = subtopic_result.scalar_one_or_none()
    if not subtopic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtopic not found",
        )

    # Get or create content row
    content_result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = content_result.scalar_one_or_none()

    if content:
        videos = content.videos or []
    else:
        # Create new content row for this subtopic
        content = SubtopicContent(
            subtopic_id=subtopic_id,
            content_type="video",
            videos=[],
            review_status="pending",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(content)
        videos = []

    # Add new video entry
    new_video = {
        "url": body.url,
        "title": body.title,
        "channel": body.channel,
        "view_count": None,
        "status": "pending",
        "last_checked_at": None,
    }
    videos.append(new_video)
    content.videos = videos

    await db.commit()
    await db.refresh(content)

    # Build response
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]
    curriculum_code = ct.curriculum.code if ct.curriculum else "UNKNOWN"  # type: ignore[attr-defined]

    pending_count = sum(1 for v in videos if v.get("status") == "pending")
    approved_count = sum(1 for v in videos if v.get("status") == "approved")

    video_entries: list[VideoEntry] = []
    for v in videos:
        video_entries.append(
            VideoEntry(
                url=v.get("url", ""),
                title=v.get("title", ""),
                channel=v.get("channel", ""),
                view_count=v.get("view_count"),
                status=v.get("status", "pending"),
                last_checked_at=v.get("last_checked_at"),
            )
        )

    return SubtopicContentReviewResponse(
        subtopic_id=subtopic.id,
        subtopic_name=subtopic.name,
        subject_code=subject_code,
        grade_level=grade_level,
        curriculum_code=curriculum_code,
        learning_objective=subtopic.learning_objective or "",
        videos=video_entries,
        pending_count=pending_count,
        approved_count=approved_count,
        explanation_review_status="",
    )
