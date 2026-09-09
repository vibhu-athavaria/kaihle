"""Integration tests for the calibration script's database-touching parts.

The pure fitting/backoff logic is covered by
app/tests/unit/test_calibrate_mastery_prior.py without a database. What needs a real
database here is Finding 4's invariant: every ACTIVE subtopic gets a row, including one
with zero response data, and the write is idempotent.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.models.curriculum import Curriculum, CurriculumTopic, Grade, Subject, Subtopic, Topic
from app.models.gap import MasteryPrior
from scripts.calibrate_mastery_prior import gather_all_subtopic_pools, resolve_prior, write_priors

_next_grade_level = iter(range(1, 10_000))


async def _make_subtopic(db, *, active: bool = True) -> Subtopic:
    """A minimal, valid curriculum chain down to one subtopic. No response data attached —
    the point of these tests is what happens when a subtopic has none."""
    curriculum = Curriculum(id=uuid.uuid4(), name=f"C-{uuid.uuid4().hex[:8]}", code=f"c{uuid.uuid4().hex[:8]}")
    subject = Subject(id=uuid.uuid4(), name=f"Subject {uuid.uuid4().hex[:8]}", code=f"S{uuid.uuid4().hex[:6]}")
    # grades.level is globally unique, so each call needs a fresh one — not one fixed value.
    grade = Grade(id=uuid.uuid4(), name=f"Grade {uuid.uuid4().hex[:6]}", level=next(_next_grade_level))
    topic = Topic(id=uuid.uuid4(), name="Topic", canonical_code=f"T{uuid.uuid4().hex[:8]}")
    db.add_all([curriculum, subject, grade, topic])
    await db.flush()

    curriculum_topic = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=active,
    )
    db.add(curriculum_topic)
    await db.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic.id,
        name="Subtopic",
        learning_objective="Objective.",
        is_active=active,
    )
    db.add(subtopic)
    await db.flush()
    return subtopic


@pytest.mark.asyncio
class TestGatherAndWrite:
    async def test_gather_when_subtopic_has_no_responses_then_included_with_empty_pools(self, db_session) -> None:
        # Finding 4: most of the curriculum has zero data today. gather_all_subtopic_pools
        # must surface such a subtopic, not silently omit it.
        subtopic = await _make_subtopic(db_session)

        pools = await gather_all_subtopic_pools(db_session)

        assert str(subtopic.id) in pools
        assert pools[str(subtopic.id)]["SUBTOPIC"] == []

    async def test_gather_when_subtopic_inactive_then_excluded(self, db_session) -> None:
        subtopic = await _make_subtopic(db_session, active=False)

        pools = await gather_all_subtopic_pools(db_session)

        assert str(subtopic.id) not in pools

    async def test_write_priors_when_subtopic_has_no_data_then_row_written_as_global(self, db_session) -> None:
        subtopic = await _make_subtopic(db_session)
        pools = await gather_all_subtopic_pools(db_session)

        resolutions = {sid: resolve_prior(p, fallback_alpha=2.0, fallback_beta=3.0) for sid, p in pools.items()}
        await write_priors(db_session, resolutions)
        await db_session.flush()

        row = await db_session.get(MasteryPrior, subtopic.id)
        assert row is not None
        assert row.source_level == "GLOBAL"

    async def test_write_priors_when_every_active_subtopic_present_then_row_count_matches(self, db_session) -> None:
        # The Finding-4 invariant, stated as a test: a row for EVERY active subtopic,
        # never a "missing row means no data yet" gap gap_service would have to special-case.
        for _ in range(3):
            await _make_subtopic(db_session)
        await _make_subtopic(db_session, active=False)  # must not get a row

        active_count = await db_session.scalar(
            select(func.count()).select_from(Subtopic).where(Subtopic.is_active.is_(True))
        )
        pools = await gather_all_subtopic_pools(db_session)
        resolutions = {sid: resolve_prior(p, fallback_alpha=2.0, fallback_beta=3.0) for sid, p in pools.items()}
        await write_priors(db_session, resolutions)
        await db_session.flush()

        written_count = await db_session.scalar(select(func.count()).select_from(MasteryPrior))
        assert written_count == active_count

    async def test_write_priors_when_run_twice_then_idempotent(self, db_session) -> None:
        subtopic = await _make_subtopic(db_session)
        pools = await gather_all_subtopic_pools(db_session)
        resolutions = {sid: resolve_prior(p, fallback_alpha=2.0, fallback_beta=3.0) for sid, p in pools.items()}

        await write_priors(db_session, resolutions)
        await db_session.flush()
        first = await db_session.get(MasteryPrior, subtopic.id)
        first_fitted_at = first.fitted_at

        await write_priors(db_session, resolutions)
        await db_session.flush()
        await db_session.refresh(first)

        count = await db_session.scalar(select(func.count()).select_from(MasteryPrior))
        assert count == 1  # upsert, not a second row
        assert first.fitted_at >= first_fitted_at  # refreshed, not stale

    async def test_write_priors_when_subtopic_deleted_then_prior_row_cascades(self, db_session) -> None:
        subtopic = await _make_subtopic(db_session)
        pools = await gather_all_subtopic_pools(db_session)
        resolutions = {sid: resolve_prior(p, fallback_alpha=2.0, fallback_beta=3.0) for sid, p in pools.items()}
        await write_priors(db_session, resolutions)
        await db_session.flush()

        await db_session.delete(subtopic)
        await db_session.flush()

        row = await db_session.get(MasteryPrior, subtopic.id)
        assert row is None
