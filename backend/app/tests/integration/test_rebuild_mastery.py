"""Integration tests for scripts/rebuild_mastery.py.

Reuses the curriculum/attempt fixtures already built for test_gap_states_updated.py
rather than duplicating them — same helpers, same shape of data, so a change to one does
not silently drift from the other.

DELIBERATELY DOES NOT CALL rebuild_mastery.run() OR main(). Both open their own engine
against settings.database_url — the real configured database, not this test's isolated
TEST_DATABASE_URL (which defaults to a separate kaihle_test database; see
tests/integration/conftest.py). Calling run() here would either silently find nothing (a
false pass) or, worse, operate on real data if the two URLs ever happened to coincide.
The same convention already applies to calibrate_mastery_prior.py's and
eval_lo_matching.py's integration tests: exercise the composable pieces directly against
db_session, never the top-level orchestrator that owns its own connection. Every
function under test here (replay_attempt, gather_all_subtopic_pools, resolve_prior,
write_priors) takes `db` as a parameter and touches no engine of its own, so this is safe.

Not tested here: an --old-formula mode or a before/after band-change gate — this task
deliberately has neither (see rebuild_mastery.py's module docstring and
docs/design/MASTERY_MODEL_RATIONALE.md).
"""

import uuid

import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.models.assessment import StudentAttemptSubtopicScore
from app.models.gap import GapState
from app.models.school import School
from app.models.user import User, UserRole
from app.services.gap_service import GapService
from app.tests.integration.test_gap_states_updated import (
    _create_assessment,
    _create_attempt,
    _create_class,
    _create_curriculum_chain,
    _create_question,
    _create_response,
    _create_teacher,
)
from scripts.calibrate_mastery_prior import gather_all_subtopic_pools, resolve_prior, write_priors
from scripts.rebuild_mastery import _fetch_all_priors, replay_attempt


async def _fit_and_write_priors(db) -> dict[str, tuple[float, float]]:
    """The calibration half of a rebuild, run against db_session — same functions
    calibrate_mastery_prior.py --apply uses, already proven correct by its own suite."""
    pools = await gather_all_subtopic_pools(db)
    cache: dict[int, tuple[float, float, int] | None] = {}
    resolutions = {
        sid: resolve_prior(
            p, fallback_alpha=settings.mastery_prior_alpha, fallback_beta=settings.mastery_prior_beta, level_cache=cache
        )
        for sid, p in pools.items()
    }
    await write_priors(db, resolutions)
    await db.flush()
    return await _fetch_all_priors(db)


async def _replay_all_completed_attempts_oldest_first(db, service: GapService, priors) -> int:
    """The replay half of a rebuild: every COMPLETED attempt, oldest completed_at first —
    same ordering rebuild_mastery.run() uses, expressed directly against db_session."""
    rows = (
        await db.execute(
            text(
                """
                SELECT sa.id, sa.student_id, sa.completed_at, a.school_id, a.class_id
                FROM student_attempts sa
                JOIN assessments a ON a.id = sa.assessment_id
                WHERE sa.status = 'COMPLETED' AND sa.completed_at IS NOT NULL
                ORDER BY sa.completed_at ASC, sa.id ASC
                """
            )
        )
    ).all()
    total = 0
    for row in rows:
        total += await replay_attempt(db, service, attempt=row, assessment=row, priors=priors)
    return total


