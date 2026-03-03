# M2-1-T2 — Gap Map API Routes
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T2
**Depends on:** M2-1-T1 (gap map service)

---

## User Story
As a teacher, parent, or student, I want API endpoints to retrieve gap map data so my app can render the correct view for my role.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/gap_map.py
backend/app/main.py                       # register router
backend/tests/integration/test_gap_map_routes.py
```

---

## Endpoints

### `GET /api/v1/classes/{class_id}/gap-map`
Auth: Teacher (own class only) | SchoolAdmin | KaihleAdmin

Query params:
- `subject_id: UUID` (required)
- `grade_id: UUID` (optional — defaults to class grade)

```
Returns: ClassGapMap (see M2-1-T1 schemas)
```

Permission check:
- Teacher: `class.teacher_id == current_user.id AND class.school_id == current_user.school_id`
- SchoolAdmin: `class.school_id == current_user.school_id`
- KaihleAdmin: unrestricted

---

### `GET /api/v1/students/{student_id}/gap-map`
Auth:
- Student: only own `student_id` (403 if different)
- Teacher: only students enrolled in own class (403 otherwise)
- Parent: only own child via `parent_student` table (403 otherwise)
- SchoolAdmin: any student in own school
- KaihleAdmin: unrestricted

Query params:
- `subject_id: UUID` (required)

```
Returns: StudentGapMap (see M2-1-T1 schemas)
```

---

## Response Shape (abbreviated)

```json
{
  "class_id": "uuid",
  "subject_id": "uuid",
  "generated_at": "2026-03-02T10:00:00Z",
  "nodes": [
    {
      "subtopic_id": "uuid",
      "subtopic_name": "Algebraic Fractions",
      "topic_id": "uuid",
      "topic_name": "Algebra",
      "class_average": 0.42,
      "student_count": 18,
      "student_scores": [
        {
          "student_id": "uuid",
          "student_name": "Aisha Rahman",
          "mastery_score": 0.65,
          "confidence": 0.8,
          "last_assessed_at": "2026-03-01T09:00:00Z"
        }
      ]
    }
  ]
}
```

---

## Acceptance Criteria

- [ ] Teacher gets class gap map for own class → 200
- [ ] Teacher requests gap map for another teacher's class → 403
- [ ] Student gets own gap map → 200
- [ ] Student requests another student's gap map → 403
- [ ] Parent gets own child's gap map → 200
- [ ] Parent requests non-child's gap map → 403
- [ ] Missing `subject_id` query param → 422
- [ ] Response time with 40 students × 50 nodes < 500ms

---

## Tests to Write

```python
test_class_gap_map_when_own_teacher_then_200()
test_class_gap_map_when_other_teacher_then_403()
test_student_gap_map_when_own_student_then_200()
test_student_gap_map_when_different_student_then_403()
test_student_gap_map_when_parent_own_child_then_200()
test_student_gap_map_when_parent_other_child_then_403()
test_class_gap_map_when_missing_subject_id_then_422()
```
