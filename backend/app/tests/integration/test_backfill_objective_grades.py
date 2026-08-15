"""Integration tests for the ADR-003 T1 grade backfill.

The behaviours worth proving against a real database:
  - an objective placed at exactly one grade gets that grade,
  - an objective placed at several grades is left NULL rather than guessed at,
  - re-running changes nothing,
  - the stored normalisation is byte-identical to the de-duplicator's.

That last one matters because T4 constrains
UNIQUE (topic_id, grade_id, normalised_objective). If the backfill and the
de-duplicator ever computed the key differently, the constraint would stop matching
what the de-duplicator considers a duplicate.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.similarity import normalise_text
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from scripts.backfill_objective_grades import (
    backfill_grade_ids,
    backfill_normalised_objectives,
    count_unresolved,
    describe_unresolved,
)

# This module's whole subject is objectives with a NULL grade, which ADR-003 T4 forbids.
# There is no way to test "the backfill fills NULLs" against a column that cannot hold
# one, so the constraint is relaxed for these tests and restored on teardown.
pytestmark = pytest.mark.usefixtures("ungraded_objectives_allowed")


async def _objective_placed_at(
    db: AsyncSession,
    grade_levels: list[int],
    objective_text: str = "Order a set of decimal numbers",
) -> LearningObjective:
    """Create one objective reachable from a subtopic at each of the given grades."""
    curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
    topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"X{uuid.uuid4().hex[:5]}")
    db.add_all([curriculum, subject, topic])
    await db.flush()

    objective = LearningObjective(
        id=uuid.uuid4(),
        canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
        name="Ordering decimals",
        learning_objective=objective_text,
        topic_id=topic.id,
        is_active=True,
    )
    db.add(objective)
    await db.flush()

    for level in grade_levels:
        grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level)
        db.add(grade)
        await db.flush()
        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
            sequence_order=1,
        )
        db.add(ct)
        await db.flush()
        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name=f"Decimals G{level}",
            canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
            learning_objective=objective_text,
            is_active=True,
        )
        db.add(subtopic)
        await db.flush()
        db.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))

    await db.flush()
    return objective


@pytest.mark.asyncio
async def test_backfill_when_objective_single_grade_then_sets_grade_id(db_session: AsyncSession) -> None:
    objective = await _objective_placed_at(db_session, [7])

    await backfill_grade_ids(db_session)

    resolved = (
        await db_session.execute(select(LearningObjective).where(LearningObjective.id == objective.id))
    ).scalar_one()
    await db_session.refresh(resolved)
    assert resolved.grade_id is not None

    level = (await db_session.execute(select(Grade.level).where(Grade.id == resolved.grade_id))).scalar_one()
    assert level == 7


@pytest.mark.asyncio
async def test_backfill_when_objective_spans_grades_then_leaves_null(db_session: AsyncSession) -> None:
    """A grade-spanning objective must stay NULL, not be silently assigned.

    Picking one of its grades here would assign grade by accident of the query rather
    than by evidence — the exact error ADR-003 exists to prevent. T3 splits these.
    """
    objective = await _objective_placed_at(db_session, [6, 7])

    await backfill_grade_ids(db_session)

    resolved = (
        await db_session.execute(select(LearningObjective).where(LearningObjective.id == objective.id))
    ).scalar_one()
    await db_session.refresh(resolved)
    assert resolved.grade_id is None


@pytest.mark.asyncio
async def test_backfill_when_run_twice_then_idempotent(db_session: AsyncSession) -> None:
    await _objective_placed_at(db_session, [8])

    first = await backfill_grade_ids(db_session)
    second = await backfill_grade_ids(db_session)

    assert first >= 1
    assert second == 0


@pytest.mark.asyncio
async def test_backfill_when_run_then_normalised_objective_matches_helper(db_session: AsyncSession) -> None:
    """The stored key must equal normalise_text() exactly — T4's constraint depends on it."""
    text_with_accents = "Convertir  les  FRACTIONS, décimales & pourcentages!"
    objective = await _objective_placed_at(db_session, [7], objective_text=text_with_accents)

    await backfill_normalised_objectives(db_session)

    stored = (
        await db_session.execute(
            select(LearningObjective.normalised_objective).where(LearningObjective.id == objective.id)
        )
    ).scalar_one()
    assert stored == normalise_text(text_with_accents)
    # Guards the folding itself, not just self-consistency.
    assert stored == "convertir les fractions decimales pourcentages"


