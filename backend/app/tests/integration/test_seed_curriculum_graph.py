"""Integration tests for curriculum graph seeding script.

Tests cover all acceptance criteria from M1-2-T1:
- Valid JSON seeds all tables with correct FK links
- Idempotency (no duplicates on re-run)
- Curriculum-subject binding rules (SCI not under igcse, etc.)
- Topic deduplication across grades
- Prerequisite resolution
- Unknown prerequisite canonical_code handling (warning, not crash)
- Subtopic learning_objective is non-null
- Subtopic embedding is NULL (populated later by M1-2-T2)
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    SubtopicPrerequisite,
    Topic,
)
from scripts.seed_curriculum_graph import CurriculumSeeder, Stats

# ---------------------------------------------------------------------------
# Minimal test JSON fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID_JSON: dict[str, Any] = {
    "_meta": {"version": "test", "format_note": "grade_level is singular int"},
    "curricula": [
        {"code": "test_curr", "name": "Test Curriculum", "description": "Test", "is_active": True}
    ],
    "subjects": [
        {"code": "MATH", "name": "Mathematics", "icon": "calculator", "color": "#0D9488"},
        {"code": "SCI", "name": "Science", "icon": "flask", "color": "#16a34a"},
    ],
    "grades": [
        {"level": 6, "name": "Grade 6"},
        {"level": 7, "name": "Grade 7"},
    ],
    "curriculum_subjects": [
        {"curriculum_code": "test_curr", "subject_code": "MATH", "is_core": True, "sort_order": 1},
        {"curriculum_code": "test_curr", "subject_code": "SCI", "is_core": True, "sort_order": 2},
    ],
    "curriculum_tree": [
        {
            "curriculum_code": "test_curr",
            "subject_code": "MATH",
            "grade_level": 6,
            "standard_code_prefix": "6M",
            "topics": [
                {
                    "name": "Number",
                    "canonical_code": "MATH-NUM",
                    "sequence_order": 1,
                    "recommended_weeks": 7,
                    "learning_objectives": ["Understand numbers", "Apply operations"],
                    "subtopics": [
                        {
                            "name": "Integers",
                            "canonical_code": "MATH-NUM-G6-01",
                            "learning_objective": "Understand the value of each digit in integers",
                            "bloom_taxonomy_level": "Understand",
                            "difficulty_level": 1,
                            "estimated_minutes": 50,
                            "sequence_order": 1,
                            "prerequisites": [],
                        },
                        {
                            "name": "Addition",
                            "canonical_code": "MATH-NUM-G6-02",
                            "learning_objective": "Add integers correctly",
                            "bloom_taxonomy_level": "Apply",
                            "difficulty_level": 2,
                            "estimated_minutes": 45,
                            "sequence_order": 2,
                            "prerequisites": ["Integers"],
                        },
                    ],
                }
            ],
        },
        {
            "curriculum_code": "test_curr",
            "subject_code": "MATH",
            "grade_level": 7,
            "standard_code_prefix": "7M",
            "topics": [
                {
                    "name": "Number",
                    "canonical_code": "MATH-NUM",
                    "sequence_order": 1,
                    "recommended_weeks": 8,
                    "learning_objectives": ["Extend number understanding"],
                    "subtopics": [
                        {
                            "name": "Fractions",
                            "canonical_code": "MATH-NUM-G7-01",
                            "learning_objective": "Work with fractions",
                            "bloom_taxonomy_level": "Apply",
                            "difficulty_level": 2,
                            "estimated_minutes": 60,
                            "sequence_order": 1,
                            "prerequisites": [],
                        },
                    ],
                }
            ],
        },
    ],
}

# JSON with an unknown prerequisite to test warning handling
JSON_WITH_UNKNOWN_PREREQ: dict[str, Any] = {
    "_meta": {"version": "test"},
    "curricula": [
        {"code": "test_curr", "name": "Test Curriculum", "is_active": True}
    ],
    "subjects": [
        {"code": "MATH", "name": "Mathematics"}
    ],
    "grades": [
        {"level": 6, "name": "Grade 6"}
    ],
    "curriculum_subjects": [
        {"curriculum_code": "test_curr", "subject_code": "MATH", "is_core": True, "sort_order": 1}
    ],
    "curriculum_tree": [
        {
            "curriculum_code": "test_curr",
            "subject_code": "MATH",
            "grade_level": 6,
            "topics": [
                {
                    "name": "Number",
                    "canonical_code": "MATH-NUM",
                    "sequence_order": 1,
                    "recommended_weeks": 5,
                    "learning_objectives": ["Learn numbers"],
                    "subtopics": [
                        {
                            "name": "Basic",
                            "canonical_code": "MATH-NUM-G6-01",
                            "learning_objective": "Learn basic numbers",
                            "bloom_taxonomy_level": "Remember",
                            "difficulty_level": 1,
                            "estimated_minutes": 30,
                            "sequence_order": 1,
                            "prerequisites": ["NonExistentSubtopic"],
                        },
                    ],
                }
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Helper: run the seeder with given JSON data
# ---------------------------------------------------------------------------

async def run_seeder(db: AsyncSession, data: dict[str, Any]) -> Stats:
    """Run the CurriculumSeeder with the given data dict. Returns Stats object."""
    stats = Stats()
    seeder = CurriculumSeeder(db=db, stats=stats, dry_run=False)
    await seeder.seed(data)
    await db.commit()
    return stats


# ---------------------------------------------------------------------------
# Acceptance Criterion 1: Valid JSON -> all tables populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_when_valid_json_then_all_tables_populated(db_session: AsyncSession) -> None:
    """Use minimal JSON: 1 curriculum, 2 subjects, 2 grades, 2 topics, 4 subtopics.
    After seed: all rows exist in correct tables with correct FK links.
    """
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    # Verify curricula
    result = await db_session.execute(select(Curriculum))
    curricula = list(result.scalars().all())
    assert len(curricula) == 1
    assert curricula[0].code == "test_curr"

    # Verify subjects
    result = await db_session.execute(select(Subject))
    subjects = list(result.scalars().all())
    assert len(subjects) == 2
    subject_codes = {s.code for s in subjects}
    assert subject_codes == {"MATH", "SCI"}

    # Verify grades
    result = await db_session.execute(select(Grade))
    grades = list(result.scalars().all())
    assert len(grades) == 2
    grade_levels = {g.level for g in grades}
    assert grade_levels == {6, 7}

    # Verify curriculum_subjects
    result = await db_session.execute(select(CurriculumSubject))
    cs_rows = list(result.scalars().all())
    assert len(cs_rows) == 2

    # Verify topics - MATH-NUM appears in both grades but should be deduplicated
    result = await db_session.execute(select(Topic))
    topics = list(result.scalars().all())
    assert len(topics) == 1
    assert topics[0].canonical_code == "MATH-NUM"

    # Verify curriculum_topics - one per (curriculum, subject, grade, topic) combo
    result = await db_session.execute(select(CurriculumTopic))
    ct_rows = list(result.scalars().all())
    assert len(ct_rows) == 2  # G6 and G7

    # Verify subtopics - 2 in G6 + 1 in G7 = 3
    result = await db_session.execute(select(Subtopic))
    subtopics = list(result.scalars().all())
    assert len(subtopics) == 3

    # Verify FK links are correct
    for st in subtopics:
        assert st.curriculum_topic_id is not None
        result_ct = await db_session.execute(
            select(CurriculumTopic).where(CurriculumTopic.id == st.curriculum_topic_id)
        )
        ct = result_ct.scalar_one_or_none()
        assert ct is not None, f"Subtopic {st.canonical_code} has invalid curriculum_topic_id"


# ---------------------------------------------------------------------------
# Acceptance Criterion 2: Idempotency - run twice, no duplicates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_when_run_twice_then_no_duplicates(db_session: AsyncSession) -> None:
    """Run seed twice -> row counts identical after second run."""
    # First run
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    # Count rows after first run
    result = await db_session.execute(select(Curriculum))
    count_curricula_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(Subject))
    count_subjects_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(Grade))
    count_grades_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(CurriculumSubject))
    count_cs_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(Topic))
    count_topics_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(CurriculumTopic))
    count_ct_1 = len(list(result.scalars().all()))
    result = await db_session.execute(select(Subtopic))
    count_subtopics_1 = len(list(result.scalars().all()))

    # Second run - should not create duplicates
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    # Count rows after second run - must be identical
    result = await db_session.execute(select(Curriculum))
    assert len(list(result.scalars().all())) == count_curricula_1
    result = await db_session.execute(select(Subject))
    assert len(list(result.scalars().all())) == count_subjects_1
    result = await db_session.execute(select(Grade))
    assert len(list(result.scalars().all())) == count_grades_1
    result = await db_session.execute(select(CurriculumSubject))
    assert len(list(result.scalars().all())) == count_cs_1
    result = await db_session.execute(select(Topic))
    assert len(list(result.scalars().all())) == count_topics_1
    result = await db_session.execute(select(CurriculumTopic))
    assert len(list(result.scalars().all())) == count_ct_1
    result = await db_session.execute(select(Subtopic))
    assert len(list(result.scalars().all())) == count_subtopics_1


# ---------------------------------------------------------------------------
# Acceptance Criterion 3: Curriculum-subject binding rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_curriculum_subjects_binding_respected(db_session: AsyncSession) -> None:
    """After seeding cambridge_v1.json: SCI does NOT appear under igcse.
    BIO, CHEM, PHY, ENGL do NOT appear under cambridge_lower.
    """
    # Load the actual cambridge_v1.json
    data_file = Path(__file__).resolve().parent.parent.parent / "data" / "curriculum" / "cambridge_v1.json"
    if not data_file.exists():
        pytest.skip("cambridge_v1.json not found")

    with data_file.open() as f:
        data: dict[str, Any] = json.load(f)

    await run_seeder(db_session, data)

    # Verify SCI is NOT linked to igcse
    result = await db_session.execute(
        select(CurriculumSubject)
        .join(Curriculum, CurriculumSubject.curriculum_id == Curriculum.id)
        .join(Subject, CurriculumSubject.subject_id == Subject.id)
        .where(Curriculum.code == "igcse", Subject.code == "SCI")
    )
    sci_igcse = list(result.scalars().all())
    assert len(sci_igcse) == 0, "SCI must NOT appear under igcse"

    # Verify BIO, CHEM, PHY, ENGL are NOT linked to cambridge_lower
    result = await db_session.execute(
        select(CurriculumSubject)
        .join(Curriculum, CurriculumSubject.curriculum_id == Curriculum.id)
        .join(Subject, CurriculumSubject.subject_id == Subject.id)
        .where(Curriculum.code == "cambridge_lower", Subject.code.in_(["BIO", "CHEM", "PHY", "ENGL"]))
    )
    lower_science = list(result.scalars().all())
    assert len(lower_science) == 0, "BIO, CHEM, PHY, ENGL must NOT appear under cambridge_lower"


# ---------------------------------------------------------------------------
# Acceptance Criterion 4: Topics are deduplicated across grades
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_topics_are_deduplicated_across_grades(db_session: AsyncSession) -> None:
    """MATH-NUM appears in multiple grades -> only ONE row in topics table.
    Multiple rows in curriculum_topics (one per grade/curriculum combo).
    """
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    # MATH-NUM should appear exactly once in topics table
    result = await db_session.execute(select(Topic).where(Topic.canonical_code == "MATH-NUM"))
    topic_rows = list(result.scalars().all())
    assert len(topic_rows) == 1, "MATH-NUM should be deduplicated to ONE topic row"

    # But curriculum_topics should have 2 rows (G6 and G7)
    topic_id = topic_rows[0].id
    result = await db_session.execute(select(CurriculumTopic).where(CurriculumTopic.topic_id == topic_id))
    ct_rows = list(result.scalars().all())
    assert len(ct_rows) == 2, "MATH-NUM should have 2 curriculum_topic rows (one per grade)"


# ---------------------------------------------------------------------------
# Acceptance Criterion 5: Prerequisites resolved correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prerequisites_when_subtopic_b_requires_a_then_row_exists(db_session: AsyncSession) -> None:
    """After seed: subtopic_prerequisites row exists for a known prerequisite pair.
    In MINIMAL_VALID_JSON, "Addition" has prerequisite "Integers".
    """
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    # Find the subtopics
    result = await db_session.execute(
        select(Subtopic).where(Subtopic.canonical_code == "MATH-NUM-G6-02")
    )
    addition = result.scalar_one_or_none()
    assert addition is not None, "Addition subtopic should exist"

    result = await db_session.execute(
        select(Subtopic).where(Subtopic.canonical_code == "MATH-NUM-G6-01")
    )
    integers = result.scalar_one_or_none()
    assert integers is not None, "Integers subtopic should exist"

    # Verify prerequisite row exists
    result = await db_session.execute(
        select(SubtopicPrerequisite).where(
            SubtopicPrerequisite.subtopic_id == addition.id,
            SubtopicPrerequisite.prerequisite_subtopic_id == integers.id,
        )
    )
    prereq = result.scalar_one_or_none()
    assert prereq is not None, "Prerequisite row should exist: Addition requires Integers"


# ---------------------------------------------------------------------------
# Acceptance Criterion 6: Unknown prerequisite -> warning logged, not crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prerequisites_when_unknown_canonical_code_then_warning_logged_not_crash(
    db_session: AsyncSession,
) -> None:
    """When a prerequisite references a non-existent subtopic name,
    the seeder logs a warning and continues - does not crash.
    """
    stats = await run_seeder(db_session, JSON_WITH_UNKNOWN_PREREQ)

    # Should have at least one warning about unresolved prerequisite
    assert len(stats.warnings) > 0, "Should have warnings for unknown prerequisite"
    assert any("NonExistentSubtopic" in w for w in stats.warnings), (
        "Warning should mention the unknown prerequisite name"
    )

    # Subtopic should still be created
    result = await db_session.execute(
        select(Subtopic).where(Subtopic.canonical_code == "MATH-NUM-G6-01")
    )
    subtopic = result.scalar_one_or_none()
    assert subtopic is not None, "Subtopic should be created even with unresolvable prerequisite"

    # No prerequisite row should be created for the unknown reference
    result = await db_session.execute(
        select(SubtopicPrerequisite).where(SubtopicPrerequisite.subtopic_id == subtopic.id)
    )
    prereqs = list(result.scalars().all())
    assert len(prereqs) == 0, "No prerequisite row should exist for unknown reference"


# ---------------------------------------------------------------------------
# Acceptance Criterion 7: Subtopic learning_objective is non-null
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subtopics_learning_objective_is_non_null(db_session: AsyncSession) -> None:
    """Every seeded subtopic has a non-null learning_objective."""
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    result = await db_session.execute(select(Subtopic))
    subtopics = list(result.scalars().all())
    assert len(subtopics) > 0, "Should have at least one subtopic"

    for st in subtopics:
        assert st.learning_objective is not None, (
            f"Subtopic {st.canonical_code} has null learning_objective"
        )
        assert len(st.learning_objective.strip()) > 0, (
            f"Subtopic {st.canonical_code} has empty learning_objective"
        )


# ---------------------------------------------------------------------------
# Acceptance Criterion 8: Subtopic embedding is NULL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subtopics_embedding_is_null(db_session: AsyncSession) -> None:
    """Every seeded subtopic has embedding = NULL (populated in M1-2-T2)."""
    await run_seeder(db_session, MINIMAL_VALID_JSON)

    result = await db_session.execute(select(Subtopic))
    subtopics = list(result.scalars().all())
    assert len(subtopics) > 0, "Should have at least one subtopic"

    for st in subtopics:
        assert st.embedding is None, (
            f"Subtopic {st.canonical_code} should have NULL embedding, got {st.embedding}"
        )
