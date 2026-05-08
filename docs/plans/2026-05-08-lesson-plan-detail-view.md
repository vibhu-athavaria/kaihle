# Lesson Plan Detail View — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the richly-structured lesson plan detail view — including LLM streaming, Pydantic validation + correction retry, raw output stored in DB, email notification on completion, and a completely redesigned frontend with a learning-style sidebar (not mastery data).

**Architecture:** Three coordinated layers. (1) Infrastructure: clean up CONSTITUTION.md (remove hardcoded model names/latency), add `raw_llm_output` DB column, add streaming to LLM router, add `LessonPlanContent` Pydantic schema. (2) Backend: rewrite Jinja2 template (learning styles only, no GapState), update Celery task (streaming, Pydantic validation + one correction retry, store raw output in DB, send email on complete/fail). (3) Frontend: remove polling, update types, redesign `LessonPlanDetailPage` with learning-style sidebar.

**Key constraint:** Lesson plans NEVER use GapState or mastery data. They use `StudentLearningProfile.modality_scores` and `interests` only. GapState belongs to study plans.

**Tech Stack:** FastAPI + SQLAlchemy async, Alembic, Pydantic v2, Jinja2, LiteLLM (streaming), Celery, Resend email, structlog, React + TypeScript, React Query (no polling), Tailwind CSS (token names only), Lucide React.

---

## What Already Exists (do NOT recreate)

- `backend/app/services/lesson_plan_service.py` — `generate_lesson_plan`, `list_class_lesson_plans`, `get_lesson_plan`, `edit_lesson_plan`, `update_lesson_plan_status`
- `backend/app/api/v1/routes/lesson_plans.py` — all routes wired
- `backend/app/models/lesson_plan.py` — `LessonPlan` ORM model, `LessonPlanStatus`, `LessonPlanFailureCode`
- `backend/app/schemas/lesson_plans.py` — `LessonPlanResponse`, `GenerateLessonPlanRequest`, `LessonPlanEditRequest`
- `backend/app/ai/providers/router.py` — `complete(task, messages, ...)` async function
- `backend/app/tasks/lesson_plan_tasks.py` — Celery task (needs major update)
- `frontend/apps/teacher/src/hooks/useLessonPlans.ts` — all hooks
- `frontend/apps/teacher/src/pages/lesson-plans/AllLessonPlansPage.tsx` — list page
- `frontend/apps/teacher/src/pages/lesson-plans/LessonPlanDetailPage.tsx` — detail page (needs full redesign)

## Files This Plan Creates or Modifies

| File | Action | Responsibility |
|---|---|---|
| `docs/CONSTITUTION.md` | **Modify** | Remove hardcoded model names + latency from §8 table |
| `backend/app/core/config.py` | **Modify** | Remove LLM model name defaults; add `kaihle_admin_email`, `frontend_url` |
| `backend/alembic/versions/<hash>_add_raw_llm_output.py` | **Create** | Add `raw_llm_output TEXT` column to `lesson_plans` |
| `backend/app/models/lesson_plan.py` | **Modify** | Add `raw_llm_output` mapped column |
| `backend/app/ai/providers/router.py` | **Modify** | Add `stream: bool = False` parameter |
| `backend/app/schemas/lesson_plan_content.py` | **Create** | Pydantic model for LLM output validation |
| `backend/app/ai/prompts/lesson_plan.jinja2` | **Rewrite** | Learning styles only (no mastery); rich JSON schema |
| `backend/app/tasks/lesson_plan_tasks.py` | **Modify** | Streaming, Pydantic validation + retry, raw output to DB, email |
| `backend/app/services/lesson_plan_service.py` | **Modify** | Pass `teacher_id` to task; remove `gap_summary` build |
| `backend/app/tests/unit/test_lesson_plan_tasks.py` | **Create** | Unit tests for task internals |
| `backend/app/tests/unit/test_router.py` | **Create** | Unit tests for streaming |
| `frontend/apps/teacher/src/hooks/useLessonPlans.ts` | **Modify** | New typed interfaces; remove polling |
| `frontend/apps/teacher/src/pages/lesson-plans/LessonPlanDetailPage.tsx` | **Rewrite** | Learning-style sidebar + redesigned content |
| `frontend/apps/teacher/src/pages/lesson-plans/AllLessonPlansPage.tsx` | **Modify** | Remove polling; static generating message |

---

## New `generated_plan` JSON Schema

The contract between the Jinja2 template and the frontend renderer. Stored in `lesson_plans.generated_plan` JSONB.

```json
{
  "lesson_hook": "Today students discover why a ball rolling to a stop doesn't mean forces have disappeared — and why that surprises almost everyone.",
  "time_breakdown": {
    "starter_minutes": 6,
    "intro_minutes": 9,
    "activity_minutes": 30,
    "exit_ticket_minutes": 6,
    "plenary_minutes": 9
  },
  "learning_objectives": [
    "I can define force as a push or pull and tell the difference between contact and non-contact forces.",
    "I can describe what happens to motion when forces are balanced or unbalanced."
  ],
  "key_concepts": [
    {
      "name": "Contact vs. non-contact forces",
      "duration_minutes": 3,
      "teacher_does": "Draw two columns on the board: 'Touching' and 'Not touching'.",
      "student_does": "Call out examples. Copy the two-column heading.",
      "check_question": "Give me one contact force and one non-contact force you've experienced today.",
      "misconception": {
        "student_error": "Students think non-contact forces only work when objects are very close.",
        "trigger_phrase": "But the Earth isn't pulling my pencil — it's just sitting there.",
        "recovery_script": "Drop your pencil. Did you touch it? No — that's gravity acting across distance right now."
      },
      "transition_cue": "Now you know the difference — what happens when two forces act on the same object at once?"
    }
  ],
  "group_activities": {
    "foundation": {
      "description": "Force card sort — physically sort 8 image cards into contact/non-contact piles.",
      "stuck_prompt": "Is the object touching anything right now? Yes = contact. No = non-contact."
    },
    "core": {
      "description": "Nature trail investigation — analyse a distance-time graph of a hiker.",
      "stuck_prompt": "What's the distance between those two points? Divide distance by time."
    },
    "extension": {
      "description": "Design a gaming level — draw a distance-time graph for a game character.",
      "stuck_prompt": "What force would make the slope steeper?"
    }
  },
  "resources_needed": ["8 force image cards · Foundation", "Mini-whiteboards × 16"],
  "exit_ticket": {
    "questions": [
      {
        "label": "Q1 — core understanding",
        "question_text": "A soccer ball rolls to a stop. Are the forces balanced or unbalanced?",
        "good_answer": "Unbalanced — friction acts opposite to motion with no forward force to match it.",
        "pivot_if_wrong": "Most wrong? Spend 2 min re-drawing the force arrows on the board."
      }
    ]
  },
  "starter": { "duration_minutes": 6, "activity": "Think-Pair-Share: 'Think of a time something moved without being touched.'" },
  "plenary": { "duration_minutes": 9, "activity": "3-2-1 reflection: 3 things learned, 2 surprises, 1 question." },
  "prior_knowledge": "Students should know that objects can move and stop, and have encountered speed as distance over time.",
  "homework": "Complete the distance-time graph for a school run using the provided data table."
}
```

## New `gap_summary` Schema (repurposed as class context snapshot)

No GapState data. Stores learning style snapshot at generation time for display in sidebar.

```json
{
  "modality_distribution": {
    "visual": 0.72,
    "auditory": 0.41,
    "reading_writing": 0.55,
    "kinesthetic": 0.63
  },
  "top_interests": ["football", "gaming", "music"],
  "student_count": 16
}
```

---

## Task 1: CONSTITUTION.md + config.py Cleanup

**Files:**
- Modify: `docs/CONSTITUTION.md` — §8 table
- Modify: `backend/app/core/config.py` — LLM model fields + add admin email/frontend URL

No tests for config/docs changes — verified by linting and code review.

- [ ] **Step 1: Update §8 table in `docs/CONSTITUTION.md`**

Find the §8 table and replace the "Default model" and "Max latency" columns with just the env-var table. The table should look like:

```markdown
## 8. LLM Provider Routing

All LLM calls go through `backend/app/ai/providers/router.py` via LiteLLM. Switching providers requires only an environment variable change — no code changes.

| Task | Env var |
|---|---|
| `gap_classification` | `LLM_GAP_CLASSIFICATION_MODEL` |
| `study_plan` | `LLM_STUDY_PLAN_MODEL` |
| `lesson_plan` | `LLM_LESSON_PLAN_MODEL` |
| `student_pack` | `LLM_STUDENT_PACK_MODEL` |

**Note:** pgvector embeddings are not used in v1. `subtopic_content` table (structured SQL) replaces cosine similarity for all content curation. Do not add embedding calls without an ADR.
```

Also remove any `time_limit` or "Max latency" references from this section.

- [ ] **Step 2: Update `backend/app/core/config.py`**

Find the LLM model fields and remove all string defaults (set to `""`). Also add `kaihle_admin_email` and `frontend_url`:

