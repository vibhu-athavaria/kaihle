# M2-1-T1 — Gap Map Aggregation Service
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T1
**Depends on:** M1-4-T3 (gap_states populated with real data), M0-2-T2 (ORM models), M0-10-T1 (schemas/gap_map.py defined)
**Blocks:** M2-1-T2 (routes call this service)
**Estimated effort:** 4–5 hours

---

## Context

This task builds the service layer that reads from `gap_states` and produces the
structured gap map views consumed by teachers and students. The Pydantic schemas for
these views — `ClassGapMap`, `StudentGapMap`, `ClassSummary`, `GapMapNode`,
`StudentGapScore`, `StudentSubtopicScore` — already exist in
`backend/app/schemas/gap_map.py` from M0-10-T1. Import them. Do not redefine them
here.

The `GapService` class was partially introduced in M1-4-T3 (it has a
`upsert_gap_state` method). This task extends that same class — it does not create a
new service file. Add the three aggregation methods below to the existing
`GapService` class in `backend/app/services/gap_service.py`.

Read CONSTITUTION.md Rule 3 before writing any query — every query in this service
must include `school_id` in its WHERE clause. A teacher from school A must never see
gap state data belonging to school B, even if they somehow obtain a valid `class_id`
from school B.

Performance is a hard requirement, not a stretch goal. The class gap map for 40
students × 50 subtopics must complete in under 500ms. This means a single SQL query
with joins — not Python loops calling the database per student or per subtopic. The
DB indexes `idx_gap_states_class` and `idx_gap_states_student` in
`kaihle_v2_1_schema.sql` exist precisely for this query pattern.

---

## User Story

As the system, I want to aggregate gap state data into structured class-level and
student-level views so teachers and students can see exactly where learning gaps exist.

---

## Files to Modify / Create

```
backend/app/services/gap_service.py        ← MODIFY: add three methods to existing class
backend/app/tests/unit/test_gap_service.py ← CREATE
backend/app/tests/integration/test_gap_map_service_integration.py ← CREATE
```

Do not create a new `gap_service.py` — extend the class that M1-4-T3 created.

---

## Imports at Top of `gap_service.py`

Add these imports if not already present:

```python
from app.schemas.gap_map import (
    ClassGapMap,
    ClassSummary,
    GapMapNode,
    StudentGapMap,
    StudentGapScore,
    StudentSubtopicScore,
)
```

---

## Method 1: `get_class_gap_map`

Full signature:

```python
async def get_class_gap_map(
    self,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> ClassGapMap:
    """Aggregate gap_states for all enrolled students in a class, grouped by subtopic.

    Returns one GapMapNode per subtopic that belongs to the given subject and grade.
    Subtopics with no gap_state rows are still included — their student_scores list
    will be empty and class_average will be None. This tells the teacher that a
    subtopic has not yet been assessed, which is different from all students having
    low mastery.

    Args:
        class_id: The class to aggregate for. Must belong to school_id.
        school_id: Used in every WHERE clause — CONSTITUTION Rule 3.
        subject_id: The subject to filter subtopics to (e.g. Mathematics UUID).
    """
```

The implementation must use a single SQL query. Do not loop in Python over students
or subtopics. The query structure is:

