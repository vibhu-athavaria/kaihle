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
    already_applied,
    apply_question_mapping,
    import_objectives,
    import_placements,
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
        }

    async def test_import_objectives_when_topic_resolves_then_creates_objective(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"

        result = await import_objectives(db_session, [self._objective_payload(topic.canonical_code, code)], False)
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

        await import_objectives(db_session, payload, False)
        await db_session.commit()
        second = await import_objectives(db_session, payload, False)
        await db_session.commit()

        assert second == {"created": 0, "already_present": 1}

    async def test_import_objectives_when_topic_missing_then_aborts(self, db_session: AsyncSession) -> None:
        """A missing topic means the curriculum seed did not complete. Continuing would
        produce a partial curriculum that still reported success."""
        from scripts.import_remap_artifact import ImportError_

        payload = [self._objective_payload("TOPIC-DOES-NOT-EXIST", f"LO-{uuid.uuid4().hex[:10]}")]

        with pytest.raises(ImportError_, match="not found"):
            await import_objectives(db_session, payload, False)
        await db_session.rollback()

    async def test_import_objectives_when_dry_run_then_writes_nothing(self, db_session: AsyncSession) -> None:
        topic, _ = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"

        result = await import_objectives(db_session, [self._objective_payload(topic.canonical_code, code)], True)
        await db_session.rollback()

        assert result["created"] == 1
        row = await db_session.execute(select(LearningObjective).where(LearningObjective.canonical_code == code))
        assert row.scalar_one_or_none() is None

    async def test_import_placements_when_both_resolve_then_links_them(self, db_session: AsyncSession) -> None:
        topic, subtopic = await self._tree(db_session)
        code = f"LO-{uuid.uuid4().hex[:10]}"
        await import_objectives(db_session, [self._objective_payload(topic.canonical_code, code)], False)
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
        await import_objectives(db_session, [self._objective_payload(topic.canonical_code, code)], False)
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
        await import_objectives(db_session, [self._objective_payload(topic.canonical_code, code)], False)
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
