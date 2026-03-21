# M4-1-T3 — Lesson Plan API Routes (Stub Replacement)
**Milestone:** M4 · **Epic:** M4-1 · **Task:** T3
**Depends on:** M4-1-T1 (LessonPlanService and LessonPlan DB rows must exist), M4-1-T2 (LessonPlanLLMOutput schema)
**Blocks:** M4-1-T4 (teacher UI calls these endpoints)
**Estimated effort:** 3–4 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/lesson_plans.py` **already exists**. It was
created by M0-10-T5. It contains five stub implementations, each marked:

```python
# STUB — M0-10-T5 | Real implementation: M4-1-T3
# Replace this entire function body. Do not change the signature or response_model.
```

This task replaces those five stub bodies with real service calls. It does **not**
create a new file. It does **not** change any route path, HTTP method, auth
dependency, or response model. Those are frozen by CONSTITUTION Rule 19.

Before writing any code, open the existing file and read every stub. Identify the
five functions. Replace only their bodies.

---

## User Story

As a teacher, I want to view my weekly lesson plan, edit any section, regenerate
when needed, and mark plans as used from the API.

---

## Files to Modify (NOT Create)

```
backend/app/api/v1/routes/lesson_plans.py          ← MODIFY: replace stub bodies only
backend/app/tests/integration/test_lesson_plan_routes.py  ← CREATE
```

---

## Service Methods to Add to `LessonPlanService`

The Celery task creates plans. These additional methods support the API endpoints.

### `list_class_lesson_plans`

```python
async def list_class_lesson_plans(
    self,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[LessonPlan], int]:
    """Return paginated lesson plans for a class, newest first.

    Verifies the teacher owns the class before returning data.
    Returns (plans_list, total_count).
    """
