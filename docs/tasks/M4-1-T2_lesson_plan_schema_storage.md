# M4-1-T2 — Lesson Plan JSON Schema & Storage (UPDATED)

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T2
**Depends on:** M0-2-T2 (SQLAlchemy models — `lesson_plans` table must exist)
**Blocks:** M4-1-T1 (needs schema to validate LLM output), M4-1-T3 (needs schema for response types)

> Build this FIRST within M4. The schema is what everything else in this milestone depends on.

> **UPDATED March 2026:** Schema expanded to support rich lesson plans with
> per-activity timelines, diagnostic gap targeting (WHERE + HOW), Cambridge
> objective codes, and VARK learning style embedding. The previous flat
> 4-field `LessonStructure` is replaced by a `timeline` array + `diagnostic_gaps`
> array. The old shape is preserved as `LessonStructureLegacy` for reference only
> — do NOT use it in new code.

---

## User Story

As a developer, I want a validated, versioned schema for lesson plan JSON so that LLM
output is always structurally correct before it is stored or shown to a teacher.

---

## What To Build

Pydantic models that validate the LLM-generated lesson plan JSON. A storage service
method that persists a validated plan to `lesson_plans`. A response schema for the API.
Unit tests covering validation edge cases.

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
from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import date

from pydantic import BaseModel, field_validator, model_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class LessonPhase(str, Enum):
    WARMUP    = "warmup"
    BRIDGE    = "bridge"
    STATION   = "station"
    DEBRIEF   = "debrief"
    EXIT      = "exit"
    ACTIVITY  = "activity"   # generic fallback for non-station plans


class LearningStyleSlug(str, Enum):
    VISUAL          = "visual"
    KINESTHETIC     = "kinesthetic"
    AUDITORY        = "auditory"
    READING_WRITING = "reading_writing"
    MIXED           = "mixed"   # class has no dominant style


class PlanStatus(str, Enum):
    GENERATED = "GENERATED"
    EDITED    = "EDITED"
    USED      = "USED"
    ARCHIVED  = "ARCHIVED"


# ── Sub-models — LLM output shape ────────────────────────────────────────────

class LearningObjective(BaseModel):
    """One Cambridge learning objective addressed by this plan."""
    code: str        # e.g. "7Pf.01"
    description: str # e.g. "Define force as a push or pull"

    @field_validator("code")
    @classmethod
    def code_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Learning objective code cannot be empty")
        return v.strip()


class DiagnosticGapTarget(BaseModel):
    """
    One diagnostic gap identified from Kaihle assessment data,
    with explicit WHERE and HOW it is addressed in this plan.
    """
    gap_description: str    # e.g. "Confusing mass and weight"
    addressed_where: str    # e.g. "Station 1 · Teacher checkpoint min 15"
    addressed_how:   str    # e.g. "Students physically compare spring balance (N) vs
                            #        digital balance (g) side-by-side"
    mastery_band: Optional[str] = None  # "needs_work" | "developing" — from gap_state

    @field_validator("gap_description", "addressed_where", "addressed_how")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("DiagnosticGapTarget fields cannot be empty")
        return v.strip()


class TimelineItem(BaseModel):
    """One activity block in the lesson timeline."""
    phase:       LessonPhase
    start_min:   int          # lesson minute this block starts, e.g. 0, 5, 8
    duration_min: int         # length in minutes
    title:       str          # short activity name, e.g. "Force Freeze — Body Simulation"
    description: str          # teacher-facing instructions, 2–5 sentences
    gap_targeted: Optional[str] = None   # gap_description from DiagnosticGapTarget, if applicable
    kinesthetic_tag: Optional[str] = None  # short tag shown in UI, e.g. "Physical card sort"
    assess_tag: Optional[str] = None       # e.g. "Diagnostic data collected"

    @field_validator("start_min", "duration_min")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Timeline timings cannot be negative")
        return v

    @field_validator("title", "description")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("TimelineItem title and description cannot be empty")
        return v.strip()


