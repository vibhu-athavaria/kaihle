# M0-9-T6 — Backend Spec Corrections
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T6
**Depends on:** M0-8-T1 (nullable school_id), M0-8-T2 (email uniqueness), M0-6-T2 (Celery tasks)
**Blocks:** M1 must not begin until this task is complete
**Estimated effort:** 3–4 hours

---

## Context

This task addresses five confirmed bugs and gaps found during the M0 technical audit,
none of which require new features — they are all corrections to existing code that
must be fixed before M1 begins. Each issue is independently fixable. They are grouped
in this task because they are all backend-only and can be completed in a single
focused session.

The five items are: the KaihleAdmin bypass missing from `schools.py`, the LiteLLM
provider router not yet implemented, inline `# type: ignore` comments in production
Celery task code, the empty question bank guard missing from `create_class_diagnostic_task`,
and the Celery dead-letter critical log missing from both Celery tasks.

Read `CONSTITUTION.md` Rules 12, 13, 17, and 18 before writing any code.

---

## Fix 1 — KaihleAdmin bypass missing from `schools.py`

### Problem

`backend/app/api/v1/routes/schools.py` contains a `_check_school_access` helper that
compares `current_user.school_id != school_id` for all roles. Because KaihleAdmin
has `school_id = None`, this comparison always evaluates to `True` for a KaihleAdmin,
which means the function always raises a 403. A KaihleAdmin cannot currently create
classes, list classes, enroll students, or perform any other action via the schools
router. This is a real bug.

The identical bug was already fixed in `users.py` — the fix pattern is established
and simply needs to be applied in `schools.py`.

### Fix

```python
# backend/app/api/v1/routes/schools.py

def _check_school_access(school_id: uuid.UUID, current_user: CurrentUser) -> None:
    """Check if user can access the given school's data.

    KaihleAdmin can access any school — explicit bypass required per CONSTITUTION Rule 12.
    All other roles must belong to the same school.
    """
    if current_user.role == UserRole.KAIHLE_ADMIN:
        return  # KaihleAdmin can access any school

    if current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school's data",
        )
```

### Tests to add (`test_school_routes.py`)

```python
test_kaihle_admin_can_create_class_in_any_school()
test_kaihle_admin_can_list_classes_in_any_school()
test_kaihle_admin_can_enroll_students_in_any_school()
test_school_admin_cannot_access_different_school_classes()
```

---

## Fix 2 — LiteLLM provider router

### Problem

`CONSTITUTION.md` §8 specifies LiteLLM as the provider-agnostic abstraction layer,
but `backend/app/ai/providers/` still contains the old individual provider files
(`base.py`, `gemini.py`, `openai.py`, `anthropic.py`, `router.py`). The old router
uses a custom `LLMProvider` ABC that each provider implements separately. This is
the pattern being replaced.

### Fix

**Step 1 — Add LiteLLM to `backend/pyproject.toml`:**

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "litellm>=1.40.0",
]
```

**Step 2 — Replace `backend/app/ai/providers/router.py` entirely:**

```python
"""LiteLLM-based provider router.

All LLM calls in Kaihle go through this module. No feature code imports
provider SDKs directly — all routing, retries, and provider switching
are handled here via configuration.

To switch a task to a different provider or to a self-hosted LLM server,
change the corresponding environment variable — no code change required.
"""
import litellm
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Task → model mapping, fully config-driven.
# These map task names to the environment variable values.
# To route lesson_plan to a self-hosted server:
#   LLM_LESSON_PLAN_MODEL=openai/your-model-name
#   LLM_LESSON_PLAN_API_BASE=http://your-server:8000
TASK_MODEL_MAP: dict[str, str] = {
    "gap_classification": settings.llm_gap_classification_model,
    "study_plan": settings.llm_study_plan_model,
    "lesson_plan": settings.llm_lesson_plan_model,
    "embeddings": settings.llm_embeddings_model,
}

