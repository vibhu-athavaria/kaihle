# AGENTS.md
# Kaihle Platform — Engineering & Review Contract

This document defines:

1. System engineering constraints (ALWAYS ACTIVE)
2. AI review contract behaviour (ONLY when explicitly invoked)

These rules are mandatory for ALL development on the Kaihle platform.
KiloCode must read this file in full before writing any code.
Feature-specific details, phase sequences, and schema definitions live in `project-plan.md`.

---

# PART 1 — SYSTEM ENGINEERING CONSTRAINTS (Always Active)

These rules apply to ALL development work at all times,
regardless of which feature or module is being built.

---

## 1. System Architecture (Non-Negotiable)

The Kaihle platform consists of:

- **FastAPI Backend** — API layer only. Auth, validation, routing, task enqueueing.
- **Celery Worker Service** (`celery_worker`) — All async, long-running, and LLM tasks. Consumes queues: `default`, `reports`, `study_plans`.
- **Manim Worker Service** (`manim_worker`) — Animation rendering only. Consumes ONLY `manim_queue`. Has Manim + LaTeX + FFmpeg installed. `celery_worker` does NOT have Manim installed. These containers are never interchangeable.
- **PostgreSQL** — Primary persistent storage. All relational data lives here. Uses `pgvector/pgvector:pg16` image (pgvector extension required).
- **Redis** — Session cache, Celery broker, rate limiting, deduplication, status flags.
- **AWS S3 / MinIO** — Permanent object storage for all generated media assets (MP4, PNG, JSON). MinIO used in development (`USE_MINIO=true`); AWS S3 used in production (`USE_MINIO=false`). S3 uploads are worker-only. Presigned URL generation is the only S3 operation permitted in the API layer.
- **React + Vite Frontend** — Client-side only. Communicates with FastAPI exclusively.
- **LLM Provider** — Google Gemini (primary for enriched content) or configured alternative (see Section 3). Called ONLY from Celery worker tasks. Never from the API layer.

### Hard Rules

1. FastAPI must NEVER call the LLM provider directly.
2. LLM calls must ONLY occur inside Celery worker tasks.
3. No long-running tasks inside the API request lifecycle.
4. Workers must NOT expose HTTP endpoints.
5. API enqueues tasks; Workers execute them. This separation is absolute.
6. Assessment question delivery must NEVER involve an LLM call at runtime.
7. The Assessment Engine is a state machine — treat it as such at all times.
8. Question generation is a content pipeline — completely separate from assessment delivery.
9. S3 uploads must NEVER occur from the FastAPI layer. Upload operations belong to Celery worker tasks only. The sole permitted S3 operation in the API layer is `generate_presigned_url` (read-only metadata, no data transfer).
10. The `manim_worker` container exclusively consumes `manim_queue`. The `celery_worker` container must NEVER consume `manim_queue`. Routing any non-animation task to `manim_queue`, or any animation task to `celery_worker`, is a hard violation. Manim is installed only in `manim_worker`.

Strict separation between API layer, Worker layer, LLM provider, and S3 storage is mandatory.

---

## 2. Difficulty Scale (Global Standard — Non-Negotiable)

All difficulty values across the entire codebase use Integer 1–5.
No other scale is permitted. No Float difficulty values. No string enums for difficulty.

| Value | Label    |
|-------|----------|
| 1     | Beginner |
| 2     | Easy     |
| 3     | Medium   |
| 4     | Hard     |
| 5     | Expert   |

This applies universally: all model columns, all API responses,
all frontend displays, and all scoring logic.
Any code that stores, compares, or transmits a difficulty value must use this scale.

---

## 3. LLM Provider Layer (Provider-Agnostic)

Kaihle supports multiple LLM providers via a unified provider strategy.
The active provider is controlled entirely by environment variables.
Business logic (Celery tasks) must NEVER reference a specific provider directly —
always use the `LLMProvider` abstraction.

### 3.1 Supported Providers

| Provider        | Value            | Notes |
|-----------------|------------------|-------|
| RunPod          | `runpod`         | Self-hosted. OpenAI-compatible endpoint. |
| AutoContent API | `autocontentapi` | OpenAI-compatible endpoint. Drop-in swap. |
| Google Gemini   | `google`         | Primary provider for enriched study plan + media generation tasks. Uses google-generativeai SDK. Multiple specialised models (see Section 3.2). |