class ResourceItem(BaseModel):
    """One physical or digital resource needed for the lesson."""
    description: str   # e.g. "Digital balance + spring balance (newton meter)"


class StudentGroupActivity(BaseModel):
    """Per-mastery-group activity for differentiated main activities."""
    group_a: str   # mastery < 0.4 — foundational
    group_b: str   # mastery 0.4–0.7 — developing
    group_c: str   # mastery > 0.7 — extension


# ── Top-level LLM output ─────────────────────────────────────────────────────

class LessonPlanLLMOutput(BaseModel):
    """
    Validates raw JSON returned by the LLM.

    The LLM is asked to return this shape via lesson_plan.jinja2.
    All fields are required. Validation failures trigger a retry.

    Design note: `timeline` is the primary lesson structure and drives
    the teacher UI. `student_groups` is preserved for differentiated
    classes where Group A/B/C activities differ within a station.
    """
    week_start:        date
    class_summary:     str   # 1–2 sentence gap summary for this class
    learning_style:    LearningStyleSlug
    lesson_duration_min: int

    learning_objectives: list[LearningObjective]   # min 1, max 6
    diagnostic_gaps:     list[DiagnosticGapTarget] # min 1, max 5
    timeline:            list[TimelineItem]         # min 3 blocks
    resources:           list[ResourceItem]         # min 1
    teacher_notes:       str                        # safety, pacing, checkpoint tips

    # Optional — present when the class has mastery-band differentiation
    student_groups: Optional[dict] = None  # {"A": {...}, "B": {...}, "C": {...}}

    @model_validator(mode="after")
    def validate_timeline_coverage(self) -> "LessonPlanLLMOutput":
        total = sum(item.duration_min for item in self.timeline)
        if total > self.lesson_duration_min + 5:  # allow 5 min slack
            raise ValueError(
                f"Timeline total ({total} min) exceeds lesson duration "
                f"({self.lesson_duration_min} min) by more than 5 minutes"
            )
        if len(self.learning_objectives) < 1:
            raise ValueError("At least one learning objective is required")
        if len(self.diagnostic_gaps) < 1:
            raise ValueError("At least one diagnostic gap target is required")
        if len(self.timeline) < 3:
            raise ValueError("Timeline must have at least 3 activity blocks")
        return self


# ── API response shape (sent to frontend) ────────────────────────────────────

class LessonPlanResponse(BaseModel):
    """Returned by GET /lesson-plans/:id — merges teacher_edits over generated_plan."""
    id:           UUID
    class_id:     UUID
    week_start:   date
    status:       PlanStatus
    plan:         LessonPlanLLMOutput   # merged view (teacher edits applied)
    generated_at: str
    ai_model:     str                   # e.g. "claude-sonnet-4-6" — for UI badge


class LessonPlanSummary(BaseModel):
    """Returned by GET /classes/:classId/lesson-plans (list view)."""
    id:           UUID
    week_start:   date
    status:       PlanStatus
    class_summary: str
    learning_style: LearningStyleSlug
    gap_count:    int
    generated_at: str


# ── Edit request (PATCH) ──────────────────────────────────────────────────────

class LessonPlanEditRequest(BaseModel):
    """
    Sparse delta stored in teacher_edits JSONB column.
    Teacher can edit any timeline item description or teacher_notes.
    Never overwrites generated_plan — edits layer on top at read time.
    """
    timeline_edits: Optional[dict[int, str]] = None
    # key = timeline item index (0-based), value = updated description
    # e.g. {0: "Updated warm-up instructions..."}

    teacher_notes: Optional[str] = None
    class_summary: Optional[str] = None
```

---

## Storage Service Addition (`lesson_plan_service.py`)

Add these two methods to the existing `LessonPlanService` class:

```python
import json
from app.schemas.lesson_plan import LessonPlanLLMOutput
from pydantic import ValidationError
import structlog

