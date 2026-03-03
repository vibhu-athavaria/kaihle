# M5-1-T1 — Parent Narrative Generation (Celery Beat Task)

**Milestone:** M5 — Parent Portal
**Epic:** M5-1 — Parent Narratives
**Task ID:** M5-1-T1
**Depends on:** M2-1-T1 (gap map service), M0-1-T2 (Celery + Redis), M4-1-T1 (beat schedule pattern)
**Blocks:** M5-1-T2 (API needs stored narratives to serve)

---

## User Story

As a parent, I want to receive a weekly plain-English summary of my child's progress so I can stay informed without needing to understand educational jargon.

---

## What To Build

A Celery beat task that runs every Sunday at 18:00. For each student who had gap state activity in the last 7 days, it generates a 150-word narrative, stores it in `parent_report_snapshots`, and emails all linked parents.

---

## Files To Create / Modify

```
/backend/app/tasks/
  parent_tasks.py               ← NEW

/backend/app/services/
  parent_report_service.py      ← NEW

/backend/app/ai/prompts/
  parent_narrative.jinja2       ← NEW

/backend/app/tasks/
  celery_app.py                 ← MODIFY — add beat schedule entry
```

---

## Beat Schedule Entry

```python
# Add to celery_app.py beat_schedule dict:
"generate-parent-narratives": {
    "task": "tasks.generate_parent_narratives",
    "schedule": crontab(hour=18, minute=0, day_of_week=0),  # Sunday
},
```

---

## `parent_tasks.py`

```python
@shared_task(name="tasks.generate_parent_narratives")
def generate_parent_narratives():
    import asyncio
    asyncio.run(_generate_all_narratives())

async def _generate_all_narratives():
    async with get_async_session() as session:
        service = ParentReportService(session)
        await service.generate_for_all_active_students()
```

---

## `parent_report_service.py`

```python
class ParentReportService:

    async def generate_for_all_active_students(self) -> None:
        """
        Find all students with gap_state activity in the last 7 days.
        Generate and store a narrative for each. Email linked parents.
        """
        week_start = self._get_current_week_start()  # Monday of this week
        active_students = await self._get_students_with_recent_activity(days=7)

        for student in active_students:
            try:
                await self.generate_for_student(student.id, week_start)
            except Exception as e:
                logger.error("parent_narrative_failed",
                             student_id=str(student.id), error=str(e))
                # Never let one student failure block others

    async def generate_for_student(self, student_id: UUID, week_start: date) -> None:
        # Idempotent — skip if narrative already exists for this week
        existing = await self._get_existing_snapshot(student_id, week_start)
        if existing:
            return

        # Load current gap map
        gap_map = await self.gap_service.get_student_gap_map(student_id)
        if not gap_map.subtopics:
            return  # No data to narrate

        # Compute week-over-week delta
        prev_snapshot = await self._get_previous_snapshot(student_id, week_start)
        improvements, gaps = self._compute_delta(gap_map, prev_snapshot)

        # Load student info
        student = await self._get_student_with_profile(student_id)

        # Generate narrative
        narrative = await self._generate_narrative(student, gap_map, improvements, gaps)

        # Store snapshot
        snapshot = await self._store_snapshot(
            student_id=student_id,
            school_id=student.school_id,
            week_start=week_start,
            narrative=narrative,
            gap_summary=self._build_gap_summary(gap_map),
            improvements=improvements,
            gaps=gaps,
        )

        # Email all linked parents
        parents = await self._get_linked_parents(student_id)
        if not parents:
            return  # No linked parents — skip silently, no error

        for parent in parents:
            await self._send_parent_email(parent, student, snapshot)

    def _compute_delta(
        self, current_gap_map, prev_snapshot
    ) -> tuple[list[str], list[str]]:
        """
        Compare current mastery to last week's gap_summary.
        Returns:
          improvements: list of subtopic names with largest positive delta (top 2)
          gaps: list of subtopic names with lowest current mastery (top 2)
        """
        if prev_snapshot is None:
            # First report — no delta, just show current state
            sorted_by_mastery = sorted(
                current_gap_map.subtopics, key=lambda s: s.mastery_score
            )
            gaps = [s.subtopic_name for s in sorted_by_mastery[:2]]
            improvements = []
            return improvements, gaps

        prev_scores = {
            item["subtopic_id"]: item["mastery_score"]
            for item in prev_snapshot.gap_summary.get("subtopics", [])
        }

        deltas = []
        for subtopic in current_gap_map.subtopics:
            prev = prev_scores.get(str(subtopic.subtopic_id), subtopic.mastery_score)
            delta = subtopic.mastery_score - prev
            deltas.append((subtopic.subtopic_name, delta, subtopic.mastery_score))

        # Top 2 improvements (highest positive delta)
        improvements = [
            name for name, delta, _ in sorted(deltas, key=lambda x: -x[1])[:2]
            if delta > 0.05  # Only report meaningful improvements
        ]

        # Top 2 gaps (lowest current mastery)
        gaps = [
            name for name, _, mastery in sorted(deltas, key=lambda x: x[2])[:2]
            if mastery < 0.7
        ]

        return improvements, gaps

    async def _generate_narrative(self, student, gap_map, improvements, gaps) -> str:
        """Call Gemini Flash with 150-word limit."""
        prompt = self._build_prompt(student, gap_map, improvements, gaps)
        provider = get_provider(task="parent_narrative")
        response = await asyncio.wait_for(
            provider.complete(LLMRequest(
                task="parent_narrative",
                prompt=prompt,
                system_prompt=(
                    "You are a friendly school progress reporter. Write in warm, "
                    "plain language for parents. Maximum 150 words. No jargon. "
                    "No scores or percentages."
                ),
                max_tokens=250,
                temperature=0.5,
                metadata={},
            )),
            timeout=10.0
        )
        return response.content
```