TASK_API_BASE_MAP: dict[str, str | None] = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan": settings.llm_study_plan_api_base,
    "lesson_plan": settings.llm_lesson_plan_api_base,
    "embeddings": settings.llm_embeddings_api_base,
}


async def complete(
    task: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Call the configured LLM for the given task. Provider-agnostic.

    Args:
        task: One of "gap_classification", "study_plan", "lesson_plan"
        messages: OpenAI-format message list [{"role": "...", "content": "..."}]
        temperature: Sampling temperature (default 0.7)
        max_tokens: Maximum tokens in response (default 2000)

    Returns:
        The model's text response as a string.

    Raises:
        ValueError: If task is not in TASK_MODEL_MAP
        litellm.exceptions.APIError: On provider API errors (caller handles retries)
    """
    if task not in TASK_MODEL_MAP:
        raise ValueError(f"Unknown LLM task: {task!r}. Valid tasks: {list(TASK_MODEL_MAP)}")

    model = TASK_MODEL_MAP[task]
    api_base = TASK_API_BASE_MAP.get(task)

    logger.info("llm_call_started", task=task, model=model, has_custom_api_base=api_base is not None)

    response = await litellm.acompletion(
        model=model,
        api_base=api_base or None,  # None tells LiteLLM to use the provider's default endpoint
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    logger.info(
        "llm_call_completed",
        task=task,
        model=model,
        tokens_used=response.usage.total_tokens if response.usage else None,
    )

    return response.choices[0].message.content


async def embed(text: str) -> list[float]:
    """Generate an embedding vector for the given text. Provider-agnostic.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.
    """
    model = TASK_MODEL_MAP["embeddings"]
    api_base = TASK_API_BASE_MAP.get("embeddings")

    response = await litellm.aembedding(
        model=model,
        api_base=api_base or None,
        input=text,
    )

    return response.data[0]["embedding"]
```

**Step 3 — Delete old provider files:**

```
backend/app/ai/providers/base.py      ← DELETE
backend/app/ai/providers/gemini.py    ← DELETE
backend/app/ai/providers/openai.py    ← DELETE
backend/app/ai/providers/anthropic.py ← DELETE
```

**Step 4 — Add LiteLLM config to `backend/app/core/config.py`:**

Add the following fields to the `Settings` class:

```python
# LLM task routing — all overridable via environment variables
llm_gap_classification_model: str = "gemini/gemini-2.5-flash"
llm_gap_classification_api_base: str | None = None

llm_study_plan_model: str = "gpt-4.1-mini"
llm_study_plan_api_base: str | None = None

llm_lesson_plan_model: str = "gpt-4.1"
llm_lesson_plan_api_base: str | None = None

llm_embeddings_model: str = "text-embedding-004"
llm_embeddings_api_base: str | None = None
```

All fields have sensible defaults so existing environments require no changes.
An environment that runs a self-hosted server only needs to set the `_api_base`
and `_model` variables for the tasks it wants to redirect.

**Step 5 — Update `.env.example`:**

Add the new LiteLLM config variables with comments explaining the self-hosted usage:

```bash
# LLM Provider Routing (all tasks default to hosted providers)
# To route a task to your own LLM server, set both _MODEL and _API_BASE:
#   LLM_LESSON_PLAN_MODEL=openai/your-model-name
#   LLM_LESSON_PLAN_API_BASE=http://your-llm-server:8000
LLM_GAP_CLASSIFICATION_MODEL=gemini/gemini-2.5-flash
LLM_GAP_CLASSIFICATION_API_BASE=
LLM_STUDY_PLAN_MODEL=gpt-4.1-mini
LLM_STUDY_PLAN_API_BASE=
LLM_LESSON_PLAN_MODEL=gpt-4.1
LLM_LESSON_PLAN_API_BASE=
LLM_EMBEDDINGS_MODEL=text-embedding-004
LLM_EMBEDDINGS_API_BASE=
```

### Tests to add (`test_llm_router.py`)

```python
test_complete_when_valid_task_then_calls_litellm_with_correct_model()
test_complete_when_unknown_task_then_raises_value_error()
test_complete_when_api_base_set_then_passes_to_litellm()
test_complete_when_api_base_none_then_uses_provider_default()
test_embed_when_called_then_returns_float_list()
```

Use `unittest.mock.patch("litellm.acompletion")` in all tests — do not make real
API calls in unit tests.

---

## Fix 3 — Remove inline `# type: ignore` comments from Celery tasks

### Problem

`backend/app/tasks/onboarding_tasks.py` contains three inline `# type: ignore`
comments that violate `CONSTITUTION.md` Rule 13 and `AGENTS.md`. These are:

```python
@celery_app.task(  # type: ignore[untyped-decorator]
def create_class_diagnostic_task(self, class_id: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
@celery_app.task(  # type: ignore[untyped-decorator]
```

### Fix

Add mypy ignore configuration to `backend/mypy.ini` (create if it does not exist):

```ini
[mypy]
strict = true
plugins = pydantic.mypy

# Celery's @task decorator is not fully typed — suppress at the module level
# rather than with inline ignores (per CONSTITUTION Rule 13)
[mypy-celery.*]
ignore_missing_imports = true
ignore_errors = true

[mypy-app.tasks.*]
# Allow untyped decorators from Celery in task files only
disallow_untyped_decorators = false
```

After adding this configuration, remove all three `# type: ignore` comments from
`onboarding_tasks.py`. Run `mypy app/tasks/` to confirm zero errors remain.

---

## Fix 4 — Empty question bank guard in `create_class_diagnostic_task`

### Problem

`create_class_diagnostic_task` calls `AssessmentService.create_class_diagnostic(class_id)`
which queries the `question_bank` table for questions matching the class's subject
and grade. If the question bank table is empty (which it will be until `M1-1-T1`
runs `import_questions.py`), the task creates an assessment record with zero
questions attached. A student who then starts this empty diagnostic sees a blank
assessment — a broken experience.

### Fix

In `backend/app/services/assessment_service.py`, update `create_class_diagnostic` to
check the question count before creating the assessment:

```python
async def create_class_diagnostic(self, class_id: uuid.UUID) -> Assessment:
    """Create a Tier 1 diagnostic assessment for a class.

    Queries the question_bank for questions matching the class's subject
    and grade. If no questions are found, raises QuestionBankEmptyError
    so the Celery task can exit cleanly without creating an empty assessment.

    Args:
        class_id: The class UUID.

    Returns:
        The created Assessment row.

    Raises:
        QuestionBankEmptyError: If no questions exist for this subject/grade.
        ValueError: If the class is not found.
    """
    class_ = await self.db.get(Class, class_id)
    if not class_:
        raise ValueError(f"Class {class_id} not found")

    # Count available questions before doing anything else
    question_count = await self.db.scalar(
        select(func.count(QuestionBank.id)).where(
            QuestionBank.subject_id == class_.subject_id,
            QuestionBank.grade_id == class_.grade_id,
        )
    )

    if not question_count:
        raise QuestionBankEmptyError(
            f"No questions in question_bank for subject={class_.subject_id} "
            f"grade={class_.grade_id}. Run import_questions.py first."
        )

    # ... rest of the existing diagnostic creation logic
```

Add `QuestionBankEmptyError` as a custom exception class in
`backend/app/services/assessment_service.py`:

```python
class QuestionBankEmptyError(Exception):
    """Raised when the question bank has no questions for the given subject/grade.

    This is an expected condition during development before import_questions.py
    has been run. The Celery task handles this by logging a warning and exiting
    cleanly without creating an empty assessment.
    """
    pass
```

In `backend/app/tasks/onboarding_tasks.py`, catch `QuestionBankEmptyError` in
`create_class_diagnostic_task` and exit cleanly:

```python
try:
    assessment = await service.create_class_diagnostic(class_id=class_uuid)
except QuestionBankEmptyError as exc:
    logger.warning(
        "create_class_diagnostic_skipped_empty_question_bank",
        class_id=class_id,
        reason=str(exc),
    )
    # Return without creating assessment — task succeeded, just had nothing to do.
    # The assessment will be created when the teacher manually triggers it after
    # import_questions.py has been run.
    return {"assessment_id": None, "class_id": class_id, "skipped": True}
```

---

## Fix 5 — Dead-letter CRITICAL log on Celery task final retry exhaustion

### Problem

Both `create_class_diagnostic_task` and `trigger_onboarding_diagnostics` have
`max_retries=3` but no mechanism to signal failure after all retries are consumed.
When a task permanently fails, it silently disappears from the queue. This means
a school admin has no way to know that a student's diagnostic was never created,
and no operational alert fires.

### Fix

Add an `on_failure` callback to each Celery task. Celery calls `on_failure` when a
task raises an unhandled exception after all retries are exhausted:

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.onboarding_tasks.create_class_diagnostic_task",
)
def create_class_diagnostic_task(self, class_id: str) -> dict[str, object]:
    # ... existing implementation ...
    pass

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called by Celery when all retries are exhausted.

        Emits a CRITICAL structured log event so the operations team is alerted.
        Per CONSTITUTION Rule 18.
        """
        logger.critical(
            "celery_task_permanently_failed",
            task_name=self.name,
            task_id=task_id,
            class_id=args[0] if args else kwargs.get("class_id"),
            error=str(exc),
            exc_info=True,
        )
```

Apply the same `on_failure` method to `trigger_onboarding_diagnostics`, including
`student_id` in the structured log:

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    logger.critical(
        "celery_task_permanently_failed",
        task_name=self.name,
        task_id=task_id,
        student_id=args[0] if args else kwargs.get("student_id"),
        class_id=args[1] if len(args) > 1 else kwargs.get("class_id"),
        error=str(exc),
        exc_info=True,
    )
```

---

## Acceptance Criteria

**Fix 1 — KaihleAdmin schools.py bypass:**
- `GET /api/v1/schools/{any_school_id}/classes` with a KaihleAdmin JWT returns 200
- `POST /api/v1/schools/{any_school_id}/classes` with a KaihleAdmin JWT returns 201
- All new integration tests pass

**Fix 2 — LiteLLM router:**
- `pip install litellm` installs successfully in the backend virtual environment
- `from app.ai.providers.router import complete, embed` imports without error
- Old provider files (`base.py`, `gemini.py`, `openai.py`, `anthropic.py`) no longer exist
- All new unit tests for the router pass using mocked `litellm.acompletion`
- `mypy app/ai/` passes with zero errors

**Fix 3 — No inline type: ignore:**
- `grep -r "# type: ignore" backend/app/tasks/` returns zero results
- `mypy app/tasks/` passes with zero errors after mypy.ini configuration is applied

**Fix 4 — Empty question bank guard:**
- Running `create_class_diagnostic_task` against an empty `question_bank` table returns
  `{"assessment_id": None, "class_id": "...", "skipped": True}` — no exception raised
- A `WARNING` log event with `"create_class_diagnostic_skipped_empty_question_bank"` appears
- No `Assessment` row is created in the database
- Unit test: `QuestionBankEmptyError` raised when question count is zero

**Fix 5 — Dead-letter CRITICAL log:**
- Unit test: after `max_retries` is exceeded, `on_failure` is called
- Unit test: `on_failure` emits a log event with level `CRITICAL` and includes
  `task_name`, `class_id`, and `error` fields
- `student_id` is included in the `trigger_onboarding_diagnostics` on_failure log

---

## Do NOT Touch

- Any database migration — none of these fixes require schema changes
- Any frontend file
- `backend/app/api/v1/routes/users.py` — its `_check_school_access` is already correct
- The existing Celery task logic beyond the specific additions described above
