"""Canonical question-selection path.

Every question selection in the application resolves through learning objectives:

    curriculum_topics -> subtopics -> subtopic_objectives -> learning_objectives
                      -> question_bank.learning_objective_id

question_bank.subtopic_id is NOT used for selection. It is retained for legacy and
audit purposes only, and is NULL for any question whose curriculum placement has been
replaced by a remap. Selecting on it silently returns nothing for remapped scopes —
after the cambridge_v2 remap it returned 0 questions for MATH/SCI grades 6-8 while the
objective path returned 999.

This module exists so that path is written once. It applies uniformly to every
curriculum scope, including those never remapped, because create_learning_objectives
--mode legacy-backfill gives every subtopic an objective. Without that, callers would
need an old-path/new-path branch forever.
"""

import uuid
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, SubtopicObjective

# IGCSE Core/Extended. Extended is a superset of Core: Extended students see
# everything, Core students must never be shown EXTENDED-only material.
# Tier lives on subtopics alone — never on the bridge or the objective — so filtering
# happens by joining through the subtopic.
StudentTier = Literal["CORE", "EXTENDED"]

TIER_VISIBILITY: dict[str, tuple[str, ...]] = {
    "CORE": ("CORE", "BOTH"),
    "EXTENDED": ("CORE", "EXTENDED", "BOTH"),
}


def join_questions_via_objectives(stmt: Select[Any]) -> Select[Any]:
    """Join CurriculumTopic through to QuestionBank via the objective bridge.

    The statement must already select from CurriculumTopic. Because a subtopic can
    teach several objectives and an objective can be taught by several subtopics, this
    join can repeat a question; callers selecting question ids should apply DISTINCT.
    """
    return (
        stmt.join(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(SubtopicObjective, SubtopicObjective.subtopic_id == Subtopic.id)
        .join(QuestionBank, QuestionBank.learning_objective_id == SubtopicObjective.learning_objective_id)
    )


def active_scope_filters(
    curriculum_id: uuid.UUID,
    subject_id: uuid.UUID,
    grade_id: uuid.UUID,
) -> list[ColumnElement[bool]]:
    """Standard predicates for a live curriculum/subject/grade scope."""
    return [
        CurriculumTopic.curriculum_id == curriculum_id,
        CurriculumTopic.subject_id == subject_id,
        CurriculumTopic.grade_id == grade_id,
        CurriculumTopic.is_active.is_(True),
        Subtopic.is_active.is_(True),
        QuestionBank.is_active.is_(True),
    ]


def questions_for_subtopic(subtopic_id: uuid.UUID) -> Select[Any]:
    """Select active questions taught by a single subtopic, via its objectives.

    The subtopic-scoped counterpart to join_questions_via_objectives, for callers that
    already hold a subtopic id and do not need the curriculum scope.

    De-duplication happens in a subquery rather than via DISTINCT on the outer select:
    a subtopic teaching several objectives can reach one question more than once, but
    Postgres rejects SELECT DISTINCT combined with an ORDER BY expression that is not
    in the select list — which would break the common `.order_by(func.random())` case.
    """
    matching_ids = (
        select(QuestionBank.id)
        .join(SubtopicObjective, SubtopicObjective.learning_objective_id == QuestionBank.learning_objective_id)
        .where(
            SubtopicObjective.subtopic_id == subtopic_id,
            QuestionBank.is_active.is_(True),
        )
        .scalar_subquery()
    )
    return select(QuestionBank).where(QuestionBank.id.in_(matching_ids))


async def resolve_objective_for_subtopic(db: AsyncSession, subtopic_id: uuid.UUID) -> uuid.UUID | None:
    """Return the objective a newly authored question for this subtopic should bind to.

    Anything that CREATES a question must set learning_objective_id. Selection resolves
    through the objective, so a question stored with only a subtopic_id is unreachable:
    generated, persisted, and never served to anyone.

    Ordered so that repeated calls pick the same objective when a subtopic teaches
    several. Returns None if the subtopic has no objective, which is a data defect the
    caller should surface rather than silently write an unreachable row.
    """
    result = await db.execute(
        select(SubtopicObjective.learning_objective_id)
        .where(SubtopicObjective.subtopic_id == subtopic_id)
        .order_by(SubtopicObjective.learning_objective_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def tier_filter(tier: StudentTier | None) -> ColumnElement[bool]:
    """Restrict to subtopics visible to a student on the given tier.

    None means no tiering applies (everything below IGCSE), so nothing is excluded.
    """
    if tier is None:
        return Subtopic.tier.in_(TIER_VISIBILITY["EXTENDED"])
    return Subtopic.tier.in_(TIER_VISIBILITY[tier])
