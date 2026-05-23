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
6. POST  /{subtopic_id}/quiz/generate         — LLM-generate quiz when none exists (or regenerate)
7. PATCH /{subtopic_id}/explanation           — edit explanation text + approve/reject
8. PATCH /{subtopic_id}/quiz                  — edit quiz questions + approve/reject
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes as orm_attrs
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import QuestionBank
from app.models.subtopic_content import SubtopicContent
from app.models.user import UserRole
from app.schemas.subtopic_content import (
    ExplanationSection,
    ExplanationUpdateRequest,
    FullSubtopicContentReviewResponse,
    ManualVideoAddRequest,
    QuizQuestionEntry,
    QuizSection,
    QuizUpdateRequest,
    ReviewQueueItem,
    ReviewQueueResponse,
    VideoEntry,
    VideoSection,
    VideoStatusUpdateRequest,
)

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
    from app.models.curriculum import CurriculumTopic, Subtopic

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
    from app.models.curriculum import CurriculumTopic, Grade, Subject, Subtopic

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
    from app.services.youtube_service import search_youtube_videos

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
    import asyncio

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
# POST /{subtopic_id}/quiz/generate
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


@router.post("/{subtopic_id}/quiz/generate", response_model=FullSubtopicContentReviewResponse)
async def generate_quiz(
    subtopic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> FullSubtopicContentReviewResponse:
    """LLM-generate (or regenerate) quiz questions for a subtopic.

    Creates the practice content row when it doesn't exist.
    Overwrites existing questions if called again — use PATCH /quiz to edit specific questions.
    """
    import json

    from app.ai.providers import router as llm_router

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
