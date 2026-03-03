# M2-1-T1 — Gap Map Aggregation Service
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T1
**Depends on:** M1-4-T3 (gap states populated), M0-2-T2 (ORM models)

---

## User Story
As the system, I want to aggregate gap state data into class-level and student-level views so teachers and students can see performance at a glance.

---

## Files to Create / Modify

```
backend/app/services/gap_service.py          # new file (or extend if started in M1)
backend/app/schemas/gap_map.py
backend/tests/unit/test_gap_service.py
backend/tests/integration/test_gap_map_api.py
```

---

## Data Structures

```python
@dataclass
class SubtopicGapNode:
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    student_scores: list[StudentScore]    # one per student in class
    class_average: float | None           # None if no data
    student_count: int                    # students with data for this subtopic

@dataclass
class StudentScore:
    student_id: UUID
    student_name: str
    mastery_score: float
    confidence: float
    last_assessed_at: datetime | None

@dataclass
class ClassGapMap:
    class_id: UUID
    subject_id: UUID
    grade_id: UUID
    nodes: list[SubtopicGapNode]          # sorted by topic, then subtopic name
    generated_at: datetime

@dataclass
class StudentGapMap:
    student_id: UUID
    subject_id: UUID
    nodes: list[SubtopicGapNode]          # single student_scores entry per node
    generated_at: datetime
```

---

## Service Methods

### `get_class_gap_map(class_id, subject_id, school_id) → ClassGapMap`

```sql
SELECT
    st.id AS subtopic_id, st.name AS subtopic_name,
    t.id AS topic_id, t.name AS topic_name,
    gs.student_id, gs.mastery_score, gs.confidence, gs.last_assessed_at,
    u.first_name, u.last_name
FROM subtopics st
JOIN curriculum_topics ct ON st.curriculum_topic_id = ct.id
JOIN topics t ON ct.topic_id = t.id
JOIN gap_states gs ON gs.subtopic_id = st.id
    AND gs.class_id = :class_id
    AND gs.school_id = :school_id
JOIN users u ON u.id = gs.student_id
WHERE ct.subject_id = :subject_id
ORDER BY t.name, st.name
```

- Subtopics with NO `gap_states` rows → still included in response if they are part of the curriculum, but with `student_scores=[]` and `class_average=None`
- Class average = `mean(mastery_score)` across all students who have data for that subtopic

### `get_student_gap_map(student_id, subject_id, school_id) → StudentGapMap`
Same query but filtered to `gs.student_id = :student_id`. Returns one node per subtopic.

---

## Performance Requirement

- Class with 40 students × 50 subtopics → response < 500ms
- Add DB indexes if needed (check `kaihle_v2_1_schema.sql` — `idx_gap_states_class`, `idx_gap_states_student` should already exist)
- Do NOT call this in a loop — single SQL query with joins

---

## Acceptance Criteria

- [ ] 5 students with gap_states → correct per-student scores in each subtopic node
- [ ] Class average computed correctly per subtopic
- [ ] Subtopics with no data included with empty `student_scores` and `class_average=None`
- [ ] Student gap map returns single-student view
- [ ] Teacher cannot get gap map for a class they don't teach → checked at route layer (M2-1-T2)
- [ ] Performance: 40 students × 50 nodes → < 500ms

---

## Tests to Write

```python
test_get_class_gap_map_when_5_students_then_correct_averages()
test_get_class_gap_map_when_subtopic_has_no_data_then_included_with_none_average()
test_get_student_gap_map_when_valid_student_then_single_student_nodes()
test_get_class_gap_map_performance_when_40_students_50_nodes_then_under_500ms()
test_get_class_gap_map_when_wrong_school_id_then_empty_result()
```