**Provider scope by task type:**

| Task | Provider | Model env var |
|---|---|---|
| Report generation, question tasks | `LLM_PROVIDER` (any) | `LLM_MODEL` / provider-specific |
| Study plan generation (`generate_enriched_study_plan`) | Google Gemini | `GEMINI_LLM_MODEL` |
| Animation scene planning (`generate_animation_manim` Stage 2) | Google Gemini | `GEMINI_LLM_MODEL` |
| Animation code generation (`generate_animation_manim` Stage 3) | Google Gemini | `GEMINI_FLASH_MODEL` |
| Animation code fix loop (`generate_animation_manim` Stage 4) | Google Gemini | `GEMINI_FLASH_MODEL` |
| TTS voiceover (`generate_animation_manim` Stage 5) | Google Gemini TTS | `GEMINI_TTS_VOICE` |
| Infographic generation (`generate_infographic`) | Google Gemini Imagen 3 | `GEMINI_IMAGE_MODEL` |
| Curriculum embeddings (`ingest_curriculum_embeddings`) | Google Gemini | `GEMINI_EMBEDDING_MODEL` |

Tasks listed above that call Google Gemini directly **bypass the `LLMProvider` abstraction** — they use `google.generativeai` SDK directly because they require model-specific features (Imagen 3, TTS, embeddings) that the unified `BaseLLMProvider.complete()` interface does not expose. This is the only sanctioned exception to the provider abstraction rule.

### 3.2 Environment Configuration

```env
# ── General LLM provider (runpod | autocontentapi | google) ──────────
# Used for report generation and question-related tasks only.
# Enriched study plan + media generation tasks always use Google Gemini
# regardless of this setting — see Section 3.1 provider scope table.
LLM_PROVIDER=runpod

# RunPod (self-hosted, OpenAI-compatible)
RUNPOD_API_BASE=https://api.runpod.ai/v2/{endpoint_id}/openai/v1
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_MODEL=your_deployed_model_name

# AutoContent API (OpenAI-compatible)
AUTOCONTENTAPI_BASE_URL=https://api.autocontentapi.com/v1
AUTOCONTENTAPI_KEY=your_autocontentapi_key
AUTOCONTENTAPI_MODEL=model_name

# Google Gemini — shared API key for ALL Gemini services (LLM, TTS, Imagen, Embeddings)
GEMINI_API_KEY=your_gemini_api_key

# Google Gemini — model selection (do not change without coordinated migration plan)
GEMINI_LLM_MODEL=gemini-2.5-pro          # study plan generation + animation scene planning
GEMINI_FLASH_MODEL=gemini-2.5-flash      # animation code generation + fix loop (faster/cheaper)
GEMINI_IMAGE_MODEL=imagen-3.0-generate-002  # infographic PNG generation
GEMINI_EMBEDDING_MODEL=text-embedding-004   # curriculum content embeddings (768 dimensions)
GEMINI_TTS_VOICE=Kore                    # Gemini TTS voice for animation voiceover

# Shared LLM settings (applied to LLMProvider abstraction tasks only)
LLM_MAX_TOKENS=4000
LLM_TEMPERATURE=0.3
LLM_TIMEOUT_SECONDS=90
```

> **Note on `GOOGLE_API_KEY`:** The previous `GOOGLE_API_KEY` variable is superseded by
> `GEMINI_API_KEY`. If you have existing `.env` files using `GOOGLE_API_KEY`, rename it.
> The application will raise `ValueError` at startup if `GEMINI_API_KEY` is not set and
> any Gemini-backed task is registered.

### 3.3 LLM Provider Abstraction

**File: `app/services/llm/provider.py`**

This file must be created and all LLM calls must route through it.
No Celery task or service may instantiate a provider client directly.