```

### `get_lesson_plan`

```python
async def get_lesson_plan(
    self,
    plan_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> LessonPlan:
    """Return a single lesson plan with teacher_edits merged over generated_plan.

    The merge is applied before returning so the route handler always
    receives the teacher's latest version without knowing about the delta.
    """
```

The merge logic is:

```python
def _merge_plan(generated: dict, edits: dict | None) -> dict:
    """Merge teacher edits over generated plan. Edits are a sparse delta."""
    if not edits:
        return generated
    merged = generated.copy()
    structure = merged.get("lesson_structure", {}).copy()
    # Map edit keys to their positions in the lesson_structure
    field_map = {
        "starter_10min": ("lesson_structure", "starter_10min"),
        "group_a_activity": ("lesson_structure", "main_activity_30min", "group_A"),
        "group_b_activity": ("lesson_structure", "main_activity_30min", "group_B"),
        "group_c_activity": ("lesson_structure", "main_activity_30min", "group_C"),
        "plenary_10min": ("lesson_structure", "plenary_10min"),
        "homework": ("lesson_structure", "homework"),
        "teacher_notes": ("teacher_notes",),
    }
    for edit_key, path in field_map.items():
        if edit_key in edits:
            if len(path) == 1:
                merged[path[0]] = edits[edit_key]
            elif len(path) == 2:
                merged[path[0]][path[1]] = edits[edit_key]
            elif len(path) == 3:
                merged[path[0]][path[1]][path[2]] = edits[edit_key]
    return merged
```

### `save_lesson_plan_edits`

```python
async def save_lesson_plan_edits(
    self,
    plan_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    edits: LessonPlanEditRequest,
) -> LessonPlan:
    """Accumulate teacher edits in teacher_edits JSONB column.

    Never overwrites generated_plan. Each call merges new edits with
    existing edits, so the teacher can make incremental changes.
    Sets status to EDITED.
    """
```

Step 1 — Load and verify the plan. Check `plan.school_id == school_id` and that the
class teacher is the requesting teacher. Step 2 — Merge:

```python
existing = plan.teacher_edits or {}
updated = {**existing, **edits.model_dump(exclude_none=True)}
plan.teacher_edits = updated
plan.status = "EDITED"
```

Step 3 — Return the plan (the route will call `get_lesson_plan` to return the merged
view to the client).

### `regenerate_lesson_plan`

```python
async def regenerate_lesson_plan(
    self,
    plan_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> LessonPlan:
    """Queue regeneration of a lesson plan. Clears previous content."""
```

Clear `generated_plan = None`, `teacher_edits = None`, `status = "GENERATING"`.
Queue the Celery task `regenerate_single_plan.delay(str(plan_id))`. Return the plan
in its clearing state so the UI can show a loading state immediately.

Add a separate Celery task `regenerate_single_plan` in `lesson_plan_tasks.py` that
calls `LessonPlanService.generate_for_class(class_)` for the specific plan's class
and updates the existing plan row rather than creating a new one.

### `update_lesson_plan_status`

```python
async def update_lesson_plan_status(
    self,
    plan_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    new_status: str,
) -> LessonPlan:
    """Update plan status. Only USED and ARCHIVED are valid transitions."""
```

Valid status transitions: `GENERATED → USED`, `GENERATED → ARCHIVED`,
`EDITED → USED`, `EDITED → ARCHIVED`. Anything else raises
`ValueError("Invalid status transition")`.

---

## The Five Stubs to Replace

### `list_class_lesson_plans` — `GET /classes/{class_id}/lesson-plans`

Replace empty `Page` stub with a call to `LessonPlanService.list_class_lesson_plans`.

Authorization: verify the teacher owns the class by checking `class_.teacher_id ==
current_user.id`. KaihleAdmin bypasses this check (CONSTITUTION Rule 12).

### `get_lesson_plan` — `GET /lesson-plans/{plan_id}`

Replace 404 stub with `LessonPlanService.get_lesson_plan`. Return
`LessonPlanResponse` built from the merged plan. Map `ValueError` → HTTP 404 or 403
depending on whether the plan was not found or access was denied.

### `edit_lesson_plan` — `PATCH /lesson-plans/{plan_id}`

Replace 404 stub with `LessonPlanService.save_lesson_plan_edits`. After saving,
call `get_lesson_plan` to return the merged view.

### `regenerate_lesson_plan` — `POST /lesson-plans/{plan_id}/regenerate`

Replace 404 stub with `LessonPlanService.regenerate_lesson_plan`. Return the plan
in `GENERATING` status. The UI should poll or use websockets in future — for now, the
teacher refreshes manually after ~30 seconds.

### `update_lesson_plan_status` — `PATCH /lesson-plans/{plan_id}/status`

Replace 404 stub with `LessonPlanService.update_lesson_plan_status`. Map
`ValueError("Invalid status transition")` → HTTP 409.

---

## Acceptance Criteria

**Integration tests — `test_lesson_plan_routes.py`**

`test_list_class_plans_when_teacher_owns_class_then_200_with_page` — Seed two lesson
plans for a class owned by the authenticated teacher. Call `GET /classes/{id}/lesson-plans`.
Assert HTTP 200, `data` contains two items, `total == 2`, ordered newest first.

`test_list_class_plans_when_teacher_does_not_own_class_then_403` — Call as a teacher
who does not own the class. Assert HTTP 403.

`test_get_lesson_plan_when_teacher_edits_exist_then_response_shows_merged_view` — Seed
a plan with `generated_plan.lesson_structure.starter_10min = "Original starter"` and
`teacher_edits = {"starter_10min": "Updated starter"}`. Call `GET /lesson-plans/{id}`
as the teacher. Assert the response's `lesson_structure.starter_10min` equals
"Updated starter" — not "Original starter".

`test_get_lesson_plan_when_no_edits_then_returns_generated_plan` — Seed a plan with
`teacher_edits = null`. Assert the response shows the generated plan content unchanged.

`test_get_lesson_plan_when_different_school_then_403_or_404` — Call as a user from
a different school. Assert HTTP 403 or 404 (not 200).

`test_patch_lesson_plan_when_valid_edit_then_200_and_edit_stored` — PATCH with
`{"starter_10min": "New starter"}`. Assert HTTP 200 and that the DB row's
`teacher_edits` dict contains `starter_10min: "New starter"`.

`test_patch_lesson_plan_accumulates_edits_across_calls` — PATCH once with
`{"starter_10min": "A"}`, then again with `{"plenary_10min": "B"}`. Assert the
DB row contains both keys in `teacher_edits`.

`test_patch_lesson_plan_never_modifies_generated_plan` — After two PATCH calls,
assert the DB row's `generated_plan` is identical to what was seeded. Only
`teacher_edits` changes.

`test_regenerate_lesson_plan_when_called_then_status_generating` — Call
`POST /lesson-plans/{id}/regenerate`. Assert HTTP 200 and the response
`status == "GENERATING"`. Assert the Celery task was queued (mock with
`unittest.mock.patch`).

`test_update_status_when_generated_to_used_then_200` — Seed a GENERATED plan. Call
`PATCH /lesson-plans/{id}/status` with `{"status": "USED"}`. Assert HTTP 200 and
the DB row `status == "USED"`.

`test_update_status_when_invalid_transition_then_409` — Seed a CLOSED plan. Try to
transition to GENERATED. Assert HTTP 409.

---

## Do NOT Touch

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
call in `routes/lesson_plans.py`. The `schemas/lesson_plans.py` file. `routes/assessments.py`.
`backend/app/main.py` — router already registered.
