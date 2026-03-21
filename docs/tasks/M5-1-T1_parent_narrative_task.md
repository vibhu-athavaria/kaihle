# M5-1-T1 — Parent Narrative Generation (Celery Beat Task)
**Milestone:** M5 · **Epic:** M5-1 · **Task:** T1
**Depends on:** M2-1-T1 (GapService.get_student_gap_map), M0-1-T2 (Celery infrastructure), M4-1-T1 (beat schedule pattern)
**Blocks:** M5-1-T2 (API reads from parent_report_snapshots table this task populates)
**Estimated effort:** 4–5 hours

---

## Context

This task builds the Celery beat task that generates weekly parent-facing narratives
every Sunday at 18:00. It follows the exact same structural pattern as `M4-1-T1`
(lesson plan generation) — read that task file first to understand the pattern before
writing this one.

Read CONSTITUTION.md Rule 18 (dead-letter CRITICAL log on final retry), Rule 8
(LiteLLM routing), and the no-scores constraint in the parent API schemas before
writing any code.

**Critical — async pattern.** Use the event loop pattern, not `asyncio.run()`:

```python
loop = asyncio.new_event_loop()
try:
    result = loop.run_until_complete(_async_function())
finally:
    loop.close()
```

**Critical — LiteLLM routing.** Call via
`app.ai.providers.router.complete(task="gap_classification", prompt=...)`. Per
CONSTITUTION §8, this routes to Gemini Flash with a 5-second hard timeout. The
150-word limit is enforced in the prompt template, not via `max_tokens`.

**Critical — no numeric scores in parent output.** The narrative, highlights, and any
structured data written to `parent_report_snapshots` must contain zero numeric mastery
scores. The LLM receives the plain-language labels (Strong/Developing/Needs Work) as
input, not raw floats. This constraint is fundamental to Kaihle's parent experience
design — see the parent API schemas in `schemas/parent.py` for why.

---

## User Story

As a parent, I want to receive a weekly plain-English summary of my child's
progress so I can stay informed without needing to interpret educational jargon.

---

## Files to Create / Modify

```
backend/app/tasks/parent_tasks.py              ← CREATE
backend/app/services/parent_report_service.py  ← CREATE
backend/app/ai/prompts/parent_narrative.jinja2 ← CREATE
backend/app/tasks/celery_app.py               ← MODIFY: add beat schedule entry
backend/app/tests/unit/test_parent_report_service.py
backend/app/tests/integration/test_parent_narrative_generation.py
```

---

## Beat Schedule Entry

Add to the `beat_schedule` dict in `celery_app.py`, alongside the lesson plan entry
added in M4-1-T1:

```python
"generate-parent-narratives": {
    "task": "app.tasks.parent_tasks.generate_parent_narratives",
    "schedule": crontab(hour=18, minute=0, day_of_week=0),  # Every Sunday 18:00
},
```

---

## `parent_tasks.py`

```python
"""Celery task for weekly parent narrative generation."""

import asyncio
import structlog
from celery import shared_task
from app.core.database import get_async_session
from app.services.parent_report_service import ParentReportService

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="app.tasks.parent_tasks.generate_parent_narratives",
    max_retries=0,   # Beat tasks do not retry — next Sunday will run again
)
def generate_parent_narratives(self) -> dict:
    """Celery beat task — runs every Sunday 18:00.

    For each student with gap state activity in the last 7 days, generates
    a 150-word plain-language narrative for linked parents.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate_all())
    finally:
        loop.close()


async def _generate_all() -> dict:
    async with get_async_session() as session:
        service = ParentReportService(session)
        return await service.generate_for_all_active_students()
```

---

## `ParentReportService` — Method Signatures

### `generate_for_all_active_students`

```python
async def generate_for_all_active_students(self) -> dict:
    """Entry point called by the Celery beat task.

    Finds all students with at least one gap_state updated in the last 7 days,
    generates a narrative for each, stores it, and emails linked parents.
    Errors on individual students are caught and logged — they do not abort the batch.

    Returns:
        dict with keys: total_students, generated, skipped, errors
    """
```