```python
# LLM model routing — configured via environment variables, no defaults here
llm_gap_classification_model: str = ""
llm_gap_classification_api_base: str = ""
llm_study_plan_model: str = ""
llm_study_plan_api_base: str = ""
llm_lesson_plan_model: str = ""
llm_lesson_plan_api_base: str = ""
llm_student_pack_model: str = ""
llm_student_pack_api_base: str = ""

# Notification recipients
kaihle_admin_email: str = Field(default="admin@kaihle.ai", env="KAIHLE_ADMIN_EMAIL")
frontend_url: str = Field(default="http://localhost:3001", env="FRONTEND_URL")
```

- [ ] **Step 3: Commit**

```bash
git add docs/CONSTITUTION.md backend/app/core/config.py
git commit -m "chore: remove hardcoded LLM model names and latency from CONSTITUTION and config"
```

---

## Task 2: DB Migration — Add `raw_llm_output` Column

**Files:**
- Create: `backend/alembic/versions/<hash>_add_raw_llm_output_to_lesson_plans.py`
- Modify: `backend/app/models/lesson_plan.py`

- [ ] **Step 1: Add the column to the ORM model**

Open `backend/app/models/lesson_plan.py` and add after the existing columns:

```python
from sqlalchemy import Text

# ... existing columns ...
raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "add_raw_llm_output_to_lesson_plans"
```

Review the generated file — it should add one column:

```python
def upgrade() -> None:
    op.add_column("lesson_plans", sa.Column("raw_llm_output", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("lesson_plans", "raw_llm_output")
```

- [ ] **Step 3: Apply migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>, add_raw_llm_output_to_lesson_plans`

- [ ] **Step 4: Commit migration + model together**

```bash
git add backend/app/models/lesson_plan.py backend/alembic/versions/
git commit -m "migration(lesson-plan): add raw_llm_output TEXT column to lesson_plans"
```

---

## Task 3: LLM Router — Add Streaming Support

**Files:**
- Modify: `backend/app/ai/providers/router.py`
- Create: `backend/app/tests/unit/test_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/unit/test_router.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_complete_when_stream_true_then_collects_chunks_and_returns_string():
    """When stream=True, complete() collects streamed chunks and returns the combined string."""
    from app.ai.providers.router import complete

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = '{"lesson_hook": '

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = '"hello world"}'

    async def mock_stream(*args, **kwargs):
        for chunk in [chunk1, chunk2]:
            yield chunk

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion.return_value = mock_stream()
        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

    assert result == '{"lesson_hook": "hello world"}'


@pytest.mark.asyncio
async def test_complete_when_stream_false_then_uses_standard_completion():
    """When stream=False (default), complete() returns response.choices[0].message.content."""
    from app.ai.providers.router import complete

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "hello"
    mock_response.usage = MagicMock(total_tokens=10)

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=False,
        )

    assert result == "hello"
    call_kwargs = mock_litellm.acompletion.call_args[1]
    assert call_kwargs.get("stream") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/unit/test_router.py -v
```

Expected: FAIL — `complete()` does not accept `stream` parameter yet.

- [ ] **Step 3: Modify `backend/app/ai/providers/router.py`**

Add `stream: bool = False` to the `complete()` signature and add streaming chunk collection. Keep the existing `max_tokens` default unchanged (do NOT change the global default — only the lesson plan task call site passes `max_tokens=4000`):

```python
async def complete(
    task: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
) -> str:
    """Call the LLM for a given task. Returns the full response text."""
    if task not in TASK_MODEL_MAP:
        raise ValueError(f"Unknown LLM task: {task!r}")

    model = TASK_MODEL_MAP[task]
    api_base = TASK_API_BASE_MAP.get(task)

    log = logger.bind(task=task, model=model, stream=stream)
    log.info("llm_request_started")

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if api_base:
        kwargs["api_base"] = api_base

    response = await litellm.acompletion(**kwargs)

    if stream:
        chunks: list[str] = []
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
        text = "".join(chunks)
        log.info("llm_request_completed_streaming", chars=len(text))
        return text
    else:
        if not response.choices or not response.choices[0].message.content:
            raise ValueError(f"LLM returned empty response for task {task!r}")
        text = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        log.info("llm_request_completed", total_tokens=getattr(usage, "total_tokens", None))
        return text
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest app/tests/unit/test_router.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/providers/router.py backend/app/tests/unit/test_router.py
git commit -m "feat(llm-router): add streaming support with async chunk collection"
```

---

## Task 4: Add `LessonPlanContent` Pydantic Validation Schema

**Files:**
- Create: `backend/app/schemas/lesson_plan_content.py`

No separate test — Pydantic validates at parse time; the task tests in Task 6 exercise this.

- [ ] **Step 1: Create `backend/app/schemas/lesson_plan_content.py`**

```python
"""Pydantic schema for LLM-generated lesson plan content validation."""
from pydantic import BaseModel


class Misconception(BaseModel):
    student_error: str
    trigger_phrase: str
    recovery_script: str


class KeyConcept(BaseModel):
    name: str
    duration_minutes: int
    teacher_does: str
    student_does: str
    check_question: str
    misconception: Misconception
    transition_cue: str | None = None


class GroupActivity(BaseModel):
    description: str
    stuck_prompt: str


class GroupActivities(BaseModel):
    foundation: GroupActivity
    core: GroupActivity
    extension: GroupActivity


class TimedActivity(BaseModel):
    duration_minutes: int
    activity: str


class TimeBreakdown(BaseModel):
    starter_minutes: int
    intro_minutes: int
    activity_minutes: int
    exit_ticket_minutes: int
    plenary_minutes: int


class ExitTicketQuestion(BaseModel):
    label: str
    question_text: str
    good_answer: str
    pivot_if_wrong: str


class ExitTicket(BaseModel):
    questions: list[ExitTicketQuestion]


class LessonPlanContent(BaseModel):
    lesson_hook: str
    time_breakdown: TimeBreakdown
    learning_objectives: list[str]
    key_concepts: list[KeyConcept]
    group_activities: GroupActivities
    resources_needed: list[str]
    exit_ticket: ExitTicket
    starter: TimedActivity
    plenary: TimedActivity
    prior_knowledge: str
    homework: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/lesson_plan_content.py
git commit -m "feat(lesson-plan): add LessonPlanContent Pydantic schema for LLM output validation"
```

---

## Task 5: Rewrite Jinja2 Prompt Template

**Files:**
- Rewrite: `backend/app/ai/prompts/lesson_plan.jinja2`

**Critical:** Template inputs are learning styles + interests only. Never GapState, mastery scores, or student bands.

- [ ] **Step 1: Replace the entire content of `backend/app/ai/prompts/lesson_plan.jinja2`**

```jinja2
You are an expert lesson planning assistant. Design a practical, immediately-usable lesson plan.

## Class context
- **Class:** {{ class_name }}
- **Subject:** {{ subject_name }}
- **Grade:** {{ grade_name }}
- **Students enrolled:** {{ student_count }}
- **Lesson duration:** {{ duration_minutes }} minutes

## Subtopics to cover
{% for s in subtopics %}
- **{{ s.name }}**{% if s.learning_objective %} — {{ s.learning_objective }}{% endif %}
{% endfor %}

## Class learning profile
{% if modality_distribution %}
Learning modality breakdown (use the dominant modality to shape HOW you teach):
{% for modality, score in modality_distribution.items() %}
- {{ modality | replace("_", " ") | capitalize }}: {{ "%.0f" | format(score * 100) }}%
{% endfor %}
Dominant modality: {{ modality_distribution | dictsort(by='value', reverse=True) | first | first | replace("_", " ") | capitalize }}
{% else %}
No learning profile data yet — design for a mixed-modality class (balance visual, discussion, and hands-on activities).
{% endif %}

{% if top_interests %}
Student interests — anchor at least one real-world example to these: {{ top_interests | join(", ") }}
{% endif %}

## Ability groups
The class will split into three groups during the main activity. Design differentiated activities for each:
- **Foundation** — needs scaffolding and concrete examples; guided practice with support prompts
- **Core** — consolidating understanding; application with moderate challenge
- **Extension** — ready to deepen, connect, and apply in novel contexts

## Time budget ({{ duration_minutes }} min total)
- Starter: {{ (duration_minutes * 0.10) | round | int }} min
- Key concepts introduction: {{ (duration_minutes * 0.15) | round | int }} min
- Group activity: {{ (duration_minutes * 0.50) | round | int }} min
- Exit ticket: {{ (duration_minutes * 0.10) | round | int }} min
- Plenary: {{ (duration_minutes * 0.15) | round | int }} min