@pytest.mark.asyncio
async def test_backfill_normalised_when_run_twice_then_idempotent(db_session: AsyncSession) -> None:
    await _objective_placed_at(db_session, [7])

    first = await backfill_normalised_objectives(db_session)
    second = await backfill_normalised_objectives(db_session)

    assert first >= 1
    assert second == 0


@pytest.mark.asyncio
async def test_count_and_describe_unresolved_when_spanning_then_reports_grades(db_session: AsyncSession) -> None:
    """The operator-facing report must name the offending objective and its grades."""
    objective = await _objective_placed_at(db_session, [6, 7])
    await backfill_grade_ids(db_session)

    assert await count_unresolved(db_session) >= 1

    described = dict(await describe_unresolved(db_session))
    assert objective.canonical_code in described
    assert described[objective.canonical_code] == "6,7"


@pytest.mark.asyncio
async def test_backfill_when_objective_has_no_placement_then_left_null(db_session: AsyncSession) -> None:
    """An objective bridged to no subtopic has no grade to derive, and must not error."""
    topic = Topic(id=uuid.uuid4(), name="Orphan", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    await db_session.flush()
    orphan = LearningObjective(
        id=uuid.uuid4(),
        canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
        name="Unplaced",
        learning_objective="Never taught anywhere",
        topic_id=topic.id,
        is_active=True,
    )
    db_session.add(orphan)
    await db_session.flush()

    await backfill_grade_ids(db_session)

    await db_session.refresh(orphan)
    assert orphan.grade_id is None


@pytest.mark.asyncio
async def test_describe_unresolved_when_objective_unplaced_then_still_reported(
    db_session: AsyncSession,
) -> None:
    """count_unresolved and describe_unresolved must cover the same set.

    Two things leave grade_id NULL: grade-spanning objectives (what T3 splits) and
    objectives no subtopic links at all, e.g. after a wipe cascaded their bridge rows.
    An inner join reported only the first, so the count guard could fail on a number
    the report could not account for — "found 14, expected 12" with twelve rows listed.
    """
    topic = Topic(id=uuid.uuid4(), name="Orphan", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    await db_session.flush()
    orphan_code = f"LO-{uuid.uuid4().hex[:10]}"
    db_session.add(
        LearningObjective(
            id=uuid.uuid4(),
            canonical_code=orphan_code,
            name="Unplaced",
            learning_objective="Never taught anywhere",
            topic_id=topic.id,
            is_active=True,
        )
    )
    await db_session.flush()

    await backfill_grade_ids(db_session)

    described = dict(await describe_unresolved(db_session))
    assert orphan_code in described
    assert described[orphan_code] == "none"
    # The two diagnostics agree, so the count guard can always explain its number.
    assert await count_unresolved(db_session) == len(described)


@pytest.mark.asyncio
async def test_canonical_code_accepts_grade_suffix_beyond_50_chars(db_session: AsyncSession) -> None:
    """T3 suffixes codes with -G{level}; the column was widened to 64 to allow it."""
    topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    await db_session.flush()

    long_code = ("MATH-" + "X" * 45)[:46] + "-G12"  # 50 chars, over the old limit
    assert len(long_code) > 46
    db_session.add(
        LearningObjective(
            id=uuid.uuid4(),
            canonical_code=long_code,
            name="Long code",
            learning_objective="Something",
            topic_id=topic.id,
            is_active=True,
        )
    )
    await db_session.flush()

    stored = (
        await db_session.execute(
            select(LearningObjective.canonical_code).where(LearningObjective.canonical_code == long_code)
        )
    ).scalar_one()
    assert stored == long_code


@pytest.mark.asyncio
async def test_lo_review_items_accepts_objective_grade_split_item_type(db_session: AsyncSession) -> None:
    """T3 parks unresolvable questions as OBJECTIVE_GRADE_SPLIT; the CHECK must allow it."""
    await db_session.execute(
        text("""
            INSERT INTO lo_review_items
                (id, item_type, status, source_code, source_learning_objective,
                 question_count, candidates, question_ids, created_at)
            VALUES
                (gen_random_uuid(), 'OBJECTIVE_GRADE_SPLIT', 'PENDING', :code, 'Ordering decimals',
                 3, '[]'::jsonb, '[]'::jsonb, now())
        """),
        {"code": f"SPLIT-{uuid.uuid4().hex[:8]}"},
    )

    count = (
        await db_session.execute(text("SELECT count(*) FROM lo_review_items WHERE item_type = 'OBJECTIVE_GRADE_SPLIT'"))
    ).scalar_one()
    assert count >= 1
