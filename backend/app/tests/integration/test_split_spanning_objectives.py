"""Integration tests for the ADR-003 T3 grade split.

The behaviours worth proving against a real database:
  - a spanning objective becomes one objective per grade, the original keeping the lowest,
  - a question with surviving subtopic provenance follows it to the right grade,
  - a question WITHOUT provenance is queued for review rather than silently relabelled,
  - re-running changes nothing,
  - a grade whose questions are gone still gets its objective, and gets reported.

The third is the load-bearing one. Everything else here is bookkeeping; that test is the
reason the script exists at all. Keeping the original row at the lowest grade means a
naive split quietly declares 39 Year-7 particle-theory questions to be Year 6 questions,
which is the precise failure ADR-003 was written to prevent.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    LearningObjectiveReviewItem,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from app.services.lo_review_service import ITEM_TYPE_GRADE_SPLIT, STATUS_PENDING
from scripts.split_spanning_objectives import find_spanning, split_objective, verify

OBJECTIVE_TEXT = "Order a set of decimal numbers"


class SpanningFixture:
    """A grade-spanning objective plus one subtopic per grade, built in the database."""

    def __init__(self, objective: LearningObjective, subtopic_by_level: dict[int, Subtopic]) -> None:
        self.objective = objective
        self.subtopic_by_level = subtopic_by_level


async def _spanning_objective(
    db: AsyncSession,
    grade_levels: list[int],
    subject_code: str = "MATH",
) -> SpanningFixture:
    """One objective bridged to a subtopic at each of the given grades, grade_id NULL.

    This is the exact post-T1 state: the backfill refused to guess a grade, so the
    objective is left unresolved for T3 to split.
    """
    curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
    subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"{subject_code}{uuid.uuid4().hex[:4]}")
    topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    db.add_all([curriculum, subject, topic])
    await db.flush()

    objective = LearningObjective(
        id=uuid.uuid4(),
        canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
        name="Ordering decimals",
        learning_objective=OBJECTIVE_TEXT,
        normalised_objective="order a set of decimal numbers",
        topic_id=topic.id,
        grade_id=None,
        is_active=True,
    )
    db.add(objective)
    await db.flush()

    subtopic_by_level: dict[int, Subtopic] = {}
    for level in grade_levels:
        grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level)
        db.add(grade)
        await db.flush()
        curriculum_topic = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
            sequence_order=1,
        )
        db.add(curriculum_topic)
        await db.flush()
        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=curriculum_topic.id,
            name=f"Decimals G{level}",
            canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
            learning_objective=OBJECTIVE_TEXT,
            is_active=True,
        )
        db.add(subtopic)
        await db.flush()
        db.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))
        subtopic_by_level[level] = subtopic

    await db.flush()
    return SpanningFixture(objective, subtopic_by_level)


async def _question(
    db: AsyncSession,
    objective_id: uuid.UUID,
    subtopic_id: uuid.UUID | None,
) -> QuestionBank:
    question = QuestionBank(
        id=uuid.uuid4(),
        subtopic_id=subtopic_id,
        learning_objective_id=objective_id,
        question_text="Which is largest?",
        question_type="MCQ",
        options=[{"key": "A", "text": "0.5"}],
        correct_answer="A",
        canonical_form=f"q-{uuid.uuid4().hex[:10]}",
        problem_signature={},
        difficulty_level=2.0,
        source="bank",
        is_active=True,
    )
    db.add(question)
    await db.flush()
    return question


async def _split_all(db: AsyncSession) -> list[dict]:
    """Run the split over every spanning objective currently in the database."""
    return [await split_objective(db, source) for source in await find_spanning(db)]


async def _grade_level(db: AsyncSession, objective_id: uuid.UUID) -> int | None:
    return (
        await db.execute(
            select(Grade.level)
            .join(LearningObjective, LearningObjective.grade_id == Grade.id)
            .where(LearningObjective.id == objective_id)
        )
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_split_when_objective_spans_two_grades_then_creates_one_new_objective(
    db_session: AsyncSession,
) -> None:
    fixture = await _spanning_objective(db_session, [6, 7])
    original_code = fixture.objective.canonical_code

    reports = await _split_all(db_session)

    assert [r["objectives_created"] for r in reports] == [1]

    # The original keeps its id and takes the LOWEST grade — questions, review items and
    # exports already reference that id, so it must survive the split.
    assert await _grade_level(db_session, fixture.objective.id) == 6

    copy = (
        await db_session.execute(
            select(LearningObjective).where(LearningObjective.canonical_code == f"{original_code}-G7")
        )
    ).scalar_one()
    assert await _grade_level(db_session, copy.id) == 7
    # Same concept, same topic, same de-duplication key. Sharing normalised_objective is
    # not an oversight — it is what T4's UNIQUE (topic_id, grade_id, normalised_objective)
    # is designed to permit once the grades differ.
    assert copy.topic_id == fixture.objective.topic_id
    assert copy.learning_objective == fixture.objective.learning_objective
    assert copy.normalised_objective == fixture.objective.normalised_objective


@pytest.mark.asyncio
async def test_split_when_question_has_legacy_subtopic_then_repoints_to_correct_grade(
    db_session: AsyncSession,
) -> None:
    """Surviving subtopic_id is evidence of grade, and must be followed."""
    fixture = await _spanning_objective(db_session, [6, 7])
    at_grade_6 = await _question(db_session, fixture.objective.id, fixture.subtopic_by_level[6].id)
    at_grade_7 = await _question(db_session, fixture.objective.id, fixture.subtopic_by_level[7].id)

    await _split_all(db_session)
    await db_session.refresh(at_grade_6)
    await db_session.refresh(at_grade_7)

    assert at_grade_6.learning_objective_id == fixture.objective.id
    assert await _grade_level(db_session, at_grade_6.learning_objective_id) == 6

    assert at_grade_7.learning_objective_id != fixture.objective.id
    assert await _grade_level(db_session, at_grade_7.learning_objective_id) == 7

    # The bridge link moves with it, so the Year 7 subtopic no longer reaches the Year 6
    # objective. Without this the objective would still resolve to two grades.
    links = (
        (
            await db_session.execute(
                select(SubtopicObjective.learning_objective_id).where(
                    SubtopicObjective.subtopic_id == fixture.subtopic_by_level[7].id
                )
            )
        )
        .scalars()
        .all()
    )
    assert list(links) == [at_grade_7.learning_objective_id]


@pytest.mark.asyncio
async def test_split_when_question_has_no_subtopic_then_creates_review_item_not_silent_default(
    db_session: AsyncSession,
) -> None:
    """The whole point of T3: no provenance means no grade, not "the lowest grade"."""
    fixture = await _spanning_objective(db_session, [6, 7])
    orphan = await _question(db_session, fixture.objective.id, None)

    await _split_all(db_session)
    await db_session.refresh(orphan)

    item = (
        await db_session.execute(
            select(LearningObjectiveReviewItem).where(
                LearningObjectiveReviewItem.item_type == ITEM_TYPE_GRADE_SPLIT,
                LearningObjectiveReviewItem.source_code == fixture.objective.canonical_code,
            )
        )
    ).scalar_one()
    assert item.status == STATUS_PENDING
    assert item.question_ids == [str(orphan.id)]
    assert item.question_count == 1

    # Every grade is offered, including the one it is parked on — a reviewer confirming
    # Year 6 must be making a decision, not accepting a default they cannot see.
    assert sorted(c["grade_level"] for c in item.candidates) == [6, 7]

    # It stays bound and therefore stays selectable. A pending review must not remove a
    # question from the bank; the binding is wrong about grade, never about concept.
    assert orphan.learning_objective_id == fixture.objective.id
    # And no grade_level on the item: which grade it is IS the open question.
    assert item.grade_level is None


@pytest.mark.asyncio
async def test_split_when_run_twice_then_idempotent(db_session: AsyncSession) -> None:
    fixture = await _spanning_objective(db_session, [6, 7, 8])
    await _question(db_session, fixture.objective.id, fixture.subtopic_by_level[8].id)

    first = await _split_all(db_session)
    objectives_after_first = (
        (
            await db_session.execute(
                select(LearningObjective.id).where(LearningObjective.topic_id == fixture.objective.topic_id)
            )
        )
        .scalars()
        .all()
    )

    second = await _split_all(db_session)

    assert sum(r["objectives_created"] for r in first) == 2
    assert second == []  # nothing is spanning any more, so there is nothing to do
    objectives_after_second = (
        (
            await db_session.execute(
                select(LearningObjective.id).where(LearningObjective.topic_id == fixture.objective.topic_id)
            )
        )
        .scalars()
        .all()
    )
    assert set(objectives_after_second) == set(objectives_after_first)


@pytest.mark.asyncio
async def test_split_when_grade_has_no_questions_then_objective_created_and_reported(
    db_session: AsyncSession,
) -> None:
    """A grade whose provenance is gone still gets its objective — and an authoring backlog entry.

    This is expected output, not a failure. The curriculum genuinely teaches the
    objective at that grade; what is missing is questions, and someone has to write them.
    """
    fixture = await _spanning_objective(db_session, [7, 8])
    await _question(db_session, fixture.objective.id, fixture.subtopic_by_level[7].id)

    reports = await _split_all(db_session)

    assert reports[0]["grades_without_questions"] == [8]
    copy = (
        await db_session.execute(
            select(LearningObjective).where(
                LearningObjective.canonical_code == f"{fixture.objective.canonical_code}-G8"
            )
        )
    ).scalar_one()
    assert await _grade_level(db_session, copy.id) == 8


@pytest.mark.asyncio
async def test_verify_when_split_complete_then_no_postcondition_failures(db_session: AsyncSession) -> None:
    """verify() checks the full invariant, not just that objectives got a grade.

    A run that created the objectives but left links or questions pointing at the wrong
    grade is worse than no run at all, because it looks finished.
    """
    fixture = await _spanning_objective(db_session, [6, 7])
    await _question(db_session, fixture.objective.id, fixture.subtopic_by_level[7].id)
    await _question(db_session, fixture.objective.id, None)

    assert await verify(db_session) != []  # spanning objective still present, so it must complain

    await _split_all(db_session)

    assert await verify(db_session) == []
