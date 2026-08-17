"""Integration tests for the ADR-003 T4 identity constraint.

`UNIQUE (topic_id, grade_id, normalised_objective)` is the whole point of ADR-003 stated
as a database rule. These tests pin the three things that rule has to get right:

  - the same concept cannot exist twice at one grade,
  - the same concept CAN exist at different grades (that is what T3's split produces),
  - the stored key matches the Python helper the de-duplicator compares with.

The third is the one real risk of a stored rather than generated column. If
normalise_text() ever changed without a backfill, the constraint would still be enforced
— just against a key nobody computes any more, so genuine duplicates would slip past it
while the database reported the invariant as held.

This module also runs between the two script-test modules that relax these constraints,
so a failure here is an early signal that one of them leaked a relaxed schema.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.similarity import normalise_text
from app.models.curriculum import Grade, LearningObjective, Topic


async def _topic(db: AsyncSession) -> Topic:
    topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:8]}")
    db.add(topic)
    await db.flush()
    return topic


async def _grade(db: AsyncSession, level: int) -> Grade:
    grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level)
    db.add(grade)
    await db.flush()
    return grade


def _objective(
    topic_id: uuid.UUID,
    grade_id: uuid.UUID,
    learning_objective: str = "Order a set of decimal numbers",
    code: str | None = None,
) -> LearningObjective:
    return LearningObjective(
        id=uuid.uuid4(),
        canonical_code=code or f"LO-{uuid.uuid4().hex[:10]}",
        name="Ordering decimals",
        learning_objective=learning_objective,
        normalised_objective=normalise_text(learning_objective),
        topic_id=topic_id,
        grade_id=grade_id,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_learning_objective_when_duplicate_topic_grade_text_then_integrity_error(
    db_session: AsyncSession,
) -> None:
    """Two rows claiming the same concept at the same grade is the failure ADR-003 names."""
    topic = await _topic(db_session)
    grade = await _grade(db_session, 7)
    db_session.add(_objective(topic.id, grade.id))
    await db_session.flush()

    db_session.add(_objective(topic.id, grade.id))
    with pytest.raises(IntegrityError) as exc:
        await db_session.flush()

    assert "uq_learning_objective_topic_grade_text" in str(exc.value)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_learning_objective_when_duplicate_differs_only_in_punctuation_then_rejected(
    db_session: AsyncSession,
) -> None:
    """The key is the normalised text, so cosmetic differences do not buy a second row.

    Keying on canonical_code instead would have let both of these exist under different
    codes — the duplication ADR-003 exists to prevent, invisible to the database.
    """
    topic = await _topic(db_session)
    grade = await _grade(db_session, 7)
    db_session.add(_objective(topic.id, grade.id, "Order a set of decimal numbers"))
    await db_session.flush()

    db_session.add(_objective(topic.id, grade.id, "  ORDER a set of  decimal, numbers!  "))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_learning_objective_when_same_text_different_grade_then_allowed(
    db_session: AsyncSession,
) -> None:
    """Exactly what T3's split produces: one concept, one row per grade.

    The copies share normalised_objective by construction. Permitting that is the reason
    grade is in the key at all.
    """
    topic = await _topic(db_session)
    year_6 = await _grade(db_session, 6)
    year_7 = await _grade(db_session, 7)

    db_session.add(_objective(topic.id, year_6.id, code="MATH-ORDER-SET-DECIMAL"))
    db_session.add(_objective(topic.id, year_7.id, code="MATH-ORDER-SET-DECIMAL-G7"))
    await db_session.flush()

    rows = (
        (await db_session.execute(select(LearningObjective).where(LearningObjective.topic_id == topic.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert len({r.normalised_objective for r in rows}) == 1  # same concept
    assert len({r.grade_id for r in rows}) == 2  # different grades


@pytest.mark.asyncio
async def test_learning_objective_when_same_text_different_topic_then_allowed(
    db_session: AsyncSession,
) -> None:
    """Topic is in the key too — the same wording under two topics is two objectives."""
    grade = await _grade(db_session, 7)
    first = await _topic(db_session)
    second = await _topic(db_session)

    db_session.add(_objective(first.id, grade.id))
    db_session.add(_objective(second.id, grade.id))
    await db_session.flush()  # no error


@pytest.mark.asyncio
async def test_learning_objective_when_grade_id_missing_then_rejected(db_session: AsyncSession) -> None:
    """Grade is part of identity, so an objective without one is not a valid objective.

    This is what makes a question's grade derivable from its objective alone, rather than
    from a subtopic_id that a curriculum remap can NULL.
    """
    topic = await _topic(db_session)
    db_session.add(
        LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
            name="Ungraded",
            learning_objective="Order a set of decimal numbers",
            normalised_objective="order a set of decimal numbers",
            topic_id=topic.id,
            grade_id=None,
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_learning_objective_when_normalised_objective_missing_then_rejected(
    db_session: AsyncSession,
) -> None:
    topic = await _topic(db_session)
    grade = await _grade(db_session, 7)
    db_session.add(
        LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
            name="Unnormalised",
            learning_objective="Order a set of decimal numbers",
            normalised_objective=None,
            topic_id=topic.id,
            grade_id=grade.id,
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_normalised_objective_when_written_then_matches_normalise_text_helper(
    db_session: AsyncSession,
) -> None:
    """Guards the stored column against drifting from the helper that computes the key.

    Asserting the folded value literally, not just self-consistency: a change to
    normalise_text() that silently altered its output would otherwise satisfy a
    round-trip comparison while invalidating every key already in the table.
    """
    topic = await _topic(db_session)
    grade = await _grade(db_session, 7)
    accented = "Convertir  les  FRACTIONS, décimales & pourcentages!"
    db_session.add(_objective(topic.id, grade.id, accented))
    await db_session.flush()

    stored = (
        await db_session.execute(
            select(LearningObjective.normalised_objective).where(LearningObjective.topic_id == topic.id)
        )
    ).scalar_one()
    assert stored == normalise_text(accented)
    assert stored == "convertir les fractions decimales pourcentages"


@pytest.mark.asyncio
async def test_constraint_is_present_in_the_live_schema(db_session: AsyncSession) -> None:
    """The rule exists in the database, not only in the model.

    Also a canary for the two script-test modules that relax these columns: if either
    leaked a relaxed schema, this fails rather than every later test failing obscurely.
    """
    row = (
        await db_session.execute(
            text("""
                SELECT count(*) FROM pg_constraint
                WHERE conname = 'uq_learning_objective_topic_grade_text'
                  AND conrelid = 'learning_objectives'::regclass
            """)
        )
    ).scalar_one()
    assert row == 1

    nullable = (
        await db_session.execute(
            text("""
                SELECT column_name, is_nullable FROM information_schema.columns
                WHERE table_name = 'learning_objectives'
                  AND column_name IN ('grade_id', 'normalised_objective')
                ORDER BY column_name
            """)
        )
    ).all()
    assert [(r.column_name, r.is_nullable) for r in nullable] == [
        ("grade_id", "NO"),
        ("normalised_objective", "NO"),
    ]