## Field-by-field instructions
- `lesson_hook`: One compelling, surprising sentence that makes students curious — connects to their interests. DO NOT start with "Today we will learn".
- `learning_objectives`: "I can..." statements for the board. 2–3 objectives only.
- `key_concepts`: 2–4 concepts in teaching sequence. Each must have:
  - `teacher_does`: Specific, named teacher actions — what to write/draw/ask/demonstrate. Example: "Draw a T-chart on the board. Add a football kick (contact) and gravity (non-contact) as first examples."
  - `student_does`: What students actively produce — not just "listen". Example: "Mini-whiteboard response", "Call out examples", "Draw a labelled diagram".
  - `check_question`: One diagnostic question the teacher asks BEFORE advancing to the next concept.
  - `misconception.student_error`: The most common wrong belief for this concept.
  - `misconception.trigger_phrase`: The exact wrong sentence students say.
  - `misconception.recovery_script`: What the teacher says/does to correct it — specific and actionable.
  - `transition_cue`: One bridging sentence to the next concept. Omit (null) on the last concept.
- `group_activities.foundation / core / extension`:
  - `description`: Named activity with specific materials. What does the student DO? Name the worksheet, resource, output.
  - `stuck_prompt`: Exact sentence the teacher says if a student is stuck.
- `resources_needed`: Every physical item needed before class. Example: "8 force image cards · Foundation"
- `exit_ticket.questions`: 2 questions. Q1 = core understanding, Q2 = application.
  - `good_answer`: Model answer a well-understanding student gives.
  - `pivot_if_wrong`: What the teacher does if most students get it wrong — 1–2 sentences, specific.
- `starter`: Named activity (Think-Pair-Share, Predict-Observe, etc.) that activates prior knowledge.
- `plenary`: Named reflection activity (3-2-1, Cold call, Exit slip, etc.).
- `prior_knowledge`: One sentence on assumed prior knowledge.
- `homework`: Optional 15–20 min task, or null.

Return ONLY valid JSON — no markdown fences, no prose before or after:

