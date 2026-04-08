# M4-1-T1 — Weekly Lesson Plan Celery Beat Task (UPDATED)

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T1
**Depends on:** M4-1-T2 (lesson plan schema), M2-1-T1 (gap map service), M0-1-T2 (Celery infra)
**Blocks:** M4-1-T3, M4-1-T4

> **UPDATED March 2026:** Prompt template replaced with a rich, Vidhya-quality
> curriculum-anchored prompt derived from `test_lesson_gen.py` (standalone research
> harness). Key additions:
> - VARK learning style injection — profile description + preferred/avoid activity lists
> - Explicit diagnostic gap targeting — LLM must state WHERE and HOW each gap is addressed
> - Cambridge objective codes required in output
> - Full timeline with per-item timings (not flat 4-section structure)
> - LLM model sourced from `LLM_LESSON_PLAN_MODEL` env var (defaults to Claude Sonnet 4.6
>   via OpenRouter); GPT-4.1 hardcode removed

---

## User Story

As a teacher, I want to automatically receive an AI-generated weekly lesson plan every
Monday morning so I can start the week prepared without extra admin work.

---

## Files To Create / Modify

```
/backend/app/tasks/
  lesson_plan_tasks.py              ← NEW (replaces placeholder)
  celery_app.py                     ← MODIFY — add beat schedule entry

/backend/app/services/
  lesson_plan_service.py            ← NEW

/backend/app/ai/prompts/
  lesson_plan_system.jinja2         ← NEW (system prompt)
  lesson_plan_user.jinja2           ← NEW (user prompt — per-class context injected here)
```

---

## Environment Variables

Add to `.env.example` and Render dashboard:

```
# Lesson plan generation
LLM_LESSON_PLAN_MODEL=openrouter/anthropic/claude-sonnet-4-6
LLM_LESSON_PLAN_TIMEOUT_S=90
LLM_LESSON_PLAN_MAX_TOKENS=4000
LLM_LESSON_PLAN_TEMPERATURE=0.7
```

**Why 90s timeout?** Rich lesson plans require ~3500 tokens of output. Claude Sonnet
takes ~85s for a high-quality plan (observed in test harness). The previous 15s timeout
guaranteed failures on any quality model. OpenRouter is the provider; self-hosted vLLM
via RunPod Serverless is the eventual target.

---

## Implementation

### `lesson_plan_tasks.py`

```python
from celery import shared_task
from app.services.lesson_plan_service import LessonPlanService
from app.core.database import get_async_session
import asyncio
import structlog

logger = structlog.get_logger()


@shared_task(name="tasks.generate_weekly_lesson_plans")
def generate_weekly_lesson_plans() -> None:
    """
    Celery beat task — runs every Monday 06:00.
    Generates one lesson plan per active class with completed assessments.
    """
    asyncio.run(_generate_all())


async def _generate_all() -> None:
    async with get_async_session() as session:
        service = LessonPlanService(session)
        await service.generate_for_all_active_classes()
```

### Beat schedule entry in `celery_app.py`

```python
app.conf.beat_schedule = {
    "generate-weekly-lesson-plans": {
        "task": "tasks.generate_weekly_lesson_plans",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Monday 06:00
    },
    # M5 adds: "generate-parent-narratives"
}
```

---

### `lesson_plan_service.py`

