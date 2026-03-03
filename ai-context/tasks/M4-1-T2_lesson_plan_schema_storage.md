# M4-1-T2 — Lesson Plan JSON Schema & Storage

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T2
**Depends on:** M0-2-T2 (SQLAlchemy models — `lesson_plans` table must exist)
**Blocks:** M4-1-T1 (needs schema to validate LLM output), M4-1-T3 (needs schema for response types)

> Build this FIRST within M4. The schema is what everything else in this milestone depends on.

---

## User Story

As a developer, I want a validated, versioned schema for lesson plan JSON so that LLM output is always structurally correct before it is stored or shown to a teacher.

---

## What To Build

Pydantic models that validate the LLM-generated lesson plan JSON. A storage service method that persists a validated plan to `lesson_plans`. A response schema for the API. Unit tests covering validation edge cases.

---

## Files To Create / Modify

```
/backend/app/schemas/
  lesson_plan.py                ← NEW — Pydantic request/response + LLM output models

/backend/app/models/
  lesson_plan.py                ← MODIFY — verify LessonPlan ORM model matches schema

/backend/app/services/
  lesson_plan_service.py        ← MODIFY — add _parse_and_validate() and _store_plan()
```

---

## Pydantic Models (`schemas/lesson_plan.py`)

```python
from pydantic import BaseModel, field_validator, model_validator
from datetime import date
from uuid import UUID

# ── LLM output shape (what we parse from GPT-4.1 response) ──────────────────

class StudentGroupDetail(BaseModel):
    count: int
    focus: str

    @field_validator("count")
    @classmethod
    def count_non_negative(cls, v):
        if v < 0:
            raise ValueError("Student group count cannot be negative")
        return v

class StudentGroups(BaseModel):
    A: StudentGroupDetail
    B: StudentGroupDetail
    C: StudentGroupDetail

class MainActivity(BaseModel):
    group_A: str
    group_B: str
    group_C: str

class LessonStructure(BaseModel):
    starter_10min: str
    main_activity_30min: MainActivity
    plenary_10min: str
    homework: str

class LessonPlanLLMOutput(BaseModel):
    """Validates raw JSON string returned by GPT-4.1."""
    week_start: date
    focus_subtopic_ids: list[UUID]
    class_summary: str
    student_groups: StudentGroups
    lesson_structure: LessonStructure
    teacher_notes: str

    @field_validator("focus_subtopic_ids")
    @classmethod
    def at_least_one_subtopic(cls, v):
        if not v:
            raise ValueError("focus_subtopic_ids cannot be empty")
        return v

    @field_validator("class_summary")
    @classmethod
    def summary_not_empty(cls, v):
        if not v.strip():
            raise ValueError("class_summary cannot be blank")
        return v

    @model_validator(mode="after")
    def total_students_positive(self):
        total = (
            self.student_groups.A.count
            + self.student_groups.B.count
            + self.student_groups.C.count
        )
        if total == 0:
            raise ValueError("Total students across all groups must be > 0")
        return self


# ── API request/response schemas ─────────────────────────────────────────────

class LessonPlanResponse(BaseModel):
    id: UUID
    class_id: UUID
    teacher_id: UUID
    week_start: date
    status: str                        # GENERATED | EDITED | USED | ARCHIVED
    generated_plan: LessonPlanLLMOutput
    teacher_edits: dict | None         # sparse delta — only fields teacher changed
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LessonPlanEditRequest(BaseModel):
    """Teacher PATCH body — partial update, only changed fields."""
    starter_10min: str | None = None
    group_a_activity: str | None = None
    group_b_activity: str | None = None
    group_c_activity: str | None = None
    plenary_10min: str | None = None
    homework: str | None = None
    teacher_notes: str | None = None

class LessonPlanStatusUpdate(BaseModel):
    status: Literal["USED", "ARCHIVED"]
```

---

## Storage Method (add to `lesson_plan_service.py`)

```python
def _parse_and_validate(self, llm_json_str: str) -> LessonPlanLLMOutput:
    """
    Parse and validate raw LLM JSON string.
    Strips markdown fences if present (LLM sometimes adds them despite instructions).
    Raises ValueError if JSON is invalid or schema validation fails.
    """
    clean = llm_json_str.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(clean)
    return LessonPlanLLMOutput.model_validate(data)

async def _store_plan(
    self,
    class_id: UUID,
    teacher_id: UUID,
    school_id: UUID,
    week_start: date,
    plan_data: LessonPlanLLMOutput,
    focus_subtopics: list,
) -> LessonPlan:
    """
    Upsert lesson plan. If one already exists for (class_id, week_start),
    update it (regeneration case). Otherwise insert.
    """
    stmt = (
        insert(LessonPlan)
        .values(
            class_id=class_id,
            teacher_id=teacher_id,
            school_id=school_id,
            week_start=week_start,
            status="GENERATED",
            generated_plan=plan_data.model_dump(mode="json"),
            teacher_edits=None,
        )
        .on_conflict_do_update(
            index_elements=["class_id", "week_start"],
            set_={"generated_plan": plan_data.model_dump(mode="json"),
                  "status": "GENERATED",
                  "updated_at": func.now()}
        )
        .returning(LessonPlan)
    )
    result = await self.session.execute(stmt)
    await self.session.commit()
    return result.scalar_one()
```

---

## `lesson_plans` Table Reference

From `kaihle_v2_1_schema.sql`:
```sql
lesson_plans
  id                UUID PK
  class_id          UUID FK → classes
  teacher_id        UUID FK → users
  school_id         UUID FK → schools
  week_start        DATE NOT NULL
  status            lesson_plan_status  -- GENERATED|EDITED|USED|ARCHIVED
  generated_plan    JSONB NOT NULL      -- LessonPlanLLMOutput stored here
  teacher_edits     JSONB               -- sparse delta only
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ
  UNIQUE(class_id, week_start)
```

---

## Acceptance Criteria

- [ ] Unit test: valid LLM JSON → `LessonPlanLLMOutput` validates without error
- [ ] Unit test: missing `lesson_structure` field → Pydantic raises `ValidationError`
- [ ] Unit test: `focus_subtopic_ids = []` → raises `ValueError`
- [ ] Unit test: `class_summary = ""` → raises `ValueError`
- [ ] Unit test: all group counts = 0 → raises `ValueError`
- [ ] Unit test: `_parse_and_validate` with markdown fences → strips correctly, validates
- [ ] Unit test: `_parse_and_validate` with invalid JSON → raises `ValueError`
- [ ] Integration test: `_store_plan` inserts new row with correct columns
- [ ] Integration test: calling `_store_plan` twice with same `(class_id, week_start)` → upserts (one row, updated content)
- [ ] Unit test: `LessonPlanEditRequest` with all None fields → valid (partial patch)

---

## Output (what M4-1-T1 and M4-1-T3 need)

- `LessonPlanLLMOutput` Pydantic model importable by `lesson_plan_service.py`
- `_parse_and_validate()` and `_store_plan()` methods available on `LessonPlanService`
- `LessonPlanResponse` Pydantic model importable by route handlers
- `lesson_plans` table UNIQUE constraint on `(class_id, week_start)` confirmed working
