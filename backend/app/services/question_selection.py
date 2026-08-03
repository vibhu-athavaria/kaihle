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

from sqlalchemy import ColumnElement, Select

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


def tier_filter(tier: StudentTier | None) -> ColumnElement[bool]:
    """Restrict to subtopics visible to a student on the given tier.

    None means no tiering applies (everything below IGCSE), so nothing is excluded.
    """
    if tier is None:
        return Subtopic.tier.in_(TIER_VISIBILITY["EXTENDED"])
    return Subtopic.tier.in_(TIER_VISIBILITY[tier])
