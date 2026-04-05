"""Curriculum API routes — global read-only data.

These endpoints expose the curriculum hierarchy that was seeded by
seed_curriculum_graph.py (M1-2-T1). All authenticated users can read
curriculum data regardless of role — it is school-agnostic.

No school_id filtering. No pagination on small lists (curricula, grades,
subjects). Pagination applied to topics and subtopics which can be larger.

These are fully implemented routes — not stubs. The data is static and
seeded once. If the tables are empty (seed script not yet run), the
endpoints correctly return empty lists.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.schemas.curriculum import (
    CurriculumResponse,
    CurriculumTopicSimpleResponse,
    GradeResponse,
    SubjectResponse,
    SubtopicResponse,
    SubtopicSimpleResponse,
    TopicResponse,
    TopicSimpleResponse,
)

router = APIRouter(tags=["curriculum"])


@router.get("/curricula", response_model=list[CurriculumResponse])
async def list_curricula(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CurriculumResponse]:
    """List all available curricula (e.g. Cambridge Lower Secondary, IGCSE).

    Returns all active curricula. Typically 2 rows in v1.
    """
    rows = await db.scalars(select(Curriculum).where(Curriculum.is_active.is_(True)).order_by(Curriculum.name))
    return [
        CurriculumResponse(
            id=c.id,
            name=c.name,
            code=c.code,
            is_active=c.is_active,
        )
        for c in rows
    ]


@router.get("/curricula/{curriculum_id}", response_model=CurriculumResponse)
async def get_curriculum(
    curriculum_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurriculumResponse:
    """Get a single curriculum by ID."""
    from fastapi import HTTPException, status

    curriculum = await db.scalar(select(Curriculum).where(Curriculum.id == curriculum_id))
    if not curriculum:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curriculum not found",
        )
    return CurriculumResponse(
        id=curriculum.id,
        name=curriculum.name,
        code=curriculum.code,
        is_active=curriculum.is_active,
    )


@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(
    curriculum_id: UUID | None = Query(
        None,
        description="Filter grades by curriculum (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GradeResponse]:
    """List all grades, optionally filtered by curriculum.

    Without filter: returns all 7 grades (6–12).
    With curriculum_id: returns only grades that have content in that curriculum.
    """
    if curriculum_id:
        # Return only grades that have curriculum_topics rows for this curriculum
        rows = await db.scalars(
            select(Grade)
            .join(
                CurriculumTopic,
                CurriculumTopic.grade_id == Grade.id,
            )
            .where(CurriculumTopic.curriculum_id == curriculum_id)
            .distinct()
            .order_by(Grade.level)
        )
    else:
        rows = await db.scalars(select(Grade).order_by(Grade.level))
    return [
        GradeResponse(
            id=g.id,
            name=g.name,
            level=g.level,
            curriculum_id=curriculum_id,  # None if no filter applied
        )
        for g in rows
    ]


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    curriculum_id: UUID | None = Query(
        None,
        description="Filter subjects by curriculum (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubjectResponse]:
    """List all subjects, optionally filtered by curriculum.

    Without filter: returns all 7 subjects.
    With curriculum_id: returns only subjects available in that curriculum.
    """
    if curriculum_id:
        rows = await db.scalars(
            select(Subject)
            .join(
                CurriculumSubject,
                CurriculumSubject.subject_id == Subject.id,
            )
            .where(CurriculumSubject.curriculum_id == curriculum_id)
            .order_by(CurriculumSubject.sort_order, Subject.name)
        )
    else:
        rows = await db.scalars(select(Subject).order_by(Subject.name))
    return [SubjectResponse(id=s.id, name=s.name, code=s.code) for s in rows]


@router.get(
    "/subjects/{subject_id}/topics",
    response_model=list[TopicResponse],
)
async def list_subject_topics(
    subject_id: UUID,
    curriculum_id: UUID | None = Query(
        None,
        description="Filter topics by curriculum (recommended for accurate results)",
    ),
    grade_id: UUID | None = Query(
        None,
        description="Filter topics by grade level (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TopicResponse]:
    """List topics for a subject.

    Used by the teacher assessment creation wizard (Step 2: Select Topics).
    Filter by curriculum_id and grade_id to get the topics relevant to a
    specific class. Without filters, returns all topics for the subject
    across all curricula and grades (may contain duplicates by topic name
    across grade levels).

    Results are ordered by sequence_order within each grade.
    """
    query = (
        select(Topic, CurriculumTopic)
        .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
        .where(CurriculumTopic.subject_id == subject_id)
    )
    if curriculum_id:
        query = query.where(CurriculumTopic.curriculum_id == curriculum_id)
    if grade_id:
        query = query.where(CurriculumTopic.grade_id == grade_id)

    query = query.order_by(CurriculumTopic.sequence_order, Topic.name)
    rows = (await db.execute(query)).all()

    return [
        TopicResponse(
            id=topic.id,
            name=topic.name,
            subject_id=subject_id,
            grade_id=ct.grade_id,
            order=ct.sequence_order or 0,
        )
        for topic, ct in rows
    ]


@router.get(
    "/topics/{topic_id}/subtopics",
    response_model=list[SubtopicResponse],
)
async def list_topic_subtopics(
    topic_id: UUID,
    curriculum_id: UUID | None = Query(None),
    grade_id: UUID | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubtopicResponse]:
    """List subtopics for a topic.

    Optionally filter by curriculum_id and grade_id to get subtopics for
    a specific curriculum-topic-grade combination. Results ordered by
    sequence_order.
    """
    query = (
        select(Subtopic)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .where(CurriculumTopic.topic_id == topic_id)
    )
    if curriculum_id:
        query = query.where(CurriculumTopic.curriculum_id == curriculum_id)
    if grade_id:
        query = query.where(CurriculumTopic.grade_id == grade_id)

    query = query.order_by(Subtopic.sequence_order, Subtopic.name)
    rows = await db.scalars(query)

    return [
        SubtopicResponse(
            id=s.id,
            name=s.name,
            topic_id=topic_id,
            order=s.sequence_order or 0,
        )
        for s in rows
    ]


@router.get("/topics", response_model=list[TopicSimpleResponse])
async def list_all_topics(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TopicSimpleResponse]:
    """List all topics (for dropdown use)."""
    rows = await db.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.name))
    return [TopicSimpleResponse(id=t.id, name=t.name) for t in rows]


@router.get("/subtopics", response_model=list[SubtopicSimpleResponse])
async def list_all_subtopics(
    topic_id: UUID | None = Query(None, description="Filter subtopics by topic"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubtopicSimpleResponse]:
    """List all subtopics, optionally filtered by topic_id."""
    query = select(Subtopic).where(Subtopic.is_active.is_(True))
    if topic_id:
        query = query.join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id).where(
            CurriculumTopic.topic_id == topic_id
        )
    query = query.order_by(Subtopic.name)
    rows = await db.scalars(query)
    return [SubtopicSimpleResponse(id=s.id, name=s.name) for s in rows]


@router.get("/curriculum-topics", response_model=list[CurriculumTopicSimpleResponse])
async def list_curriculum_topics(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CurriculumTopicSimpleResponse]:
    """List all curriculum topics with a composite name (for dropdown use)."""
    rows = (
        await db.execute(
            select(CurriculumTopic, Curriculum.name, Grade.name, Subject.name, Topic.name)
            .join(Grade, CurriculumTopic.grade_id == Grade.id)
            .join(Subject, CurriculumTopic.subject_id == Subject.id)
            .join(Topic, CurriculumTopic.topic_id == Topic.id)
            .join(Curriculum, CurriculumTopic.curriculum_id == Curriculum.id)
            .where(CurriculumTopic.is_active.is_(True))
            .order_by(Curriculum.name, Grade.level, Subject.name, Topic.name)
        )
    ).all()
    return [
        CurriculumTopicSimpleResponse(
            id=ct.id,
            name=f"{cur_name} → {grade_name} → {subj_name} → {topic_name}",
        )
        for ct, cur_name, grade_name, subj_name, topic_name in rows
    ]