```python
import os
import asyncio
from uuid import UUID
from datetime import date, timedelta

import litellm
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.lesson_plan import LessonPlanLLMOutput, LearningStyleSlug
from app.services.gap_service import GapService
from app.models.lesson_plan import LessonPlan
from app.core.email import send_lesson_plan_email

logger = structlog.get_logger()

# ── VARK profiles — mirrors test_lesson_gen.py LearningStyleProfile ──────────
# Sourced from student learning profile (onboarding questionnaire).
# If a class has mixed styles, LearningStyleSlug.MIXED is passed and the
# prompt defaults to a balanced multi-modal approach.

VARK_PROFILES = {
    LearningStyleSlug.VISUAL: {
        "label": "Visual Learner",
        "description": (
            "Learns best through diagrams, charts, colour-coding, and spatial organisation. "
            "Thinks in pictures. Struggles with dense text-only explanations."
        ),
        "preferred": [
            "mind maps and concept webs",
            "annotated diagrams and labelling tasks",
            "colour-coded notes and graphic organisers",
            "video demonstrations and animations",
            "comparing before/after visuals",
        ],
        "avoid": [
            "long unbroken blocks of text",
            "purely verbal instruction without visual anchor",
        ],
    },
    LearningStyleSlug.KINESTHETIC: {
        "label": "Kinesthetic Learner",
        "description": (
            "Learns through doing, experimenting, and physical engagement. "
            "Needs to touch, build, or move to consolidate understanding. "
            "Gets restless with passive seat-work."
        ),
        "preferred": [
            "hands-on experiments and lab work",
            "role-play and physical simulations",
            "building models or prototypes",
            "card-sort and matching activities",
            "station rotations with physical tasks",
        ],
        "avoid": [
            "extended listening or watching without action",
            "lengthy written tasks as the primary mode",
        ],
    },
    LearningStyleSlug.AUDITORY: {
        "label": "Auditory Learner",
        "description": (
            "Learns through listening, discussion, and verbalising ideas. "
            "Benefits from talking through problems aloud."
        ),
        "preferred": [
            "think-pair-share discussions",
            "teacher-led questioning and Socratic dialogue",
            "peer explanation (teach-back) tasks",
            "verbal summarising and oral quizzes",
        ],
        "avoid": [
            "silent independent work as the main activity",
            "reading-heavy tasks without discussion follow-up",
        ],
    },
    LearningStyleSlug.READING_WRITING: {
        "label": "Reading/Writing Learner",
        "description": (
            "Learns through reading, note-taking, and written expression. "
            "Thrives with lists, definitions, and structured notes."
        ),
        "preferred": [
            "structured Cornell or two-column note-taking",
            "reading and annotating source texts",
            "written summaries and paraphrasing tasks",
            "definition glossaries and vocabulary banks",
        ],
        "avoid": [
            "tasks that require no writing at all",
            "heavily visual tasks with no written component",
        ],
    },
    LearningStyleSlug.MIXED: {
        "label": "Mixed / No Dominant Style",
        "description": "Class has no dominant learning style. Use a balanced multi-modal approach.",
        "preferred": [
            "varied activity types across visual, kinesthetic, and discussion",
            "student choice in how they demonstrate understanding",
        ],
        "avoid": [
            "designing for only one modality",
        ],
    },
}

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../ai/prompts")
_jinja_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR))

MODEL       = os.getenv("LLM_LESSON_PLAN_MODEL", "openrouter/anthropic/claude-sonnet-4-6")
TIMEOUT_S   = float(os.getenv("LLM_LESSON_PLAN_TIMEOUT_S", "90"))
MAX_TOKENS  = int(os.getenv("LLM_LESSON_PLAN_MAX_TOKENS", "4000"))
TEMPERATURE = float(os.getenv("LLM_LESSON_PLAN_TEMPERATURE", "0.7"))
API_KEY     = os.getenv("OPENROUTER_API_KEY", "")


class LessonPlanService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gap_service = GapService(session)

    # ── Entry point ───────────────────────────────────────────────────────────

    async def generate_for_all_active_classes(self) -> None:
        """Called by Celery beat every Monday 06:00."""
        active_classes = await self._get_active_classes()
        logger.info("lesson_plan_batch_start", class_count=len(active_classes))

        for cls in active_classes:
            try:
                await self._generate_for_class(cls)
            except Exception as exc:
                logger.error(
                    "lesson_plan_class_failed",
                    class_id=str(cls.id),
                    error=str(exc),
                )
                # Continue to next class — one failure must not block others

    # ── Per-class generation ──────────────────────────────────────────────────

    async def _generate_for_class(self, cls) -> None:
        gap_map        = await self.gap_service.get_class_gap_map(cls.id)
        focus_subtopics = self._get_weakest_subtopics(gap_map, n=2)
        student_groups  = self._cluster_students(gap_map, focus_subtopics)
        rag_context     = await self._get_subtopic_context(focus_subtopics)
        learning_style  = await self._get_dominant_style(cls.id)
        vark_profile    = VARK_PROFILES[learning_style]
        week_start      = self._current_week_start()

        system_prompt = self._render_system_prompt()
        user_prompt   = self._render_user_prompt(
            cls=cls,
            gap_map=gap_map,
            focus_subtopics=focus_subtopics,
            student_groups=student_groups,
            rag_context=rag_context,
            vark_profile=vark_profile,
            week_start=week_start,
        )

        validated = await self._call_llm_with_retry(system_prompt, user_prompt)
        if validated is None:
            logger.error("lesson_plan_generation_failed", class_id=str(cls.id))
            return  # Do NOT store partial plan, do NOT email teacher

        plan = await self._store_plan(
            class_id=cls.id,
            teacher_id=cls.teacher_id,
            validated=validated,
            ai_model=MODEL,
        )
        await send_lesson_plan_email(teacher_id=cls.teacher_id, plan_id=plan.id)
        logger.info("lesson_plan_complete", class_id=str(cls.id), plan_id=str(plan.id))

    # ── LLM call ──────────────────────────────────────────────────────────────

    async def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LessonPlanLLMOutput | None:
        """
        Call LLM with TIMEOUT_S timeout. Retry once on failure or validation error.
        Returns None if both attempts fail — caller handles gracefully.
        """
        is_openrouter = MODEL.startswith("openrouter/")
        kwargs: dict = dict(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        if API_KEY and is_openrouter:
            kwargs["api_key"] = API_KEY

        for attempt in range(2):
            try:
                response = await asyncio.wait_for(
                    litellm.acompletion(**kwargs),
                    timeout=TIMEOUT_S,
                )
                raw = response.choices[0].message.content or ""
                validated = await self._parse_and_validate(raw)
                if validated is not None:
                    return validated
                logger.warning(
                    "lesson_plan_validation_retry",
                    attempt=attempt + 1,
                )
            except asyncio.TimeoutError:
                logger.warning("lesson_plan_timeout", attempt=attempt + 1, timeout=TIMEOUT_S)
            except Exception as exc:
                logger.warning("lesson_plan_llm_error", attempt=attempt + 1, error=str(exc))

        return None  # Both attempts failed

    # ── Prompt rendering ──────────────────────────────────────────────────────

    def _render_system_prompt(self) -> str:
        tmpl = _jinja_env.get_template("lesson_plan_system.jinja2")
        return tmpl.render()

    def _render_user_prompt(self, *, cls, gap_map, focus_subtopics,
                            student_groups, rag_context, vark_profile,
                            week_start: date) -> str:
        tmpl = _jinja_env.get_template("lesson_plan_user.jinja2")
        return tmpl.render(
            curriculum_code=cls.curriculum_code,
            grade_level=cls.grade_level,
            subject_name=cls.subject_name,
            lesson_duration_min=60,
            week_start=week_start.isoformat(),
            focus_subtopics=[s.name for s in focus_subtopics],
            learning_objectives=self._get_learning_objectives(focus_subtopics),
            diagnostic_gaps=[s.gap_description for s in focus_subtopics],
            gap_summary=gap_map.summary_text,
            total_students=gap_map.total_students,
            group_a_count=len(student_groups["A"]),
            group_b_count=len(student_groups["B"]),
            group_c_count=len(student_groups["C"]),
            rag_context=rag_context,
            vark_label=vark_profile["label"],
            vark_description=vark_profile["description"],
            vark_preferred=vark_profile["preferred"],
            vark_avoid=vark_profile["avoid"],
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_weakest_subtopics(self, gap_map, n: int = 2):
        return sorted(gap_map.subtopics, key=lambda s: s.class_average_mastery)[:n]

    def _cluster_students(self, gap_map, focus_subtopics) -> dict:
        student_scores: dict[str, list[float]] = {}
        for subtopic in focus_subtopics:
            for student in subtopic.student_scores:
                student_scores.setdefault(str(student.student_id), []).append(
                    student.mastery_score
                )
        groups: dict[str, list] = {"A": [], "B": [], "C": []}
        for student_id, scores in student_scores.items():
            avg = sum(scores) / len(scores)
            if avg < 0.4:
                groups["A"].append(student_id)
            elif avg <= 0.7:
                groups["B"].append(student_id)
            else:
                groups["C"].append(student_id)
        return groups

    async def _get_subtopic_context(self, focus_subtopics) -> str:
        """
        Load approved explanations from subtopic_content per focus subtopic.
        Falls back to learning_objective text if no approved explanation exists yet.
        REPLACES _get_rag_context() — no curriculum_chunks, no pgvector.
        """
        from app.models.subtopic_content import SubtopicContent
        parts = []
        for subtopic in focus_subtopics:
            content = await self.session.get(SubtopicContent, subtopic.id)
            if content and content.approved_explanation:
                parts.append(
                    f"## {subtopic.name}\n{content.approved_explanation}"
                )
            else:
                parts.append(
                    f"## {subtopic.name}\n{subtopic.learning_objective}"
                )
        return "\n\n---\n\n".join(parts)

    async def _get_dominant_style(self, class_id: UUID) -> LearningStyleSlug:
        """
        Returns the most common learning style across enrolled students in this class.
        Falls back to MIXED if no clear majority or no profiles exist.
        """
        profiles = await self.gap_service.get_class_learning_profiles(class_id)
        if not profiles:
            return LearningStyleSlug.MIXED
        style_counts: dict[str, int] = {}
        for p in profiles:
            if p.dominant_learning_style:
                style_counts[p.dominant_learning_style] = (
                    style_counts.get(p.dominant_learning_style, 0) + 1
                )
        if not style_counts:
            return LearningStyleSlug.MIXED
        dominant = max(style_counts, key=style_counts.__getitem__)
        # Only use dominant style if > 50% of students share it
        if style_counts[dominant] / len(profiles) > 0.5:
            return LearningStyleSlug(dominant)
        return LearningStyleSlug.MIXED

    @staticmethod
    def _current_week_start() -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())  # Monday of current week

    @staticmethod
    def _get_learning_objectives(focus_subtopics) -> list[str]:
        objectives = []
        for subtopic in focus_subtopics:
            objectives.extend(subtopic.learning_objectives or [])
        return objectives[:6]  # cap — prompt gets too large beyond 6
```

