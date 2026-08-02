"""Integration tests for the scoped curriculum wipe.

The wipe is destructive and irreversible in-place, so the properties that matter are
tested against a real database rather than mocks:
  - it removes exactly the requested scope and nothing else,
  - it preserves every question,
  - it refuses to destroy teacher-authored data unless explicitly waived,
  - it keeps topics that are still referenced elsewhere.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User, UserRole
from scripts.wipe_curriculum import (
    WipeScopeError,
    _params,
    assert_no_blocking_rows,
    execute_wipe,
    verify_postconditions,
    verify_scope_exists,
)


@pytest.mark.asyncio
class TestScopedWipe:
    """Each test builds an in-scope and an out-of-scope slice, then wipes only one."""

    async def _build(
        self,
        db: AsyncSession,
        *,
        curriculum_code: str,
        subject_code: str,
        grade_level: int,
        topic: Topic,
        with_question: bool = False,
    ) -> tuple[Curriculum, Subject, Grade, Subtopic]:
        curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=curriculum_code, is_active=True)
        subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=subject_code, is_active=True)
        grade = Grade(id=uuid.uuid4(), name=f"Grade {grade_level}", level=grade_level, is_active=True)
        db.add_all([curriculum, subject, grade])
        await db.flush()

        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
            sequence_order=1,
            is_required=True,
        )
        db.add(ct)
        await db.flush()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name="Subtopic",
            canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
            learning_objective="Do the thing.",
            is_active=True,
        )
        db.add(subtopic)
        await db.flush()

        if with_question:
            db.add(
                QuestionBank(
                    id=uuid.uuid4(),
                    subtopic_id=subtopic.id,
                    question_text="What is 2 + 2?",
                    question_type="MCQ",
                    options=[{"key": "A", "text": "4"}],
                    correct_answer="A",
                    canonical_form="2+2",
                    problem_signature={},
                    difficulty_level=1.0,
                    source="bank",
                    is_active=True,
                )
            )
        await db.commit()
        return curriculum, subject, grade, subtopic

    @staticmethod
    def _uniq(prefix: str) -> str:
        return f"{prefix}{uuid.uuid4().hex[:6]}"

    async def test_wipe_when_scope_given_then_out_of_scope_slice_survives(self, db_session: AsyncSession) -> None:
        shared_topic = Topic(id=uuid.uuid4(), name="Shared", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(shared_topic)
        await db_session.flush()

        curriculum, subject, _, in_scope = await self._build(
            db_session,
            curriculum_code=self._uniq("cur"),
            subject_code=self._uniq("A"),
            grade_level=6,
            topic=shared_topic,
        )
        # Same curriculum and subject, different grade — must not be touched.
        out_grade = Grade(id=uuid.uuid4(), name="Grade 9", level=9, is_active=True)
        db_session.add(out_grade)
        await db_session.flush()
        out_ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=out_grade.id,
            topic_id=shared_topic.id,
            sequence_order=1,
        )
        db_session.add(out_ct)
        await db_session.flush()
        out_scope = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=out_ct.id,
            name="Out of scope",
            canonical_code=self._uniq("ST"),
            learning_objective="Survive.",
            is_active=True,
        )
        db_session.add(out_scope)
        await db_session.commit()

        params = _params(curriculum.code, [subject.code], [6])
        await execute_wipe(db_session, params, delete_topic_bindings=False)
        await db_session.commit()

        remaining = await db_session.execute(select(Subtopic.id).where(Subtopic.id.in_([in_scope.id, out_scope.id])))
        assert {r[0] for r in remaining} == {out_scope.id}

    async def test_wipe_when_questions_in_scope_then_kept_and_unbound(self, db_session: AsyncSession) -> None:
        """Questions are the asset being preserved — they are unbound, never deleted."""
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(topic)
        await db_session.flush()
        curriculum, subject, _, subtopic = await self._build(
            db_session,
            curriculum_code=self._uniq("cur"),
            subject_code=self._uniq("A"),
            grade_level=6,
            topic=topic,
            with_question=True,
        )

        params = _params(curriculum.code, [subject.code], [6])
        affected = await execute_wipe(db_session, params, delete_topic_bindings=False)
        await db_session.commit()

        assert affected["question_bank_unbound"] == 1
        result = await db_session.execute(select(QuestionBank).where(QuestionBank.canonical_form == "2+2"))
        question = result.scalar_one()
        assert question.subtopic_id is None
        assert question.is_active is True

    async def test_wipe_when_topic_still_referenced_elsewhere_then_topic_survives(
        self, db_session: AsyncSession
    ) -> None:
        """Topics are shared across grades and curricula; only true orphans are removed."""
        shared_topic = Topic(id=uuid.uuid4(), name="Shared", canonical_code=self._uniq("T"), is_active=True)
        orphan_topic = Topic(id=uuid.uuid4(), name="Orphan", canonical_code=self._uniq("T"), is_active=True)
        db_session.add_all([shared_topic, orphan_topic])
        await db_session.flush()

        curriculum, subject, grade, _ = await self._build(
            db_session,
            curriculum_code=self._uniq("cur"),
            subject_code=self._uniq("A"),
            grade_level=6,
            topic=orphan_topic,
        )
        # shared_topic is referenced by an out-of-scope curriculum_topic.
        other_curriculum = Curriculum(
            id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=self._uniq("cur"), is_active=True
        )
        db_session.add(other_curriculum)
        await db_session.flush()
        db_session.add(
            CurriculumTopic(
                id=uuid.uuid4(),
                curriculum_id=other_curriculum.id,
                subject_id=subject.id,
                grade_id=grade.id,
                topic_id=shared_topic.id,
                sequence_order=1,
            )
        )
        # ...and also by the in-scope one, so the wipe "sees" it.
        db_session.add(
            CurriculumTopic(
                id=uuid.uuid4(),
                curriculum_id=curriculum.id,
                subject_id=subject.id,
                grade_id=grade.id,
                topic_id=shared_topic.id,
                sequence_order=2,
            )
        )
        await db_session.commit()

        params = _params(curriculum.code, [subject.code], [6])
        await execute_wipe(db_session, params, delete_topic_bindings=False)
        await db_session.commit()

        surviving = await db_session.execute(select(Topic.id).where(Topic.id.in_([shared_topic.id, orphan_topic.id])))
        assert {r[0] for r in surviving} == {shared_topic.id}

    async def test_blocking_check_when_class_topic_bound_then_refuses_without_waiver(
        self, db_session: AsyncSession, test_school_class_topic: tuple[str, str, int]
    ) -> None:
        curriculum_code, subject_code, grade_level = test_school_class_topic
        params = _params(curriculum_code, [subject_code], [grade_level])

        with pytest.raises(WipeScopeError, match="class_topics"):
            await assert_no_blocking_rows(db_session, params, delete_topic_bindings=False)

    async def test_blocking_check_when_waiver_passed_then_allows_wipe(
        self, db_session: AsyncSession, test_school_class_topic: tuple[str, str, int]
    ) -> None:
        curriculum_code, subject_code, grade_level = test_school_class_topic
        params = _params(curriculum_code, [subject_code], [grade_level])

        await assert_no_blocking_rows(db_session, params, delete_topic_bindings=True)

    async def test_verify_scope_when_subject_code_unknown_then_raises(self, db_session: AsyncSession) -> None:
        """A typo must fail loudly, not look like a successful no-op wipe."""
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(topic)
        await db_session.flush()
        curriculum, _, _, _ = await self._build(
            db_session,
            curriculum_code=self._uniq("cur"),
            subject_code=self._uniq("A"),
            grade_level=6,
            topic=topic,
        )

        with pytest.raises(WipeScopeError, match="Unknown subject code"):
            await verify_scope_exists(db_session, _params(curriculum.code, ["NOPE_NOT_A_SUBJECT"], [6]))

    async def test_verify_scope_when_curriculum_code_unknown_then_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(WipeScopeError, match="No curriculum with code"):
            await verify_scope_exists(db_session, _params("no_such_curriculum", ["MATH"], [6]))

    async def test_verify_scope_when_scope_matches_nothing_then_raises(self, db_session: AsyncSession) -> None:
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(topic)
        await db_session.flush()
        curriculum, subject, _, _ = await self._build(
            db_session, curriculum_code=self._uniq("cur"), subject_code=self._uniq("A"), grade_level=6, topic=topic
        )

        # Right curriculum and subject, but a grade with no rows.
        with pytest.raises(WipeScopeError, match="matched 0 curriculum_topics"):
            await verify_scope_exists(db_session, _params(curriculum.code, [subject.code], [13]))

    async def test_postconditions_when_scope_fully_cleared_then_passes(self, db_session: AsyncSession) -> None:
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(topic)
        await db_session.flush()
        curriculum, subject, _, _ = await self._build(
            db_session,
            curriculum_code=self._uniq("cur"),
            subject_code=self._uniq("A"),
            grade_level=6,
            topic=topic,
            with_question=True,
        )
        params = _params(curriculum.code, [subject.code], [6])

        await execute_wipe(db_session, params, delete_topic_bindings=False)
        await verify_postconditions(db_session, params)

    async def test_postconditions_when_scope_not_cleared_then_raises(self, db_session: AsyncSession) -> None:
        """Guards against a wipe that silently under-deletes."""
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=self._uniq("T"), is_active=True)
        db_session.add(topic)
        await db_session.flush()
        curriculum, subject, _, _ = await self._build(
            db_session, curriculum_code=self._uniq("cur"), subject_code=self._uniq("A"), grade_level=6, topic=topic
        )
        params = _params(curriculum.code, [subject.code], [6])

        with pytest.raises(WipeScopeError, match="still in scope"):
            await verify_postconditions(db_session, params)


@pytest.fixture
async def test_school_class_topic(
    db_session: AsyncSession,
) -> tuple[str, str, int]:
    """Build a scope with a class_topics row bound to it, the RESTRICT blocker case."""
    curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
    subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"B{uuid.uuid4().hex[:6]}")
    grade = Grade(id=uuid.uuid4(), name="Grade 6", level=6)
    topic = Topic(id=uuid.uuid4(), name="T", canonical_code=f"T{uuid.uuid4().hex[:6]}")
    school = School(id=uuid.uuid4(), name="S", slug=f"s-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add_all([curriculum, subject, grade, topic, school])
    await db_session.flush()

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"t-{uuid.uuid4().hex[:8]}@example.com",
        first_name="T",
        last_name="T",
        role=UserRole.TEACHER,
    )
    db_session.add(teacher)
    await db_session.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        sequence_order=1,
    )
    klass = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        name="Math",
        teacher_id=teacher.id,
        academic_year="2026-2027",
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
    )
    db_session.add_all([ct, klass])
    await db_session.flush()

    await db_session.execute(
        text(
            "INSERT INTO class_topics "
            "(id, school_id, class_id, curriculum_topic_id, sequence_order, is_covered, created_at) "
            "VALUES (:i, :s, :c, :ct, 1, false, now())"
        ),
        {"i": uuid.uuid4(), "s": school.id, "c": klass.id, "ct": ct.id},
    )
    await db_session.commit()
    return curriculum.code, subject.code, 6