```python
"""
LLMProvider — unified interface for all LLM backends.

Usage in Celery tasks:
    from app.services.llm.provider import get_llm_provider
    llm = get_llm_provider()
    response = llm.complete(system_prompt, user_prompt)

Never instantiate a provider client directly in business logic.
"""

class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str

class BaseLLMProvider:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        raise NotImplementedError

class RunPodProvider(BaseLLMProvider):
    """Uses OpenAI-compatible client pointed at RunPod endpoint."""
    ...

class AutoContentAPIProvider(BaseLLMProvider):
    """Uses OpenAI-compatible client pointed at AutoContent API endpoint."""
    ...

class GoogleGeminiProvider(BaseLLMProvider):
    """Uses google-generativeai SDK."""
    ...

def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function. Reads LLM_PROVIDER from settings.
    Returns the correct provider instance.
    Raises ValueError for unknown provider values.
    """
    provider = settings.LLM_PROVIDER
    if provider == "runpod":
        return RunPodProvider()
    elif provider == "autocontentapi":
        return AutoContentAPIProvider()
    elif provider == "google":
        return GoogleGeminiProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

### 3.4 LLM Call Protocol (Mandatory — applies to ALL providers)

Before ANY call to any LLM provider:

1. Generate a deterministic cache key using the format:
   ```
   kaihle:llm_cache:{prompt_type}:{hash(system_prompt + user_prompt)}
   ```
2. Check Redis for a cached result.
3. If cached → return immediately. Do NOT call the LLM.
4. If not cached:
   - Call LLM via `get_llm_provider().complete(...)`
   - Log the call (see Section 3.5)
   - Store result in Redis with appropriate TTL
   - Update per-student LLM usage tracking in DB

LLM calls without caching are forbidden — **except for the three tasks listed in
Section 3.4.1, which use S3 as their permanent content cache instead of Redis.**

### 3.4.1 S3-Backed Content Cache (Exception to Section 3.4)

The following three tasks are **exempt from the Redis LLM cache rule** in Section 3.4.
They use S3 as their permanent content store. Do NOT apply Redis caching to them.

| Task Name | S3 Content Stored |
|---|---|
| `tasks.generate_enriched_study_plan` | Multi-modal content spec JSON |
| `tasks.generate_animation_manim` | Manim Python code + rendered MP4 |
| `tasks.generate_infographic` | Image generation prompt + rendered PNG |

**The S3-backed cache protocol for these three tasks (replaces the Redis check in 3.4):**

1. Build `prompt_hash` = SHA-256 of canonical prompt inputs.
   Canonical string: `json.dumps(inputs, sort_keys=True, ensure_ascii=True)`.
   Required input keys: `grade_code`, `subject_code`, `subtopic_id`, `mastery_band`,
   `priority`, `rag_content_ids` (sorted list), `learning_style`, `content_type`.
   Any missing key must raise `KeyError` immediately — do not proceed with partial inputs.
2. Query `generated_content` table:
   `WHERE prompt_hash = :hash AND content_type = :type AND status = 'completed'`
3. If row found → return existing `s3_key`. Do NOT call the LLM. Do NOT upload anything.
4. If no row found → call LLM/media API → upload result to S3 → insert `GeneratedContent`
   row with `status = 'completed'` and `s3_key` populated.

**All other LLM calls** (assessment report generation, question-related tasks, etc.) continue
to use the Redis caching protocol in Section 3.4 unchanged.

### 3.5 LLM Usage Logging (Mandatory)

Every LLM call must produce a structured log entry with at minimum:

```json
{
  "timestamp": "ISO8601",
  "level": "info",
  "service": "worker",
  "task": "{celery_task_name}",
  "student_id": "{uuid}",
  "provider": "{active_provider}",
  "model": "{model_name}",
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "cached": false
}
```

Never log: raw prompt content, student PII, or API keys of any kind.

### 3.6 Provider Switching

Switching providers requires only changing `LLM_PROVIDER` in `.env`.
No code changes are required.
Provider switching must have test coverage verifying all three providers
can be instantiated and route correctly.

---

## 4. Assessment Engine Rules (Non-Negotiable)

The assessment engine is a state machine.
These rules govern its behaviour absolutely.

### 4.1 Separation of Concerns

```
Question Generation Pipeline   ←→   Assessment Session Engine
(Celery batch tasks, offline)        (Runtime state machine, no LLM)
```

These are two completely separate systems. They must never be coupled.

### 4.2 Adaptive Questioning Rules

- The number of questions per subtopic and the starting difficulty are
  controlled by environment variables. See `project-plan.md` for specifics.
- Correct answer → next difficulty increases by 1, capped at maximum (5).
- Incorrect answer → next difficulty decreases by 1, floored at minimum (1).
- Difficulty is always Integer 1–5. Never Float. Never string.
- Questions are selected ONE AT A TIME as answers come in. Never pre-selected.
- Used question IDs are tracked per subtopic per session to prevent repetition.

### 4.3 Assessment State Machine Transitions

```
STARTED → IN_PROGRESS (first answer received)
IN_PROGRESS → COMPLETED (final question answered)
IN_PROGRESS → ABANDONED (explicit abandon or timeout)
```

The session state in Redis and the assessment status in PostgreSQL
must stay in sync on every transition. Inconsistency is a bug.

### 4.4 Answer Submission Rules

- An assessment question record is created when a question is SERVED, not at session init.
- The same record is UPDATED when the answer is submitted.
- Re-answering an already-answered question must return `409 Conflict`.
- Submitting to a COMPLETED assessment must return `400 Bad Request`.
- Submitting a question that is not the current active question must return `404 Not Found`.
- The correct answer, explanation, and correctness flag must NEVER appear in the
  question-delivery API response. These are report-only fields.

---

## 5. Redis Usage (Required)

Redis is mandatory for session state, task status flags, LLM caching, and rate limiting.

### 5.1 Key Format Convention (Non-Negotiable)

All Redis keys must follow this format:

```
kaihle:{service}:{entity}:{identifier}
```

No arbitrary key names are permitted.
Every new Redis key must follow this format without exception.
Feature-specific key definitions are documented in `project-plan.md`.

### 5.2 Required TTLs

Every Redis key must have an explicit TTL set at write time.
Keys without TTL are forbidden — they cause unbounded memory growth.
TTL values for each key type are defined in `project-plan.md`.

---

## 6. Database Rules (Non-Negotiable)

1. All columns used in WHERE clauses must be indexed.
2. No `SELECT *` in production code. Always select explicit columns.
3. All schema changes must go through Alembic migrations. No manual `ALTER TABLE`.
4. All migrations must be reversible — include a working `downgrade()`.
5. Unique constraints must be enforced at the DB level, not just application level.
6. All primary keys use UUID. No integer sequences for new tables.
7. All timestamps in UTC with timezone awareness.
8. No raw SQL strings in application code. Use SQLAlchemy ORM or `text()` with explicit params.

Feature-specific index definitions are documented in `project-plan.md`.

---

## 6.1 Import Style (Non-Negotiable)

All imports must be declared at the top of the file. Inline imports are forbidden.

### Allowed Exceptions

The only permitted inline imports are:

1. **Optional dependencies** that may not be installed in all environments:
   ```python
   try:
       import google.generativeai as genai
       GOOGLE_AVAILABLE = True
   except ImportError:
       genai = None
       GOOGLE_AVAILABLE = False
   ```

2. **Type-checking imports** to avoid circular dependencies:
   ```python
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from app.models.user import User
   ```

### Forbidden Patterns

```python
# FORBIDDEN - inline import inside function
def my_function():
    from app.services.llm.provider import get_llm_provider
    llm = get_llm_provider()