---

## Prompt Template (`parent_narrative.jinja2`)

```jinja2
Write a short weekly progress update for a parent.

Student: {{ student_first_name }}, Grade {{ grade_level }}
Subject: {{ subject_name }}

{% if improvements %}
This week {{ student_first_name }} showed improvement in:
{% for topic in improvements %}- {{ topic }}
{% endfor %}
{% endif %}

Areas still being developed:
{% for topic in gaps %}- {{ topic }}
{% endfor %}

Suggested next steps for home support:
{% for step in next_steps %}- {{ step }}
{% endfor %}

Write 2-3 sentences in a warm, encouraging tone.
Do not use numbers, percentages, or technical terms.
Maximum 150 words.
```

---

## Parent Email Template

```
Subject: {{ student_first_name }}'s weekly progress update — {{ subject_name }}

Hi {{ parent_first_name }},

Here's {{ student_first_name }}'s progress this week in {{ subject_name }}:

{{ narrative }}

View the full progress dashboard:
{{ portal_url }}/parent/children/{{ student_id }}/progress

—
The Kaihle Team
```

---

## `parent_report_snapshots` Table Reference

From `kaihle_v2_1_schema.sql`:
```sql
parent_report_snapshots
  id            UUID PK
  student_id    UUID FK → users
  school_id     UUID FK → schools
  week_start    DATE NOT NULL
  narrative     TEXT NOT NULL          -- 150-word LLM output
  gap_summary   JSONB                  -- { subtopics: [{subtopic_id, subtopic_name, mastery_score}] }
  created_at    TIMESTAMPTZ
  UNIQUE(student_id, week_start)
```

---

## Acceptance Criteria

- [ ] Unit test: student with no linked parents → skips silently, no error raised
- [ ] Unit test: `_compute_delta` — mastery 0.3→0.65 (+0.35) appears in improvements
- [ ] Unit test: `_compute_delta` with no previous snapshot → returns empty improvements, top 2 gaps
- [ ] Unit test: delta < 0.05 threshold → not reported as improvement
- [ ] Unit test: student with no gap activity in 7 days → not included in run
- [ ] Unit test: existing snapshot for current week → skipped (idempotent)
- [ ] Unit test: LLM timeout → logs error, continues to next student
- [ ] Integration test: narrative stored in `parent_report_snapshots` with correct `student_id` and `week_start`
- [ ] Integration test: parent email sent via Resend mock with student first name in subject
- [ ] Integration test: one student failure → other students still get reports

---

## Output (what M5-1-T2 needs)

- `parent_report_snapshots` table populated with real weekly narratives
- `ParentReportService.generate_for_student()` callable on-demand for testing
- Beat task registered at `tasks.generate_parent_narratives`
