"""Teacher content review service — M3-0-T2b.

Business logic for the teacher explanation review workflow.
Scoped to the class context; caller must verify class ownership before calling.
"""

from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Class, SubtopicContent
from app.models.curriculum import CurriculumTopic, Subtopic

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

    # Base JOIN condition shared across all queries
    def _base_where(q: Select[_ST]) -> Select[_ST]:
        return q.where(
            SubtopicContent.content_type == "explanation",
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
    ).where(SubtopicContent.review_status == "pending")
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


async def list_all_explanation_content(
    db: AsyncSession,
    teacher_id: UUID,
    school_id: UUID,
    status_filter: str | None,
) -> list[dict[str, Any]]:
    """Query explanation content across all classes owned by a teacher.

    More efficient than calling list_explanation_content for each class - uses a single
    query with JOIN to filter by teacher's classes.

    Args:
        db: Async SQLAlchemy session.
        teacher_id: The teacher's ID.
        school_id: The school to scope to.
        status_filter: Optional status string to filter by.

    Returns:
        List of dicts with explanation data and class info.
    """
    # First get the teacher's class subject+grade combinations
    class_subj_grade = select(Class.id, Class.name, Class.subject_id, Class.grade_id).where(
        Class.teacher_id == teacher_id,
        Class.school_id == school_id,
        Class.is_active.is_(True),
    )
    class_result = await db.execute(class_subj_grade)
    classes = list(class_result.all())

    if not classes:
        return []

    # Build sets of subject_ids and grade_ids for the teacher's classes
    subject_ids = {c.subject_id for c in classes}
    grade_ids = {c.grade_id for c in classes}

    # Build a lookup from (subject_id, grade_id) -> class name
    class_lookup: dict[tuple[UUID, UUID], str] = {}
    class_id_lookup: dict[tuple[UUID, UUID], UUID] = {}
    for c in classes:
        key = (c.subject_id, c.grade_id)
        class_lookup[key] = c.name
        class_id_lookup[key] = c.id

    # Query subtopic content for these subject+grade combinations
    base_q = (
        select(SubtopicContent, CurriculumTopic.subject_id, CurriculumTopic.grade_id)
        .join(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .where(
            SubtopicContent.content_type == "explanation",
            CurriculumTopic.subject_id.in_(subject_ids),
            CurriculumTopic.grade_id.in_(grade_ids),
        )
    )

    if status_filter and status_filter != "all":
        base_q = base_q.where(SubtopicContent.review_status == status_filter)

    data_q = base_q.options(joinedload(SubtopicContent.subtopic).joinedload(Subtopic.curriculum_topic)).order_by(
        SubtopicContent.id.desc()
    )

    result = await db.execute(data_q)
    rows = result.unique().all()

    items: list[dict[str, Any]] = []
    for sc, subj_id, grade_id in rows:
        key = (subj_id, grade_id)
        class_name = class_lookup.get(key, "Unknown")
        class_id = class_id_lookup.get(key, None)

        items.append(
            {
                "subtopic_content_id": sc.id,
                "subtopic_id": sc.subtopic_id,
                "subtopic_name": sc.subtopic.name if sc.subtopic else str(sc.subtopic_id),
                "explanation_text": sc.explanation_text,
                "teacher_explanation": sc.teacher_explanation,
                "review_status": sc.review_status,
                "has_teacher_override": sc.teacher_explanation is not None,
                "class_id": str(class_id) if class_id else "",
                "class_name": class_name,
                "created_at": sc.created_at.isoformat() if sc.created_at else "",
                "thumbs_up_count": sc.thumbs_up_count,
                "thumbs_down_count": sc.thumbs_down_count,
            }
        )

    return items
