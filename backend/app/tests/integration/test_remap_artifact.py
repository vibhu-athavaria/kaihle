"""Integration tests for curriculum remap artifact export and import.

These scripts are the mechanism for promoting curriculum decisions between
environments, and they will be relied on for every future increment (ENG grades 6-8,
IGCSE, A-level). Until now their only verification was a manual round trip.

The properties that matter: the import is deterministic and keyed on canonical codes
rather than UUIDs, it is idempotent, it refuses to silently re-apply, and it reports
rather than hides anything it could not resolve.
"""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.similarity import normalise_text
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from scripts.import_remap_artifact import (
    ImportError_,
    already_applied,
    apply_question_mapping,
    import_objectives,
    import_placements,
    resolve_grades,
)


@pytest.mark.asyncio
class TestArtifactImport:
    async def _tree(self, db: AsyncSession) -> tuple[Topic, Subtopic]:
        curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
        subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"X{uuid.uuid4().hex[:5]}")
        grade = Grade(id=uuid.uuid4(), name="Grade 6", level=6)
        topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"TOPIC-{uuid.uuid4().hex[:8]}")
        db.add_all([curriculum, subject, grade, topic])
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
            name="Sub",
            canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
            learning_objective="Do the thing.",
            is_active=True,
        )
        db.add(subtopic)
        await db.commit()
        return topic, subtopic

    @staticmethod
    def _objective_payload(topic_code: str, code: str) -> dict:
        return {
            "canonical_code": code,
            "name": "Imported objective",
            "learning_objective": "Order negative integers on a number line.",
            "bloom_taxonomy_level": "Apply",
            # Exported as pgvector's text form; the importer must pass it through.
            "embedding": "[" + ",".join(["0.01"] * 768) + "]",
            "topic_code": topic_code,
            # v2 field. ADR-003 T4 makes grade_id NOT NULL, and nothing in an artifact
            # may be keyed on a UUID, so grade travels as a level and each environment
            # resolves it against its own grades table.
            "grade_level": 6,
        }

    async def _grade_map(self, db: AsyncSession, payload: list[dict]) -> dict[str, uuid.UUID]:
        """Resolve every payload objective to this environment's Grade 6.

        import_objectives takes a pre-resolved map rather than deriving grade itself, so
        that a v1 artifact which cannot yield one aborts before anything is written.
        These tests are about topic and code resolution, so they all use the single grade
        _tree() creates; the grade-specific behaviour is covered by TestArtifactGrades.
        """
        grade_id = (await db.execute(select(Grade.id).where(Grade.level == 6))).scalar_one()
        return {objective["canonical_code"]: grade_id for objective in payload}

    async def test_import_objectives_when_topic_resolves_then_creates_objective(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        payload = [self._objective_payload(topic.canonical_code, code)]

        result = await import_objectives(db_session, payload, await self._grade_map(db_session, payload), False)
        await db_session.commit()

        assert result == {"created": 1, "already_present": 0}
        row = await db_session.execute(select(LearningObjective).where(LearningObjective.canonical_code == code))
        objective = row.scalar_one()
        # Keyed on the topic's canonical_code, never a UUID from the source environment.
        assert objective.topic_id == topic.id
        assert objective.embedding is not None

    async def test_import_objectives_when_run_twice_then_second_creates_nothing(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree(db_session)
        payload = [self._objective_payload(topic.canonical_code, f"LO-{uuid.uuid4().hex[:10]}")]
        grades = await self._grade_map(db_session, payload)

        await import_objectives(db_session, payload, grades, False)
        await db_session.commit()
        second = await import_objectives(db_session, payload, grades, False)
        await db_session.commit()

        assert second == {"created": 0, "already_present": 1}

    async def test_import_objectives_when_topic_missing_then_aborts(self, db_session: AsyncSession) -> None:
        """A missing topic means the curriculum seed did not complete. Continuing would
        produce a partial curriculum that still reported success."""
        await self._tree(db_session)
        payload = [self._objective_payload("TOPIC-DOES-NOT-EXIST", f"LO-{uuid.uuid4().hex[:10]}")]

        with pytest.raises(ImportError_, match="not found"):
            await import_objectives(db_session, payload, await self._grade_map(db_session, payload), False)
        await db_session.rollback()

    async def test_import_objectives_when_dry_run_then_writes_nothing(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        payload = [self._objective_payload(topic.canonical_code, code)]

        result = await import_objectives(db_session, payload, await self._grade_map(db_session, payload), True)
        await db_session.rollback()

        assert result["created"] == 1
        row = await db_session.execute(select(LearningObjective).where(LearningObjective.canonical_code == code))
        assert row.scalar_one_or_none() is None

    async def test_import_placements_when_both_resolve_then_links_them(self, db_session: AsyncSession) -> None:
        topic, subtopic = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        payload = [self._objective_payload(topic.canonical_code, code)]
        await import_objectives(db_session, payload, await self._grade_map(db_session, payload), False)
        await db_session.flush()

        # canonical_code is nullable on the model but always set by the seeder, and the
        # artifact join key depends on it — production has 984/984 populated.
        assert subtopic.canonical_code is not None
        result = await import_placements(
            db_session, [{"subtopic_code": subtopic.canonical_code, "objective_code": code}], False
        )
        await db_session.commit()

        assert result == {"linked": 1, "skipped": 0}
        rows = await db_session.execute(select(SubtopicObjective).where(SubtopicObjective.subtopic_id == subtopic.id))
        assert len(rows.scalars().all()) == 1

    async def test_import_placements_when_subtopic_absent_then_skipped_not_failed(
        self, db_session: AsyncSession
    ) -> None:
        """A target environment may simply lack a subtopic the source had. That is
        reported, not fatal — the rest of the artifact still applies."""
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        payload = [self._objective_payload(topic.canonical_code, code)]
        await import_objectives(db_session, payload, await self._grade_map(db_session, payload), False)
        await db_session.flush()

        result = await import_placements(db_session, [{"subtopic_code": "ST-NOT-HERE", "objective_code": code}], False)

        assert result == {"linked": 0, "skipped": 1}

    async def test_apply_question_mapping_binds_local_questions_via_local_snapshot(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Question UUIDs come from THIS environment's snapshot, never from the
        artifact — which is what lets the artifact apply where question rows differ."""
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        payload = [self._objective_payload(topic.canonical_code, code)]
        await import_objectives(db_session, payload, await self._grade_map(db_session, payload), False)
        await db_session.flush()

        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=None,
            learning_objective_id=None,
            question_text="Q?",
            question_type="MCQ",
            options=[{"key": "A", "text": "1"}],
            correct_answer="A",
            canonical_form=f"q-{uuid.uuid4().hex[:10]}",
            problem_signature={},
            difficulty_level=1.0,
            source="bank",
            is_active=True,
        )
        db_session.add(question)
        await db_session.flush()

        snapshot = tmp_path / "snap.json"
        snapshot.write_text(json.dumps([{"question_id": str(question.id), "canonical_code": "OLD-1"}]))

        result = await apply_question_mapping(
            db_session,
            [{"old_subtopic_code": "OLD-1", "objective_code": code, "question_count": 1}],
            snapshot,
            False,
        )
        await db_session.commit()

        assert result["questions_bound"] == 1
        assert result["groups_absent_from_artifact"] == 0
        await db_session.refresh(question)
        assert question.learning_objective_id is not None

    async def test_apply_question_mapping_when_group_absent_from_artifact_then_reported(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """This environment had an old subtopic the artifact never saw. Silence here
        would look identical to a complete application."""
        snapshot = tmp_path / "snap.json"
        snapshot.write_text(json.dumps([{"question_id": str(uuid.uuid4()), "canonical_code": "UNKNOWN-1"}]))

        result = await apply_question_mapping(db_session, [], snapshot, True)

        assert result["groups_absent_from_artifact"] == 1
        assert result["questions_bound"] == 0

    async def test_apply_question_mapping_when_decision_was_null_then_left_unresolved(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """A null objective_code means the source environment deliberately left it for
        review. The target must report the same gap, not invent a binding."""
        snapshot = tmp_path / "snap.json"
        snapshot.write_text(json.dumps([{"question_id": str(uuid.uuid4()), "canonical_code": "OLD-2"}]))

        result = await apply_question_mapping(
            db_session,
            [{"old_subtopic_code": "OLD-2", "objective_code": None, "question_count": 1}],
            snapshot,
            True,
        )

        assert result["unresolved_groups"] == 1
        assert result["questions_bound"] == 0

    async def test_already_applied_when_recorded_then_returns_the_prior_run(self, db_session: AsyncSession) -> None:
        """Alembic tracks schema migrations; this is the equivalent for curriculum
        artifacts, so a second apply cannot happen unnoticed."""
        name = f"artifact_{uuid.uuid4().hex[:8]}.json"
        assert await already_applied(db_session, name) is None

        await db_session.execute(
            text(
                """
                INSERT INTO curriculum_migrations (
                    id, artifact_name, artifact_version, scope, objectives_created,
                    placements_linked, questions_bound, groups_unresolved, applied_at
                ) VALUES (gen_random_uuid(), :n, 1, '{}'::jsonb, 5, 6, 7, 8, now())
                """
            ),
            {"n": name},
        )
        await db_session.commit()

        prior = await already_applied(db_session, name)
        assert prior is not None
        assert prior["objectives_created"] == 5
        assert prior["questions_bound"] == 7


@pytest.mark.asyncio
class TestArtifactGrades:
    """Grade resolution across artifact versions (ADR-003 T4).

    T4 makes learning_objectives.grade_id NOT NULL. The importer's INSERT omitted it, so
    T4 would have broken every future artifact import — and production has a
    curriculum_migrations row, so that path is live, not hypothetical.

    v2 carries the grade as a LEVEL, never a UUID, because grades.id differs per
    environment while grades.level is a stable natural key. v1 predates ADR-003 and
    carries no grade at all; it is recovered from the artifact's own placements, but only
    where that derivation is unambiguous.
    """

    async def _tree_at(self, db: AsyncSession, levels: list[int]) -> tuple[Topic, dict[int, str]]:
        """One topic placed at each given grade, keyed to that grade's subtopic CODE.

        Codes rather than Subtopic rows: the artifact joins on canonical_code and never
        on a UUID, so the code is the only field these tests need — and returning it as
        str keeps the model's nullable column out of every call site.
        """
        curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
        subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"X{uuid.uuid4().hex[:5]}")
        topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"TOPIC-{uuid.uuid4().hex[:8]}")
        db.add_all([curriculum, subject, topic])
        await db.flush()

        subtopic_codes: dict[int, str] = {}
        for level in levels:
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
            code = f"ST-{uuid.uuid4().hex[:8]}"
            db.add(
                Subtopic(
                    id=uuid.uuid4(),
                    curriculum_topic_id=ct.id,
                    name=f"Sub G{level}",
                    canonical_code=code,
                    learning_objective="Do the thing.",
                    is_active=True,
                )
            )
            await db.flush()
            subtopic_codes[level] = code

        await db.commit()
        return topic, subtopic_codes

    @staticmethod
    def _artifact(
        version: int,
        topic_code: str,
        code: str,
        placements: list[dict[str, str]],
        grade_level: int | None = None,
    ) -> dict:
        objective: dict = {
            "canonical_code": code,
            "name": "Imported objective",
            "learning_objective": "Order  NEGATIVE integers, on a number line!",
            "bloom_taxonomy_level": "Apply",
            "embedding": None,
            "topic_code": topic_code,
        }
        if version >= 2:
            objective["grade_level"] = grade_level
            objective["normalised_objective"] = normalise_text(objective["learning_objective"])
        return {
            "artifact_version": version,
            "scope": {"curriculum": "c", "subjects": ["X"], "grades": [6, 7]},
            "learning_objectives": [objective],
            "placements": placements,
            "question_mapping": [],
        }

    async def test_resolve_grades_when_v2_then_maps_level_to_local_grade_id(self, db_session: AsyncSession) -> None:
        """v2 states the grade; the importer resolves the LEVEL against local grades."""
        topic, subtopic_codes = await self._tree_at(db_session, [6, 7])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(2, topic.canonical_code, code, placements=[], grade_level=7)

        resolved = await resolve_grades(db_session, artifact)

        expected = (await db_session.execute(select(Grade.id).where(Grade.level == 7))).scalar_one()
        assert resolved == {code: expected}
        assert subtopic_codes[7]  # placements existed but were not needed

    async def test_resolve_grades_when_v2_level_absent_locally_then_aborts(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree_at(db_session, [6])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(2, topic.canonical_code, code, placements=[], grade_level=11)

        with pytest.raises(ImportError_, match="grade level 11"):
            await resolve_grades(db_session, artifact)

    async def test_resolve_grades_when_v1_single_placement_then_derives_grade(self, db_session: AsyncSession) -> None:
        """v1 carries no grade, so it is recovered the same way T1's backfill does."""
        topic, subtopic_codes = await self._tree_at(db_session, [6, 7])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(
            1,
            topic.canonical_code,
            code,
            placements=[{"subtopic_code": subtopic_codes[7], "objective_code": code}],
        )

        resolved = await resolve_grades(db_session, artifact)

        expected = (await db_session.execute(select(Grade.id).where(Grade.level == 7))).scalar_one()
        assert resolved == {code: expected}

    async def test_resolve_grades_when_v1_spans_grades_then_aborts_rather_than_guessing(
        self, db_session: AsyncSession
    ) -> None:
        """The decision this refuses to make is exactly what T3's review queue exists for.

        Picking a grade here would repeat that decision in a second place, with no
        reviewer and no record — the failure ADR-003 was written to prevent.
        """
        topic, subtopic_codes = await self._tree_at(db_session, [6, 7])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(
            1,
            topic.canonical_code,
            code,
            placements=[
                {"subtopic_code": subtopic_codes[6], "objective_code": code},
                {"subtopic_code": subtopic_codes[7], "objective_code": code},
            ],
        )

        with pytest.raises(ImportError_, match="grade-spanning"):
            await resolve_grades(db_session, artifact)

    async def test_resolve_grades_when_v1_objective_unplaced_then_aborts(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree_at(db_session, [6])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(1, topic.canonical_code, code, placements=[])

        with pytest.raises(ImportError_, match="unplaced"):
            await resolve_grades(db_session, artifact)

    async def test_import_objectives_when_applied_then_normalised_objective_matches_helper(
        self, db_session: AsyncSession
    ) -> None:
        """Recomputed, never trusted from the artifact.

        A v1 artifact has no normalised_objective at all, and T4's UNIQUE constrains on
        it. Computing it with the same helper the de-duplicator uses is what stops the
        stored key from disagreeing with what the de-duplicator calls a duplicate.
        """
        topic, subtopic_codes = await self._tree_at(db_session, [6])
        code = f"LO-{uuid.uuid4().hex[:10]}"
        artifact = self._artifact(
            1,
            topic.canonical_code,
            code,
            placements=[{"subtopic_code": subtopic_codes[6], "objective_code": code}],
        )

        grades = await resolve_grades(db_session, artifact)
        await import_objectives(db_session, artifact["learning_objectives"], grades, False)
        await db_session.commit()

        stored = (
            await db_session.execute(select(LearningObjective).where(LearningObjective.canonical_code == code))
        ).scalar_one()
        assert stored.normalised_objective == normalise_text("Order  NEGATIVE integers, on a number line!")
        assert stored.normalised_objective == "order negative integers on a number line"
        assert stored.grade_id is not None