# REQUIRED - import at top of file
from app.services.llm.provider import get_llm_provider

def my_function():
    llm = get_llm_provider()
```

### Rationale

- Imports at the top make dependencies explicit and visible
- Easier to identify what a module depends on
- Prevents runtime import errors hidden in rarely-executed code paths
- Improves IDE support and static analysis

---

## 7. Async & Performance Rules

1. No blocking I/O in async FastAPI endpoints.
2. All database access in FastAPI must use async SQLAlchemy (`AsyncSession`).
3. All Redis access in FastAPI endpoints must use `redis.asyncio`.
4. Celery tasks use synchronous DB and Redis clients — Celery is not async-native.
5. Heavy computation must not block the API event loop.
6. No N+1 query patterns. Use joins or explicit eager loading.

### 7.1 Performance Targets

All API endpoints must respond within 500ms excluding Celery-dispatched work.
Feature-specific targets for individual operations are defined in `project-plan.md`.
Any code path that risks exceeding performance targets must include a comment explaining the risk.

---

## 8. Cost Control

### 8.1 LLM Cost Controls

- All LLM calls must be cached — see Section 3.4 for Redis caching (default) and
  Section 3.4.1 for the S3-backed cache used by the three media generation tasks.
  There are no uncached LLM calls anywhere in the codebase.
- LLM calls must never occur during assessment question delivery.
- LLM timeout must be enforced via `LLM_TIMEOUT_SECONDS`.
- On LLM timeout: retry up to `max_retries`, then fail the task gracefully.
- Celery tasks must not loop LLM calls — one call per task invocation where possible.
- S3 uploads are permanent and billable. Never upload to S3 without first performing
  the prompt_hash dedup check in `generated_content` (Section 3.4.1). Duplicate uploads
  are a cost bug.

### 8.2 DB Cost Controls

- No unbounded queries. All list queries must have pagination or explicit limits.
- No query inside a loop. Batch load, then process in memory.

---

## 9. Logging & Observability

All logs must be structured JSON. Use `structlog` or equivalent.

Every log entry must include:

```json
{
  "timestamp": "ISO8601",
  "level": "info | warning | error",
  "service": "api | worker",
  "user_id": "uuid or null",
  "student_id": "uuid or null",
  "action": "descriptive_action_name",
  "status": "success | failure | started"
}
```

### 9.1 What Must Be Logged

- Every Celery task: started, completed, failed (with retry count)
- Every LLM call: provider, model, tokens, cached (true/false)
- Every assessment state transition
- Every answer submission (student_id, is_correct, difficulty level)
- Every Redis cache hit/miss for LLM calls
- Every S3 upload: task name, s3_key, content_type, file_size_bytes
- Every S3-backed cache hit (prompt_hash match found — LLM call skipped)
- Every content reuse event: new_content_id, reused_from_id, subtopic_id (fingerprint match)
- Every GeneratedContent status transition: PENDING → COMPLETED / FAILED / REUSED

### 9.2 What Must NEVER Be Logged

- Student passwords or hashed passwords
- JWT tokens
- Raw LLM prompt content containing student data
- API keys of any provider

---

## 10. Fail Fast Philosophy (Non-Negotiable)

Over-protective, defensive programming is forbidden.
The system must fail loudly, immediately, and at the exact point of failure.

### 10.1 Core Principle

If a required condition is not met — raise an exception.
Do NOT silently handle it, substitute a default, or let execution continue.

A function that requires a value must receive that value.
If it does not, it must raise immediately — not guess, not skip, not log-and-continue.

A crash with a clear error message is always preferable to corrupted or silent behaviour.

### 10.2 Hard Rules

1. **Required function arguments must be enforced at the call site.**
   If a function requires a value, the caller must pass it.
   The function must NOT check for None and silently return early.

   ```python
   # FORBIDDEN — hides the real bug
   def get_session(student_id: UUID | None):
       if not student_id:
           return None

   # REQUIRED — fails at the right place
   def get_session(student_id: UUID):
       ...
   ```

2. **No silent fallbacks for missing required data.**
   If a required DB record does not exist, raise `404` or a domain exception.
   Do NOT return an empty object, `None`, or a default placeholder.

3. **No swallowed exceptions.**

   ```python
   # FORBIDDEN
   try:
       result = some_operation()
   except Exception:
       pass

   # REQUIRED — catch only what you handle, re-raise everything else
   try:
       result = some_operation()
   except SpecificException as e:
       logger.error("specific failure", error=str(e))
       raise
   ```

4. **No default substitution for invalid state.**
   If the system enters an unexpected state, raise immediately.
   Do NOT attempt to recover silently.

5. **Pydantic validation must be strict.**
   All required fields are non-optional in schemas.
   Do NOT use `Optional` for fields that are functionally required.
   Validation failure must surface as `422` immediately.

6. **Type hints are contracts, not suggestions.**
   If a function is typed to receive `UUID`, it must receive `UUID`.
   Functions must not internally guard against `None` or `str`
   unless the type hint explicitly declares it.

### 10.3 Where Defensive Handling IS Acceptable

The only legitimate cases for defensive handling in Kaihle:

- **LLM provider calls (RunPod, AutoContent API, Google Gemini)**
  — external systems can fail for reasons outside our control.
  Catch, log, retry via Celery, then fail the task gracefully after max retries.
- **Celery task retries**
  — transient failures are expected. `max_retries` is intentional, not defensive.
- **Redis cold cache fallback to DB**
  — explicitly defined in the architecture. Acceptable and documented.
- **S3 upload/download operations (boto3 / MinIO)**
  — network and service errors are transient. Catch `ClientError`, log, retry via Celery.
  `S3Client.NotFoundError` on download is a legitimate failure — mark `GeneratedContent`
  as FAILED and do not retry.
- **Gemini media API calls (TTS, Imagen 3)**
  — external media APIs can fail or apply safety filters. Catch API errors and retry via
  Celery. Safety filter rejections (deterministic) must mark `GeneratedContent` as FAILED
  immediately — do not retry a safety block.
- **RAG embedding API calls (Gemini text-embedding-004)**
  — rate limit and transient errors are expected at bulk ingestion scale.
  Catch, log, retry with exponential backoff. Respect the `rate_limit="30/m"` task setting.

Everything else: fail fast, fail loudly.

---

## 11. Security Rules

1. All input validated via Pydantic schemas before any processing.
2. JWT tokens must have expiry. Refresh token rotation is required.
3. Students must not access other students' data. Enforce at service layer, not just route.
4. Parents must only access data for their own registered children.
5. File uploads (if any): validate MIME type and enforce max size.
6. No sensitive data in error responses returned to clients.
7. All environment secrets loaded via `.env` only. Never hardcoded.

---

## 12. Implementation Order (Non-Negotiable)

Development must follow `project-plan.md` phases sequentially.
The phase sequence, branch names, and acceptance criteria are defined in `project-plan.md`.

Do NOT implement future phases prematurely.
Do NOT begin a new phase until the current phase is fully closed per the Git Workflow below.

---

## 13. Git Workflow (Non-Negotiable)

Every unit of work is developed on its own dedicated branch.
Work is never done directly on `main`.

### 13.1 Branch Convention

Create branches from `main` before writing any code:

```bash
git checkout main
git pull origin main
git checkout -b feature/{short-description}
```

Branch names must be lowercase, hyphenated, and descriptive.
One branch per logical unit of work. No combined branches.

### 13.2 Work Completion Requirements

A branch is NOT ready to close until ALL of the following are true:

1. **All acceptance criteria met** — as defined in `project-plan.md` for the current phase.

2. **Test coverage ≥ 90%** — enforced by the test runner, not self-assessed.

   Backend:
   ```bash
   pytest --cov=app --cov-report=term-missing --cov-fail-under=90
   ```

   Frontend:
   ```bash
   npm run test -- --coverage --coverageThreshold='{"global":{"lines":90}}'
   ```

   Coverage below 90% blocks closure. Write missing tests before proceeding.

3. **Code is clean and committed:**
   - No uncommitted changes (`git status` is clean)
   - No debug code, commented-out blocks, or TODOs in production paths
   - All new environment variables documented in `.env.example`
   - Migration files committed alongside their model changes

   Use conventional commit format:
   ```
   feat(scope):  new functionality
   fix(scope):   bug fix
   chore(scope): config, migration, tooling
   ```

4. **Branch pushed to origin and confirmed:**
   ```bash
   git push origin feature/{short-description}
   ```

### 13.3 Commit Hygiene

- One logical unit of work per commit where possible.
- Do not commit broken or untested code at any point.
- Migration files must always be committed with the model changes they support.
- Do not bundle unrelated changes into one commit.

---

# PART 2 — AI ENGINEERING REVIEW CONTRACT
(Activated ONLY when explicitly invoked)

This contract applies ONLY when the user says:
- "Full Engineering Review"
- "Review Mode"
- Or a similar explicit instruction

For normal development, default behaviour applies.

---

## 1. Engineering Philosophy (Non-Negotiable)

### 1.1 DRY
- Identify duplication aggressively.
- Consolidate unless doing so increases coupling.

### 1.2 Testing
- Prefer strong, explicit assertions over broad ones.
- Identify missing edge cases and failure modes.
- Test the unhappy path as rigorously as the happy path.

### 1.3 Engineering Balance
- Avoid under-engineering (no error handling, no edge cases).
- Avoid premature abstraction (solving problems that don't exist yet).
- Aim for "engineered enough."

### 1.4 Explicit Over Clever
- Prefer clarity over terseness.
- Avoid magic, hidden behaviour, and implicit side effects.

### 1.5 Edge Cases
- Identify missing validation.
- Identify unhandled boundary conditions.
- Identify unhandled failure paths.

---

## 2. Review Structure (Strict Order)

The review must be conducted in this exact order:

1. Architectural Review
2. Code Quality Review
3. Test Review
4. Performance Review

The agent must NOT skip any section.
The agent must NOT combine sections.

---

## 3. Review Modes (User Must Choose)

Before beginning review, the agent MUST ask the user to choose:

**Option 1 — BIG CHANGE**
- Work section by section
- Maximum 4 issues per section
- Pause and wait for user response after each section

**Option 2 — SMALL CHANGE**
- One issue at a time
- Fully interactive
- Pause and wait for user response after each issue

The agent MUST wait for the user's selection before proceeding.

---

## 4. Issue Reporting Format (Strict)

For EVERY issue found:

```
## Issue X: <Concise Title>