Step 1 — Find all students with recent gap state activity:

```python
from datetime import datetime, timedelta, timezone
cutoff = datetime.now(timezone.utc) - timedelta(days=7)

active_student_ids = await self.db.scalars(
    select(GapState.student_id)
    .where(GapState.last_assessed_at >= cutoff)
    .distinct()
)
```

Step 2 — For each student ID, call `generate_for_student(student_id)`. Wrap in
try/except — log errors at ERROR level with `student_id` and continue.

Step 3 — Return summary dict.

### `generate_for_student`

```python
async def generate_for_student(
    self,
    student_id: uuid.UUID,
) -> ParentReportSnapshot:
    """Generate and store one weekly narrative for a student.

    Args:
        student_id: The student to generate for. All their enrolled subjects
                    are processed. One narrative is generated per subject with
                    recent activity.

    Returns:
        The most recently created ParentReportSnapshot row.
    """
```

Step 1 — Load the student's enrolled subjects by joining `class_enrollments → classes
→ subjects`. One narrative per subject.

Step 2 — For each subject with recent gap activity, call `_generate_subject_narrative`.

Step 3 — Email all parents linked via `parent_student` once all narratives are stored.
If no parents are linked, log at DEBUG level and skip the email step (student exists but
no parent account set up yet).

### `_generate_subject_narrative`

```python
async def _generate_subject_narrative(
    self,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    school_id: uuid.UUID,
) -> ParentReportSnapshot | None:
    """Generate a single narrative for one student/subject combination.

    Returns None and logs at WARNING if insufficient data exists (fewer than
    3 gap state rows for this subject — not enough to write a meaningful narrative).
    """
```

Step 1 — Load current gap map using `GapService.get_student_gap_map(student_id, school_id, subject_id)`.

Step 2 — Convert mastery scores to plain-language labels before passing to the LLM.
The LLM must never receive raw floats:

```python
def _mastery_to_label(score: float | None) -> str:
    if score is None:
        return "Not yet assessed"
    if score >= 0.7:
        return "Strong"
    if score >= 0.4:
        return "Developing"
    return "Needs Work"
```

Step 3 — Load the previous week's snapshot (if exists) to compute deltas:

```python
week_start = _current_sunday() - timedelta(days=7)
prev_snapshot = await self.db.scalar(
    select(ParentReportSnapshot).where(
        ParentReportSnapshot.student_id == student_id,
        ParentReportSnapshot.subject_id == subject_id,
        ParentReportSnapshot.week_start == week_start,
    )
)
```

Step 4 — Identify improvements and gaps:

Improvements are subtopics where the current label is better than the previous
snapshot's label (e.g. went from Developing to Strong). If no previous snapshot
exists, improvements are the subtopics currently labelled Strong.

Areas needing work are the two subtopics with the worst label (Needs Work first,
then Developing).

Step 5 — Build the prompt with plain-language labels only. Render the Jinja2 template.
Call the LLM via `router.complete(task="gap_classification", prompt=...)` with a
5-second hard timeout. On failure, log at WARNING and return None (skip this narrative).

Step 6 — Parse the LLM response. The model returns plain text — wrap it in the
`ParentReportSnapshot` structure:

```python
snapshot = ParentReportSnapshot(
    id=uuid.uuid4(),
    student_id=student_id,
    subject_id=subject_id,
    school_id=school_id,
    week_start=_current_sunday(),
    narrative=llm_response.strip()[:1000],   # cap at 1000 chars as safety guard
    highlights=[s.subtopic_name for s in improvements[:2]],
    gap_summary={
        s.subtopic_name: _mastery_to_label(s.mastery_score)
        for s in gap_map.scores
        if s.mastery_score is not None
    },
    # CRITICAL: gap_summary values are plain-language labels — never raw floats.
)
```

Step 7 — Upsert using `ON CONFLICT (student_id, subject_id, week_start) DO UPDATE`.
This makes the task idempotent.

---

## Jinja2 Prompt Template (`parent_narrative.jinja2`)

```jinja2
System: You write brief, warm, plain-English progress updates for parents of
        students at {{ school_name }}.
        Write in a friendly, reassuring tone — like a trusted teacher speaking
        directly to the parent.
        Maximum 150 words. No jargon. No numeric scores. No percentages.
        Do NOT mention specific test scores, mastery levels, or grades.