logger = structlog.get_logger()

async def _parse_and_validate(self, raw_json: str) -> LessonPlanLLMOutput | None:
    """
    Parse and validate LLM output JSON.
    Returns None on validation failure (caller will retry).
    Strips markdown fences if LLM wraps output in ```json ... ```.
    """
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        # Strip ```json ... ``` fences
        lines = cleaned.split("\n")
        cleaned = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        )
    try:
        data = json.loads(cleaned)
        return LessonPlanLLMOutput(**data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning(
            "lesson_plan_validation_failed",
            error=str(exc),
            raw_length=len(raw_json),
        )
        return None


async def _store_plan(
    self,
    class_id: UUID,
    teacher_id: UUID,
    validated: LessonPlanLLMOutput,
    ai_model: str,
) -> LessonPlan:
    """
    Persist a validated lesson plan to the lesson_plans table.
    Sets status = GENERATED. Does NOT send email — caller handles that.
    """
    plan = LessonPlan(
        class_id=class_id,
        teacher_id=teacher_id,
        week_start=validated.week_start,
        status="GENERATED",
        generated_plan=validated.model_dump(mode="json"),
        teacher_edits=None,
        ai_model=ai_model,
    )
    self.session.add(plan)
    await self.session.commit()
    await self.session.refresh(plan)
    logger.info(
        "lesson_plan_stored",
        plan_id=str(plan.id),
        class_id=str(class_id),
        week_start=str(validated.week_start),
        gap_count=len(validated.diagnostic_gaps),
        timeline_items=len(validated.timeline),
    )
    return plan
```

---

## ORM Model Check (`models/lesson_plan.py`)

Verify these columns exist on the `LessonPlan` SQLAlchemy model.
Add `ai_model` if missing — it was not in the original schema:

```python
class LessonPlan(Base):
    __tablename__ = "lesson_plans"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    class_id      = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    teacher_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_start    = Column(Date, nullable=False)
    status        = Column(String, nullable=False, default="GENERATED")
    generated_plan = Column(JSONB, nullable=True)   # LessonPlanLLMOutput as JSON
    teacher_edits  = Column(JSONB, nullable=True)   # sparse delta from PATCH
    ai_model       = Column(String, nullable=True)  # ← ADD IF MISSING
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("class_id", "week_start", name="uq_lesson_plan_class_week"),
    )
```

If `ai_model` is missing, generate an Alembic migration:
```bash
alembic revision --autogenerate -m "add ai_model to lesson_plans"
```

---

## Unit Tests

```
/backend/tests/unit/test_lesson_plan_schema.py
```

```python
import pytest
from datetime import date
from app.schemas.lesson_plan import (
    LessonPlanLLMOutput, LearningObjective, DiagnosticGapTarget,
    TimelineItem, LessonPhase, ResourceItem, LearningStyleSlug
)

def make_valid_plan(**overrides) -> dict:
    base = {
        "week_start": "2026-03-02",
        "class_summary": "Students struggle with mass vs weight.",
        "learning_style": "kinesthetic",
        "lesson_duration_min": 60,
        "learning_objectives": [
            {"code": "7Pf.01", "description": "Define force"}
        ],
        "diagnostic_gaps": [
            {
                "gap_description": "Confusing mass and weight",
                "addressed_where": "Station 1",
                "addressed_how": "Spring balance vs digital balance comparison"
            }
        ],
        "timeline": [
            {"phase": "warmup",   "start_min": 0,  "duration_min": 5,  "title": "Warm up",  "description": "Students act out forces."},
            {"phase": "station",  "start_min": 5,  "duration_min": 30, "title": "Station",  "description": "Hands-on activity."},
            {"phase": "exit",     "start_min": 50, "duration_min": 10, "title": "Exit task","description": "Assessment."},
        ],
        "resources": [{"description": "Spring balance"}],
        "teacher_notes": "Keep transitions snappy.",
    }
    base.update(overrides)
    return base