---

## Prompt Templates

### `lesson_plan_system.jinja2`

```jinja2
You are an expert curriculum designer and classroom teacher specialising in
Cambridge Lower Secondary education (Grades 6–8) for small international schools.

You create lesson plans that are:
- Curriculum-anchored: every activity maps to explicit Cambridge learning objectives
  with objective codes (e.g. 7Pf.01)
- Practically executable: a real teacher can pick this up and teach it today
- Differentiation-aware: activities are specifically shaped to the student's learning style
- Diagnostic-responsive: gaps identified from Kaihle assessment data are explicitly
  addressed — you must state WHERE in the lesson and HOW each gap is tackled
- Time-realistic: all activities fit within the stated lesson duration

Return ONLY valid JSON — no preamble, no markdown fences, no explanation.
The JSON must exactly match this structure:

{
  "week_start": "YYYY-MM-DD",
  "class_summary": "1-2 sentence summary of the class gap situation",
  "learning_style": "visual|kinesthetic|auditory|reading_writing|mixed",
  "lesson_duration_min": 60,
  "learning_objectives": [
    {"code": "7Pf.01", "description": "Define force as a push or pull"}
  ],
  "diagnostic_gaps": [
    {
      "gap_description": "Confusing mass and weight",
      "addressed_where": "Station 1 · Teacher checkpoint min 15",
      "addressed_how": "Students physically compare spring balance (N) vs digital balance (g)"
    }
  ],
  "timeline": [
    {
      "phase": "warmup|bridge|station|debrief|exit|activity",
      "start_min": 0,
      "duration_min": 5,
      "title": "Short activity name",
      "description": "Teacher-facing instructions, 2-5 sentences",
      "gap_targeted": "gap_description value if this activity targets a gap, else null",
      "kinesthetic_tag": "Short UI tag if movement-based, else null",
      "assess_tag": "Short UI tag if assessment happens here, else null"
    }
  ],
  "resources": [
    {"description": "Resource name and any relevant detail"}
  ],
  "teacher_notes": "Safety, pacing, and checkpoint tips for the teacher"
}
```

