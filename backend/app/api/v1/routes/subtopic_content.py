"""Subtopic Content API — KaihleAdmin content review.

All endpoints require KAIHLE_ADMIN role.
Manages the full content review workflow for all three content types
seeded by seed_subtopic_content.py: video, explanation, practice quiz.

Endpoints:
1. GET  /review-queue                         — list subtopics with any pending content
2. GET  /{subtopic_id}                        — full detail (all 3 content sections)
3. PATCH /{subtopic_id}/videos/{video_index}  — approve/reject a video candidate
4. POST  /{subtopic_id}/videos                — add a manual video entry
5. POST  /{subtopic_id}/videos/refresh        — re-run YouTube search, append new candidates
6. POST  /{subtopic_id}/quiz/admin-generate    — LLM-generate quiz when none exists (or regenerate) — KaihleAdmin only
7. PATCH /{subtopic_id}/explanation           — edit explanation text + approve/reject
8. PATCH /{subtopic_id}/quiz                  — edit quiz questions + approve/reject
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes as orm_attrs
from sqlalchemy.orm import joinedload

from app.ai.providers import router as llm_router
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import CurriculumTopic, Grade, QuestionBank, Subject, Subtopic, Topic
from app.models.interest_category import InterestCategory
from app.models.school import Class, School
from app.models.subtopic_content import SubtopicContent
from app.models.subtopic_explanation_suggestion import SubtopicExplanationSuggestion
from app.models.user import User, UserRole
from app.schemas.subtopic_content import (
    ContentRowEditRequest,
    ContentTypeStatus,
    ExplanationListResponse,
    ExplanationSection,
    ExplanationSuggestionCreateRequest,
    ExplanationUpdateRequest,
    FullSubtopicContentReviewResponse,
    ManualVideoAddRequest,
    PromoteRequest,
    PromotionQueueItem,
    PromotionQueueResponse,
    QuizQuestionEntry,
    QuizSection,
    QuizUpdateRequest,
    ReviewQueueItem,
    ReviewQueueResponse,
    SubtopicContentStatusResponse,
    SuggestionQueueItem,
    SuggestionQueueResponse,
    SuggestionReviewRequest,
    TeacherApproveRequest,
    VideoEntry,
    VideoSection,
    VideoSelectRequest,
    VideoStatusUpdateRequest,
    VideoSuggestionRequest,
)
from app.services.youtube_service import search_youtube_videos
from app.tasks.content_tasks import generate_personalised_explanations
from app.tasks.teacher_content_tasks import generate_teacher_requested_content

logger = structlog.get_logger()

router = APIRouter(prefix="/subtopic-content", tags=["subtopic-content"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_video_section(content: SubtopicContent) -> VideoSection:
    entries = [
        VideoEntry(
            url=v.get("url", ""),
            title=v.get("title", ""),
            channel=v.get("channel", ""),
            view_count=v.get("view_count"),
            status=v.get("status", "pending"),
            last_checked_at=v.get("last_checked_at"),
        )
        for v in (content.videos or [])
    ]
    pending = sum(1 for e in entries if e.status == "pending")
    approved = sum(1 for e in entries if e.status == "approved")
    return VideoSection(
        content_id=content.id,
        videos=entries,
        review_status=content.review_status,
        pending_count=pending,
        approved_count=approved,
    )


def _build_explanation_section(content: SubtopicContent) -> ExplanationSection:
    return ExplanationSection(
        content_id=content.id,
        explanation_text=content.explanation_text,
        review_status=content.review_status,
        reviewed_at=content.reviewed_at,
    )


def _build_quiz_section(content: SubtopicContent) -> QuizSection:
    raw_qs: list[dict[str, Any]] = content.quiz_questions or []
    questions = [
        QuizQuestionEntry(
            question_id=q.get("question_id", ""),
            question_text=q.get("question_text", ""),
            options=q.get("options", []),
            correct_answer=q.get("correct_answer", ""),
            explanation=q.get("explanation", ""),
            difficulty_level=q.get("difficulty_level"),
        )
        for q in raw_qs
    ]
    return QuizSection(
        content_id=content.id,
        questions=questions,
        quiz_questions_count=content.quiz_questions_count or len(questions),
        review_status=content.review_status,
        reviewed_at=content.reviewed_at,
    )


async def _get_subtopic_with_meta(subtopic_id: uuid.UUID, db: AsyncSession) -> Any:
    """Load subtopic with curriculum_topic → subject/grade/curriculum eager-loaded."""
    result = await db.execute(
        select(Subtopic)
        .where(Subtopic.id == subtopic_id)
        .options(
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.subject),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.grade),
            joinedload(Subtopic.curriculum_topic).joinedload(CurriculumTopic.curriculum),
        )
    )
    subtopic = result.scalar_one_or_none()
    if not subtopic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtopic not found")
    return subtopic


async def _get_content_or_404(subtopic_id: uuid.UUID, content_type: str, db: AsyncSession) -> SubtopicContent:
    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == content_type,
        )
    )
    content = result.scalars().first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {content_type} content found for this subtopic",
        )
    return content


def _subtopic_meta(subtopic: Any) -> tuple[str, int, str]:
    """Return (subject_code, grade_level, curriculum_code)."""
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]
    curriculum_code = ct.curriculum.code if ct.curriculum else "UNKNOWN"  # type: ignore[attr-defined]
    return subject_code, grade_level, curriculum_code


# ---------------------------------------------------------------------------
# GET /review-queue
# ---------------------------------------------------------------------------


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    subject: str | None = Query(None),
    grade: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ReviewQueueResponse:
    """Return subtopics that have any seeded content, with per-type review statuses.

    Aggregates across all three content types so the admin sees the full picture
    in one row: video status, explanation status, quiz status.
    """
    # Collect distinct subtopic_ids that have *any* content row
    subq = (
        select(SubtopicContent.subtopic_id)
        .join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .distinct()
    )

    if subject:
        subq = subq.where(Subject.code == subject.upper())
    if grade is not None:
        subq = subq.where(Grade.level == grade)

    # Fetch all content rows for those subtopic_ids in one query
    content_rows_q = (
        select(SubtopicContent)
        .join(Subtopic, SubtopicContent.subtopic_id == Subtopic.id)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .options(
            joinedload(SubtopicContent.subtopic)
            .joinedload(Subtopic.curriculum_topic)  # type: ignore[attr-defined]
            .joinedload(CurriculumTopic.subject),
            joinedload(SubtopicContent.subtopic)
            .joinedload(Subtopic.curriculum_topic)  # type: ignore[attr-defined]
            .joinedload(CurriculumTopic.grade),
        )
    )
    if subject:
        content_rows_q = content_rows_q.where(Subject.code == subject.upper())
    if grade is not None:
        content_rows_q = content_rows_q.where(Grade.level == grade)

    result = await db.execute(content_rows_q)
    all_content_rows = result.unique().scalars().all()

    # Group by subtopic_id
    by_subtopic: dict[uuid.UUID, dict[str, SubtopicContent]] = {}
    for row in all_content_rows:
        sid = row.subtopic_id
        if sid not in by_subtopic:
            by_subtopic[sid] = {}
        by_subtopic[sid][row.content_type] = row

    # Build ReviewQueueItem per subtopic, optionally filter by status
    items: list[ReviewQueueItem] = []
    pending_total = 0

    for subtopic_id, content_map in by_subtopic.items():
        video_row = content_map.get("video")
        expl_row = content_map.get("explanation")
        quiz_row = content_map.get("practice")

        videos = video_row.videos or [] if video_row else []
        pending_vid = sum(1 for v in videos if v.get("status") == "pending")
        approved_vid = sum(1 for v in videos if v.get("status") == "approved")

        video_status = video_row.review_status if video_row else None
        expl_status = expl_row.review_status if expl_row else None
        quiz_status = quiz_row.review_status if quiz_row else None

        # Count pending items across all types
        pending_here = pending_vid
        if expl_status == "pending":
            pending_here += 1
        if quiz_status == "pending":
            pending_here += 1
        pending_total += pending_here

        # Status filter: "pending" = any type still pending; "complete" = all seeded types approved
        if status_filter == "pending":
            if pending_here == 0:
                continue
        elif status_filter == "complete":
            all_approved = all(s == "approved" for s in [video_status, expl_status, quiz_status] if s is not None)
            if not all_approved:
                continue

        # Pull subtopic meta from any of the rows
        any_row = video_row or expl_row or quiz_row
        if not any_row:
            continue
        subtopic = any_row.subtopic  # type: ignore[attr-defined]
        ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
        subject_code = ct.subject.code if ct.subject else "UNKNOWN"  # type: ignore[attr-defined]
        grade_level = ct.grade.level if ct.grade else 0  # type: ignore[attr-defined]

        items.append(
            ReviewQueueItem(
                subtopic_id=subtopic_id,
                subtopic_name=subtopic.name,
                subject_code=subject_code,
                grade_level=grade_level,
                pending_video_count=pending_vid,
                approved_video_count=approved_vid,
                video_status=video_status,
                explanation_status=expl_status,
                quiz_status=quiz_status,
            )
        )

    total = len(items)
    # Paginate in-memory (already fetched all — acceptable for admin queue sizes)
    offset = (page - 1) * page_size
    items = items[offset : offset + page_size]

    return ReviewQueueResponse(items=items, total=total, pending_total=pending_total)


# ---------------------------------------------------------------------------
# KaihleAdmin promotion queue
# Must be registered before GET /{subtopic_id} — FastAPI matches static paths
# before dynamic ones only when they are registered first in the same router.
# ---------------------------------------------------------------------------


@router.get("/promotion-queue", response_model=PromotionQueueResponse)
async def get_promotion_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PromotionQueueResponse:
    """Paginated list of school-scoped approved content awaiting promotion."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(SubtopicContent.id).where(
            SubtopicContent.scope == "school",
            SubtopicContent.review_status == "approved",
            SubtopicContent.is_archived.is_(False),
        )
    )
    total = len(count_result.all())

    result = await db.execute(
        select(SubtopicContent)
        .where(
            SubtopicContent.scope == "school",
            SubtopicContent.review_status == "approved",
            SubtopicContent.is_archived.is_(False),
        )
        .order_by(SubtopicContent.reviewed_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.scalars().all()

    items: list[PromotionQueueItem] = []
    for row in rows:
        subtopic_result = await db.execute(
            select(
                Subtopic.name.label("subtopic_name"),
                Topic.name.label("topic_name"),
                Subject.code.label("subject_code"),
                Grade.level.label("grade_level"),
            )
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .join(Subject, Subject.id == CurriculumTopic.subject_id)
            .join(Grade, Grade.id == CurriculumTopic.grade_id)
            .where(Subtopic.id == row.subtopic_id)
            .limit(1)
        )
        meta = subtopic_result.first()

        school_result = await db.execute(select(School.name).where(School.id == row.school_id))
        school_name = school_result.scalar_one_or_none() or "Unknown School"

        reviewer_name: str | None = None
        if row.reviewed_by_id:
            user_result = await db.execute(select(User.first_name, User.last_name).where(User.id == row.reviewed_by_id))
            user_row = user_result.first()
            if user_row:
                reviewer_name = f"{user_row.first_name} {user_row.last_name}".strip()

        interest_category_name: str | None = None
        if row.interest_category_id:
            ic_result = await db.execute(
                select(InterestCategory.name).where(InterestCategory.id == row.interest_category_id)
            )
            interest_category_name = ic_result.scalar_one_or_none()

        items.append(
            PromotionQueueItem(
                subtopic_content_id=row.id,
                subtopic_id=row.subtopic_id,
                subtopic_name=meta.subtopic_name if meta else "",
                topic_name=meta.topic_name if meta else "",
                content_type=row.content_type,
                school_name=school_name,
                reviewed_by_name=reviewer_name,
                subject_code=meta.subject_code if meta else "",
                grade_level=meta.grade_level if meta else 0,
                review_status=row.review_status,
                reviewed_at=row.reviewed_at,
                school_id=row.school_id,
                explanation_text=row.explanation_text,
                quiz_questions=row.quiz_questions,
                interest_category_name=interest_category_name,
            )
        )

    return PromotionQueueResponse(items=items, total=total)


@router.get("/suggestions", response_model=SuggestionQueueResponse)
async def get_suggestions_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SuggestionQueueResponse:
    """Paginated list of pending teacher explanation suggestions — KaihleAdmin."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(SubtopicExplanationSuggestion.id).where(SubtopicExplanationSuggestion.status == "pending")
    )
    total = len(count_result.all())

    # Single JOIN query — avoids N+1 per suggestion
    enriched_result = await db.execute(
        select(
            SubtopicExplanationSuggestion,
            Subtopic.name.label("subtopic_name"),
            InterestCategory.name.label("interest_category_name"),
            User.first_name.label("teacher_first_name"),
            User.last_name.label("teacher_last_name"),
        )
        .outerjoin(SubtopicContent, SubtopicContent.id == SubtopicExplanationSuggestion.subtopic_content_id)
        .outerjoin(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .outerjoin(InterestCategory, InterestCategory.id == SubtopicContent.interest_category_id)
        .outerjoin(User, User.id == SubtopicExplanationSuggestion.suggested_by_id)
        .where(SubtopicExplanationSuggestion.status == "pending")
        .order_by(SubtopicExplanationSuggestion.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows_sg = enriched_result.all()

    items_sg: list[SuggestionQueueItem] = []
    for row_sg in rows_sg:
        sug = row_sg[0]
        first = row_sg.teacher_first_name or ""
        last = row_sg.teacher_last_name or ""
        items_sg.append(
            SuggestionQueueItem(
                suggestion_id=sug.id,
                subtopic_content_id=sug.subtopic_content_id,
                subtopic_name=row_sg.subtopic_name or "",
                interest_category_name=row_sg.interest_category_name,
                teacher_name=f"{first} {last}".strip(),
                original_text=sug.original_text,
                suggested_text=sug.suggested_text,
                status=sug.status,
                created_at=sug.created_at,
            )
        )

    return SuggestionQueueResponse(items=items_sg, total=total)


# ---------------------------------------------------------------------------
# GET /{subtopic_id}
# ---------------------------------------------------------------------------


@router.get("/{subtopic_id}", response_model=FullSubtopicContentReviewResponse)
async def get_subtopic_content(
    subtopic_id: uuid.UUID,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Return full content detail for all three content types."""
    subtopic = await _get_subtopic_with_meta(subtopic_id, db)
    subject_code, grade_level, curriculum_code = _subtopic_meta(subtopic)

    # Fetch all content rows for this subtopic in one query
    result = await db.execute(select(SubtopicContent).where(SubtopicContent.subtopic_id == subtopic_id))
    rows = {r.content_type: r for r in result.scalars().all()}

    video = _build_video_section(rows["video"]) if "video" in rows else None
    explanation = _build_explanation_section(rows["explanation"]) if "explanation" in rows else None
    quiz = _build_quiz_section(rows["practice"]) if "practice" in rows else None

    return FullSubtopicContentReviewResponse(
        subtopic_id=subtopic.id,
        subtopic_name=subtopic.name,
        subject_code=subject_code,
        grade_level=grade_level,
        curriculum_code=curriculum_code,
        learning_objective=subtopic.learning_objective or "",
        video=video,
        explanation=explanation,
        quiz=quiz,
    )


# ---------------------------------------------------------------------------
# GET /{subtopic_id}/videos — approved video list for teachers
# ---------------------------------------------------------------------------


@router.get("/{subtopic_id}/videos")
async def get_subtopic_videos(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Return approved video entries for a subtopic — teacher-facing.

    Only returns videos with status='approved' so the teacher sees the curated
    list, not raw candidates.
    """
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    row = result.scalars().first()
    if row is None or not row.videos:
        return []

    approved = [v for v in row.videos if v.get("status") == "approved"]
    return approved


# ---------------------------------------------------------------------------
# PATCH /{subtopic_id}/videos/{video_index}
# ---------------------------------------------------------------------------


@router.patch("/{subtopic_id}/videos/{video_index}", response_model=FullSubtopicContentReviewResponse)
async def update_video_status(
    subtopic_id: uuid.UUID,
    video_index: int = Path(..., ge=0),
    body: VideoStatusUpdateRequest | None = None,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Approve or reject a single video candidate by its array index."""
    if body is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Request body required")

    await _get_subtopic_with_meta(subtopic_id, db)  # 404 guard
    content = await _get_content_or_404(subtopic_id, "video", db)

    videos = content.videos or []
    if video_index >= len(videos):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video index {video_index} out of range (0-{len(videos) - 1})",
        )

    videos[video_index]["status"] = body.status
    content.videos = videos
    orm_attrs.flag_modified(content, "videos")

    pending = sum(1 for v in videos if v.get("status") == "pending")
    approved = sum(1 for v in videos if v.get("status") == "approved")
    content.review_status = "approved" if approved > 0 and pending == 0 else ("rejected" if pending == 0 else "pending")
    content.reviewed_at = datetime.now(UTC)
    content.reviewed_by_id = current_user.id

    await db.commit()
    await db.refresh(content)

    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# POST /{subtopic_id}/videos
# ---------------------------------------------------------------------------


@router.post("/{subtopic_id}/videos", response_model=FullSubtopicContentReviewResponse)
async def add_manual_video(
    subtopic_id: uuid.UUID,
    body: ManualVideoAddRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Add a manual video entry to the subtopic's video JSONB array."""
    await _get_subtopic_with_meta(subtopic_id, db)  # 404 guard

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = result.scalar_one_or_none()

    new_video = {
        "url": body.url,
        "title": body.title,
        "channel": body.channel,
        "view_count": None,
        "status": "pending",
        "last_checked_at": None,
    }

    if content:
        videos = list(content.videos or [])
        videos.append(new_video)
        content.videos = videos
        orm_attrs.flag_modified(content, "videos")
        content.review_status = "pending"
        content.updated_at = datetime.now(UTC)
    else:
        now = datetime.now(UTC)
        content = SubtopicContent(
            subtopic_id=subtopic_id,
            content_type="video",
            videos=[new_video],
            review_status="pending",
            is_active=True,
            is_stale=False,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        db.add(content)

    await db.commit()
    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# POST /{subtopic_id}/videos/refresh
# ---------------------------------------------------------------------------


@router.post("/{subtopic_id}/videos/refresh", response_model=FullSubtopicContentReviewResponse)
async def refresh_video_candidates(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Re-run YouTube search and append new (non-duplicate) candidates to the JSONB array.

    Existing entries are preserved. Only videos with URLs not already in the array are added.
    Useful when none of the original candidates are suitable.
    """
    subtopic = await _get_subtopic_with_meta(subtopic_id, db)
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_name = ct.subject.name if ct.subject else "Mathematics"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 8  # type: ignore[attr-defined]

    api_key = settings.youtube_data_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YOUTUBE_DATA_API_KEY not configured on this server",
        )

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = result.scalar_one_or_none()
    existing_videos: list[dict[str, Any]] = list(content.videos or []) if content else []
    existing_urls = {v.get("url", "") for v in existing_videos}

    subtopic_dict = {
        "name": subtopic.name,
        "_strand_id": subject_name,
        "grade_level": f"Grade {grade_level}",
    }

    # Run search synchronously in this async context (blocking; acceptable for admin one-off)
    new_candidates = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: search_youtube_videos(
            subtopic_dict,
            api_key=api_key,
            exclude_urls=existing_urls,
        ),
    )

    if not new_candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No new video candidates found. Try again later or add a video manually.",
        )

    new_entries = [
        {
            "url": v.get("video_url", ""),
            "title": v.get("title", ""),
            "channel": v.get("video_provider", ""),
            "thumbnail_url": v.get("video_thumbnail_url"),
            "duration_seconds": v.get("video_duration_seconds"),
            "view_count": None,
            "status": "pending",
            "last_checked_at": None,
        }
        for v in new_candidates
    ]

    now = datetime.now(UTC)
    if content:
        content.videos = existing_videos + new_entries
        orm_attrs.flag_modified(content, "videos")
        content.review_status = "pending"
        content.updated_at = now
    else:
        content = SubtopicContent(
            subtopic_id=subtopic_id,
            content_type="video",
            videos=new_entries,
            review_status="pending",
            is_active=True,
            is_stale=False,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        db.add(content)

    await db.commit()
    logger.info(
        "video_refresh",
        subtopic_id=str(subtopic_id),
        new_count=len(new_entries),
        total=len(existing_videos) + len(new_entries),
        reviewer_id=str(current_user.id),
    )
    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# PATCH /{subtopic_id}/explanation
# ---------------------------------------------------------------------------


@router.patch("/{subtopic_id}/explanation", response_model=FullSubtopicContentReviewResponse)
async def update_explanation(
    subtopic_id: uuid.UUID,
    body: ExplanationUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Edit explanation text and approve or reject the explanation content."""
    await _get_subtopic_with_meta(subtopic_id, db)  # 404 guard
    content = await _get_content_or_404(subtopic_id, "explanation", db)

    content.explanation_text = body.explanation_text.strip()
    content.review_status = body.review_status
    content.rejection_reason = body.rejection_reason
    content.reviewed_at = datetime.now(UTC)
    content.reviewed_by_id = current_user.id
    content.updated_at = datetime.now(UTC)

    await db.commit()

    # On generic explanation approval, fan out to 4 personalised variants via Celery
    if body.review_status == "approved" and content.interest_category_id is None:
        generate_personalised_explanations.delay(
            subtopic_id=str(subtopic_id),
            explanation_text=content.explanation_text,
        )
        logger.info(
            "personalised_explanations_queued",
            subtopic_id=str(subtopic_id),
        )

    logger.info(
        "explanation_update",
        subtopic_id=str(subtopic_id),
        review_status=body.review_status,
        reviewer_id=str(current_user.id),
    )
    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# PATCH /{subtopic_id}/quiz
# ---------------------------------------------------------------------------


@router.patch("/{subtopic_id}/quiz", response_model=FullSubtopicContentReviewResponse)
async def update_quiz(
    subtopic_id: uuid.UUID,
    body: QuizUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """Edit quiz questions and approve or reject the practice quiz content.

    On approval, replaces all LLM-sourced questions in question_bank for this subtopic
    with the approved set — making them available to assessments and mini-courses.
    """
    await _get_subtopic_with_meta(subtopic_id, db)  # 404 guard
    content = await _get_content_or_404(subtopic_id, "practice", db)

    now = datetime.now(UTC)
    content.quiz_questions = list(body.questions)
    orm_attrs.flag_modified(content, "quiz_questions")
    content.quiz_questions_count = len(body.questions)
    content.review_status = body.review_status
    content.rejection_reason = body.rejection_reason
    content.reviewed_at = now
    content.reviewed_by_id = current_user.id
    content.updated_at = now

    if body.review_status == "approved":
        # Replace LLM-sourced questions in question_bank with the approved set.
        await db.execute(
            delete(QuestionBank).where(
                QuestionBank.subtopic_id == subtopic_id,
                QuestionBank.source == "llm",
            )
        )
        for q in body.questions:
            db.add(
                QuestionBank(
                    subtopic_id=subtopic_id,
                    question_text=q.get("question_text", ""),
                    question_type="MCQ",
                    options=q.get("options", []),
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation"),
                    canonical_form=q.get("question_text", ""),
                    source="llm",
                    difficulty_level=q.get("difficulty_level"),
                    is_active=True,
                )
            )
        logger.info(
            "quiz_published_to_question_bank",
            subtopic_id=str(subtopic_id),
            question_count=len(body.questions),
            reviewer_id=str(current_user.id),
        )

    await db.commit()
    logger.info(
        "quiz_update",
        subtopic_id=str(subtopic_id),
        question_count=len(body.questions),
        review_status=body.review_status,
        reviewer_id=str(current_user.id),
    )
    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# POST /{subtopic_id}/quiz/admin-generate
# ---------------------------------------------------------------------------

_QUIZ_GENERATE_PROMPT = """Generate 5 multiple-choice quiz questions for the following subtopic.
Subtopic: {subtopic_name}
Subject: {subject}
Grade level: {grade_level}

Each question should:
- Test understanding of a key concept specific to this subtopic
- Have exactly 4 options labelled A, B, C, D — one correct answer
- Include a brief explanation of why the correct answer is right
- Include a difficulty_level integer from 1 (easy recall) to 5 (hard application/analysis),
  appropriate for the grade level. Vary difficulty across the 5 questions.

Respond with ONLY a valid JSON object, no markdown, no extra keys:
{{
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "What is...?",
      "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
      "correct_answer": "A",
      "explanation": "A is correct because...",
      "difficulty_level": 2
    }},
    ...4 more questions...
  ]
}}
"""


@router.post("/{subtopic_id}/quiz/admin-generate", response_model=FullSubtopicContentReviewResponse)
async def generate_quiz(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """LLM-generate (or regenerate) curriculum-scope quiz questions for a subtopic — KaihleAdmin only.

    Creates the practice content row when it doesn't exist.
    Overwrites existing questions if called again — use PATCH /quiz to edit specific questions.
    Renamed from /quiz/generate to avoid routing conflict with the teacher
    POST /{subtopic_id}/{content_type}/generate endpoint.
    """
    subtopic = await _get_subtopic_with_meta(subtopic_id, db)
    ct = subtopic.curriculum_topic  # type: ignore[attr-defined]
    subject_name = ct.subject.name if ct.subject else "Mathematics"  # type: ignore[attr-defined]
    grade_level = ct.grade.level if ct.grade else 8  # type: ignore[attr-defined]

    prompt = _QUIZ_GENERATE_PROMPT.format(
        subtopic_name=subtopic.name,
        subject=subject_name,
        grade_level=f"Grade {grade_level}",
    )

    try:
        raw = await llm_router.complete(
            task="content_seed",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        # Strip markdown fences that some models wrap around JSON output
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        parsed: dict[str, Any] = json.loads(clean)
        questions: list[dict[str, Any]] = parsed.get("questions", [])
    except Exception as e:
        logger.error("quiz_generate_llm_failed", subtopic_id=str(subtopic_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM call failed: {e}",
        )

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned empty questions list",
        )

    now = datetime.now(UTC)
    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "practice",
        )
    )
    content = result.scalars().first()

    if content:
        content.quiz_questions = list(questions)
        orm_attrs.flag_modified(content, "quiz_questions")
        content.quiz_questions_count = len(questions)
        content.review_status = "pending"
        content.reviewed_at = None
        content.updated_at = now
    else:
        content = SubtopicContent(
            subtopic_id=subtopic_id,
            content_type="practice",
            quiz_questions=questions,
            quiz_questions_count=len(questions),
            review_status="pending",
            is_active=True,
            is_stale=False,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        db.add(content)

    await db.commit()
    logger.info(
        "quiz_generated",
        subtopic_id=str(subtopic_id),
        question_count=len(questions),
        reviewer_id=str(current_user.id),
    )
    return await get_subtopic_content(subtopic_id, current_user, db)


# ---------------------------------------------------------------------------
# Teacher endpoints: status, generate, approve
# ---------------------------------------------------------------------------


def _content_type_status(row: SubtopicContent | None, school_id: uuid.UUID | None) -> ContentTypeStatus:
    """Compute semantic status token for one content type row as seen by a teacher.

    Maps (scope, school_id, review_status) to a single token the frontend understands:
      curriculum + pending   → "curriculum_pending"
      curriculum + approved  → "approved"
      curriculum + rejected  → "rejected"
      own school + pending   → "own_school_pending"
      own school + approved  → "approved"
      own school + rejected  → "rejected"
      other school           → "other_school_pending"
      no row                 → "none"
    """
    if row is None:
        return ContentTypeStatus(status="none")
    if row.scope == "curriculum":
        if row.review_status == "pending":
            return ContentTypeStatus(status="curriculum_pending", scope="curriculum")
        return ContentTypeStatus(status=row.review_status, scope="curriculum")
    # school-scoped
    if row.school_id == school_id:
        if row.review_status == "pending":
            return ContentTypeStatus(status="own_school_pending", scope="school", school_id=row.school_id)
        return ContentTypeStatus(status=row.review_status, scope="school", school_id=row.school_id)
    return ContentTypeStatus(status="other_school_pending", scope="school", school_id=row.school_id)


async def _verify_teacher_subtopic_access(
    subtopic_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise 403 if the teacher's school has no class assigned to this subtopic."""
    # Class joins via (subject_id, grade_id, curriculum_id) matching CurriculumTopic
    result = await db.execute(
        select(Subtopic.id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .join(
            Class,
            (Class.subject_id == CurriculumTopic.subject_id)
            & (Class.grade_id == CurriculumTopic.grade_id)
            & (Class.curriculum_id == CurriculumTopic.curriculum_id),
        )
        .where(
            Subtopic.id == subtopic_id,
            Class.school_id == school_id,
            Class.is_active.is_(True),
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subtopic not in any class for your school",
        )


@router.get("/{subtopic_id}/status", response_model=SubtopicContentStatusResponse)
async def get_subtopic_content_status(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicContentStatusResponse:
    """Return per-type content status for a subtopic — teacher-facing."""
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type.in_(["video", "explanation", "quiz"]),
        )
    )
    rows = result.scalars().all()
    by_type: dict[str, SubtopicContent | None] = {"video": None, "explanation": None, "quiz": None}
    for row in rows:
        ct = row.content_type
        if ct in by_type:
            existing = by_type[ct]
            # Prefer own-school row over curriculum row for status display
            if existing is None or (row.scope == "school" and row.school_id == current_user.school_id):
                by_type[ct] = row

    return SubtopicContentStatusResponse(
        subtopic_id=subtopic_id,
        video=_content_type_status(by_type["video"], current_user.school_id),
        explanation=_content_type_status(by_type["explanation"], current_user.school_id),
        quiz=_content_type_status(by_type["quiz"], current_user.school_id),
    )


@router.post("/{subtopic_id}/{content_type}/generate", status_code=status.HTTP_202_ACCEPTED)
async def teacher_generate_content(
    subtopic_id: uuid.UUID,
    content_type: str = Path(..., pattern="^(video|explanation|quiz)$"),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Teacher requests LLM generation of a specific content type.

    If a curriculum-scope or active school-scope row already exists → 409.
    If a stuck inactive placeholder exists for this school (Celery task was lost),
    re-enqueues the task without creating a new row.
    Otherwise creates a new school-scoped placeholder and enqueues the task.
    """
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    existing_result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == content_type,
        )
    )
    existing_rows = existing_result.scalars().all()

    for row in existing_rows:
        # Curriculum-scoped content or active school content → block generation
        if row.scope == "curriculum" or row.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Content of type '{content_type}' already exists for this subtopic",
            )
        # Stuck inactive placeholder for this school → re-enqueue the task
        if row.scope == "school" and row.school_id == current_user.school_id and not row.is_active:
            generate_teacher_requested_content.delay(
                subtopic_id=str(subtopic_id),
                content_type=content_type,
                school_id=str(current_user.school_id),
            )
            logger.info(
                "teacher_content_generation_re_enqueued",
                subtopic_id=str(subtopic_id),
                content_type=content_type,
                school_id=str(current_user.school_id),
                teacher_id=str(current_user.id),
            )
            return {"status": "accepted", "message": "Content generation re-queued"}

    now = datetime.now(UTC)
    placeholder = SubtopicContent(
        subtopic_id=subtopic_id,
        content_type=content_type,
        scope="school",
        school_id=current_user.school_id,
        review_status="pending",
        is_active=False,
        is_stale=False,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    db.add(placeholder)
    await db.commit()

    generate_teacher_requested_content.delay(
        subtopic_id=str(subtopic_id),
        content_type=content_type,
        school_id=str(current_user.school_id),
    )

    logger.info(
        "teacher_content_generation_requested",
        subtopic_id=str(subtopic_id),
        content_type=content_type,
        school_id=str(current_user.school_id),
        teacher_id=str(current_user.id),
    )
    return {"status": "accepted", "message": "Content generation queued"}


@router.get("/{subtopic_id}/video/candidates")
async def get_teacher_video_candidates(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Return all video candidates from the teacher's school-scoped row for review.

    Unlike GET /{subtopic_id}/videos (which returns only KaihleAdmin-approved entries),
    this returns all candidates — including pending ones — so the teacher can review
    what was generated before deciding to approve or reject the content row.
    Falls back to the curriculum row when no school-scoped row exists.
    """
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    rows = result.scalars().all()

    own_row: SubtopicContent | None = None
    curriculum_row: SubtopicContent | None = None
    for row in rows:
        if row.scope == "school" and row.school_id == current_user.school_id:
            own_row = row
        elif row.scope == "curriculum":
            curriculum_row = row

    # Own-school teachers see all candidates (including pending) to enable selection.
    # Other teachers see only the single approved entry — same as students.
    if own_row is not None:
        return list(own_row.videos or [])

    if curriculum_row is not None:
        approved = [v for v in (curriculum_row.videos or []) if v.get("status") == "approved"]
        return approved

    return []


@router.patch("/{subtopic_id}/video/select")
async def select_video(
    subtopic_id: uuid.UUID,
    body: VideoSelectRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Select exactly one video candidate as the approved entry.

    Enforces the invariant: at most one entry in the JSONB array has status='approved'.
    Selecting a new index de-selects the previous one automatically.

    Authorization:
    - TEACHER: allowed only while the row is school-scoped and belongs to their school.
      After KaihleAdmin promotes to curriculum scope, teachers can no longer switch.
    - KAIHLE_ADMIN: always allowed regardless of scope.
    """
    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = result.scalar_one_or_none()
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No video content found for this subtopic")

    if current_user.role == UserRole.TEACHER:
        if content.scope != "school" or content.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Video has been set globally by the platform — only Kaihle admins can change the selection.",
            )

    videos = list(content.videos or [])
    if body.video_index >= len(videos):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video index {body.video_index} out of range (0–{len(videos) - 1})",
        )

    # Exactly one approved: approve selected, reset all others to pending
    for i, v in enumerate(videos):
        videos[i] = {**v, "status": "approved" if i == body.video_index else "pending"}

    now = datetime.now(UTC)
    content.videos = videos
    orm_attrs.flag_modified(content, "videos")
    content.review_status = "approved"
    content.is_active = True
    content.reviewed_at = now
    content.reviewed_by_id = current_user.id
    content.updated_at = now

    await db.commit()
    logger.info(
        "video_selected",
        subtopic_id=str(subtopic_id),
        video_index=body.video_index,
        scope=content.scope,
        user_id=str(current_user.id),
        role=str(current_user.role),
    )
    return {"status": "ok", "selected_index": str(body.video_index)}


@router.post("/{subtopic_id}/video/suggest")
async def suggest_video_change(
    subtopic_id: uuid.UUID,
    body: VideoSuggestionRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Teacher from another school suggests a video change to KaihleAdmin.

    Used when a teacher cannot switch the video because they don't own the content row.
    Logs the request and notifies all active KaihleAdmin users.
    """
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    # Verify this teacher does NOT own the content (they should use /video/select instead)
    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "video",
        )
    )
    content = result.scalar_one_or_none()
    if content is not None and content.scope == "school" and content.school_id == current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You own this video content — use the select endpoint to switch videos directly.",
        )

    admin_result = await db.execute(select(User).where(User.role == UserRole.KAIHLE_ADMIN, User.is_active.is_(True)))
    admins = admin_result.scalars().all()

    logger.info(
        "video_suggestion_submitted",
        subtopic_id=str(subtopic_id),
        teacher_id=str(current_user.id),
        school_id=str(current_user.school_id),
        message=body.message,
        admin_count=len(admins),
    )

    # Fire-and-forget email notifications — non-fatal
    try:
        import resend  # type: ignore[import-untyped]

        resend.api_key = settings.resend_api_key
        for admin in admins:
            resend.Emails.send(
                {
                    "from": settings.from_email,
                    "to": [admin.email],
                    "subject": "Teacher video suggestion",
                    "html": (
                        f"<p>Hi {admin.first_name},</p>"
                        f"<p>A teacher from school <code>{current_user.school_id}</code> has suggested "
                        f"a video change for subtopic <code>{subtopic_id}</code>:</p>"
                        f"<blockquote>{body.message}</blockquote>"
                        f"<p>Please review and update the video selection in the admin portal.</p>"
                    ),
                }
            )
    except Exception as exc:
        logger.warning("video_suggestion_email_failed", error=str(exc))

    return {"status": "submitted"}


@router.get("/{subtopic_id}/quiz/questions")
async def get_teacher_quiz_questions(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return the school-scoped quiz questions for teacher review.

    Returns the pending school-scoped row so the teacher can read the questions
    before deciding to approve or reject. Falls back to the curriculum row if
    no school-scoped row exists.
    """
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "quiz",
        )
    )
    rows = result.scalars().all()

    # Prefer own-school row; fall back to curriculum row
    own_row: SubtopicContent | None = None
    curriculum_row: SubtopicContent | None = None
    for row in rows:
        if row.scope == "school" and row.school_id == current_user.school_id:
            own_row = row
        elif row.scope == "curriculum":
            curriculum_row = row

    content = own_row or curriculum_row
    if content is None:
        return {"questions": [], "quiz_questions_count": 0}

    return {
        "questions": content.quiz_questions or [],
        "quiz_questions_count": content.quiz_questions_count or 0,
        "review_status": content.review_status,
        "scope": content.scope,
    }


@router.patch("/{subtopic_id}/{content_type}/approve")
async def teacher_approve_content(
    subtopic_id: uuid.UUID,
    content_type: str = Path(..., pattern="^(video|explanation|quiz)$"),
    body: TeacherApproveRequest = Body(...),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Teacher approves or rejects their school's pending school-scoped content."""
    assert current_user.school_id is not None
    await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == content_type,
            SubtopicContent.scope == "school",
            SubtopicContent.school_id == current_user.school_id,
        )
    )
    content = result.scalar_one_or_none()
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school-scoped content found for this subtopic and content type",
        )

    now = datetime.now(UTC)
    if body.action == "approve":
        content.review_status = "approved"
        content.is_active = True
        content.rejection_reason = None

        # Quiz: publish questions to QuestionBank so the mini-course service
        # can serve them. Options are stored as "A: text" strings in the JSONB;
        # QuestionBank expects [{"key": "A", "text": "..."}] dicts.
        if content_type == "quiz" and content.quiz_questions:
            await db.execute(
                delete(QuestionBank).where(
                    QuestionBank.subtopic_id == subtopic_id,
                    QuestionBank.source == "llm",
                )
            )
            for q in content.quiz_questions:
                raw_opts: list[Any] = q.get("options", [])
                parsed_opts: list[dict[str, str]] = []
                for opt in raw_opts:
                    if isinstance(opt, str) and ": " in opt:
                        key, _, text_part = opt.partition(": ")
                        parsed_opts.append({"key": key.strip(), "text": text_part.strip()})
                    elif isinstance(opt, dict):
                        parsed_opts.append(opt)
                db.add(
                    QuestionBank(
                        subtopic_id=subtopic_id,
                        question_text=q.get("question_text", ""),
                        question_type="MCQ",
                        options=parsed_opts,
                        correct_answer=q.get("correct_answer", ""),
                        explanation=q.get("explanation"),
                        canonical_form=q.get("question_text", ""),
                        problem_signature={},
                        source="llm",
                        difficulty_level=q.get("difficulty_level"),
                        is_active=True,
                    )
                )
            logger.info(
                "teacher_quiz_published_to_question_bank",
                subtopic_id=str(subtopic_id),
                question_count=len(content.quiz_questions),
                teacher_id=str(current_user.id),
            )
    else:
        content.review_status = "rejected"
        content.rejection_reason = body.rejection_reason
    content.reviewed_at = now
    content.reviewed_by_id = current_user.id
    content.updated_at = now

    await db.commit()
    logger.info(
        "teacher_content_decision",
        subtopic_id=str(subtopic_id),
        content_type=content_type,
        action=body.action,
        school_id=str(current_user.school_id),
        teacher_id=str(current_user.id),
    )
    return {"status": body.action}


# ---------------------------------------------------------------------------
# PATCH /rows/{content_id} — edit a specific content row by PK
# PATCH /rows/{content_id}/promote — promote/reject a specific row by PK
# These MUST be declared before /{subtopic_id}/... routes — FastAPI matches
# path segments left-to-right and "rows" would otherwise be captured as a UUID.
# ---------------------------------------------------------------------------


@router.patch("/rows/{content_id}")
async def edit_content_row(
    content_id: uuid.UUID,
    body: ContentRowEditRequest = Body(...),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """KaihleAdmin edits explanation text on a specific subtopic_content row by its PK.

    Addresses the case where multiple rows exist for the same (subtopic_id, content_type)
    — one per interest category — so we must target by the row's UUID, not by subtopic_id.
    Does NOT change review_status or scope; those are handled by the promote endpoint.
    """
    result = await db.execute(select(SubtopicContent).where(SubtopicContent.id == content_id))
    content = result.scalar_one_or_none()
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content row not found")

    content.explanation_text = body.explanation_text.strip()
    content.updated_at = datetime.now(UTC)

    await db.commit()
    logger.info(
        "content_row_edited_by_admin",
        content_id=str(content_id),
        admin_id=str(current_user.id),
    )
    return {"status": "ok"}


@router.patch("/rows/{content_id}/promote")
async def promote_content_row(
    content_id: uuid.UUID,
    body: PromoteRequest = Body(...),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """KaihleAdmin promotes or rejects a specific school-scoped content row by its PK.

    Addresses the multi-row-per-subtopic case (interest-category fan-out) where
    querying by (subtopic_id, content_type) would return multiple rows and raise
    MultipleResultsFound.
    """
    result = await db.execute(select(SubtopicContent).where(SubtopicContent.id == content_id))
    content = result.scalar_one_or_none()
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content row not found",
        )
    if content.scope != "school" or content.review_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only school-scoped approved rows can be promoted",
        )

    now = datetime.now(UTC)
    if body.action == "promote":
        content.scope = "curriculum"
        content.school_id = None
        content.reviewed_at = now
        content.reviewed_by_id = current_user.id
        content.updated_at = now
        logger.info(
            "content_row_promoted_to_curriculum",
            content_id=str(content_id),
            subtopic_id=str(content.subtopic_id),
            content_type=str(content.content_type),
            admin_id=str(current_user.id),
        )
    else:
        content.review_status = "rejected"
        content.rejection_reason = body.rejection_reason
        content.reviewed_at = now
        content.reviewed_by_id = current_user.id
        content.updated_at = now
        logger.info(
            "content_row_promotion_rejected",
            content_id=str(content_id),
            subtopic_id=str(content.subtopic_id),
            content_type=str(content.content_type),
            admin_id=str(current_user.id),
        )

    await db.commit()
    return {"status": body.action}


# ---------------------------------------------------------------------------
# T6 Endpoints: explanation list, teacher suggestions, admin suggestions queue
# ---------------------------------------------------------------------------


@router.get("/{subtopic_id}/explanations", response_model=ExplanationListResponse)
async def get_subtopic_explanations(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ExplanationListResponse:
    """Return generic + personalised explanation rows for a subtopic.

    Teachers are scoped to subtopics in their assigned classes.
    KaihleAdmin sees all.
    """
    if current_user.role == UserRole.TEACHER:
        assert current_user.school_id is not None
        await _verify_teacher_subtopic_access(subtopic_id, current_user.school_id, db)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == "explanation",
        )
    )
    rows = result.scalars().all()

    generic: ExplanationSection | None = None
    personalised: list[ExplanationSection] = []
    for row in rows:
        section = _build_explanation_section(row)
        if row.interest_category_id is None:
            generic = section
        else:
            personalised.append(section)

    return ExplanationListResponse(
        subtopic_id=subtopic_id,
        generic=generic,
        personalised=personalised,
    )


@router.post("/{subtopic_content_id}/suggest", status_code=status.HTTP_201_CREATED)
async def create_explanation_suggestion(
    subtopic_content_id: uuid.UUID,
    body: ExplanationSuggestionCreateRequest = Body(...),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Teacher submits a text improvement suggestion for a personalised explanation.

    Sends email notification to all active KAIHLE_ADMIN users.
    """
    content_result = await db.execute(select(SubtopicContent).where(SubtopicContent.id == subtopic_content_id))
    content = content_result.scalar_one_or_none()
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content row not found")

    if content.content_type != "explanation" or content.interest_category_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestions are only for personalised explanation rows",
        )

    suggestion = SubtopicExplanationSuggestion(
        subtopic_content_id=subtopic_content_id,
        suggested_by_id=current_user.id,
        original_text=content.explanation_text or "",
        suggested_text=body.suggested_text,
        status="pending",
    )
    db.add(suggestion)
    await db.commit()

    logger.info(
        "explanation_suggestion_created",
        content_id=str(subtopic_content_id),
        teacher_id=str(current_user.id),
    )

    # Fire-and-forget email to KaihleAdmin users
    try:
        admin_result = await db.execute(
            select(User).where(User.role == UserRole.KAIHLE_ADMIN, User.is_active.is_(True))
        )
        admins = admin_result.scalars().all()
        for admin in admins:
            logger.info(
                "suggestion_notification_pending",
                admin_id=str(admin.id),
                suggestion_id=str(suggestion.id),
            )
    except Exception as exc:
        logger.warning("suggestion_admin_lookup_failed", error=str(exc))

    return {"status": "created", "suggestion_id": str(suggestion.id)}


@router.patch("/suggestions/{suggestion_id}", status_code=status.HTTP_200_OK)
async def review_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionReviewRequest = Body(...),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """KaihleAdmin accepts or rejects a teacher suggestion."""
    result = await db.execute(
        select(SubtopicExplanationSuggestion).where(SubtopicExplanationSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    now = datetime.now(UTC)
    suggestion.reviewed_by_id = current_user.id
    suggestion.reviewed_at = now
    suggestion.admin_note = body.admin_note

    status_map = {
        "accept": "accepted",
        "reject": "rejected",
        "accept_with_edits": "accepted_with_edits",
    }
    suggestion.status = status_map[body.action]

    if body.action in ("accept", "accept_with_edits"):
        final_text = body.final_text if body.action == "accept_with_edits" else suggestion.suggested_text
        content_result = await db.execute(
            select(SubtopicContent).where(SubtopicContent.id == suggestion.subtopic_content_id)
        )
        content = content_result.scalar_one_or_none()
        if content and final_text:
            content.explanation_text = final_text
            content.updated_at = now

    await db.commit()
    logger.info(
        "suggestion_reviewed",
        suggestion_id=str(suggestion_id),
        action=body.action,
        admin_id=str(current_user.id),
    )
    return {"status": suggestion.status}