def test_valid_plan_parses():
    plan = LessonPlanLLMOutput(**make_valid_plan())
    assert plan.learning_style == LearningStyleSlug.KINESTHETIC
    assert len(plan.timeline) == 3
    assert len(plan.diagnostic_gaps) == 1


def test_empty_objective_code_raises():
    data = make_valid_plan()
    data["learning_objectives"] = [{"code": "", "description": "Something"}]
    with pytest.raises(Exception):
        LessonPlanLLMOutput(**data)


def test_timeline_overflow_raises():
    data = make_valid_plan()
    # Total = 70 min, lesson = 60 min, slack = 5 → should fail
    data["timeline"][1]["duration_min"] = 55
    with pytest.raises(Exception):
        LessonPlanLLMOutput(**data)


def test_missing_diagnostic_gap_raises():
    data = make_valid_plan()
    data["diagnostic_gaps"] = []
    with pytest.raises(Exception):
        LessonPlanLLMOutput(**data)


def test_fewer_than_3_timeline_items_raises():
    data = make_valid_plan()
    data["timeline"] = data["timeline"][:2]
    with pytest.raises(Exception):
        LessonPlanLLMOutput(**data)


def test_negative_start_min_raises():
    data = make_valid_plan()
    data["timeline"][0]["start_min"] = -1
    with pytest.raises(Exception):
        LessonPlanLLMOutput(**data)
```

---

## Acceptance Criteria

- [ ] `LessonPlanLLMOutput` validates a well-formed plan with all required fields
- [ ] Missing `learning_objectives` raises `ValidationError`
- [ ] Empty `diagnostic_gaps` list raises `ValidationError`
- [ ] Timeline total > lesson duration + 5 min raises `ValidationError`
- [ ] `_parse_and_validate()` strips markdown fences before parsing
- [ ] `_parse_and_validate()` returns `None` on malformed JSON (does not raise)
- [ ] `_store_plan()` writes a row to `lesson_plans` with `status = "GENERATED"`
- [ ] `ai_model` column exists on `lesson_plans` table (via migration if needed)
- [ ] All unit tests in `test_lesson_plan_schema.py` pass
- [ ] `tsc --noEmit` unaffected (backend-only change)

---

## ADDENDUM — April 2026: Student Pack Architecture

> Added when lesson plan architecture was expanded to produce two distinct outputs:
> a **Teacher Plan** (this task) and a **Student Pack** (M4-2-T1).

### What changed

The teacher-facing `LessonPlanLLMOutput` schema defined in this task is **unchanged
and remains the authoritative teacher plan schema**. Do not alter it.

The student-facing plan is a separate on-demand generation — not part of the Monday
Celery beat task. It is defined and implemented in `M4-2-T1_student_pack_generation.md`.

### Student pack table

The `student_lesson_packs` table is created in migration `M3-0-T1` (added alongside
`subtopic_content`). The ORM model lives at:
```
backend/app/models/student_lesson_pack.py
```

This task does **not** create or modify that model — M4-2-T1 owns it.

### Key distinction for coding agents

| | Teacher Plan | Student Pack |
|---|---|---|
| Task file | **This file (M4-1-T2)** | M4-2-T1 |
| Schema | `LessonPlanLLMOutput` | `StudentPackLLMOutput` |
| Generation | Celery beat, Monday 06:00 | On-demand, first student access |
| Storage table | `lesson_plans` | `student_lesson_packs` |
| Audience | Teacher only | Student only |
| LO language | Cambridge codes + formal LO text | Plain language "what you'll learn" |
| Resources | YouTube links for teacher preview | Embedded video from `subtopic_content` |

### Do NOT add student pack generation to this task

All student pack generation logic belongs in M4-2-T1. This task ends at the teacher
plan schema, storage, and unit tests. No student-facing schema or endpoint goes here.

---

*Addendum authored by Kramer (Technical Lead) · April 2026*
