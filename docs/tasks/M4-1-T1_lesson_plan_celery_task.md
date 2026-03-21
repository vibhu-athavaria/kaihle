# M4-1-T1 — Weekly Lesson Plan Celery Beat Task
**Milestone:** M4 · **Epic:** M4-1 · **Task:** T1
**Depends on:** M4-1-T2 (LessonPlanLLMOutput schema must be defined before this task can store output), M2-1-T1 (GapService.get_class_gap_map must exist), M0-1-T2 (Celery infrastructure)
**Blocks:** M4-1-T3 (routes read from lesson_plans table), M4-1-T4 (UI)
**Estimated effort:** 4–5 hours

---

## Context

This task builds the Celery beat task that automatically generates weekly lesson plans
every Monday at 06:00. Read CONSTITUTION.md Rule 18 (dead-letter CRITICAL log on final
retry) and Rule 8 (LiteLLM routing via `app.ai.providers.router`) before writing any code.

**Critical — async pattern.** The correct pattern for calling async code inside a
synchronous Celery task is the event loop pattern established in `M0-8-T1`
(`onboarding_tasks.py`). Do NOT use `asyncio.run()` — it fails in some Celery worker
configurations. Use:

```python
loop = asyncio.new_event_loop()
try:
    result = loop.run_until_complete(_async_function())
finally:
    loop.close()
```

**Critical — LiteLLM routing.** All LLM calls in this task go through
`app.ai.providers.router.complete(task="lesson_plan", prompt=...)`. Never import
OpenAI, Gemini, or any other provider SDK directly. Per CONSTITUTION §8, the
`lesson_plan` task routes to GPT-4.1 with a 15-second hard timeout.

---

## User Story

As a teacher, I want to automatically receive an AI-generated weekly lesson plan
every Monday morning so I can start the week prepared without extra admin work.

---

## Files to Create / Modify

```
backend/app/tasks/lesson_plan_tasks.py     ← CREATE
backend/app/services/lesson_plan_service.py ← CREATE
backend/app/ai/prompts/lesson_plan.jinja2  ← CREATE
backend/app/tasks/celery_app.py            ← MODIFY: add beat schedule entry
backend/app/tests/unit/test_lesson_plan_service.py
backend/app/tests/integration/test_lesson_plan_generation.py
```

---

## Beat Schedule Entry

Add to the `beat_schedule` dict in `celery_app.py`:

```python
"generate-weekly-lesson-plans": {
    "task": "app.tasks.lesson_plan_tasks.generate_weekly_lesson_plans",
    "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Every Monday 06:00
},
```

The existing `generate-parent-narratives` entry will be added by M5-1-T1 — leave a
comment placeholder:

```python
# M5-1-T1 will add: "generate-parent-narratives" here
```

---

## `lesson_plan_tasks.py`

```python
"""Celery task for weekly lesson plan generation."""

import asyncio
import structlog
from celery import shared_task
from app.core.database import get_async_session
from app.services.lesson_plan_service import LessonPlanService

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="app.tasks.lesson_plan_tasks.generate_weekly_lesson_plans",
    max_retries=0,   # Beat tasks do not retry — next Monday will run again
)
def generate_weekly_lesson_plans(self) -> dict:
    """Celery beat task — runs every Monday 06:00.

    Generates one lesson plan per active class that has at least one
    completed assessment. Does not raise on individual class failures —
    logs errors and continues to the next class.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate_all())
    finally:
        loop.close()


async def _generate_all() -> dict:
    async with get_async_session() as session:
        service = LessonPlanService(session)
        return await service.generate_for_all_active_classes()
```

---

## `LessonPlanService` — Method Signatures

All four methods belong to the same `LessonPlanService` class.

### `generate_for_all_active_classes`

```python
async def generate_for_all_active_classes(self) -> dict:
    """Entry point called by the Celery beat task.

    Loads all active classes that have at least one completed assessment,
    then calls generate_for_class() for each. Errors in individual classes
    are caught and logged — they do not abort the whole batch.

    Returns:
        dict with keys: total_classes, generated, skipped, errors
    """
```

Step-by-step logic:

Step 1 — Load all active classes that have at least one `student_attempts` row with
`status = "COMPLETED"`. Use a subquery to filter:

```python
classes_with_data = await self.db.scalars(
    select(Class)
    .where(
        Class.is_active.is_(True),
        Class.id.in_(
            select(StudentAttempt.class_id)
            .join(Assessment, Assessment.id == StudentAttempt.assessment_id)
            .where(StudentAttempt.status == "COMPLETED")
            .distinct()
        ),
    )
)
```

Step 2 — For each class, call `generate_for_class(class_)`. Wrap in try/except — if
generation fails for one class, log at ERROR level with `class_id` and continue.

Step 3 — Return the summary dict so the Celery task result is inspectable.

### `generate_for_class`

```python
async def generate_for_class(
    self,
    class_: Class,
) -> LessonPlan:
    """Generate a lesson plan for one class.

    Identifies the two weakest subtopics, clusters students into groups,
    retrieves RAG context, calls LLM, stores result, emails teacher.

    Args:
        class_: The Class ORM object to generate for.

    Returns:
        The created LessonPlan row.

    Raises:
        LessonPlanGenerationError: if LLM fails after retry.
    """
```

Step-by-step logic:

Step 1 — Load the class gap map using `GapService.get_class_gap_map`. Identify the
two subtopics with the lowest `class_average` (exclude nodes where `class_average is None`
— cannot plan around unassessed subtopics). If fewer than two subtopics have data,
generate a plan for whatever data exists (minimum one).

Step 2 — Cluster enrolled students into three groups based on their mastery score for
the focus subtopics (use the average across the focus subtopics if there are two):

Group A: `mastery_score < 0.4` — Foundational support
Group B: `mastery_score >= 0.4 and <= 0.7` — Developing
Group C: `mastery_score > 0.7` — Extension

Students with no mastery data go into Group A by default.

Step 3 — Retrieve RAG context. For each focus subtopic, fetch the 3 most similar
`curriculum_chunks` using pgvector cosine similarity against `subtopic.embedding`:

```python
chunks = await self.db.scalars(
    select(CurriculumChunk)
    .where(CurriculumChunk.curriculum_id == class_.curriculum_id)
    .order_by(
        CurriculumChunk.embedding.cosine_distance(focus_subtopic.embedding)
    )
    .limit(3)
)
```

Step 4 — Build and call the LLM. Load the Jinja2 template from
`app/ai/prompts/lesson_plan.jinja2`. Render with the class context, student groups,
and RAG chunks. Call via:

```python
from app.ai.providers.router import get_router
router = get_router()
response = await router.complete(
    task="lesson_plan",
    prompt=rendered_template,
)
```

On timeout (>15 seconds), retry once. If the second attempt also times out, log at
ERROR level with `class_id` and `school_id` and raise `LessonPlanGenerationError`.
Do NOT store a partial plan. Do NOT email the teacher for a failed generation.

Step 5 — Parse and validate the LLM response against `LessonPlanLLMOutput` from
M4-1-T2. If validation fails, log at ERROR with the raw response (truncated to 500
characters) and raise `LessonPlanGenerationError`.

Step 6 — Store the plan:

```python
plan = LessonPlan(
    id=uuid.uuid4(),
    school_id=class_.school_id,
    class_id=class_.id,
    week_start=_current_monday(),
    status="GENERATED",
    generated_plan=validated_output.model_dump(),
    teacher_edits=None,
)
self.db.add(plan)
await self.db.flush()
```

Step 7 — Send email to the teacher via Resend. Use the existing email utility pattern
from auth (magic link emails). Subject: "Your lesson plan for this week is ready".
Body: teacher's first name, class name, a brief summary of the two focus subtopics,
and a link to `{FRONTEND_URL}/teacher/classes/{class_id}/lesson-plans`. If the email
fails, log at WARNING level — do not raise. The plan is already stored; missing the
email is recoverable.

### `_current_monday`

```python
def _current_monday() -> date:
    """Return the date of the most recent Monday (or today if Monday)."""
    today = date.today()
    return today - timedelta(days=today.weekday())
```

---

## Jinja2 Prompt Template (`lesson_plan.jinja2`)