### `lesson_plan_user.jinja2`

```jinja2
Generate a complete lesson plan for the following context:

CURRICULUM: {{ curriculum_code }}
GRADE: {{ grade_level }}
SUBJECT: {{ subject_name }}
TOPIC: {{ focus_subtopics | join(', ') }}
LESSON DURATION: {{ lesson_duration_min }} minutes
WEEK OF: {{ week_start }}

LEARNING OBJECTIVES:
{% for obj in learning_objectives %}
  - {{ obj }}
{% endfor %}

CLASS GAP SUMMARY: {{ gap_summary }}

DIAGNOSTIC GAPS (from Kaihle assessment data — these MUST be addressed):
{% for gap in diagnostic_gaps %}
  - {{ gap }}
{% endfor %}
For each gap, the output JSON must include an entry in diagnostic_gaps with
addressed_where (which activity and minute) and addressed_how (the specific
mechanism used — not just "discussed", but the hands-on method).

STUDENT GROUPS:
- Group A ({{ group_a_count }} students, mastery < 40%): foundational support needed
- Group B ({{ group_b_count }} students, mastery 40–70%): developing
- Group C ({{ group_c_count }} students, mastery > 70%): ready for extension

TOTAL CLASS SIZE: {{ total_students }} students

TARGET LEARNING STYLE: {{ vark_label }}
Profile description: {{ vark_description }}

Preferred activity types for this learner:
{% for activity in vark_preferred %}
  - {{ activity }}
{% endfor %}

Activities to minimise or avoid:
{% for item in vark_avoid %}
  - {{ item }}
{% endfor %}

Design the lesson so that the delivery methods, task types, and resources are
authentically suited to a {{ vark_label }}. Do not just mention the learning
style — embed it structurally throughout every timeline item.

CURRICULUM CONTEXT (use to ensure activities are aligned to learning objectives):
{{ rag_context }}

Be specific. Avoid generic advice. Every timeline item should be actionable by
a teacher who has never seen this lesson before.
```

---

## Acceptance Criteria

- [ ] Beat task fires every Monday 06:00 (unit test with frozen clock)
- [ ] Plan generated for each active class with ≥ 1 completed assessment
- [ ] `_get_dominant_style()` returns MIXED when < 50% share a style
- [ ] `_get_dominant_style()` returns correct slug when > 50% share a style
- [ ] VARK profile is injected into user prompt (verify via prompt string assertion in unit test)
- [ ] Diagnostic gaps appear in rendered user prompt
- [ ] On LLM timeout: retry once → if second fails → log error → no plan stored → no email
- [ ] On validation failure: retry once → if second fails → log error → no plan stored
- [ ] On success: plan stored with `status = "GENERATED"`, teacher email sent
- [ ] `ai_model` stored on plan row matches `LLM_LESSON_PLAN_MODEL` env var value
- [ ] One class failure does not prevent other classes from generating
- [ ] Unit test: student grouping — scores [0.2, 0.3, 0.55, 0.65, 0.9] → A:2, B:2, C:1
- [ ] Integration test: beat trigger → plans stored for all active classes
