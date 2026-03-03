# M4-1-T1 — Weekly Lesson Plan Celery Beat Task

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T1
**Depends on:** M4-1-T2 (lesson plan schema — must be defined first so this task knows what to store), M2-1-T1 (gap map service), M0-1-T2 (Celery infrastructure)
**Blocks:** M4-1-T3, M4-1-T4

---

## User Story

As a teacher, I want to automatically receive an AI-generated weekly lesson plan every Monday morning so I can start the week prepared without extra admin work.

---

## What To Build

A Celery beat task that runs every Monday at 06:00 and generates one lesson plan per active class that has at least one completed assessment. It loads the class gap map, identifies the two weakest subtopics, clusters students into three groups, retrieves RAG context, calls GPT-4.1, stores the result, and emails the teacher.

---

## Files To Create / Modify

```
/backend/app/tasks/
  lesson_plan_tasks.py          ← NEW
  celery_app.py                 ← MODIFY — add beat schedule entry

/backend/app/services/
  lesson_plan_service.py        ← NEW

/backend/app/ai/prompts/
  lesson_plan.jinja2            ← NEW
```

---

## Implementation

### `lesson_plan_tasks.py`

```python
from celery import shared_task
from app.services.lesson_plan_service import LessonPlanService
from app.core.database import get_async_session
import structlog

logger = structlog.get_logger()

@shared_task(name="tasks.generate_weekly_lesson_plans")
def generate_weekly_lesson_plans():
    """
    Celery beat task — runs every Monday 06:00.
    Generates one lesson plan per active class with completed assessments.
    """
    import asyncio
    asyncio.run(_generate_all())

async def _generate_all():
    async with get_async_session() as session:
        service = LessonPlanService(session)
        await service.generate_for_all_active_classes()
```

### Beat schedule entry in `celery_app.py`
```python
app.conf.beat_schedule = {
    "generate-weekly-lesson-plans": {
        "task": "tasks.generate_weekly_lesson_plans",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Monday
    },
    # M5 will add: "generate-parent-narratives" here
}
```

### `lesson_plan_service.py`

```python
class LessonPlanService:

    async def generate_for_all_active_classes(self) -> None:
        """Entry point called by Celery beat task."""
        active_classes = await self._get_active_classes_with_assessments()
        for cls in active_classes:
            try:
                await self.generate_for_class(cls.id, cls.teacher_id, cls.school_id)
            except Exception as e:
                logger.error("lesson_plan_generation_failed",
                             class_id=str(cls.id), error=str(e))
                # Continue to next class — never let one failure block others

    async def generate_for_class(
        self, class_id: UUID, teacher_id: UUID, school_id: UUID
    ) -> LessonPlan:
        """
        Full generation pipeline for one class.
        Returns the stored LessonPlan or raises on unrecoverable error.
        """
        week_start = self._get_current_week_monday()

        # Idempotent: skip if plan already exists for this week
        existing = await self._get_existing_plan(class_id, week_start)
        if existing:
            return existing

        # Step 1: Load gap map
        gap_map = await self.gap_service.get_class_gap_map(class_id)
        if not gap_map.subtopics:
            logger.info("lesson_plan_skipped_no_gap_data", class_id=str(class_id))
            return None

        # Step 2: Find 2 weakest subtopics
        focus_subtopics = self._get_weakest_subtopics(gap_map, n=2)

        # Step 3: Cluster students
        groups = self._cluster_students(gap_map, focus_subtopics)

        # Step 4: RAG context
        rag_chunks = await self.rag_retriever.get_chunks_for_subtopics(
            [s.id for s in focus_subtopics], top_k=3
        )

        # Step 5: Build + call LLM (GPT-4.1, 15s hard timeout)
        prompt = self._build_prompt(gap_map, focus_subtopics, groups, rag_chunks)
        llm_response = await self._call_llm_with_retry(prompt)

        if llm_response is None:
            logger.error("lesson_plan_llm_failed_after_retry", class_id=str(class_id))
            return None  # Do NOT store partial plan, do NOT email teacher

        # Step 6: Validate + store
        plan_data = self._parse_and_validate(llm_response)
        lesson_plan = await self._store_plan(
            class_id, teacher_id, school_id, week_start, plan_data, focus_subtopics
        )

        # Step 7: Email teacher
        await self._notify_teacher(teacher_id, lesson_plan)

        return lesson_plan

    def _get_weakest_subtopics(self, gap_map, n: int = 2):
        """Return n subtopics with lowest class average mastery."""
        return sorted(
            gap_map.subtopics,
            key=lambda s: s.class_average_mastery
        )[:n]

    def _cluster_students(self, gap_map, focus_subtopics) -> dict:
        """
        Group students by their average mastery across the focus subtopics.
        A: < 0.4, B: 0.4-0.7, C: > 0.7
        """
        student_scores = {}
        for subtopic in focus_subtopics:
            for student in subtopic.student_scores:
                scores = student_scores.setdefault(student.student_id, [])
                scores.append(student.mastery_score)

        groups = {"A": [], "B": [], "C": []}
        for student_id, scores in student_scores.items():
            avg = sum(scores) / len(scores)
            if avg < 0.4:
                groups["A"].append(student_id)
            elif avg <= 0.7:
                groups["B"].append(student_id)
            else:
                groups["C"].append(student_id)
        return groups

    async def _call_llm_with_retry(self, prompt: str) -> str | None:
        """Call GPT-4.1 with 15s timeout. Retry once on failure."""
        provider = get_provider(task="lesson_plan")
        for attempt in range(2):
            try:
                response = await asyncio.wait_for(
                    provider.complete(LLMRequest(
                        task="lesson_plan",
                        prompt=prompt,
                        system_prompt="You are an expert curriculum lesson planner. Return ONLY valid JSON.",
                        max_tokens=1500,
                        temperature=0.4,
                        metadata={},
                    )),
                    timeout=15.0
                )
                return response.content
            except asyncio.TimeoutError:
                logger.warning("lesson_plan_llm_timeout", attempt=attempt + 1)
        return None  # Both attempts failed
```