```jinja2
System: You are an experienced {{ curriculum_code }} {{ subject_name }} teacher
        creating a differentiated weekly lesson plan.
        Return ONLY valid JSON — no preamble, no markdown fences.

Class: {{ class_name }}, Grade {{ grade_level }}, {{ academic_year }}

Focus areas this week (lowest mastery in the class):
{% for subtopic in focus_subtopics %}
- {{ subtopic.name }} (class average: {{ "%.0f"|format(subtopic.class_average * 100) }}%)
{% endfor %}

Student groups:
- Group A ({{ group_a_count }} students, foundational): mastery below 40%
- Group B ({{ group_b_count }} students, developing): mastery 40–70%
- Group C ({{ group_c_count }} students, extension): mastery above 70%

Curriculum context:
{{ rag_context }}

Return this JSON structure exactly:
{
  "week_start": "{{ week_start }}",
  "focus_subtopic_ids": {{ focus_subtopic_ids | tojson }},
  "class_summary": "<2 sentences summarising the main gap and opportunity>",
  "student_groups": {
    "A": { "count": {{ group_a_count }}, "focus": "<activity description, max 40 words>" },
    "B": { "count": {{ group_b_count }}, "focus": "<activity description, max 40 words>" },
    "C": { "count": {{ group_c_count }}, "focus": "<activity description, max 40 words>" }
  },
  "lesson_structure": {
    "starter_10min": "<whole-class activity, max 50 words>",
    "main_activity_30min": {
      "group_A": "<tailored activity for foundational group, max 60 words>",
      "group_B": "<tailored activity for developing group, max 60 words>",
      "group_C": "<tailored activity for extension group, max 60 words>"
    },
    "plenary_10min": "<whole-class closing, max 50 words>",
    "homework": "<optional homework suggestion, max 40 words>"
  },
  "teacher_notes": "<optional tip for the teacher, max 40 words>"
}
```

---

## Acceptance Criteria

**Unit tests — `test_lesson_plan_service.py`**

`test_cluster_students_when_mastery_below_0_4_then_group_a` — Call the clustering
logic with a student mastery of 0.35. Assert the student is placed in Group A.

`test_cluster_students_when_mastery_0_4_exactly_then_group_b` — Mastery = 0.4 is
the lower boundary of Group B. Assert placement in Group B, not Group A.

`test_cluster_students_when_mastery_0_7_exactly_then_group_c` — Mastery = 0.7 is
the lower boundary of Group C. Assert placement in Group C.

`test_cluster_students_when_no_mastery_data_then_group_a` — A student with
`mastery_score = None` should default to Group A. Assert this.

`test_focus_subtopics_when_multiple_subtopics_then_two_lowest_selected` — Build a
gap map with five subtopics with averages [0.8, 0.3, 0.6, 0.2, 0.5]. Assert the two
selected focus subtopics have averages 0.2 and 0.3.

`test_focus_subtopics_when_all_unassessed_then_skips_class` — Build a gap map where
all nodes have `class_average = None`. Assert the service skips this class without
calling the LLM.

`test_generate_for_class_when_llm_timeout_then_retries_once_and_raises` — Mock the
LLM router to always raise `TimeoutError`. Assert `LessonPlanGenerationError` is
raised after exactly two LLM call attempts (one + one retry).

`test_generate_for_class_when_llm_returns_invalid_json_then_raises` — Mock the LLM
to return a string that is not valid JSON. Assert `LessonPlanGenerationError` is
raised and no `LessonPlan` row is written to the DB.

`test_generate_for_all_classes_when_one_fails_then_others_still_generated` — Set up
two classes. Mock the LLM to succeed for the first class and raise an error for the
second. Assert the first class has a `LessonPlan` row in the DB and the error summary
dict shows `errors: 1` and `generated: 1`.

`test_current_monday_when_tuesday_then_returns_last_monday` — Call `_current_monday()`
on a Tuesday. Assert the returned date is the previous Monday (not the upcoming Monday).

**Integration tests — `test_lesson_plan_generation.py`**

`test_task_when_class_has_completed_assessments_then_plan_created` — Seed a class
with one completed assessment and gap states. Run `_generate_all()` with a mocked
LLM router. Assert one `LessonPlan` row is created in the DB with
`status = "GENERATED"`.

`test_task_when_class_has_no_completed_assessments_then_no_plan_created` — Seed a
class with no completed assessments. Run the task. Assert no `LessonPlan` row is
created.

---

## Do NOT Touch

`backend/app/services/gap_service.py` — use `GapService.get_class_gap_map()` as-is.
`backend/app/schemas/lesson_plans.py` — defined in M0-10-T1, do not modify.
`backend/app/api/v1/routes/lesson_plans.py` — defined in M0-10-T5, do not modify here.
Any existing Celery task file (`onboarding_tasks.py`, `gap_tasks.py`).