### Problem
Concrete description of the issue.
Reference file names and line numbers where available.

### Options

A. <Recommended Option>
- Implementation effort: Low / Medium / High
- Risk level: Low / Medium / High
- Impact: description
- Maintenance burden: description

B. <Alternative Option>
- Same breakdown as above

C. Do Nothing
- Explicit analysis of consequences of leaving this unresolved

### Recommendation
Clear opinion on which option to take.
Justified using the Engineering Philosophy above.

### Decision Required
"Regarding Issue X, do you want Option A (recommended) or Option B?"
```

---

## 5. Section Evaluation Criteria

### 5.1 Architectural Review
Evaluate:
- API vs Worker boundary violations
- Coupling between layers
- Data flow correctness
- Assessment engine state machine integrity
- LLM call location (must be in Worker only)
- Redis key format compliance
- Redis TTL compliance (no keys without TTL)
- Security boundary violations
- Cost amplification risks
- S3 upload calls from the API layer (forbidden — workers only, except `generate_presigned_url`)
- S3-backed cache bypass: media generation tasks must check `generated_content` prompt_hash
  before calling LLM or media APIs (Section 3.4.1). Missing this check is a cost bug.
- Manim task routing: `tasks.generate_animation_manim` must be in `manim_queue` only.
  Any route to `default` or `study_plans` queue is a hard architectural violation.

### 5.2 Code Quality Review
Evaluate:
- DRY violations
- Error handling gaps
- Unhandled edge cases
- Over-engineering or under-engineering
- Difficulty scale violations (Float or string where Integer 1–5 required)
- Missing provider abstraction in text LLM calls (must use `get_llm_provider()`)
- Gemini media/embedding SDK called directly when it should route through provider abstraction
  (only TTS, Imagen, and embedding calls are permitted to bypass — all others are violations)
- Fail fast violations (swallowed exceptions, silent fallbacks, missing raises)
- Hidden cost multipliers
- S3 upload operations in FastAPI route handlers (absolute violation — workers only)
- Missing prompt_hash dedup check before S3 upload in media generation tasks
- `tasks.generate_animation_manim` importing or calling Manim outside `manim_worker` context

### 5.3 Test Review
Evaluate:
- Coverage gaps (minimum: 90%)
- Assertion strength (assert specific values, not just truthy/falsy)
- Missing adaptive difficulty edge case tests
- Missing LLM caching tests
- Missing idempotency tests
- Missing Redis cold cache fallback tests
- Missing provider switching tests
- Untested failure modes

### 5.4 Performance Review
Evaluate:
- N+1 query patterns
- Blocking async calls
- Missing Redis usage where required
- Missing or incorrect DB indexes
- Queries exceeding performance targets defined in `project-plan.md`
- Unindexed filter columns
- LLM calls outside of Worker

---

## 6. Interaction Constraints

- Do NOT assume scope priorities — always ask.
- Do NOT batch multiple decisions into one question.
- Always pause after each section (Review Mode 1) or each issue (Review Mode 2).
- Never skip the structured issue format.
- Never make changes without explicit user approval.

---

## 7. Tone

- Direct
- Structured
- Opinionated but always justified
- No vague generalities
- No speculative abstraction
- Reference specific files, functions, and line numbers wherever possible