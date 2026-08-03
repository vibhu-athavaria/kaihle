"""Unit tests for the canonical question-selection path.

The properties that matter here are structural: selection must never key on
question_bank.subtopic_id, and a Core student must never be able to reach
EXTENDED-only material.
"""

import uuid

from sqlalchemy import select

from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, SubtopicObjective
from app.services.question_selection import (
    TIER_VISIBILITY,
    active_scope_filters,
    join_questions_via_objectives,
    tier_filter,
)


class TestJoinQuestionsViaObjectives:
    def test_join_when_applied_then_routes_through_the_objective_bridge(self) -> None:
        stmt = join_questions_via_objectives(select(QuestionBank.id).select_from(CurriculumTopic))
        sql = str(stmt)

        assert "subtopic_objectives" in sql
        assert "learning_objective_id" in sql

    def test_join_when_applied_then_never_keys_on_question_subtopic_id(self) -> None:
        """question_bank.subtopic_id is legacy/audit only. Selecting on it silently
        returns nothing for any remapped scope."""
        stmt = join_questions_via_objectives(select(QuestionBank.id).select_from(CurriculumTopic))
        sql = str(stmt)

        assert "question_bank.subtopic_id" not in sql

    def test_join_when_applied_then_reaches_all_four_tables(self) -> None:
        stmt = join_questions_via_objectives(select(QuestionBank.id).select_from(CurriculumTopic))
        sql = str(stmt)

        for table in ("curriculum_topics", "subtopics", "subtopic_objectives", "question_bank"):
            assert table in sql


class TestTierVisibility:
    def test_core_students_cannot_see_extended_only_material(self) -> None:
        assert "EXTENDED" not in TIER_VISIBILITY["CORE"]

    def test_extended_students_see_core_material_too(self) -> None:
        # Extended is a superset of Core, not a disjoint alternative.
        assert set(TIER_VISIBILITY["CORE"]).issubset(set(TIER_VISIBILITY["EXTENDED"]))

    def test_both_is_visible_to_every_tier(self) -> None:
        assert all("BOTH" in visible for visible in TIER_VISIBILITY.values())

    def test_tier_filter_when_core_then_excludes_extended(self) -> None:
        sql = str(tier_filter("CORE").compile(compile_kwargs={"literal_binds": True}))
        assert "EXTENDED" not in sql
        assert "CORE" in sql and "BOTH" in sql

    def test_tier_filter_when_extended_then_includes_all_tiers(self) -> None:
        sql = str(tier_filter("EXTENDED").compile(compile_kwargs={"literal_binds": True}))
        assert "CORE" in sql and "EXTENDED" in sql and "BOTH" in sql

    def test_tier_filter_when_none_then_excludes_nothing(self) -> None:
        """Below IGCSE there is no tiering, so no subtopic may be filtered out."""
        sql = str(tier_filter(None).compile(compile_kwargs={"literal_binds": True}))
        assert "CORE" in sql and "EXTENDED" in sql and "BOTH" in sql

    def test_tier_filter_when_applied_then_targets_subtopics_not_the_bridge(self) -> None:
        # Tier lives only on subtopics — never on subtopic_objectives or the objective.
        sql = str(tier_filter("CORE"))
        assert "subtopics.tier" in sql


class TestActiveScopeFilters:
    def test_filters_when_built_then_restrict_to_scope_and_active_rows(self) -> None:
        filters = active_scope_filters(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        rendered = " ".join(str(f) for f in filters)

        assert "curriculum_topics.curriculum_id" in rendered
        assert "curriculum_topics.subject_id" in rendered
        assert "curriculum_topics.grade_id" in rendered
        # Inactive curriculum rows or retired questions must never enter a pool.
        assert "curriculum_topics.is_active" in rendered
        assert "subtopics.is_active" in rendered
        assert "question_bank.is_active" in rendered

    def test_filters_when_built_then_usable_in_a_statement(self) -> None:
        stmt = join_questions_via_objectives(select(QuestionBank.id).select_from(CurriculumTopic)).where(
            *active_scope_filters(uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
            tier_filter("CORE"),
        )
        assert "WHERE" in str(stmt)


class TestModelWiring:
    def test_bridge_links_subtopic_to_objective(self) -> None:
        assert SubtopicObjective.__tablename__ == "subtopic_objectives"

    def test_subtopic_carries_the_tier_column(self) -> None:
        assert "tier" in Subtopic.__table__.c
