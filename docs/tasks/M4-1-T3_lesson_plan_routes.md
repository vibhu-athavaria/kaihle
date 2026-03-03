# M4-1-T3 — Lesson Plan API Routes

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T3
**Depends on:** M4-1-T1 (Celery task + service), M4-1-T2 (schema + storage)
**Blocks:** M4-1-T4 (UI needs these endpoints)

---

## User Story

As a teacher, I want to fetch, edit, regenerate, and mark my lesson plans as used via the API so the frontend can display and manage them.

---

## What To Build

Five REST endpoints for lesson plan management. All are teacher-scoped — a teacher can only access plans for their own classes.

---

## Files To Create / Modify

```
/backend/app/api/v1/routes/
  lesson_plans.py               ← NEW

/backend/app/api/v1/
  router.py                     ← MODIFY — mount lesson_plans router
```

---

## Endpoints

### `GET /api/v1/classes/{class_id}/lesson-plans`
List all lesson plans for a class, newest first.

**Auth:** Teacher (own class), KaihleAdmin
**Response:**
```json
[
  {
    "id": "uuid",
    "class_id": "uuid",
    "week_start": "2026-03-02",
    "status": "GENERATED",
    "generated_plan": { ... },
    "teacher_edits": null,
    "created_at": "2026-03-02T06:00:00Z"
  }
]
```

---

### `GET /api/v1/lesson-plans/{plan_id}`
Fetch a single lesson plan by ID.

**Auth:** Teacher of that class, KaihleAdmin

**Response merge logic:** When returning to the frontend, merge `teacher_edits` over `generated_plan` so the UI always receives the teacher's latest version:
```python
def merge_plan(generated: dict, edits: dict | None) -> dict:
    if not edits:
        return generated
    merged = generated.copy()
    # Apply sparse delta — only top-level lesson_structure fields
    structure = merged["lesson_structure"].copy()
    if "starter_10min" in edits:
        structure["starter_10min"] = edits["starter_10min"]
    if "group_a_activity" in edits:
        structure["main_activity_30min"]["group_A"] = edits["group_a_activity"]
    # ... etc
    merged["lesson_structure"] = structure
    if "teacher_notes" in edits:
        merged["teacher_notes"] = edits["teacher_notes"]
    return merged
```

---

### `PATCH /api/v1/lesson-plans/{plan_id}`
Save teacher edits. Stores delta in `teacher_edits` column — never overwrites `generated_plan`.

**Auth:** Teacher of that class

**Request body:** `LessonPlanEditRequest` (partial — all fields optional)
```json
{
  "starter_10min": "Updated starter activity description",
  "teacher_notes": "Watch out for group B — they struggled last week"
}
```

**Logic:**
```python
# Merge new edits with existing edits (accumulate changes)
existing_edits = plan.teacher_edits or {}
updated_edits = {**existing_edits, **edit_request.model_dump(exclude_none=True)}
plan.teacher_edits = updated_edits
plan.status = "EDITED"
```

**Response:** Updated `LessonPlanResponse` with merged view

---

### `POST /api/v1/lesson-plans/{plan_id}/regenerate`
Regenerate the lesson plan using the current gap map. Discards previous `generated_plan` and `teacher_edits`.

**Auth:** Teacher of that class

**Request body:** None

**Logic:**
1. Load plan to get `class_id`, `teacher_id`, `school_id`, `week_start`
2. Call `LessonPlanService.generate_for_class(class_id, teacher_id, school_id)`
   - The service's `_store_plan` upserts on `(class_id, week_start)` — existing plan is overwritten
   - `teacher_edits` reset to `null` by the upsert
3. Do NOT re-send teacher notification email on manual regeneration

**Response:** `{ "status": "regenerating", "message": "Your plan will be ready in ~30 seconds" }`

> Note: Generation is synchronous in this endpoint (not queued). The 15s LLM timeout applies. If generation fails, return 503 with helpful message.

---

### `PATCH /api/v1/lesson-plans/{plan_id}/status`
Teacher marks plan as used or archives it.

**Auth:** Teacher of that class

**Request body:**
```json
{ "status": "USED" }
```
Valid values: `"USED"`, `"ARCHIVED"`

**Response:** Updated `LessonPlanResponse`

---

## Route Implementation Pattern

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, require_role
from app.services.lesson_plan_service import LessonPlanService

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])

@router.get("/classes/{class_id}/lesson-plans", response_model=list[LessonPlanResponse])
async def list_lesson_plans(
    class_id: UUID,
    current_user=Depends(get_current_user),
    session=Depends(get_async_session),
):
    service = LessonPlanService(session)
    await service.verify_class_access(class_id, current_user)  # raises 403 if not teacher
    return await service.list_for_class(class_id)

@router.patch("/{plan_id}", response_model=LessonPlanResponse)
async def edit_lesson_plan(
    plan_id: UUID,
    body: LessonPlanEditRequest,
    current_user=Depends(get_current_user),
    session=Depends(get_async_session),
):
    service = LessonPlanService(session)
    plan = await service.get_or_404(plan_id)
    await service.verify_class_access(plan.class_id, current_user)
    return await service.apply_edits(plan, body)
```

---

## Acceptance Criteria

- [ ] Integration test: teacher fetches this week's plan for own class → 200 with correct JSON
- [ ] Integration test: teacher fetches plan for a different class → 403
- [ ] Integration test: `PATCH` with `starter_10min` → `teacher_edits` updated, `status` = "EDITED", `generated_plan` unchanged
- [ ] Integration test: second `PATCH` → edits accumulate (don't overwrite previous edits)
- [ ] Integration test: `POST /regenerate` → plan updated, `teacher_edits` reset to null
- [ ] Integration test: `PATCH /status` with `"USED"` → status updated
- [ ] Integration test: `PATCH /status` with invalid value → 422
- [ ] Integration test: KaihleAdmin can access any plan
- [ ] Unit test: `merge_plan` with edits → correct merged output
- [ ] Unit test: `merge_plan` with no edits → returns generated_plan unchanged

---

## Output (what M4-1-T4 needs)

All five endpoints operational and tested:
- `GET /api/v1/classes/{class_id}/lesson-plans`
- `GET /api/v1/lesson-plans/{plan_id}`
- `PATCH /api/v1/lesson-plans/{plan_id}`
- `POST /api/v1/lesson-plans/{plan_id}/regenerate`
- `PATCH /api/v1/lesson-plans/{plan_id}/status`
