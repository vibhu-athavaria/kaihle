# M5-1-T2 — Parent Portal API Routes (Stub Replacement)
**Milestone:** M5 · **Epic:** M5-1 · **Task:** T2
**Depends on:** M5-1-T1 (parent_report_snapshots table populated with real data)
**Blocks:** M5-1-T3 (parent UI calls these endpoints)
**Estimated effort:** 3–4 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/parent.py` **already exists**. It was created
by M0-10-T6. It contains four stub implementations, each marked:

```python
# STUB — M0-10-T6 | Real implementation: M5-1-T2
# Replace this entire function body. Do not change the signature or response_model.
```

This task replaces those four stub bodies with real service calls. It does **not**
create a new file. It does **not** change any route path, HTTP method, auth
dependency, or response model. Those are frozen by CONSTITUTION Rule 19.

The no-scores constraint applies throughout this task. The `ParentGapMap` Pydantic
schema has no `mastery_score` field by design. The `ParentService` must convert raw
gap state data to plain-language labels before populating any response schema. If
you find yourself writing code that passes a float mastery score into a parent
response, stop and reconsider the approach.

---

## User Story

As a parent, I want to view my children's weekly progress reports and simplified
gap maps without seeing raw scores or educational jargon.

---

## Files to Modify / Create

```
backend/app/api/v1/routes/parent.py            ← MODIFY: replace stub bodies only
backend/app/services/parent_service.py         ← CREATE: authorization + data access
backend/app/tests/integration/test_parent_portal_routes.py  ← CREATE
```

---

## `ParentService` — Full Method Signatures

### `verify_parent_child_link`

```python
async def verify_parent_child_link(
    self,
    parent_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    """Verify a parent_student link exists. Raises HTTP 403 if not linked.

    Called at the start of every parent endpoint that takes a student_id.
    This is the primary authorization boundary for parent data access.
    """
    link = await self.db.scalar(
        select(ParentStudent).where(
            ParentStudent.parent_id == parent_user_id,
            ParentStudent.student_id == student_id,
        )
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not linked to this student",
        )
```

### `get_children`

```python
async def get_children(
    self,
    parent_user_id: uuid.UUID,
) -> list[ChildSummary]:
    """Return all students linked to this parent.

    Joins parent_student → users → class_enrollments → classes → subjects
    to build the full ChildSummary for each child.

    Never exposes school_id or internal IDs beyond student_id.
    """
```

The query must return one `ChildSummary` per linked student. The `subjects` field is
a deduplicated list of subject names from the student's active class enrollments.

### `get_child_reports`

```python
async def get_child_reports(
    self,
    parent_user_id: uuid.UUID,
    student_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[WeeklyReport], int]:
    """Return paginated weekly reports for a child.

    Calls verify_parent_child_link first. Returns (reports_list, total_count).
    Reports are sorted by week_start DESC (most recent first).
    """
```

Reads from `parent_report_snapshots`. Returns one `WeeklyReport` per row. The
`highlights` field maps directly from `parent_report_snapshots.highlights`.

### `get_simplified_gap_map`

```python
async def get_simplified_gap_map(
    self,
    parent_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> ParentGapMap:
    """Return a simplified gap map for a parent — plain language only.

    CRITICAL: This method must never include numeric mastery scores in its output.
    All mastery values are converted to TopicStatus objects with plain-language
    labels before being returned.

    The aggregation is at topic level (not subtopic level) to keep the parent
    view simple. A topic's overall status is the worst label among its subtopics
    (if any subtopic is Needs Work, the topic is Needs Work).
    """
```

Step 1 — Call `verify_parent_child_link`.

Step 2 — Load all gap states for the student across all their enrolled subjects:

```python
gap_states = await self.db.scalars(
    select(GapState)
    .join(ClassEnrollment, ClassEnrollment.student_id == GapState.student_id)
    .where(
        GapState.student_id == student_id,
    )
)
```

Step 3 — Convert mastery scores to labels using the same `_mastery_to_label` function
from `ParentReportService`. Group by `(subject_name, topic_name)`. The worst label
in the group determines the topic status (Needs Work > Developing > Strong > Not assessed).

Step 4 — Build `ParentGapMap`. The `subjects` list contains `SubjectGapSummary` objects,
each with a list of `TopicStatus` objects. Sort topics within each subject: Needs Work
topics first, then Developing, then Strong. This ordering helps parents quickly see
which areas need attention.

```python
return ParentGapMap(
    student_name=f"{student.first_name} {student.last_name}",
    grade_name=grade.name,
    subjects=[
        SubjectGapSummary(
            subject_name=subject_name,
            topics=[
                TopicStatus(
                    topic_name=topic_name,
                    status=worst_label,
                    status_label=_label_to_color(worst_label),
                )
                for topic_name, worst_label in sorted_topics
            ],
        )
        for subject_name, sorted_topics in subject_groups.items()
    ],
)
```

Where `_label_to_color` maps: "Strong" → "green", "Developing" → "amber",
"Needs Work" → "red", "Not yet assessed" → "grey".

---

## The Four Stubs to Replace

### `list_children` — `GET /parent/children`

Replace the empty list stub:

```python
service = ParentService(db)
return await service.get_children(parent_user_id=current_user.id)
```

### `list_child_reports` — `GET /parent/children/{student_id}/reports`

Replace the empty `Page` stub:

```python
service = ParentService(db)
reports, total = await service.get_child_reports(
    parent_user_id=current_user.id,
    student_id=student_id,
    page=page,
    page_size=page_size,
)
return Page(data=reports, total=total, page=page, page_size=page_size)
```

### `get_child_report` — `GET /parent/children/{student_id}/reports/{report_id}`

Replace the 404 stub. Load the specific snapshot by `report_id` after verifying the
parent-child link. Map not-found → HTTP 404.

### `get_child_gap_map` — `GET /parent/children/{student_id}/gap-map`

Replace the empty `ParentGapMap` stub:

```python
service = ParentService(db)
return await service.get_simplified_gap_map(
    parent_user_id=current_user.id,
    student_id=student_id,
)
```

---

## Acceptance Criteria

**Integration tests — `test_parent_portal_routes.py`**

Each test specifies the full arrange-act-assert.

`test_list_children_when_parent_linked_to_two_students_then_returns_both` — Create a
parent linked via `parent_student` to two students. Call `GET /parent/children`.
Assert HTTP 200 and the response contains two items, each with `student_id`,
`first_name`, `grade_name`, and a non-empty `subjects` list.

`test_list_children_when_parent_linked_to_no_students_then_returns_empty_list` —
Create a parent with no `parent_student` rows. Assert HTTP 200 with an empty list
(not 404).

`test_list_children_when_teacher_role_then_403` — Call `GET /parent/children` with a
Teacher JWT. Assert HTTP 403.

`test_list_child_reports_when_reports_exist_then_returns_newest_first` — Seed three
`parent_report_snapshots` for a child, for three different Sundays. Call
`GET /parent/children/{id}/reports`. Assert the first item in `data` has the most
recent `week_start`.

`test_list_child_reports_when_not_linked_then_403` — Call the endpoint as a parent
who is not linked to that student. Assert HTTP 403.

`test_list_child_reports_when_no_reports_then_empty_page` — No snapshots exist for
the student. Assert HTTP 200 with `data: []` and `total: 0`, not a 404.

`test_get_child_gap_map_when_valid_then_200_with_topics` — Seed gap states for a
linked child. Call `GET /parent/children/{id}/gap-map`. Assert HTTP 200 and the
response contains at least one `SubjectGapSummary` with at least one `TopicStatus`.

`test_get_child_gap_map_response_contains_no_mastery_score_anywhere` — Call the
gap map endpoint. Serialize the entire response to a JSON string. Use a regex to
assert the string contains no floating-point numbers matching `\d+\.\d+`. This is
the non-negotiable constraint — failing this test is a blocking issue.

`test_get_child_gap_map_topic_with_needs_work_subtopic_shows_needs_work` — Seed one
topic with two subtopics: one Developing (0.6) and one Needs Work (0.3). Assert the
topic's `status` is "Needs Work" (worst label wins).

`test_get_child_gap_map_status_label_values_are_valid` — Call the endpoint. Assert
every `status_label` value in the entire response is one of: "green", "amber", "red",
"grey". No other values are acceptable.

`test_get_child_gap_map_when_not_linked_then_403` — Call as a parent who is not
linked to that student. Assert HTTP 403.

`test_get_child_report_by_id_when_valid_then_200` — Seed one snapshot. Call
`GET /parent/children/{id}/reports/{report_id}`. Assert HTTP 200 and the response
`narrative` field is non-empty.

`test_get_child_report_by_id_when_wrong_parent_then_403` — Call as a parent not
linked to the student. Assert HTTP 403.

---

## Do NOT Touch

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
in `routes/parent.py`. The `schemas/parent.py` file — especially the `ParentGapMap`
class, which deliberately has no `mastery_score` field. `backend/app/main.py` —
router already registered.
