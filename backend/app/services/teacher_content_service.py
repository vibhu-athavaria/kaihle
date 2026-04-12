"""Teacher content review service — M3-0-T2b.

Business logic for the teacher explanation review workflow.
Scoped to the class context; caller must verify class ownership before calling.
"""

from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import SubtopicContent
from app.models.curriculum import CurriculumTopic, Subtopic
from app.models.subtopic_content import ContentType, ReviewStatus

_ST = TypeVar("_ST", bound="tuple[Any, ...]")


async def list_explanation_content(
    db: AsyncSession,
    subject_id: UUID,
    grade_id: UUID,
    status_filter: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int, int]:
    """Query explanation content for a class's subject/grade.

    Args:
        db: Async SQLAlchemy session.
        subject_id: UUID of the class subject.
        grade_id: UUID of the class grade.
        status_filter: Optional status string to filter by ("pending", "approved", "rejected").
        page: 1-indexed page number.
        page_size: Items per page.

    Returns:
        Tuple of (items, total, pending_count):
            - items: list of dicts with explanation data
            - total: total number of explanation rows (before filter)
            - pending_count: number of rows with status PENDING
    """
    from sqlalchemy import func

    # Base JOIN condition shared across all queries
    def _base_where(q: Select[_ST]) -> Select[_ST]:
        return q.where(
            SubtopicContent.content_type == ContentType.EXPLANATION,
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.grade_id == grade_id,
        )

    join_chain = (
        select(SubtopicContent)
        .join(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
    )

    # Count total (all statuses)
    count_q = _base_where(
        select(func.count(SubtopicContent.id))
        .join(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar_one() or 0

    # Count pending
    pending_q = _base_where(
        select(func.count(SubtopicContent.id))
        .join(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
    ).where(SubtopicContent.review_status == ReviewStatus.PENDING)
    pending_result = await db.execute(pending_q)
    pending_count = pending_result.scalar_one() or 0

    # Build data query with optional status filter and pagination
    data_q = _base_where(join_chain)
    if status_filter and status_filter != "all":
        data_q = data_q.where(SubtopicContent.review_status == status_filter)

    offset = (page - 1) * page_size
    data_q = (
        data_q.options(joinedload(SubtopicContent.subtopic).joinedload(Subtopic.curriculum_topic))
        .order_by(SubtopicContent.id.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(data_q)
    rows = result.unique().scalars().all()

    items: list[dict[str, Any]] = [
        {
            "subtopic_content_id": sc.id,
            "subtopic_id": sc.subtopic_id,
            "subtopic_name": sc.subtopic.name if sc.subtopic else str(sc.subtopic_id),
            "explanation_text": sc.explanation_text,
            "teacher_explanation": sc.teacher_explanation,
            "review_status": sc.review_status,
            "has_teacher_override": sc.teacher_explanation is not None,
        }
        for sc in rows
    ]
    return items, total, pending_count