```python
from sqlalchemy import select, func, case
from app.models import (
    Subtopic, CurriculumTopic, Topic, GapState, User, Class
)

# Step 1: Verify the class exists and belongs to the school
class_ = await self.db.scalar(
    select(Class).where(
        Class.id == class_id,
        Class.school_id == school_id,
        Class.is_active.is_(True),
    )
)
if not class_:
    raise ValueError(f"Class {class_id} not found in school {school_id}")

# Step 2: Load all subtopics for this subject + grade in one query
subtopics_query = (
    select(
        Subtopic.id.label("subtopic_id"),
        Subtopic.name.label("subtopic_name"),
        Topic.id.label("topic_id"),
        Topic.name.label("topic_name"),
    )
    .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
    .join(Topic, Topic.id == CurriculumTopic.topic_id)
    .where(
        CurriculumTopic.subject_id == subject_id,
        CurriculumTopic.grade_id == class_.grade_id,
    )
    .order_by(Topic.name, Subtopic.name)
)
subtopic_rows = (await self.db.execute(subtopics_query)).all()

# Step 3: Load all gap_states for this class in one query
gap_query = (
    select(
        GapState.subtopic_id,
        GapState.student_id,
        GapState.mastery_score,
        GapState.last_assessed_at,
        User.first_name,
        User.last_name,
    )
    .join(User, User.id == GapState.student_id)
    .where(
        GapState.class_id == class_id,
        GapState.school_id == school_id,
    )
)
gap_rows = (await self.db.execute(gap_query)).all()
```

After loading both result sets in Python, group the gap rows by `subtopic_id` into
a dictionary `{subtopic_id: [gap_row, ...]}`. Then build the `GapMapNode` list by
iterating over `subtopic_rows` and looking up each subtopic's rows in the dict.

```python
# Group gap rows by subtopic
gaps_by_subtopic: dict[uuid.UUID, list] = defaultdict(list)
for row in gap_rows:
    gaps_by_subtopic[row.subtopic_id].append(row)

# Build nodes
nodes = []
for st in subtopic_rows:
    student_gaps = gaps_by_subtopic.get(st.subtopic_id, [])
    student_scores = [
        StudentGapScore(
            student_id=g.student_id,
            student_name=f"{g.first_name} {g.last_name}",
            mastery_score=g.mastery_score,
            last_assessed_at=g.last_assessed_at,
        )
        for g in student_gaps
    ]
    class_average = (
        sum(s.mastery_score for s in student_scores) / len(student_scores)
        if student_scores else None
    )
    nodes.append(GapMapNode(
        subtopic_id=st.subtopic_id,
        subtopic_name=st.subtopic_name,
        topic_id=st.topic_id,
        topic_name=st.topic_name,
        class_average=class_average,
        student_count=len(student_scores),
        student_scores=student_scores,
    ))

return ClassGapMap(
    class_id=class_id,
    subject_id=subject_id,
    generated_at=datetime.now(timezone.utc),
    nodes=nodes,
)
```

---

## Method 2: `get_student_gap_map`

Full signature:

```python
async def get_student_gap_map(
    self,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> StudentGapMap:
    """Return all gap_states for a single student filtered by subject.

    Args:
        student_id: The student to return data for.
        school_id: Multi-tenancy guard — CONSTITUTION Rule 3.
        subject_id: Filter to one subject's subtopics.
    """
```

This method follows the same two-query pattern as `get_class_gap_map` but filters
gap rows to `GapState.student_id == student_id`. It returns a `StudentGapMap` with
one `StudentSubtopicScore` per subtopic. Subtopics with no gap state are included
with `mastery_score=None` and `last_assessed_at=None` — the frontend renders these
as grey "Not assessed" indicators.

---

## Method 3: `get_class_summary`

Full signature:

```python
async def get_class_summary(
    self,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> ClassSummary:
    """Return lightweight mastery summary for a teacher dashboard class card.

    This is a cheaper query than get_class_gap_map — it returns aggregate counts
    only, no per-student breakdown. Used to populate the avg_mastery indicator on
    each class card without loading the full heatmap dataset.

    Args:
        class_id: Must belong to school_id.
        school_id: Multi-tenancy guard — CONSTITUTION Rule 3.
    """
```

The query aggregates across all `gap_states` rows for the class:

```python
result = await self.db.execute(
    select(
        func.avg(GapState.mastery_score).label("avg_mastery"),
        func.count(func.distinct(GapState.student_id)).label("assessed_students"),
        func.max(GapState.last_assessed_at).label("last_updated"),
    )
    .where(
        GapState.class_id == class_id,
        GapState.school_id == school_id,
    )
)
row = result.one()

# Count total enrolled students (not just those with gap states)
total_students = await self.db.scalar(
    select(func.count())
    .select_from(ClassEnrollment)
    .where(
        ClassEnrollment.class_id == class_id,
        ClassEnrollment.is_active.is_(True),
    )
)

return ClassSummary(
    class_id=class_id,
    avg_mastery=float(row.avg_mastery) if row.avg_mastery is not None else None,
    student_count=total_students or 0,
    assessed_student_count=row.assessed_students or 0,
    last_updated_at=row.last_updated,
)
```

---

## Acceptance Criteria

**Unit tests — `test_gap_service.py`**

Each test uses an async DB session with seeded data rather than mocking service
internals. Descriptions below specify what to seed and what to assert.

`test_get_class_gap_map_when_5_students_3_subtopics_then_correct_averages` — Seed
5 students, 3 subtopics, one `gap_state` row per student per subtopic with known
mastery scores. Call `get_class_gap_map`. Assert that each node's `class_average`
matches the arithmetic mean of the seeded scores for that subtopic, and that each
node's `student_scores` list has exactly 5 entries.

`test_get_class_gap_map_when_subtopic_has_no_data_then_included_with_none_average` —
Seed 3 subtopics in the curriculum but only insert `gap_state` rows for 2 of them.
Call `get_class_gap_map`. Assert the response has 3 nodes, and the node for the
unassessed subtopic has `class_average=None` and `student_scores=[]`.

`test_get_class_gap_map_when_wrong_school_id_then_raises_value_error` — Call
`get_class_gap_map` with a `school_id` that does not match the class's `school_id`.
Assert `ValueError` is raised and no gap data is returned.

`test_get_class_gap_map_nodes_ordered_by_topic_then_subtopic` — Seed two topics
("Geometry" and "Algebra") each with two subtopics. Assert nodes are returned in
order: Algebra subtopics first (alphabetically), then Geometry subtopics — matching
the `ORDER BY t.name, st.name` clause.

`test_get_student_gap_map_when_valid_student_then_single_student_view` — Seed
gap states for two students for the same subtopic. Call `get_student_gap_map` for
student A. Assert the returned map contains only student A's scores and has no data
for student B.

`test_get_student_gap_map_when_subtopic_unassessed_then_included_with_none_score` —
Seed 2 subtopics, only insert a gap_state row for one. Call `get_student_gap_map`.
Assert both subtopics appear, and the unassessed one has `mastery_score=None`.

`test_get_class_summary_when_2_of_5_students_assessed_then_counts_correct` — Enroll
5 students, insert gap_state rows for 2. Call `get_class_summary`. Assert
`student_count=5` and `assessed_student_count=2`.

`test_get_class_summary_when_no_assessments_then_avg_mastery_none` — Enroll students
but insert no gap_state rows. Call `get_class_summary`. Assert `avg_mastery=None`.

`test_get_class_summary_computes_correct_average_across_all_subtopics` — Seed gap
states with scores [0.2, 0.4, 0.8]. Assert `avg_mastery` is approximately 0.467
(mean of all rows across all subtopics — not just per-subtopic averages).

**Integration / performance test — `test_gap_map_service_integration.py`**

`test_get_class_gap_map_performance_40_students_50_subtopics_under_500ms` — Seed a
class with 40 students and 50 subtopics with `gap_state` rows for every
student–subtopic pair (2,000 rows total). Time the `get_class_gap_map` call using
`time.perf_counter`. Assert it completes in under 500ms. If the test fails due to
missing indexes, check that `idx_gap_states_class` exists on `gap_states(class_id,
school_id)` — add it via a new Alembic migration if needed.

---

## Do NOT Touch

`backend/app/schemas/gap_map.py` — schemas are frozen from M0-10-T1. Import them,
do not modify them. `backend/app/tasks/gap_tasks.py` — do not modify the Celery
task. `backend/app/services/assessment_service.py` — do not modify. Any existing
migration file.
