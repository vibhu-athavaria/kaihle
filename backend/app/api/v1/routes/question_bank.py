"""
Question Bank API — KaihleAdmin question browser and editor.
All routes require KAIHLE_ADMIN role.
"""

import hashlib
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from app.models.user import UserRole
from app.schemas.question_bank import (
    QuestionBankCreateRequest,
    QuestionBankListResponse,
    QuestionBankResponse,
    QuestionBankUpdateRequest,
)
from app.services.question_selection import resolve_objective_for_subtopic

router = APIRouter(prefix="/question-bank", tags=["question-bank"])


def _base_query():
    """SELECT with all joins for curriculum context.

    Curriculum context is reached through the objective bridge, never through
    QuestionBank.subtopic_id. That column is NULL for every question whose placement
    was replaced by a remap — all 1401 MATH/SCI grade 6-8 questions after cambridge_v2 —
    so the old inner join silently dropped them and the browser showed an empty bank
    while the diagnostic selector was finding them without trouble.

    A subtopic is chosen per question rather than joined across all of them: an
    objective taught in several grades would otherwise repeat the question once per
    placement, inflating totals and breaking the single-row get_question. Only 78 of
    5702 questions have more than one placement, and the ordering here matches
    resolve_objective_for_subtopic so the choice is stable between calls.
    """
    representative_subtopic = (
        select(SubtopicObjective.subtopic_id)
        .where(SubtopicObjective.learning_objective_id == QuestionBank.learning_objective_id)
        .order_by(SubtopicObjective.subtopic_id)
        .limit(1)
        .scalar_subquery()
    )
    return (
        select(
            QuestionBank,
            Curriculum.id.label("curriculum_id"),
            Curriculum.name.label("curriculum_name"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Grade.id.label("grade_id"),
            Grade.name.label("grade_name"),
            Topic.id.label("topic_id"),
            Topic.name.label("topic_name"),
            Subtopic.name.label("subtopic_name"),
            CurriculumTopic.id.label("curriculum_topic_id"),
        )
        # Explicit left side: the correlated subquery in the ON clause below otherwise
        # leaves SQLAlchemy unable to infer which FROM to join from.
        .select_from(QuestionBank)
        .join(Subtopic, Subtopic.id == representative_subtopic)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Curriculum, CurriculumTopic.curriculum_id == Curriculum.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .join(Topic, CurriculumTopic.topic_id == Topic.id)
    )


def _to_response(row: Any) -> QuestionBankResponse:
    (
        qb,
        curriculum_id,
        curriculum_name,
        subject_id,
        subject_name,
        grade_id,
        grade_name,
        topic_id,
        topic_name,
        subtopic_name,
        ct_id,
    ) = row
    return QuestionBankResponse(
        id=qb.id,
        question_text=qb.question_text,
        question_type=qb.question_type,
        options=qb.options,
        correct_answer=qb.correct_answer,
        explanation=qb.explanation,
        difficulty_level=qb.difficulty_level,
        is_active=qb.is_active,
        meta_tags=qb.meta_tags,
        source=qb.source,
        replaces_question_id=qb.replaces_question_id,
        subtopic_id=qb.subtopic_id,
        created_at=qb.created_at,
        updated_at=qb.updated_at,
        curriculum_id=curriculum_id,
        curriculum_name=curriculum_name,
        subject_id=subject_id,
        subject_name=subject_name,
        grade_id=grade_id,
        grade_name=grade_name,
        topic_id=topic_id,
        topic_name=topic_name,
        subtopic_name=subtopic_name,
        curriculum_topic_id=ct_id,
    )


@router.get("", response_model=QuestionBankListResponse)
async def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    curriculum_id: UUID | None = Query(None),
    grade_id: UUID | None = Query(None),
    subject_id: UUID | None = Query(None),
    topic_id: UUID | None = Query(None),
    subtopic_id: UUID | None = Query(None),
    curriculum_topic_id: UUID | None = Query(None),
    question_type: str | None = Query(None),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    source: str | None = Query(None),
    has_replaces: bool | None = Query(None, description="Filter questions that have a replaces_question_id"),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankListResponse:
    """Paginated, filterable question list. KAIHLE_ADMIN only."""
    query = _base_query()

    if curriculum_id:
        query = query.where(Curriculum.id == curriculum_id)
    if grade_id:
        query = query.where(Grade.id == grade_id)
    if subject_id:
        query = query.where(Subject.id == subject_id)
    if topic_id:
        query = query.where(Topic.id == topic_id)
    if subtopic_id:
        query = query.where(Subtopic.id == subtopic_id)
    if curriculum_topic_id:
        query = query.where(CurriculumTopic.id == curriculum_topic_id)
    if question_type:
        query = query.where(QuestionBank.question_type == question_type)
    if search:
        query = query.where(QuestionBank.question_text.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(QuestionBank.is_active == is_active)
    if source:
        query = query.where(QuestionBank.source == source)
    if has_replaces is True:
        query = query.where(QuestionBank.replaces_question_id.isnot(None))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.order_by(QuestionBank.created_at.desc())
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()

    return QuestionBankListResponse(
        questions=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{question_id}", response_model=QuestionBankResponse)
async def get_question(
    question_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankResponse:
    """Get a single question by ID with curriculum context."""
    row = (await db.execute(_base_query().where(QuestionBank.id == question_id))).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return _to_response(row)


@router.patch("/{question_id}", response_model=QuestionBankResponse)
async def update_question(
    question_id: UUID,
    payload: QuestionBankUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankResponse:
    """
    Partial update of a question. KAIHLE_ADMIN only.
    Pass subtopic_id to reassign curriculum context.
    Omitted fields are unchanged.
    """
    question = await db.get(QuestionBank, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if payload.subtopic_id is not None:
        if not await db.get(Subtopic, payload.subtopic_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="subtopic_id does not exist",
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)

    row = (await db.execute(_base_query().where(QuestionBank.id == question_id))).one_or_none()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to reload question after update")

    return _to_response(row)


@router.post("", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionBankCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankResponse:
    """Create a new question in the bank. KAIHLE_ADMIN only."""
    subtopic = await db.get(Subtopic, payload.subtopic_id)
    if not subtopic:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="subtopic_id does not exist",
        )

    # Selection resolves through the objective, so a question stored with only a
    # subtopic_id is unreachable: authored, saved, and never served to any student.
    # Refuse rather than write a row that silently does nothing.
    objective_id = await resolve_objective_for_subtopic(db, payload.subtopic_id)
    if objective_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Subtopic has no learning objective, so a question created here could "
                "never be selected. Add an objective to this subtopic first."
            ),
        )

    # SHA-256 of normalized text — matches compute_canonical_form in scripts/import_questions.py
    canonical_form = hashlib.sha256(payload.question_text.strip().lower().encode()).hexdigest()

    question = QuestionBank(
        subtopic_id=payload.subtopic_id,
        learning_objective_id=objective_id,
        question_text=payload.question_text,
        question_type=payload.question_type,
        options=payload.options,
        correct_answer=payload.correct_answer,
        explanation=payload.explanation,
        difficulty_level=payload.difficulty_level,
        is_active=payload.is_active,
        canonical_form=canonical_form,
        source="bank",
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    row = (await db.execute(_base_query().where(QuestionBank.id == question.id))).one_or_none()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to reload question after create")

    return _to_response(row)


@router.post("/{question_id}/approve", response_model=QuestionBankResponse)
async def approve_correction(
    question_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankResponse:
    """Atomically approve a correction: activate the correction and deactivate the original.

    In a single transaction:
      1. Sets is_active=true on the correction (the question_id param)
      2. Sets is_active=false on the original question (via replaces_question_id)
    """
    correction = await db.get(QuestionBank, question_id)
    if not correction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction not found")
    if correction.source != "llm-correction":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only llm-correction questions can be approved",
        )
    if not correction.replaces_question_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Correction has no replaces_question_id",
        )

    # Fetch original
    original = await db.get(QuestionBank, correction.replaces_question_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original question not found",
        )

    # Atomic transaction: activate correction, deactivate original
    correction.is_active = True
    original.is_active = False
    await db.commit()
    await db.refresh(correction)

    row = (await db.execute(_base_query().where(QuestionBank.id == correction.id))).one_or_none()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to reload question after approval")

    return _to_response(row)
