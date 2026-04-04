"""
Question Bank API — KaihleAdmin question browser and editor.
All routes require KAIHLE_ADMIN role.
"""

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
    Topic,
)
from app.models.user import UserRole
from app.schemas.question_bank import (
    QuestionBankListResponse,
    QuestionBankResponse,
    QuestionBankUpdateRequest,
)

router = APIRouter(prefix="/question-bank", tags=["question-bank"])


def _base_query():
    """SELECT with all joins for curriculum context."""
    return (
        select(
            QuestionBank,
            Curriculum.name.label("curriculum_name"),
            Subject.name.label("subject_name"),
            Grade.name.label("grade_name"),
            Topic.name.label("topic_name"),
            Subtopic.name.label("subtopic_name"),
            CurriculumTopic.id.label("curriculum_topic_id"),
        )
        .join(Subtopic, QuestionBank.subtopic_id == Subtopic.id)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Curriculum, CurriculumTopic.curriculum_id == Curriculum.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .join(Topic, CurriculumTopic.topic_id == Topic.id)
    )


def _to_response(row: Any) -> QuestionBankResponse:
    qb, curriculum_name, subject_name, grade_name, topic_name, subtopic_name, ct_id = row
    return QuestionBankResponse(
        id=qb.id,
        question_text=qb.question_text,
        question_type=qb.question_type,
        correct_answer=qb.correct_answer,
        explanation=qb.explanation,
        difficulty_level=qb.difficulty_level,
        is_active=qb.is_active,
        created_at=qb.created_at,
        updated_at=qb.updated_at,
        curriculum_name=curriculum_name,
        subject_name=subject_name,
        grade_name=grade_name,
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

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()

    return QuestionBankListResponse(
        questions=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


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