Student: {{ student_first_name }}, Grade {{ grade_level }}
Subject: {{ subject_name }}
This week:

{% if improvements %}
Showed improvement in: {{ improvements | join(', ') }}
{% endif %}

{% if gaps %}
Still working on: {{ gaps | join(', ') }}
{% endif %}

Next steps: {{ subject_name }} lessons next week will focus on {{ next_focus }}.

Write a single paragraph (2–4 sentences) that a parent would find warm and useful.
Do not use bullet points. Do not start with "Dear Parent."
```

---

## Acceptance Criteria

**Unit tests — `test_parent_report_service.py`**

`test_mastery_to_label_when_above_0_7_then_strong` — Call `_mastery_to_label(0.71)`.
Assert return value is "Strong".

`test_mastery_to_label_when_0_7_exactly_then_strong` — Boundary: `_mastery_to_label(0.7)`.
Assert "Strong".

`test_mastery_to_label_when_0_4_exactly_then_developing` — Boundary:
`_mastery_to_label(0.4)`. Assert "Developing".

`test_mastery_to_label_when_below_0_4_then_needs_work` — `_mastery_to_label(0.39)`.
Assert "Needs Work".

`test_mastery_to_label_when_none_then_not_yet_assessed` — `_mastery_to_label(None)`.
Assert "Not yet assessed".

`test_identify_improvements_when_label_improved_then_subtopic_in_list` — Build a
previous snapshot where subtopic A was "Developing". Set current mastery for subtopic
A to 0.8 (Strong). Assert subtopic A appears in the improvements list.

`test_identify_improvements_when_no_prev_snapshot_then_strong_subtopics_used` — No
previous snapshot. Set two subtopics to Strong. Assert both appear as improvements.

`test_identify_gaps_when_needs_work_then_included` — Set subtopic mastery to 0.3.
Assert it appears in the areas-needing-work list.

`test_narrative_does_not_contain_numeric_scores` — Run `generate_for_student` with a
mocked LLM that returns a narrative. Assert the stored `narrative` field contains no
floating-point numbers (use a regex: `\d+\.\d+`).

`test_gap_summary_values_are_plain_language_not_floats` — After generation, load the
`ParentReportSnapshot` from DB. Assert every value in `gap_summary` is one of
"Strong", "Developing", "Needs Work", "Not yet assessed" — never a number.

`test_generate_for_student_when_insufficient_data_then_returns_none` — Seed fewer than
3 gap state rows for the student/subject. Assert the method returns None and no
snapshot is created.

`test_task_idempotent_when_run_twice_same_week` — Run the generation twice for the
same student and week. Assert only one `parent_report_snapshots` row exists for that
`(student_id, subject_id, week_start)` combination.

**Integration tests — `test_parent_narrative_generation.py`**

`test_task_when_student_has_recent_gap_activity_then_snapshot_created` — Seed a
student with `gap_state` rows updated within the last 7 days. Run `_generate_all()`
with a mocked LLM router. Assert a `ParentReportSnapshot` row exists in the DB.

`test_task_when_student_has_no_recent_gap_activity_then_no_snapshot_created` — Seed
a student whose last `gap_state` update was 10 days ago (outside the 7-day window).
Run the task. Assert no snapshot is created for that student.

`test_task_when_parents_linked_then_email_queued` — Seed a `parent_student` link.
Run the task with a mocked email sender. Assert the email mock was called with the
parent's email address.

---

## Do NOT Touch

`backend/app/services/gap_service.py` — use `GapService.get_student_gap_map()` as-is.
`backend/app/schemas/parent.py` — defined in M0-10-T1, do not modify.
`backend/app/api/v1/routes/parent.py` — defined in M0-10-T6, do not modify here.
Any existing Celery task file (`lesson_plan_tasks.py`, `gap_tasks.py`, `onboarding_tasks.py`).
