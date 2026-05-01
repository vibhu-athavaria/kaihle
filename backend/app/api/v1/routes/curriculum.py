"""Curriculum API routes — read and write operations.

These endpoints expose the curriculum hierarchy that was seeded by
seed_curriculum_graph.py (M1-2-T1).

Read endpoints: All authenticated users can read curriculum data
regardless of role — it is school-agnostic.

Write endpoints: Restricted to KAIHLE_ADMIN role only.

No school_id filtering on reads. No pagination on small lists (curricula,
grades, subjects). Pagination applied to topics and subtopics which can be larger.
"""

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.models.user import UserRole
from app.schemas.curriculum import (
    CurriculumAdminResponse,
    CurriculumCreate,
    CurriculumResponse,
    CurriculumSubjectResponse,
    CurriculumTopicCreate,
    CurriculumTopicSimpleResponse,
    CurriculumTopicUpdate,
    CurriculumUpdate,
    GradeAdminResponse,
    GradeCreate,
    GradeResponse,
    GradeUpdate,
    LinkSubjectRequest,
    SubjectAdminResponse,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
    SubtopicAdminResponse,
    SubtopicCreate,
    SubtopicSimpleResponse,
    SubtopicUpdate,
    TopicAdminResponse,
    TopicSimpleResponse,
)
from app.services.curriculum_service import (
    CurriculumService,
    DuplicateError,
    NotFoundError,
    ValidationError,
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
    base_query = select(Grade).options(selectinload(Grade.curricula)).order_by(Grade.level)

    if curriculum_id:
        # Filter to grades that have content in the requested curriculum
        base_query = (
            base_query.join(CurriculumTopic, CurriculumTopic.grade_id == Grade.id)
            .where(CurriculumTopic.curriculum_id == curriculum_id)
            .distinct()
        )

    rows = await db.scalars(base_query)
    return [
        GradeResponse(
            id=g.id,
            name=g.name,
            level=g.level,
            is_active=g.is_active,
            curriculum_ids=[c.id for c in g.curricula],
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
    response_model=list[TopicAdminResponse],
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
) -> list[TopicAdminResponse]:
    """List topics for a subject.

    Used by the teacher assessment creation wizard (Step 2: Select Topics).
    Filter by curriculum_id and grade_id to get the topics relevant to a
    specific class. Without filters, returns all topics for the subject
    across all curricula and grades (may contain duplicates by topic name
    across grade levels).

    Results are ordered by sequence_order within each grade.
    """
    subtopic_count_subq = (
        select(func.count(Subtopic.id))
        .where(Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .correlate(CurriculumTopic)
        .scalar_subquery()
    )

    query = (
        select(Topic, CurriculumTopic, subtopic_count_subq.label("subtopic_count"), Grade)
        .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
        .join(Grade, Grade.id == CurriculumTopic.grade_id)
        .where(CurriculumTopic.subject_id == subject_id)
    )
    if curriculum_id:
        query = query.where(CurriculumTopic.curriculum_id == curriculum_id)
    if grade_id:
        query = query.where(CurriculumTopic.grade_id == grade_id)

    query = query.order_by(Grade.level, CurriculumTopic.sequence_order, Topic.name)
    rows = (await db.execute(query)).all()

    return [
        TopicAdminResponse(
            curriculum_topic_id=ct.id,
            topic_id=topic.id,
            name=topic.name,
            canonical_code=topic.canonical_code,
            standard_code=ct.standard_code,
            sequence_order=ct.sequence_order,
            learning_objectives=ct.learning_objectives or [],
            recommended_weeks=ct.recommended_weeks,
            is_required=ct.is_required,
            is_active=ct.is_active,
            subtopic_count=subtopic_count or 0,
            grade_id=grade.id,
            grade_name=grade.name,
        )
        for topic, ct, subtopic_count, grade in rows
    ]


@router.get(
    "/topics/{topic_id}/subtopics",
    response_model=list[SubtopicAdminResponse],
)
async def list_topic_subtopics(
    topic_id: UUID,
    curriculum_id: UUID | None = Query(None),
    grade_id: UUID | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubtopicAdminResponse]:
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

    return [SubtopicAdminResponse.model_validate(s) for s in rows]


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


# =============================================================================
# Write Endpoints (KAIHLE_ADMIN only)
# =============================================================================


def _handle_service_error(e: Exception) -> NoReturn:
    """Convert service exceptions to HTTPExceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if isinstance(e, DuplicateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    raise e


# ------------------------------------------------------------------------------
# Curriculum Write Routes
# ------------------------------------------------------------------------------


@router.post(
    "/curricula",
    response_model=CurriculumAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_curriculum(
    data: CurriculumCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CurriculumAdminResponse:
    """Create a new curriculum board. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.create_curriculum(data)
    except (DuplicateError, ValidationError) as e:
        _handle_service_error(e)


@router.patch(
    "/curricula/{curriculum_id}",
    response_model=CurriculumAdminResponse,
)
async def update_curriculum(
    curriculum_id: UUID,
    data: CurriculumUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CurriculumAdminResponse:
    """Update an existing curriculum. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.update_curriculum(curriculum_id, data)
    except (NotFoundError, DuplicateError, ValidationError) as e:
        _handle_service_error(e)


# ------------------------------------------------------------------------------
# Grade Write Routes
# ------------------------------------------------------------------------------


@router.post(
    "/grades",
    response_model=GradeAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_grade(
    data: GradeCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GradeAdminResponse:
    """Create a new grade level. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.create_grade(data)
    except (DuplicateError, ValidationError) as e:
        _handle_service_error(e)


@router.patch(
    "/grades/{grade_id}",
    response_model=GradeAdminResponse,
)
async def update_grade(
    grade_id: UUID,
    data: GradeUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GradeAdminResponse:
    """Update an existing grade. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.update_grade(grade_id, data)
    except (NotFoundError, DuplicateError, ValidationError) as e:
        _handle_service_error(e)


# ------------------------------------------------------------------------------
# Subject Write Routes
# ------------------------------------------------------------------------------


@router.post(
    "/subjects",
    response_model=SubjectAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subject(
    data: SubjectCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubjectAdminResponse:
    """Create a new subject. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.create_subject(data)
    except (DuplicateError, ValidationError) as e:
        _handle_service_error(e)


@router.patch(
    "/subjects/{subject_id}",
    response_model=SubjectAdminResponse,
)
async def update_subject(
    subject_id: UUID,
    data: SubjectUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubjectAdminResponse:
    """Update an existing subject. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.update_subject(subject_id, data)
    except (NotFoundError, DuplicateError, ValidationError) as e:
        _handle_service_error(e)


# ------------------------------------------------------------------------------
# CurriculumSubject Link Routes
# ------------------------------------------------------------------------------


@router.post(
    "/curricula/{curriculum_id}/subjects",
    response_model=CurriculumSubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_subject_to_curriculum(
    curriculum_id: UUID,
    data: LinkSubjectRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> CurriculumSubjectResponse:
    """Link a subject to a curriculum. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.link_subject_to_curriculum(curriculum_id, data)
    except (NotFoundError, DuplicateError) as e:
        _handle_service_error(e)


@router.delete(
    "/curricula/{curriculum_id}/subjects/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_subject_from_curriculum(
    curriculum_id: UUID,
    subject_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink a subject from a curriculum. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        await service.unlink_subject_from_curriculum(curriculum_id, subject_id)
    except NotFoundError as e:
        _handle_service_error(e)


# ------------------------------------------------------------------------------
# CurriculumTopic Write Routes
# ------------------------------------------------------------------------------


@router.post(
    "/curricula/{curriculum_id}/grades/{grade_id}/subjects/{subject_id}/topics",
    response_model=TopicAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_topic_to_curriculum(
    curriculum_id: UUID,
    grade_id: UUID,
    subject_id: UUID,
    data: CurriculumTopicCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> TopicAdminResponse:
    """Add a topic to a curriculum/grade/subject placement. KAIHLE_ADMIN only.

    Accepts either topic_id (existing topic) or topic_data (create new).
    Returns 400 if neither or both are provided.
    """
    service = CurriculumService(db)
    try:
        return await service.add_topic_to_curriculum(curriculum_id, grade_id, subject_id, data)
    except (NotFoundError, DuplicateError, ValidationError) as e:
        _handle_service_error(e)


@router.patch(
    "/curriculum-topics/{ct_id}",
    response_model=TopicAdminResponse,
)
async def update_curriculum_topic(
    ct_id: UUID,
    data: CurriculumTopicUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> TopicAdminResponse:
    """Update a curriculum topic placement. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.update_curriculum_topic(ct_id, data)
    except NotFoundError as e:
        _handle_service_error(e)


@router.delete(
    "/curriculum-topics/{ct_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_curriculum_topic(
    ct_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a topic from a curriculum (deletes placement, not topic). KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        await service.delete_curriculum_topic(ct_id)
    except NotFoundError as e:
        _handle_service_error(e)


# ------------------------------------------------------------------------------
# Subtopic Write Routes
# ------------------------------------------------------------------------------


@router.post(
    "/curriculum-topics/{ct_id}/subtopics",
    response_model=SubtopicAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtopic(
    ct_id: UUID,
    data: SubtopicCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicAdminResponse:
    """Create a subtopic under a curriculum topic. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.create_subtopic(ct_id, data)
    except (NotFoundError, ValidationError) as e:
        _handle_service_error(e)


@router.patch(
    "/subtopics/{subtopic_id}",
    response_model=SubtopicAdminResponse,
)
async def update_subtopic(
    subtopic_id: UUID,
    data: SubtopicUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SubtopicAdminResponse:
    """Update a subtopic. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        return await service.update_subtopic(subtopic_id, data)
    except (NotFoundError, ValidationError) as e:
        _handle_service_error(e)


@router.delete(
    "/subtopics/{subtopic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subtopic(
    subtopic_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a subtopic. KAIHLE_ADMIN only."""
    service = CurriculumService(db)
    try:
        await service.delete_subtopic(subtopic_id)
    except NotFoundError as e:
        _handle_service_error(e)