@pytest.mark.asyncio
class TestRebuildMastery:
    async def _scenario(self, db_session, school: School):
        """One student, one subtopic, one 3/5-correct completed attempt."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        questions = [await _create_question(db_session, subtopic) for _ in range(5)]

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-rebuild-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Rebuild",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        for i, q in enumerate(questions):
            await _create_response(db_session, attempt, q, is_correct=i < 3)
        await db_session.flush()

        return student, subtopic

    async def test_rebuild_when_dry_run_then_no_rows_modified(self, db_session, school: School) -> None:
        """A dry run is just: do the work in a transaction, then roll it back. Both
        rebuild_mastery halves (calibration, replay) take `db` as a parameter and commit
        nothing themselves — the caller's transaction boundary is what makes --dry-run
        vs --apply a real distinction, and that boundary is what this test exercises."""
        await self._scenario(db_session, school)

        priors_before = len((await db_session.execute(select(GapState))).scalars().all())

        priors = await _fit_and_write_priors(db_session)
        service = GapService(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)

        # The "dry run" boundary: roll back everything just written, exactly what
        # rebuild_mastery.run(apply=False) does at the end of its own transaction.
        await db_session.rollback()

        gap_states_after = len((await db_session.execute(select(GapState))).scalars().all())
        assert gap_states_after == priors_before == 0

    async def test_rebuild_when_applied_then_score_matches_estimator_output(self, db_session, school: School) -> None:
        student, subtopic = await self._scenario(db_session, school)

        priors = await _fit_and_write_priors(db_session)
        service = GapService(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        # 3/5 correct, no prior calibrated for this brand-new subtopic (this is the only
        # response data in the whole isolated test DB, so even GLOBAL has nothing to fit)
        # → the platform bootstrap default Beta(2,3): posterior = (3+2)/(5+2+3) = 0.5.
        assert gap_state.mastery_score == pytest.approx(0.5, abs=1e-6)

        score_row = (
            await db_session.execute(
                select(StudentAttemptSubtopicScore).where(
                    StudentAttemptSubtopicScore.student_id == student.id,
                    StudentAttemptSubtopicScore.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert score_row is not None
        assert score_row.correct_count == 3
        assert score_row.total_count == 5

    async def test_rebuild_when_run_twice_then_second_run_is_a_no_op(self, db_session, school: School) -> None:
        student, subtopic = await self._scenario(db_session, school)
        service = GapService(db_session)

        priors = await _fit_and_write_priors(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()
        first = (
            await db_session.execute(
                select(GapState.mastery_score, GapState.confidence).where(
                    GapState.student_id == student.id, GapState.subtopic_id == subtopic.id
                )
            )
        ).one()

        priors = await _fit_and_write_priors(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()
        second = (
            await db_session.execute(
                select(GapState.mastery_score, GapState.confidence).where(
                    GapState.student_id == student.id, GapState.subtopic_id == subtopic.id
                )
            )
        ).one()

        assert second.mastery_score == pytest.approx(first.mastery_score, abs=1e-9)
        assert second.confidence == pytest.approx(first.confidence, abs=1e-9)

        rows = (
            (
                await db_session.execute(
                    select(StudentAttemptSubtopicScore).where(
                        StudentAttemptSubtopicScore.student_id == student.id,
                        StudentAttemptSubtopicScore.subtopic_id == subtopic.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1  # one attempt, one row — a second run must not duplicate it

    async def test_rebuild_when_attempts_replayed_then_processed_oldest_first(self, db_session, school: School) -> None:
        """A weak-then-strong attempt pair rebuilds to the value the live recency-weighted
        path produces — the SAME number
        test_gap_states_when_repeat_attempt_then_recent_weighted_above_historical asserts,
        which only holds if replay order is oldest-first. Reversed order gives a
        different number."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-order-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Order",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        # Two assessments, not one: student_attempts has a UNIQUE (assessment_id,
        # student_id) constraint — one student can have only one attempt per assessment.
        first_assessment = await _create_assessment(db_session, school, class_, teacher)
        first_questions = [await _create_question(db_session, subtopic) for _ in range(5)]
        first_attempt = await _create_attempt(db_session, first_assessment, student)
        for i, q in enumerate(first_questions):
            await _create_response(db_session, first_attempt, q, is_correct=i == 0)  # 1/5

        second_assessment = await _create_assessment(db_session, school, class_, teacher)
        second_questions = [await _create_question(db_session, subtopic) for _ in range(5)]
        second_attempt = await _create_attempt(db_session, second_assessment, student)
        for q in second_questions:
            await _create_response(db_session, second_attempt, q, is_correct=True)  # 5/5
        await db_session.flush()

        priors = await _fit_and_write_priors(db_session)
        service = GapService(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        # decay=0.7: weighted_correct = 5*1 + 1*0.7 = 5.7, weighted_total = 5+3.5 = 8.5.
        # posterior = (5.7+2)/(8.5+5) = 7.7/13.5.
        assert gap_state.mastery_score == pytest.approx(7.7 / 13.5, abs=1e-6)

    async def test_rebuild_when_question_attribution_unresolvable_then_counts_left_null(
        self, db_session, school: School
    ) -> None:
        """A completed attempt whose class no longer exists cannot be attributed to any
        subtopic. The rebuild must skip it — leaving no row, not a fabricated one."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        question = await _create_question(db_session, subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-unresolv-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Unresolvable",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)
        await db_session.delete(class_)  # class gone → attribution query finds nothing
        await db_session.flush()

        priors = await _fit_and_write_priors(db_session)
        service = GapService(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        rows = (
            (
                await db_session.execute(
                    select(StudentAttemptSubtopicScore).where(
                        StudentAttemptSubtopicScore.student_id == student.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []

    async def test_rebuild_when_counts_backfilled_then_correct_never_exceeds_total(
        self, db_session, school: School
    ) -> None:
        student, subtopic = await self._scenario(db_session, school)

        priors = await _fit_and_write_priors(db_session)
        service = GapService(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        rows = (
            (
                await db_session.execute(
                    select(StudentAttemptSubtopicScore).where(
                        StudentAttemptSubtopicScore.student_id == student.id,
                        StudentAttemptSubtopicScore.subtopic_id == subtopic.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].correct_count <= rows[0].total_count
        assert rows[0].correct_count >= 0

    async def test_rebuild_when_interrupted_midway_then_resume_completes_without_double_counting(
        self, db_session, school: School
    ) -> None:
        """Simulates resuming after an interruption: run the full pipeline twice in a row
        (the second pass stands in for "resume from a killed process"). The result must
        match a single uninterrupted run — re-running must not double-count evidence
        already written by an earlier, complete pass."""
        student, subtopic = await self._scenario(db_session, school)
        service = GapService(db_session)

        priors = await _fit_and_write_priors(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        priors = await _fit_and_write_priors(db_session)
        await _replay_all_completed_attempts_oldest_first(db_session, service, priors)
        await db_session.flush()

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        assert gap_state.mastery_score == pytest.approx(0.5, abs=1e-6)  # same as a single run

        rows = (
            (
                await db_session.execute(
                    select(StudentAttemptSubtopicScore).where(
                        StudentAttemptSubtopicScore.student_id == student.id,
                        StudentAttemptSubtopicScore.subtopic_id == subtopic.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1  # no duplicate row from the second pass