{
  "lesson_hook": "<string>",
  "time_breakdown": {
    "starter_minutes": <int>,
    "intro_minutes": <int>,
    "activity_minutes": <int>,
    "exit_ticket_minutes": <int>,
    "plenary_minutes": <int>
  },
  "learning_objectives": ["<string>"],
  "key_concepts": [
    {
      "name": "<string>",
      "duration_minutes": <int>,
      "teacher_does": "<string>",
      "student_does": "<string>",
      "check_question": "<string>",
      "misconception": {
        "student_error": "<string>",
        "trigger_phrase": "<string>",
        "recovery_script": "<string>"
      },
      "transition_cue": "<string or null>"
    }
  ],
  "group_activities": {
    "foundation": { "description": "<string>", "stuck_prompt": "<string>" },
    "core":       { "description": "<string>", "stuck_prompt": "<string>" },
    "extension":  { "description": "<string>", "stuck_prompt": "<string>" }
  },
  "resources_needed": ["<string>"],
  "exit_ticket": {
    "questions": [
      {
        "label": "Q1 — core understanding",
        "question_text": "<string>",
        "good_answer": "<string>",
        "pivot_if_wrong": "<string>"
      },
      {
        "label": "Q2 — application",
        "question_text": "<string>",
        "good_answer": "<string>",
        "pivot_if_wrong": "<string>"
      }
    ]
  },
  "starter": { "duration_minutes": <int>, "activity": "<string>" },
  "plenary":  { "duration_minutes": <int>, "activity": "<string>" },
  "prior_knowledge": "<string>",
  "homework": "<string or null>"
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ai/prompts/lesson_plan.jinja2
git commit -m "feat(lesson-plan): rewrite Jinja2 prompt for learning-styles-only input and rich JSON schema"
```

---

## Task 6: Update Celery Task — Streaming, Validation+Retry, DB Storage, Email

**Files:**
- Modify: `backend/app/tasks/lesson_plan_tasks.py`
- Create: `backend/app/tests/unit/test_lesson_plan_tasks.py`

**Architectural rules for this task:**
- No GapState queries. Lesson plan context comes from `StudentLearningProfile` only.
- `plan.gap_summary` stores `{modality_distribution, top_interests, student_count}` as a snapshot.
- `plan.raw_llm_output` stores the raw LLM response text (not a file on disk).
- Remove `time_limit` from the `@celery_app.task` decorator.
- Task signature must include `teacher_id: str` for email routing.
- Pydantic validation: try parse → if fails, send correction prompt once → if second attempt fails, archive with `JSON_PARSE_FAILED`.

- [ ] **Step 1: Write failing tests**

Create `backend/app/tests/unit/test_lesson_plan_tasks.py`:

```python
"""Unit tests for lesson plan Celery task internals."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_plan(status="GENERATING"):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.status = status
    plan.generated_plan = None
    plan.raw_llm_output = None
    plan.failure_code = None
    plan.failure_reason = None
    plan.gap_summary = None
    return plan


def _make_valid_json() -> dict:
    return {
        "lesson_hook": "Test hook",
        "time_breakdown": {
            "starter_minutes": 6,
            "intro_minutes": 9,
            "activity_minutes": 30,
            "exit_ticket_minutes": 6,
            "plenary_minutes": 9,
        },
        "learning_objectives": ["I can do X"],
        "key_concepts": [],
        "group_activities": {
            "foundation": {"description": "a", "stuck_prompt": "b"},
            "core": {"description": "c", "stuck_prompt": "d"},
            "extension": {"description": "e", "stuck_prompt": "f"},
        },
        "resources_needed": [],
        "exit_ticket": {"questions": []},
        "starter": {"duration_minutes": 6, "activity": "test"},
        "plenary": {"duration_minutes": 9, "activity": "test"},
        "prior_knowledge": "test",
        "homework": None,
    }


@pytest.mark.asyncio
async def test_generate_when_llm_returns_valid_json_then_stores_plan_and_raw_output():
    """Happy path: valid LLM JSON → plan.generated_plan set, raw_llm_output stored, status=GENERATED."""
    from app.tasks.lesson_plan_tasks import _generate_async
    from app.models.lesson_plan import LessonPlanStatus

    plan = _make_plan()
    plan_id = str(plan.id)
    class_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())

    valid_json = _make_valid_json()
    response_text = json.dumps(valid_json)

    mock_db = AsyncMock()
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    # class lookup, grade, subject, enrollment count, enrolled profiles
    mock_class = MagicMock()
    mock_class.name = "7A Science"
    mock_class.grade_id = uuid.uuid4()
    mock_class.subject_id = uuid.uuid4()
    class_result = MagicMock()
    class_result.scalar_one_or_none.return_value = mock_class

    grade = MagicMock()
    grade.name = "Grade 7"
    subject = MagicMock()
    subject.name = "Science"

    enroll_count_result = MagicMock()
    enroll_count_result.scalar_one.return_value = 16

    profiles_result = MagicMock()
    profiles = [
        MagicMock(modality_scores={"visual": 0.8, "auditory": 0.3, "reading_writing": 0.5, "kinesthetic": 0.4}, interests=["football"]),
        MagicMock(modality_scores={"visual": 0.6, "auditory": 0.5, "reading_writing": 0.4, "kinesthetic": 0.7}, interests=["gaming"]),
    ]
    profiles_result.scalars.return_value.all.return_value = profiles

    mock_db.execute = AsyncMock(side_effect=[plan_result, class_result, enroll_count_result, profiles_result])
    mock_db.get = AsyncMock(side_effect=[grade, subject])
    mock_db.commit = AsyncMock()

    with patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email") as mock_email, \
         patch("app.ai.providers.router.complete", new=AsyncMock(return_value=response_text)):
        await _generate_async(
            lesson_plan_id=plan_id,
            class_id=class_id,
            focus_subtopic_ids=[str(uuid.uuid4())],
            duration_minutes=60,
            teacher_id=teacher_id,
            db=mock_db,
        )

    assert plan.generated_plan == valid_json
    assert plan.raw_llm_output == response_text
    assert plan.status == LessonPlanStatus.GENERATED
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_generate_when_llm_returns_invalid_json_then_retries_once_and_archives():
    """When LLM returns invalid JSON twice, plan is archived with JSON_PARSE_FAILED."""
    from app.tasks.lesson_plan_tasks import _generate_async
    from app.models.lesson_plan import LessonPlanStatus, LessonPlanFailureCode

    plan = _make_plan()
    plan_id = str(plan.id)
    class_id = str(uuid.uuid4())

    mock_db = AsyncMock()
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    mock_class = MagicMock()
    mock_class.name = "7A"
    mock_class.grade_id = uuid.uuid4()
    mock_class.subject_id = uuid.uuid4()
    class_result = MagicMock()
    class_result.scalar_one_or_none.return_value = mock_class

    grade = MagicMock(); grade.name = "Grade 7"
    subject = MagicMock(); subject.name = "Science"

    enroll_count_result = MagicMock(); enroll_count_result.scalar_one.return_value = 5
    profiles_result = MagicMock(); profiles_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[plan_result, class_result, enroll_count_result, profiles_result])
    mock_db.get = AsyncMock(side_effect=[grade, subject])
    mock_db.commit = AsyncMock()

    with patch("app.tasks.lesson_plan_tasks.send_lesson_plan_failed_email") as mock_fail_email, \
         patch("app.ai.providers.router.complete", new=AsyncMock(return_value="not valid json")):
        await _generate_async(
            lesson_plan_id=plan_id,
            class_id=class_id,
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.ARCHIVED
    assert plan.failure_code == LessonPlanFailureCode.JSON_PARSE_FAILED
    mock_fail_email.assert_called_once()


@pytest.mark.asyncio
async def test_generate_when_first_attempt_fails_but_retry_succeeds_then_plan_generated():
    """When first attempt returns invalid JSON but correction prompt returns valid JSON, plan is GENERATED."""
    from app.tasks.lesson_plan_tasks import _generate_async
    from app.models.lesson_plan import LessonPlanStatus

    plan = _make_plan()

    mock_db = AsyncMock()
    plan_result = MagicMock(); plan_result.scalar_one_or_none.return_value = plan
    mock_class = MagicMock(); mock_class.name = "7A"; mock_class.grade_id = uuid.uuid4(); mock_class.subject_id = uuid.uuid4()
    class_result = MagicMock(); class_result.scalar_one_or_none.return_value = mock_class
    grade = MagicMock(); grade.name = "Grade 7"
    subject = MagicMock(); subject.name = "Science"
    enroll_count_result = MagicMock(); enroll_count_result.scalar_one.return_value = 8
    profiles_result = MagicMock(); profiles_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[plan_result, class_result, enroll_count_result, profiles_result])
    mock_db.get = AsyncMock(side_effect=[grade, subject])
    mock_db.commit = AsyncMock()

    valid_json = json.dumps(_make_valid_json())

    # First call returns bad JSON, second (correction) returns valid JSON
    complete_mock = AsyncMock(side_effect=["not valid json", valid_json])

    with patch("app.tasks.lesson_plan_tasks.send_lesson_plan_ready_email"), \
         patch("app.ai.providers.router.complete", new=complete_mock):
        await _generate_async(
            lesson_plan_id=str(plan.id),
            class_id=str(uuid.uuid4()),
            focus_subtopic_ids=[],
            duration_minutes=60,
            teacher_id=str(uuid.uuid4()),
            db=mock_db,
        )

    assert plan.status == LessonPlanStatus.GENERATED
    assert complete_mock.call_count == 2  # initial + one correction
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/unit/test_lesson_plan_tasks.py -v
```

Expected: FAIL — `_generate_async`, `send_lesson_plan_ready_email`, `send_lesson_plan_failed_email` don't exist yet.

- [ ] **Step 3: Rewrite `backend/app/tasks/lesson_plan_tasks.py`**

The full updated task file. Preserve the existing `@celery_app.task` wrapper (sync Celery entry point → runs `_generate_async` via `asyncio`). Remove `time_limit`. Add `teacher_id` to signature.

Key additions:
1. Build class context from `StudentLearningProfile` (no GapState).
2. Store context snapshot in `plan.gap_summary`.
3. Call LLM with `stream=True, max_tokens=4000`.
4. Store raw response in `plan.raw_llm_output`.
5. Validate with `LessonPlanContent`. If fails, send correction prompt once. If still fails, archive + email admin.
6. On success, set `plan.generated_plan`, `plan.status = GENERATED`, email teacher + BCC admin.
7. On failure, `plan.status = ARCHIVED`, email admin only.

```python
"""Celery task: generate a lesson plan asynchronously."""
import asyncio
import json
import uuid
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.models.lesson_plan import LessonPlan, LessonPlanFailureCode, LessonPlanStatus
from app.models.student_profile import StudentLearningProfile
from app.models.school import ClassEnrollment
from app.schemas.lesson_plan_content import LessonPlanContent
from app.tasks.celery_app import celery_app
import app.ai.providers.router as llm_router

logger = structlog.get_logger()

_PROMPT_ENV = Environment(
    loader=FileSystemLoader(str(__file__).replace("tasks/lesson_plan_tasks.py", "ai/prompts")),
    autoescape=select_autoescape([]),
)

_CORRECTION_PROMPT = """Your previous response could not be parsed as valid JSON matching the required schema.

Error: {error}

Previous response (first 500 chars):
{previous_response}

Return ONLY valid JSON matching the exact schema. No markdown fences, no prose."""


# ── Email helpers ──────────────────────────────────────────────────────────────

def send_lesson_plan_ready_email(teacher_email: str, plan_id: str, class_name: str) -> None:
    """Send success email to teacher with BCC to kaihle-admin."""
    import resend  # type: ignore[import]
    resend.api_key = settings.resend_api_key
    plan_url = f"{settings.frontend_url}/teacher/lesson-plans/{plan_id}"
    resend.Emails.send({
        "from": settings.from_email,
        "to": [teacher_email],
        "bcc": [settings.kaihle_admin_email],
        "subject": f"Your lesson plan for {class_name} is ready",
        "html": (
            f"<p>Your lesson plan for <strong>{class_name}</strong> has been generated.</p>"
            f'<p><a href="{plan_url}">View lesson plan →</a></p>'
        ),
    })


def send_lesson_plan_failed_email(plan_id: str, class_name: str, reason: str) -> None:
    """Send failure notification to kaihle-admin only."""
    import resend  # type: ignore[import]
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.from_email,
        "to": [settings.kaihle_admin_email],
        "subject": f"[ALERT] Lesson plan generation failed — {class_name}",
        "html": (
            f"<p>Plan ID: {plan_id}<br>Class: {class_name}<br>Reason: {reason}</p>"
        ),
    })


# ── Core async logic ───────────────────────────────────────────────────────────

def _compute_class_context(profiles: list) -> dict[str, Any]:
    """Aggregate modality scores and interests across all student learning profiles."""
    if not profiles:
        return {"modality_distribution": {}, "top_interests": [], "student_count": 0}

    modality_keys = ["visual", "auditory", "reading_writing", "kinesthetic"]
    totals: dict[str, float] = {k: 0.0 for k in modality_keys}
    interest_counts: dict[str, int] = {}

    for profile in profiles:
        scores = profile.modality_scores or {}
        for k in modality_keys:
            totals[k] += scores.get(k, 0.0)
        for interest in (profile.interests or []):
            interest_counts[interest] = interest_counts.get(interest, 0) + 1

    n = len(profiles)
    modality_distribution = {k: round(v / n, 3) for k, v in totals.items()}
    top_interests = sorted(interest_counts, key=lambda x: -interest_counts[x])[:5]

    return {
        "modality_distribution": modality_distribution,
        "top_interests": top_interests,
        "student_count": n,
    }


def _try_validate(raw_text: str) -> tuple[dict | None, str]:
    """Parse and validate raw LLM text. Returns (parsed_dict, error_message)."""
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    try:
        LessonPlanContent.model_validate(parsed)
        return parsed, ""
    except ValidationError as exc:
        return None, f"Schema validation error: {exc}"


async def _generate_async(
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    duration_minutes: int,
    teacher_id: str,
    db: AsyncSession,
) -> None:
    log = logger.bind(lesson_plan_id=lesson_plan_id, class_id=class_id)

    # ── Load plan ────────────────────────────────────────────────────────────
    plan_result = await db.execute(select(LessonPlan).where(LessonPlan.id == uuid.UUID(lesson_plan_id)))
    plan: LessonPlan | None = plan_result.scalar_one_or_none()
    if not plan:
        log.error("lesson_plan_task_plan_not_found")
        return

    # ── Load class, grade, subject ────────────────────────────────────────────
    from app.models.school import Class
    class_result = await db.execute(select(Class).where(Class.id == uuid.UUID(class_id)))
    cls = class_result.scalar_one_or_none()
    if not cls:
        log.error("lesson_plan_task_class_not_found")
        plan.status = LessonPlanStatus.ARCHIVED
        plan.failure_code = LessonPlanFailureCode.CLASS_NOT_FOUND
        await db.commit()
        return

    grade = await db.get(type(cls).grade_id.property.mapper.class_, cls.grade_id)  # type: ignore[attr-defined]
    subject = await db.get(type(cls).subject_id.property.mapper.class_, cls.subject_id)  # type: ignore[attr-defined]

    # ── Enrollment count ──────────────────────────────────────────────────────
    count_result = await db.execute(
        select(func.count()).select_from(ClassEnrollment).where(ClassEnrollment.class_id == cls.id)
    )
    enrollment_count: int = count_result.scalar_one()

    # ── Learning profiles (NO GapState — learning styles only) ───────────────
    profiles_result = await db.execute(
        select(StudentLearningProfile).where(
            StudentLearningProfile.student_id.in_(
                select(ClassEnrollment.student_id).where(ClassEnrollment.class_id == cls.id)
            )
        )
    )
    profiles = profiles_result.scalars().all()
    class_context = _compute_class_context(list(profiles))

    # Store snapshot in gap_summary (column is misleadingly named — stores class context)
    plan.gap_summary = class_context
    log.info("lesson_plan_task_context_built", student_count=class_context["student_count"])

    # ── Fetch subtopic names ──────────────────────────────────────────────────
    from app.models.curriculum import Subtopic
    subtopic_uuids = [uuid.UUID(s) for s in focus_subtopic_ids]
    subtopics_for_prompt: list[dict] = []
    if subtopic_uuids:
        sub_result = await db.execute(select(Subtopic).where(Subtopic.id.in_(subtopic_uuids)))
        for sub in sub_result.scalars().all():
            subtopics_for_prompt.append({
                "name": sub.name,
                "learning_objective": sub.learning_objective or "",
            })

    # ── Render prompt ─────────────────────────────────────────────────────────
    template = _PROMPT_ENV.get_template("lesson_plan.jinja2")
    prompt_text = template.render(
        class_name=cls.name,
        subject_name=subject.name if subject else "Unknown",
        grade_name=grade.name if grade else "Unknown",
        student_count=enrollment_count,
        duration_minutes=duration_minutes,
        subtopics=subtopics_for_prompt,
        modality_distribution=class_context["modality_distribution"],
        top_interests=class_context["top_interests"],
    )

    # ── LLM call (streaming) ──────────────────────────────────────────────────
    try:
        response_text = await llm_router.complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=4000,
            stream=True,
        )
    except Exception as exc:
        log.error("lesson_plan_task_llm_error", error=str(exc), exc_info=True)
        plan.status = LessonPlanStatus.ARCHIVED
        plan.failure_code = LessonPlanFailureCode.LLM_ERROR
        plan.failure_reason = str(exc)
        await db.commit()
        send_lesson_plan_failed_email(lesson_plan_id, cls.name, f"LLM error: {exc}")
        return

    # Store raw output regardless of validation outcome
    plan.raw_llm_output = response_text
    log.info("lesson_plan_task_llm_response_received", chars=len(response_text))

    # ── Validate — one correction retry ──────────────────────────────────────
    parsed, error = _try_validate(response_text)

    if parsed is None:
        log.warning("lesson_plan_task_validation_failed_first_attempt", error=error)
        correction_prompt = _CORRECTION_PROMPT.format(
            error=error,
            previous_response=response_text[:500],
        )
        try:
            retry_text = await llm_router.complete(
                task="lesson_plan",
                messages=[
                    {"role": "user", "content": prompt_text},
                    {"role": "assistant", "content": response_text},
                    {"role": "user", "content": correction_prompt},
                ],
                max_tokens=4000,
                stream=True,
            )
        except Exception as exc:
            log.error("lesson_plan_task_correction_llm_error", error=str(exc), exc_info=True)
            retry_text = ""

        plan.raw_llm_output = retry_text or response_text  # keep the retry output if available
        parsed, error = _try_validate(retry_text) if retry_text else (None, "Empty retry response")

    if parsed is None:
        log.error("lesson_plan_task_validation_failed_after_retry", error=error)
        plan.status = LessonPlanStatus.ARCHIVED
        plan.failure_code = LessonPlanFailureCode.JSON_PARSE_FAILED
        plan.failure_reason = error
        await db.commit()
        send_lesson_plan_failed_email(lesson_plan_id, cls.name, f"Validation failed after retry: {error}")
        return

    # ── Success ───────────────────────────────────────────────────────────────
    plan.generated_plan = parsed
    plan.status = LessonPlanStatus.GENERATED
    await db.commit()
    log.info("lesson_plan_task_completed", lesson_plan_id=lesson_plan_id)

    # Fetch teacher email for notification
    try:
        from app.models.user import User
        teacher = await db.get(User, uuid.UUID(teacher_id))
        if teacher:
            send_lesson_plan_ready_email(teacher.email, lesson_plan_id, cls.name)
    except Exception as exc:
        log.warning("lesson_plan_task_email_failed", error=str(exc))


# ── Celery entry point ─────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=0, name="lesson_plan.generate")
def generate_lesson_plan_task(
    self,
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    duration_minutes: int,
    teacher_id: str,
) -> None:
    """Celery task entry point — runs async generation logic synchronously."""
    loop = asyncio.new_event_loop()
    try:
        async def _run():
            async with AsyncSessionFactory() as db:
                await _generate_async(
                    lesson_plan_id=lesson_plan_id,
                    class_id=class_id,
                    focus_subtopic_ids=focus_subtopic_ids,
                    duration_minutes=duration_minutes,
                    teacher_id=teacher_id,
                    db=db,
                )
        loop.run_until_complete(_run())
    finally:
        loop.close()
```

- [ ] **Step 4: Update `backend/app/services/lesson_plan_service.py`**

In `generate_lesson_plan`, update the Celery task dispatch to include `teacher_id` and remove `gap_summary`:

```python
# In generate_lesson_plan service method, replace the task dispatch call:
generate_lesson_plan_task.delay(
    lesson_plan_id=str(plan.id),
    class_id=str(class_id),
    focus_subtopic_ids=[str(s) for s in request.focus_subtopic_ids],
    duration_minutes=request.duration_minutes,
    teacher_id=str(current_user.id),
)
```

Also remove any `_build_gap_summary` helper if it exists in this file — gap summary is now built inside the task itself.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest app/tests/unit/test_lesson_plan_tasks.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Run full unit test suite**

```bash
cd backend && uv run pytest app/tests/unit/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/lesson_plan_tasks.py \
        backend/app/services/lesson_plan_service.py \
        backend/app/tests/unit/test_lesson_plan_tasks.py
git commit -m "feat(lesson-plan-task): streaming, Pydantic validation+retry, raw output to DB, email notification"
```

---

## Task 7: Update Frontend Types + Remove Polling

**Files:**
- Modify: `frontend/apps/teacher/src/hooks/useLessonPlans.ts`
- Modify: `frontend/apps/teacher/src/pages/lesson-plans/AllLessonPlansPage.tsx`

- [ ] **Step 1: Update `useLessonPlans.ts`**

Open the file. Add new typed interfaces BEFORE the `LessonPlan` interface. Remove `refetchInterval` from `useLessonPlan` and `useClassLessonPlans`:

```typescript
// ── Typed plan content (matches lesson_plan.jinja2 JSON schema) ─────────────

export interface LessonPlanMisconception {
  student_error: string
  trigger_phrase: string
  recovery_script: string
}

export interface LessonPlanConcept {
  name: string
  duration_minutes: number
  teacher_does: string
  student_does: string
  check_question: string
  misconception: LessonPlanMisconception
  transition_cue: string | null
}

export interface LessonPlanGroupActivity {
  description: string
  stuck_prompt: string
}

export interface LessonPlanExitTicketQuestion {
  label: string
  question_text: string
  good_answer: string
  pivot_if_wrong: string
}

export interface LessonPlanContent {
  lesson_hook: string
  time_breakdown: {
    starter_minutes: number
    intro_minutes: number
    activity_minutes: number
    exit_ticket_minutes: number
    plenary_minutes: number
  }
  learning_objectives: string[]
  key_concepts: LessonPlanConcept[]
  group_activities: {
    foundation: LessonPlanGroupActivity
    core: LessonPlanGroupActivity
    extension: LessonPlanGroupActivity
  }
  resources_needed: string[]
  exit_ticket: { questions: LessonPlanExitTicketQuestion[] }
  starter: { duration_minutes: number; activity: string }
  plenary: { duration_minutes: number; activity: string }
  prior_knowledge: string
  homework: string | null
}

// ── Class context snapshot (from gap_summary — column is misleadingly named) ─

export interface ClassContextSnapshot {
  modality_distribution: Record<string, number>
  top_interests: string[]
  student_count: number
}

// ── LessonPlan type ───────────────────────────────────────────────────────────

export interface LessonPlan {
  id: string
  class_id: string
  week_start: string | null
  status: LessonPlanStatus
  generated_plan: LessonPlanContent | null
  teacher_edits: Partial<LessonPlanContent> | null
  gap_summary: ClassContextSnapshot | null
  focus_subtopics: SubtopicContext[]
  generated_at: string
  failure_code: string | null
  failure_reason: string | null
}
```

Remove `refetchInterval` from both `useLessonPlan` and `useClassLessonPlans`:

```typescript
// Before (remove this):
// refetchInterval: (data) => data?.status === 'GENERATING' ? 5000 : false,

// After — no polling, teacher is notified by email when ready
```

- [ ] **Step 2: Update `AllLessonPlansPage.tsx`**

Find the GENERATING badge/status display and update the message:

```tsx
// For a plan with status === 'GENERATING', show:
<span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700">
  <RefreshCw className="w-3 h-3" aria-hidden="true" />
  Generating — you'll be emailed when ready
</span>
```

Also remove any `refetchInterval` from the `useClassLessonPlans` call in this component if it's set locally.

- [ ] **Step 3: Run typecheck**

```bash
cd frontend/apps/teacher && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/teacher/src/hooks/useLessonPlans.ts \
        frontend/apps/teacher/src/pages/lesson-plans/AllLessonPlansPage.tsx
git commit -m "feat(lesson-plan-frontend): typed interfaces for new schema, remove polling, static generating message"
```

---

## Task 8: Redesign `LessonPlanDetailPage.tsx`

**Files:**
- Rewrite: `frontend/apps/teacher/src/pages/lesson-plans/LessonPlanDetailPage.tsx`
- Create: `frontend/apps/teacher/src/pages/lesson-plans/__tests__/LessonPlanDetailPage.test.tsx`

**Layout:** Two-column. 240px sidebar (time flow bar + learning style summary). Scrollable main content. Breaks out of `DashboardLayout` padding using `-m-6 h-[calc(100vh-50px)]`.

**Sidebar shows:** Time flow bar (colored segments) + modality % bars + top interests. NOT student names, NOT mastery groups.

**GENERATING state:** Static message — "You'll receive an email when your lesson plan is ready." No spinner auto-refresh.

- [ ] **Step 1: Write component tests**

Create `frontend/apps/teacher/src/pages/lesson-plans/__tests__/LessonPlanDetailPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { LessonPlanDetailPage } from "../LessonPlanDetailPage"
import * as hooks from "../../../hooks/useLessonPlans"

jest.mock("../../../hooks/useLessonPlans")

const mockUseLessonPlan = hooks.useLessonPlan as jest.Mock

function renderPage(planId = "plan-1", classId = "class-1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/teacher/classes/${classId}/lesson-plans/${planId}`]}>
        <Routes>
          <Route path="/teacher/classes/:classId/lesson-plans/:planId" element={<LessonPlanDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const MOCK_PLAN = {
  id: "plan-1",
  class_id: "class-1",
  week_start: null,
  status: "GENERATED" as const,
  generated_plan: {
    lesson_hook: "Today students discover something surprising about forces.",
    time_breakdown: { starter_minutes: 6, intro_minutes: 9, activity_minutes: 30, exit_ticket_minutes: 6, plenary_minutes: 9 },
    learning_objectives: ["I can define force.", "I can calculate speed."],
    key_concepts: [
      {
        name: "Contact vs. non-contact forces",
        duration_minutes: 3,
        teacher_does: "Draw two columns on the board.",
        student_does: "Call out examples.",
        check_question: "Give me one contact force.",
        misconception: {
          student_error: "Students think non-contact forces only work up close.",
          trigger_phrase: "But the Earth isn't pulling my pencil.",
          recovery_script: "Drop your pencil. Did you touch it?",
        },
        transition_cue: "Now you know the difference.",
      },
    ],
    group_activities: {
      foundation: { description: "Force card sort activity.", stuck_prompt: "Is it touching?" },
      core: { description: "Nature trail investigation.", stuck_prompt: "Divide distance by time." },
      extension: { description: "Design a gaming level.", stuck_prompt: "What force steepens the slope?" },
    },
    resources_needed: ["Mini-whiteboards × 16"],
    exit_ticket: {
      questions: [
        {
          label: "Q1 — core understanding",
          question_text: "A ball rolls to a stop. Are forces balanced?",
          good_answer: "Unbalanced — friction decelerates it.",
          pivot_if_wrong: "Redraw force arrows on the board.",
        },
      ],
    },
    starter: { duration_minutes: 6, activity: "Think-Pair-Share about forces." },
    plenary: { duration_minutes: 9, activity: "3-2-1 reflection." },
    prior_knowledge: "Students know about speed.",
    homework: null,
  },
  teacher_edits: null,
  gap_summary: {
    modality_distribution: { visual: 0.72, auditory: 0.41, reading_writing: 0.55, kinesthetic: 0.63 },
    top_interests: ["football", "gaming"],
    student_count: 16,
  },
  focus_subtopics: [{ subtopic_id: "sub-1", name: "Forces", topic_name: "Motion" }],
  generated_at: "2026-05-08T10:00:00Z",
  failure_code: null,
  failure_reason: null,
}

test("renders lesson hook", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText(/Today students discover something surprising/)).toBeInTheDocument()
})

test("renders learning objectives", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText("I can define force.")).toBeInTheDocument()
  expect(screen.getByText("I can calculate speed.")).toBeInTheDocument()
})

test("renders concept card with teacher and student columns", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText("Contact vs. non-contact forces")).toBeInTheDocument()
  expect(screen.getByText("Draw two columns on the board.")).toBeInTheDocument()
  expect(screen.getByText("Call out examples.")).toBeInTheDocument()
})

test("renders misconception box with recovery script", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText("Drop your pencil. Did you touch it?")).toBeInTheDocument()
  expect(screen.getByText(/But the Earth isn't pulling my pencil/)).toBeInTheDocument()
})

test("renders all three group activity cards", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText("Force card sort activity.")).toBeInTheDocument()
  expect(screen.getByText("Nature trail investigation.")).toBeInTheDocument()
  expect(screen.getByText("Design a gaming level.")).toBeInTheDocument()
})

test("renders exit ticket with good answer and pivot", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText(/A ball rolls to a stop/)).toBeInTheDocument()
  expect(screen.getByText("Unbalanced — friction decelerates it.")).toBeInTheDocument()
  expect(screen.getByText("Redraw force arrows on the board.")).toBeInTheDocument()
})

test("sidebar shows modality labels", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  // Sidebar shows modality distribution, not student names
  expect(screen.getByText(/visual/i)).toBeInTheDocument()
})

test("sidebar shows top interests", () => {
  mockUseLessonPlan.mockReturnValue({ data: MOCK_PLAN, isLoading: false })
  renderPage()
  expect(screen.getByText("football")).toBeInTheDocument()
  expect(screen.getByText("gaming")).toBeInTheDocument()
})

test("shows static email message when GENERATING", () => {
  mockUseLessonPlan.mockReturnValue({
    data: { ...MOCK_PLAN, status: "GENERATING", generated_plan: null },
    isLoading: false,
  })
  renderPage()
  expect(screen.getByText(/email/i)).toBeInTheDocument()
})

test("shows skeleton when loading", () => {
  mockUseLessonPlan.mockReturnValue({ data: undefined, isLoading: true })
  renderPage()
  expect(screen.queryByText(/Today students/)).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && pnpm --filter "@kaihle/teacher" exec jest pages/lesson-plans/__tests__/LessonPlanDetailPage.test.tsx --verbose
```

Expected: FAIL (old component doesn't render new content).

- [ ] **Step 3: Rewrite `LessonPlanDetailPage.tsx`**

Replace entire file with:

```tsx
import { useParams, Link } from "react-router-dom"
import { ChevronLeft, RefreshCw } from "lucide-react"
import { useLessonPlan } from "../../hooks/useLessonPlans"
import type { LessonPlanConcept, LessonPlanExitTicketQuestion } from "../../hooks/useLessonPlans"

// ── Sidebar: Time Flow Bar ──────────────────────────────────────────────────────

function TimeFlowBar({
  breakdown,
}: {
  breakdown: {
    starter_minutes: number
    intro_minutes: number
    activity_minutes: number
    exit_ticket_minutes: number
    plenary_minutes: number
  }
}) {
  const total =
    breakdown.starter_minutes +
    breakdown.intro_minutes +
    breakdown.activity_minutes +
    breakdown.exit_ticket_minutes +
    breakdown.plenary_minutes

  const pct = (min: number) => `${((min / total) * 100).toFixed(1)}%`
  const segments = [
    { color: "bg-brand-green", label: "Starter", min: breakdown.starter_minutes },
    { color: "bg-blue-500", label: "Key concepts", min: breakdown.intro_minutes },
    { color: "bg-brand-gold", label: "Group activity", min: breakdown.activity_minutes },
    { color: "bg-orange-500", label: "Exit ticket", min: breakdown.exit_ticket_minutes },
    { color: "bg-violet-500", label: "Plenary", min: breakdown.plenary_minutes },
  ]

  return (
    <div>
      <div className="flex h-1.5 rounded-full overflow-hidden mb-2.5">
        {segments.map((s) => (
          <div key={s.label} className={s.color} style={{ width: pct(s.min) }} aria-label={`${s.label}: ${s.min} min`} />
        ))}
      </div>
      <div className="space-y-1.5">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-[11px] text-brand-body">
            <div className={`w-2 h-2 rounded-sm flex-shrink-0 ${s.color}`} aria-hidden="true" />
            {s.label} · {s.min} min
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Sidebar: Learning Style Summary ───────────────────────────────────────────

function LearningStyleSidebar({
  ctx,
}: {
  ctx: { modality_distribution: Record<string, number>; top_interests: string[]; student_count: number } | null
}) {
  if (!ctx) {
    return (
      <p className="text-[11px] text-brand-muted italic leading-snug">
        No learning profile data yet — plan designed for a mixed-modality class.
      </p>
    )
  }

  const modalityOrder = ["visual", "auditory", "reading_writing", "kinesthetic"]
  const modalityColors: Record<string, string> = {
    visual: "bg-blue-400",
    auditory: "bg-violet-400",
    reading_writing: "bg-amber-400",
    kinesthetic: "bg-brand-green",
  }

  return (
    <div className="space-y-4">
      {/* Modality bars */}
      <div className="space-y-2.5">
        {modalityOrder.map((key) => {
          const score = ctx.modality_distribution[key] ?? 0
          const pct = Math.round(score * 100)
          const label = key.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())
          return (
            <div key={key}>
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-[11px] text-brand-body">{label}</span>
                <span className="text-[10px] text-brand-muted font-medium">{pct}%</span>
              </div>
              <div className="w-full h-[5px] bg-brand-border rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${modalityColors[key] ?? "bg-brand-muted"}`}
                  style={{ width: `${pct}%` }}
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Interests */}
      {ctx.top_interests.length > 0 && (
        <div>
          <div className="text-[9px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-2">
            Top interests
          </div>
          <div className="flex flex-wrap gap-1.5">
            {ctx.top_interests.map((interest) => (
              <span key={interest} className="text-[11px] px-2 py-0.5 rounded-full bg-brand-bg border border-brand-border text-brand-body">
                {interest}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-brand-muted">{ctx.student_count} students</p>
    </div>
  )
}

// ── Main Content: Phase Divider ────────────────────────────────────────────────

function PhaseDivider({ label, badge, color }: { label: string; badge: string; color: "blue" | "gold" | "orange" | "violet" }) {
  const colorMap = {
    blue:   { text: "text-blue-600",   badgeBg: "bg-blue-50",   badgeText: "text-blue-700" },
    gold:   { text: "text-brand-gold", badgeBg: "bg-amber-50",  badgeText: "text-amber-700" },
    orange: { text: "text-orange-600", badgeBg: "bg-orange-50", badgeText: "text-orange-700" },
    violet: { text: "text-violet-600", badgeBg: "bg-violet-50", badgeText: "text-violet-700" },
  }
  const c = colorMap[color]
  return (
    <div className={`flex items-center gap-2.5 text-[10px] font-semibold uppercase tracking-wide ${c.text}`}>
      {label}
      <span className={`text-[10px] px-2 py-0.5 rounded-full font-normal normal-case tracking-normal ${c.badgeBg} ${c.badgeText}`}>{badge}</span>
      <div className="flex-1 h-px bg-brand-border" />
    </div>
  )
}

// ── Main Content: Concept Card ─────────────────────────────────────────────────

function ConceptCard({ concept, index, total }: { concept: LessonPlanConcept; index: number; total: number }) {
  return (
    <div className="bg-white border border-brand-border rounded-2xl overflow-hidden">
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-brand-border">
        <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold">
          Concept {index + 1} of {total}
        </span>
        <span className="text-sm font-semibold text-brand-ink flex-1">{concept.name}</span>
        <span className="text-[11px] text-brand-muted">~{concept.duration_minutes} min</span>
      </div>
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-lg p-3 bg-blue-50">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-blue-600 mb-1.5">Teacher does</div>
            <p className="text-[12px] text-blue-900 leading-relaxed">{concept.teacher_does}</p>
          </div>
          <div className="rounded-lg p-3 bg-gray-50">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-brand-muted mb-1.5">Students do</div>
            <p className="text-[12px] text-brand-body leading-relaxed">{concept.student_does}</p>
          </div>
        </div>
        <div className="text-[12px] text-brand-ink bg-brand-bg border-l-2 border-brand-green rounded-r-lg px-3 py-2 leading-relaxed">
          <span className="font-semibold text-brand-green">✓ Check before moving on: </span>
          &ldquo;{concept.check_question}&rdquo;
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold text-red-800 uppercase tracking-wide mb-1.5">
            <span aria-hidden="true">⚠</span> Misconception — surfaces here
          </div>
          <p className="text-[12px] text-red-900 leading-relaxed mb-1.5">{concept.misconception.student_error}</p>
          {concept.misconception.trigger_phrase && (
            <p className="text-[11px] text-red-700 italic mb-2">
              Trigger: &ldquo;{concept.misconception.trigger_phrase}&rdquo;
            </p>
          )}
          <div className="bg-brand-green-light rounded-md px-2.5 py-1.5 text-[11px] text-brand-green leading-relaxed">
            Recovery: {concept.misconception.recovery_script}
          </div>
        </div>
        {concept.transition_cue && (
          <div className="flex items-center gap-2 text-[11px] text-brand-muted bg-gray-50 border border-brand-border rounded-lg px-3 py-2">
            <span aria-hidden="true">→</span> {concept.transition_cue}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Content: Group Activity Grid ─────────────────────────────────────────

function GroupActivityGrid({
  foundation, core, extension,
}: {
  foundation: { description: string; stuck_prompt: string }
  core: { description: string; stuck_prompt: string }
  extension: { description: string; stuck_prompt: string }
}) {
  const groups = [
    { key: "foundation", label: "◆ Foundation", headBg: "bg-red-50", headText: "text-red-800", data: foundation },
    { key: "core",       label: "◆ Core",       headBg: "bg-amber-50", headText: "text-amber-800", data: core },
    { key: "extension",  label: "◆ Extension",  headBg: "bg-brand-green-light", headText: "text-brand-green", data: extension },
  ]
  return (
    <div className="grid grid-cols-3 gap-3">
      {groups.map((g) => (
        <div key={g.key} className="bg-white border border-brand-border rounded-xl overflow-hidden">
          <div className={`px-3 py-2 text-[12px] font-semibold ${g.headBg} ${g.headText}`}>{g.label}</div>
          <div className="px-3 py-3 text-[12px] text-brand-body leading-relaxed">{g.data.description}</div>
          <div className="px-3 py-2 border-t border-brand-border">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-brand-muted mb-1">If stuck, say:</div>
            <div className="text-[11px] text-brand-body italic leading-snug">&ldquo;{g.data.stuck_prompt}&rdquo;</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Content: Exit Ticket Card ─────────────────────────────────────────────

function ExitTicketCard({ questions }: { questions: LessonPlanExitTicketQuestion[] }) {
  return (
    <div className="bg-white border border-brand-border rounded-2xl overflow-hidden">
      <div className="bg-brand-green-light px-5 py-3 flex items-center gap-2">
        <span className="text-base" aria-hidden="true">✓</span>
        <span className="text-[13px] font-semibold text-brand-green">
          Two questions — mark as a class, then use results to shape the plenary
        </span>
      </div>
      <div className="divide-y divide-brand-border">
        {questions.map((q, i) => (
          <div key={i} className="px-5 py-4 space-y-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-brand-green">{q.label}</div>
            <p className="text-[13px] text-brand-ink leading-relaxed">{q.question_text}</p>
            <div className="bg-brand-green-light rounded-md px-2.5 py-1.5 text-[11px] text-brand-green leading-relaxed">
              <span className="font-semibold">✓ Good answer: </span>{q.good_answer}
            </div>
            <div className="bg-amber-50 rounded-md px-2.5 py-1.5 text-[11px] text-amber-700 leading-relaxed">
              <span className="font-semibold">↳ Most wrong? </span>{q.pivot_if_wrong}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export function LessonPlanDetailPage() {
  const { classId, planId } = useParams<{ classId: string; planId: string }>()
  const { data: plan, isLoading } = useLessonPlan(planId)

  if (isLoading) {
    return (
      <div className="-m-6 flex h-[calc(100vh-50px)]">
        <div className="w-60 flex-shrink-0 bg-white border-r border-brand-border p-4 animate-pulse space-y-3">
          <div className="h-3 bg-brand-border rounded-full w-3/4" />
          <div className="h-2 bg-brand-border rounded-full" />
          <div className="h-2 bg-brand-border rounded-full w-5/6" />
        </div>
        <div className="flex-1 p-6 animate-pulse space-y-4">
          <div className="h-6 bg-brand-border rounded w-48" />
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 bg-brand-border rounded-2xl" />)}
        </div>
      </div>
    )
  }

  if (!plan) {
    return <div className="p-6 text-sm text-brand-muted">Lesson plan not found.</div>
  }

  const isGenerating = plan.status === "GENERATING"
  const c = plan.generated_plan
  const ctx = plan.gap_summary

  return (
    <div className="-m-6 flex h-[calc(100vh-50px)]">

      {/* ── Session Sidebar ── */}
      <div className="w-60 flex-shrink-0 bg-white border-r border-brand-border overflow-y-auto">
        <div className="p-4 space-y-5">

          {/* Time flow */}
          <div>
            <div className="text-[9px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-3">
              Lesson flow{c ? ` · ${Object.values(c.time_breakdown).reduce((a, b) => a + b, 0)} min` : ""}
            </div>
            {c ? <TimeFlowBar breakdown={c.time_breakdown} /> : <div className="h-1.5 bg-brand-border rounded-full" />}
          </div>

          <div className="h-px bg-brand-border" />

          {/* Learning style */}
          <div>
            <div className="text-[9px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-3">
              Class learning style
            </div>
            <LearningStyleSidebar ctx={ctx} />
          </div>
        </div>
      </div>

      {/* ── Main Content ── */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">

        <div className="flex items-center gap-3">
          <Link
            to={`/teacher/classes/${classId}/lesson-plans`}
            className="text-brand-muted hover:text-brand-ink transition-colors"
            aria-label="Back to lesson plans"
          >
            <ChevronLeft className="w-5 h-5" aria-hidden="true" />
          </Link>
          <h1 className="font-display font-bold text-2xl text-brand-ink flex-1">Lesson Plan</h1>
          {isGenerating && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 animate-pulse">
              <RefreshCw className="w-3 h-3" aria-hidden="true" />
              Generating…
            </span>
          )}
        </div>

        {isGenerating && (
          <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
            <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center mx-auto mb-4" aria-hidden="true">
              <RefreshCw className="w-5 h-5 text-brand-gold" />
            </div>
            <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">Your lesson plan is being generated.</h3>
            <p className="text-sm text-brand-muted max-w-sm mx-auto">
              This usually takes under 60 seconds. You&apos;ll receive an email when your lesson plan is ready.
            </p>
          </div>
        )}

        {!isGenerating && c && (
          <>
            {/* Header card */}
            <div className="bg-white border border-brand-border rounded-2xl p-5">
              <p className="font-display text-[17px] font-medium text-brand-ink leading-relaxed mb-3">{c.lesson_hook}</p>
              <div className="flex flex-wrap gap-2">
                {[
                  plan.focus_subtopics.map((s) => s.topic_name).join(", "),
                  `${Object.values(c.time_breakdown).reduce((a, b) => a + b, 0)} min`,
                  ctx ? `${ctx.student_count} students` : "",
                ].filter(Boolean).map((pill) => (
                  <span key={pill} className="text-[11px] px-2.5 py-1 rounded-full bg-brand-bg text-brand-body border border-brand-border">
                    {pill}
                  </span>
                ))}
              </div>
            </div>

            {/* Learning objectives */}
            {c.learning_objectives.length > 0 && (
              <div className="bg-white border border-brand-border rounded-2xl p-5">
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-3">
                  Learning objectives — write these on the board
                </div>
                <div className="space-y-2">
                  {c.learning_objectives.map((obj, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="w-5 h-5 rounded-full bg-brand-green-light text-brand-green text-[10px] font-semibold flex items-center justify-center flex-shrink-0 mt-0.5">
                        {i + 1}
                      </div>
                      <p className="text-[13px] text-brand-ink leading-relaxed">{obj}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Key concepts */}
            {c.key_concepts.length > 0 && (
              <>
                <PhaseDivider label="Key concept introduction" badge={`${c.time_breakdown.intro_minutes} min`} color="blue" />
                {c.key_concepts.map((concept, i) => (
                  <ConceptCard key={i} concept={concept} index={i} total={c.key_concepts.length} />
                ))}
              </>
            )}

            {/* Group activity */}
            <PhaseDivider label="Group activity" badge={`${c.time_breakdown.activity_minutes} min · three groups`} color="gold" />
            <div className="bg-white border border-brand-border rounded-2xl p-4 space-y-4">
              <GroupActivityGrid foundation={c.group_activities.foundation} core={c.group_activities.core} extension={c.group_activities.extension} />
              {c.resources_needed.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-2">Resources to prepare</div>
                  <div className="flex flex-wrap gap-2">
                    {c.resources_needed.map((r, i) => (
                      <span key={i} className="text-[11px] px-2.5 py-1 rounded-md bg-brand-bg border border-brand-border text-brand-body">{r}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Exit ticket */}
            {c.exit_ticket.questions.length > 0 && (
              <>
                <PhaseDivider label="Exit ticket" badge={`${c.time_breakdown.exit_ticket_minutes} min`} color="orange" />
                <ExitTicketCard questions={c.exit_ticket.questions} />
              </>
            )}

            {/* Plenary */}
            {c.plenary && (
              <>
                <PhaseDivider label="Plenary" badge={`${c.time_breakdown.plenary_minutes} min`} color="violet" />
                <div className="bg-white border border-brand-border rounded-2xl p-5">
                  <p className="text-[13px] text-brand-body leading-relaxed">{c.plenary.activity}</p>
                </div>
              </>
            )}

            {/* Homework */}
            {c.homework && (
              <div className="bg-white border border-brand-border rounded-2xl p-5">
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-brand-muted mb-2">Homework</div>
                <p className="text-[13px] text-brand-body leading-relaxed">{c.homework}</p>
              </div>
            )}

            <div className="h-8" />
          </>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run component tests**

```bash
cd frontend && pnpm --filter "@kaihle/teacher" exec jest pages/lesson-plans/__tests__/LessonPlanDetailPage.test.tsx --verbose
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Run full typecheck**

```bash
cd frontend/apps/teacher && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/teacher/src/pages/lesson-plans/LessonPlanDetailPage.tsx \
        frontend/apps/teacher/src/pages/lesson-plans/__tests__/LessonPlanDetailPage.test.tsx
git commit -m "feat(lesson-plan-detail): redesign with learning-style sidebar, concept cards, group activity, exit ticket"
```

---

## Task 9: Final Tests, Linters, and Verification

- [ ] **Step 1: Run backend unit tests with coverage**

```bash
cd backend && uv run pytest app/tests/unit/ -v --cov=app/services --cov-report=term-missing
```

Expected: All tests PASS, `app/services/lesson_plan_service.py` coverage ≥ 90%.

- [ ] **Step 2: Run backend linters**

```bash
cd backend && uv run ruff check --fix app/ && uv run ruff format app/ && uv run mypy app/
```

Expected: No errors. If mypy flags `Any` in task file, add `from typing import Any` and annotate `-> None` where missing.

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && pnpm test
```

Expected: All tests PASS.

- [ ] **Step 4: Run frontend lint and typecheck**

```bash
cd frontend && pnpm lint && pnpm typecheck
```

Expected: Clean.

- [ ] **Step 5: Commit any lint fixes**

```bash
git add -p
git commit -m "chore: fix lint and type errors from lesson plan implementation"
```

---

## Verification (End-to-End)

### Backend

1. Start full stack:
   ```bash
   docker compose up -d && docker compose exec backend alembic upgrade head
   ```
2. Verify `raw_llm_output` column exists:
   ```bash
   docker compose exec db psql -U postgres -d kaihle -c "\d lesson_plans" | grep raw_llm_output
   ```
3. Seed test data: `docker compose exec backend python -m scripts.seed_test_data`
4. As teacher, POST to `/api/v1/classes/{classId}/lesson-plans/generate` with `focus_subtopic_ids` and `duration_minutes: 60`
5. Poll `GET /api/v1/lesson-plans/{planId}` until `status: "GENERATED"`
6. Verify:
   - `gap_summary` = `{modality_distribution, top_interests, student_count}` (no GapState/mastery data)
   - `generated_plan` has `lesson_hook`, `key_concepts[].teacher_does`, `group_activities`, `exit_ticket.questions[].good_answer`
   - `raw_llm_output` is non-null in the DB (check via admin or query)
7. Check teacher email inbox + kaihle-admin BCC received

### Frontend

1. Start teacher app: `cd frontend && pnpm dev:teacher`
2. Navigate to a GENERATED plan
3. Verify:
   - Left sidebar: time flow bar (5 colored segments) + modality % bars + interest tags. **No student names.**
   - Lesson hook in Fraunces font inside header card
   - Learning objectives numbered with green circles
   - Concept cards: blue/gray two-column grid, red misconception box, green left-border check question, arrow transition cue
   - Group activity 3-column grid with "if stuck" prompts
   - Exit ticket: green "good answer" boxes + amber "pivot" boxes
   - GENERATING state: static message mentions email (no auto-refresh spinner)

---

## Self-Review

- [x] Lesson plan NEVER queries GapState — `_compute_class_context` uses `StudentLearningProfile` only ✓
- [x] `gap_summary` stores `{modality_distribution, top_interests, student_count}` — no mastery data ✓
- [x] No hardcoded LLM model names in plan, config, or CONSTITUTION ✓
- [x] `time_limit` removed from Celery task decorator ✓
- [x] `raw_llm_output` stored in DB column (not filesystem) — survives Render.com ephemeral disk ✓
- [x] Pydantic validation + one correction retry before archiving ✓
- [x] Email: teacher + BCC admin on success; admin only on failure ✓
- [x] No polling in frontend ✓
- [x] GENERATING state shows email notification message ✓
- [x] `max_tokens` default in `router.py` stays at 2000 — only lesson plan task passes 4000 explicitly ✓
- [x] No green action buttons in teacher role (design system rule) ✓
- [x] Loading state uses skeleton not full-page spinner (CONSTITUTION Rule 22) ✓
- [x] All modals use `Modal` from `@kaihle/ui` — no new modals in this plan ✓
- [x] Migration has downgrade path ✓
- [x] Task includes `teacher_id` in signature for email routing ✓