---

## Prompt Template (`lesson_plan.jinja2`)

```jinja2
You are an expert {{ curriculum_code }} {{ subject_name }} teacher
planning a 50-minute lesson for Grade {{ grade_level }}.
Return ONLY valid JSON — no preamble, no markdown fences.

Class: {{ total_students }} students total.

Focus subtopics (lowest class mastery):
{% for s in focus_subtopics %}
- {{ s.name }}: class average {{ "%.0f"|format(s.class_average * 100) }}%
{% endfor %}

Student groups:
- Group A ({{ groups.A|length }} students, mastery < 40%): need foundational support
- Group B ({{ groups.B|length }} students, mastery 40-70%): consolidating understanding
- Group C ({{ groups.C|length }} students, mastery > 70%): ready for extension

Curriculum context:
{{ rag_context }}

Return JSON matching exactly this structure:
{
  "week_start": "{{ week_start }}",
  "focus_subtopic_ids": {{ focus_subtopic_ids | tojson }},
  "class_summary": "2-3 sentence plain English summary of where the class is",
  "student_groups": {
    "A": { "count": {{ groups.A|length }}, "focus": "one sentence describing their activity focus" },
    "B": { "count": {{ groups.B|length }}, "focus": "one sentence" },
    "C": { "count": {{ groups.C|length }}, "focus": "one sentence" }
  },
  "lesson_structure": {
    "starter_10min": "description of starter activity for whole class",
    "main_activity_30min": {
      "group_A": "specific activity for Group A",
      "group_B": "specific activity for Group B",
      "group_C": "specific activity for Group C"
    },
    "plenary_10min": "whole class plenary activity",
    "homework": "one homework task suitable for all groups"
  },
  "teacher_notes": "any tips or watch-outs for this lesson"
}
```

---

## Teacher Notification Email

Sent via Resend after successful plan storage:

```
Subject: Your lesson plan for this week is ready — [Subject Name]

Hi [Teacher First Name],

Your AI-generated lesson plan for [Class Name] is ready for week starting [date].

Focus: [Subtopic 1] and [Subtopic 2]

View and edit your plan: [link to /teacher/classes/{class_id}/lesson-plans]

—
Kaihle
```

---

## Acceptance Criteria

- [ ] Unit test: `_get_weakest_subtopics` returns 2 subtopics with lowest `class_average_mastery`
- [ ] Unit test: `_cluster_students` — scores [0.2, 0.3, 0.55, 0.65, 0.9] → A:2, B:2, C:1
- [ ] Unit test: class with no gap data → task skips gracefully, no plan created
- [ ] Unit test: LLM timeout on both attempts → returns None, no plan stored, no email sent
- [ ] Unit test: existing plan for current week → skipped (idempotent)
- [ ] Integration test: beat trigger → plans stored for all active classes within 5 minutes
- [ ] Integration test: teacher receives Resend email with correct subject line
- [ ] Integration test: one class fails LLM → other classes still get plans (no propagation)
- [ ] Unit test: `_call_llm_with_retry` retries exactly once on TimeoutError

---

## Output (what M4-1-T3 needs)

- `lesson_plans` table populated with generated plans (via `_store_plan`)
- `LessonPlanService.generate_for_class()` callable on-demand (used by regenerate endpoint in M4-1-T3)
- Beat task registered in Celery app
