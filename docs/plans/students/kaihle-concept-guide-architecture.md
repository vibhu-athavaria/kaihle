# AI Concept Guide — Technical Architecture
**Feature:** ST-020 / SP-004
**Reviewed by:** Kramer (engineering) · Pixel (frontend) · Vidhya (pedagogy)
**Status:** Architecture locked — implement against this document, not ST-020 alone

---

## What We Should Have Checked Before Writing ST-020

Before specifying any AI feature in Kaihle, the team must verify:
1. What schema tables hold the input data
2. What API endpoints already exist vs. need to be built
3. Where the LLM call lives (always backend — never client-side)
4. Which LLM task routing entry to add

None of this was done in ST-020. This document corrects the record.

---

## Correction — `interests` Type Was Wrong in ST-020 v2

The v2 task file changed `interests: string[]` to `interestCategory: string` with an
`INTEREST_LABELS` enum mapping. **This was wrong.** The schema is authoritative:

```sql
-- student_learning_profiles
interests TEXT[]
-- Free-text tags stored lowercase.
-- e.g. ARRAY['football', 'music', 'gaming', 'cooking']
```

The data is already human-readable. No enum mapping layer is needed.
The Concept Guide system prompt calls `interests[0:2].join(", ")` directly.

**ST-020 v2 must be corrected on this point — see the errata section at the bottom.**

---

## Data Available (All Exists Today)

### From `student_learning_profiles`
```
modality_scores  JSONB  {"visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5}
interests        TEXT[] ["football", "music", "gaming"]   ← already human-readable
work_style       JSONB  {"prefers_solo": true, "short_sessions": false, "concept_first": false}
completed_at     TIMESTAMPTZ  non-NULL = profile is usable
```
Retrieved via: `GET /api/v1/onboarding/learning-profile` (student calls own profile)

> ⚠️ This endpoint's implementation status: listed as a task in M0-10-T7 addendum.
> Before ST-020 ships: verify it returns real `student_learning_profiles` data, not a stub.
> If it is a stub, implementing ST-020 depends on this being resolved first.

### From `gap_states`
```
mastery_score   FLOAT  0.0–1.0
subtopic_id     UUID
student_id      UUID
class_id        UUID
```
Retrieved via: `GET /api/v1/students/me/gap-map?subject_id=` — confirmed live.
The frontend already has `masteryScore` for each subtopic in `SubtopicScoreRow`
from the gap map data. It does not need a separate API call to get the mastery score
— it's passed as a prop to the panel.

### From `subtopics` (via gap map response)
```
subtopic_id    UUID
subtopic_name  TEXT  e.g. "Solving simultaneous equations by substitution"
topic_name     TEXT  e.g. "Algebra"
```
The gap map response (`StudentGapMap`) includes `subtopic_name` and `topic_name`
per `StudentSubtopicScore`. The frontend passes `subtopicName` to the panel.

### From student's class enrollment (via `/students/me/info` or existing query)
```
grade_name  TEXT  e.g. "Grade 9"
```
Already available in `useStudentInfo()` return data — `studentInfo.gradeName`.

---

## What Does NOT Exist and Must Be Built

### 1. Backend endpoint — `POST /api/v1/students/me/concept-guide`

Does not exist. No stub. Must be created as part of ST-020.

```python
# backend/app/api/v1/routes/concept_guide.py (new file)

POST /api/v1/students/me/concept-guide
Auth:          Student JWT required (own profile only — no teacher access)
Rate limit:    20 requests per student per hour (slowapi)
Content-Type:  application/json

Request body:
{
  "subtopic_id":   UUID,       # required — the subtopic to explain
  "subtopic_name": str,        # passed from frontend — avoids a DB lookup
  "topic_name":    str,        # passed from frontend
  "mastery_score": float|null, # passed from frontend gap map data
  "grade_name":    str         # passed from frontend studentInfo
}

Response 200:
{
  "explanation":     str,   # 100–180 words — the main explanation
  "analogy":         str,   # one sentence linking to student's interest
  "steps":           list[str],  # 3–5 step breakdown
  "check_question":  str,
  "check_options":   list[str],  # exactly 4 items: ["A) ...", "B) ...", "C) ...", "D) ..."]
  "correct_answer":  str         # one of "A", "B", "C", "D"
}

Response 422: malformed request
Response 429: rate limit exceeded — {"detail": "Rate limit exceeded. Try again in a moment."}
Response 503: LLM unavailable — {"detail": "Guide is temporarily unavailable. Please try again."}
```

**Why mastery_score, subtopic_name, grade_name come from the frontend:**
The frontend already has all three from existing queries (`useMyGapMap`, `useStudentInfo`).
Having the backend re-fetch them from the DB is a redundant round trip. The backend's job
is to load the learning profile (which the frontend doesn't hold), build the prompt, and
call the LLM.

**What the backend loads (one DB query):**
```python
# concept_guide_service.py
async def get_concept_guide(
    student_id: UUID,
    request: ConceptGuideRequest,
    db: AsyncSession,
) -> ConceptGuideResponse:
    # 1. Load learning profile
    profile = await db.execute(
        select(StudentLearningProfile)
        .where(StudentLearningProfile.student_id == student_id)
        .where(StudentLearningProfile.completed_at.isnot(None))
    )
    profile = profile.scalar_one_or_none()

    if not profile:
        raise ValueError("Learning profile not complete — cannot personalise explanation.")

    # 2. Derive dominant modality
    modality_scores = profile.modality_scores or {}
    dominant_modality = max(modality_scores, key=modality_scores.get) if modality_scores else "visual"

    # 3. Take top 2 interests (already human-readable — no mapping needed)
    interests = (profile.interests or [])[:2]
    interest_text = ", ".join(interests) if interests else "general topics"

    # 4. Build prompt and call LLM
    response_text = await _call_llm(request, dominant_modality, interest_text)

    # 5. Parse JSON response
    return _parse_response(response_text)
```

---

### 2. LLM task entry in `router.py`

```python
# backend/app/ai/providers/router.py — add one entry to each map

TASK_MODEL_MAP = {
    "gap_classification": settings.llm_gap_classification_model,
    "study_plan":         settings.llm_study_plan_model,
    "lesson_plan":        settings.llm_lesson_plan_model,
    "embeddings":         settings.llm_embeddings_model,
    "concept_guide":      settings.llm_concept_guide_model,    # ← NEW
}

TASK_API_BASE_MAP = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan":         settings.llm_study_plan_api_base,
    "lesson_plan":        settings.llm_lesson_plan_api_base,
    "embeddings":         settings.llm_embeddings_api_base,
    "concept_guide":      settings.llm_concept_guide_api_base, # ← NEW
}
```

**New environment variables (add to `.env` and Render secrets):**
```bash
LLM_CONCEPT_GUIDE_MODEL=gemini/gemini-2.5-flash
LLM_CONCEPT_GUIDE_API_BASE=   # empty = use provider default
```

**Why Gemini 2.5 Flash, not Pro:**
The response is short and highly structured (JSON with fixed keys). Flash is faster
(sub-3s vs sub-8s), cheaper, and produces consistent JSON at this output size.
Pro doesn't add value here — it's for longer generative tasks like lesson plans.
Latency SLA for concept_guide: **5 seconds hard timeout**.

---

### 3. Environment variable in `app/core/config.py`

```python
# Add to Settings class:
llm_concept_guide_model:    str = "gemini/gemini-2.5-flash"
llm_concept_guide_api_base: str | None = None
```

---

## Complete Data Flow

```
Student taps "Explain this →" on SubtopicScoreRow (masteryScore < 0.7)
    │
    │  Props already in component:
    │  - subtopicId, subtopicName, topicName (from gap map query)
    │  - masteryScore (from gap map query)
    │  - gradeName (from useStudentInfo())
    ▼
ConceptGuidePanel.tsx opens (inline right panel, no route change)
Shows loading skeleton
    │
    ▼
POST /api/v1/students/me/concept-guide
Body: { subtopic_id, subtopic_name, topic_name, mastery_score, grade_name }
Auth: Bearer <student JWT>
    │
    ▼
concept_guide_service.py
    ├── SELECT student_learning_profiles WHERE student_id = me
    │     returns: modality_scores, interests[], work_style
    ├── derive dominant_modality (max of 4 scores)
    ├── take interests[0:2] (already human-readable TEXT[])
    ├── build system_prompt (see below)
    ├── await router.complete("concept_guide", messages, max_tokens=600, temperature=0.7)
    │     → LiteLLM → Gemini 2.5 Flash
    ├── parse JSON from response
    └── return ConceptGuideResponse
    │
    ▼
ConceptGuidePanel.tsx receives response
Renders:
  - explanation text
  - analogy block (interest-contextualised)
  - numbered steps
  - MCQ check question (4 options A/B/C/D)

Student selects answer → client-side evaluation (no second API call)
  Correct: green feedback + "Great — try a practice assessment"
  Wrong:   amber feedback + show correct answer + "Try again later"
```

---

## System Prompt

```python
# backend/app/ai/prompts/concept_guide.py

SYSTEM_PROMPT = """You are a patient, encouraging tutor helping a {grade_name} student 
understand "{subtopic_name}" (part of {topic_name}).

Their current mastery level is {mastery_pct}% — they have encountered this topic but 
have real gaps. Do not explain it as if they have never seen it, and do not assume they 
understand it fully.

Their dominant learning style is {dominant_modality}. Adapt your explanation:
- visual: spatial descriptions, numbered step blocks, visual comparisons
- auditory: rhythm and pattern ("First... then... finally...")
- reading_writing: clear definitions first, then structured examples
- kinesthetic: real-world application FIRST, then the abstract rule

Their interests include: {interest_text}. Where it fits naturally, frame one example 
using this context. Do not force it.

RULES — follow exactly:
1. Explain the concept only. Never solve assignments or write full essays for the student.
2. Stay on topic. If asked about anything unrelated to "{subtopic_name}", respond only:
   "I'm here to help you with {subtopic_name} — let's stay focused on that."
3. After your explanation, ask one multiple choice check question.
4. Keep responses concise — this is a mobile app, not a lecture.

You MUST respond with valid JSON only, no markdown fences, no preamble:
{{
  "explanation": "100–180 words. The core concept explained for this student.",
  "analogy": "One sentence connecting this concept to their interests.",
  "steps": ["Step 1...", "Step 2...", "Step 3..."],
  "check_question": "One clear question testing the core concept.",
  "check_options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "B"
}}"""
```

**Notes on the prompt:**
- `mastery_pct` = `round(mastery_score * 100)` if not null, else `"unknown"`
- `interest_text` = `", ".join(profile.interests[:2])` — raw TEXT[] values, no mapping
- Double braces `{{}}` in the f-string template escape the literal JSON braces
- Temperature 0.7: enough variation to not feel robotic, not so high it hallucinates the JSON format
- max_tokens 600: sufficient for the structured JSON. At 600 tokens, the response is bounded.

---

## Frontend Architecture — `ConceptGuidePanel.tsx`

**Location:** `src/components/ai/ConceptGuidePanel.tsx`
(Component, not page — no route change. Renders as a right-panel within the current view.)

**State machine:**
```
IDLE
  │ (subtopicId prop provided + user taps "Explain this →")
  ▼
LOADING  ← show skeleton (3 placeholder blocks)
  │ (POST /students/me/concept-guide returns)
  ├─ success ──────────────────────────────────────────────────────────────▶ READY
  └─ error (429, 503, network) ──────────────────────────────────────────▶ ERROR

READY   ← show explanation + analogy + steps + MCQ question
  │ (student selects answer)
  ▼
ANSWERED
  │ correct ──▶ show green feedback + "Try a practice assessment →"
  └─ wrong ───▶ show amber feedback + reveal correct answer
                "Close guide" button returns student to plan/progress page
```

**Props:**
```ts
interface ConceptGuidePanelProps {
  subtopicId:    string;
  subtopicName:  string;
  topicName:     string;
  masteryScore:  number | null;
  gradeName:     string;
  onClose:       () => void;
}
```

**useConceptGuide hook:**
```ts
// src/hooks/useConceptGuide.ts
export function useConceptGuide(props: ConceptGuideRequest | null) {
  return useQuery({
    queryKey: ["concept-guide", props?.subtopicId],
    queryFn: async () => {
      if (!props) throw new Error("No subtopic provided");
      const res = await apiClient.post<ConceptGuideResponse>(
        "/api/v1/students/me/concept-guide",
        props,
      );
      return res.data;
    },
    enabled: !!props?.subtopicId,
    staleTime: 10 * 60 * 1000, // 10 min — same subtopic same student = cache it
    retry: 1,                   // one retry on network error, not on 429/503
  });
}
```

**Error handling:**
- 429 (rate limited): show "You've asked the guide a lot today. Try again in a moment."
- 503 (LLM down): show "Guide is temporarily unavailable. Your mastery data is unaffected."
- Network error: show "Something went wrong. Check your connection and try again."
- Never show a blank panel. Loading → content or loading → error, always.

**Where it's triggered:**
```ts
// MyProgress.tsx — SubtopicScoreRow
// Only render when masteryScore < 0.7
{(subtopic.masteryScore ?? 1) < 0.7 && (
  <button
    type="button"
    className="text-xs font-semibold text-brand-primary"
    onClick={() => setGuideSubtopic(subtopic)}
  >
    Explain this →
  </button>
)}

// StudentDashboard.tsx — NextStepCard action button
// Weakest subtopic from resolvedSubjectScores → opens ConceptGuidePanel
```

---

---

## Named Tests — Constitution Rule 20

All function names follow Rule 7: `test_<what>_when_<condition>_then_<expected>`

### Backend unit tests
**File:** `backend/tests/unit/test_concept_guide_service.py`

```python
async def test_get_concept_guide_when_visual_is_highest_modality_then_prompt_uses_visual_style(db_session, mock_visual_profile): ...
async def test_get_concept_guide_when_interests_has_two_items_then_both_injected_into_prompt(db_session, mock_profile_two_interests): ...
async def test_get_concept_guide_when_interests_is_empty_then_fallback_general_topics_used(db_session, mock_profile_no_interests): ...
async def test_get_concept_guide_when_interests_has_five_items_then_only_first_two_used(db_session, mock_profile_many_interests): ...
async def test_get_concept_guide_when_mastery_score_is_none_then_prompt_uses_unknown_not_crash(db_session, mock_visual_profile): ...
async def test_get_concept_guide_when_profile_completed_at_is_null_then_raises_value_error(db_session, mock_incomplete_profile): ...
async def test_get_concept_guide_when_no_profile_row_exists_then_raises_value_error(db_session): ...
async def test_get_concept_guide_when_llm_returns_valid_json_then_all_response_fields_populated(db_session, mock_visual_profile, mock_llm_valid_json): ...
async def test_get_concept_guide_when_llm_returns_prose_not_json_then_raises_value_error(db_session, mock_visual_profile, mock_llm_prose_response): ...
```

Mock setup required:
- `mock_visual_profile`: `student_learning_profiles` row with `modality_scores={"visual":0.9,"auditory":0.2,"reading_writing":0.3,"kinesthetic":0.1}`, `interests=["football","music"]`, `completed_at=datetime.utcnow()`
- `mock_profile_no_interests`: same but `interests=[]`
- `mock_profile_many_interests`: same but `interests=["football","music","gaming","cooking","animals"]`
- `mock_incomplete_profile`: row with `completed_at=None`
- `mock_llm_valid_json`: `router.complete` returns valid JSON string with all required keys
- `mock_llm_prose_response`: `router.complete` returns plain English prose

### Backend integration tests
**File:** `backend/tests/integration/test_concept_guide_route.py`

```python
async def test_post_concept_guide_when_authenticated_student_with_profile_then_returns_200(async_client, student_auth_headers, seeded_profile, mock_llm_router): ...
async def test_post_concept_guide_when_no_auth_header_then_returns_401(async_client): ...
async def test_post_concept_guide_when_student_has_no_completed_profile_then_returns_422(async_client, student_auth_headers_no_profile): ...
async def test_post_concept_guide_when_request_body_missing_subtopic_id_then_returns_422(async_client, student_auth_headers): ...
```

### Frontend component tests
**File:** `apps/student/src/components/ai/__tests__/ConceptGuidePanel.test.tsx`

```tsx
test('renders_loading_skeleton_while_query_is_pending', ...)
test('renders_explanation_analogy_steps_and_mcq_when_query_resolves', ...)
test('highlights_correct_option_in_green_when_correct_answer_selected', ...)
test('highlights_selected_option_in_amber_and_shows_correct_when_wrong_answer_selected', ...)
test('shows_rate_limit_message_when_api_returns_429', ...)
test('shows_unavailable_message_when_api_returns_503', ...)
test('calls_onClose_when_close_button_is_clicked', ...)
test('does_not_render_when_masteryScore_is_gte_0_7', ...)
```

---

## What Is Not In Scope for This Sprint

| Feature | Why deferred |
|---|---|
| Streaming response | Adds SSE complexity to both backend and frontend. Response is short (~600 tokens). Non-streaming is fine for v1. |
| Conversation history | Guide is single-turn. Student gets one explanation + one check question. Multi-turn is a future sprint. |
| Response caching server-side | `useQuery` with 10-min staleTime handles client-side dedup. Server-side cache adds infra complexity. Not needed at pilot scale. |
| "Why did I get this wrong?" from Assessment Results | Requires question-level data not currently in the gap map response. Planned post-M1. |
| Guide triggered from Study Plan activity | SP-003/SP-004 are separate tasks. The panel component is shared, but the triggering context is different. |

---

## Dependencies and Build Order

```
Prerequisite (before any ST-020 work):
  Verify GET /students/me/learning-profile returns real student_learning_profiles data.
  If it's still a stub → unblock it first. ST-020 cannot ship without this.

Backend (done first):
  1. Add concept_guide to TASK_MODEL_MAP in router.py
  2. Add LLM_CONCEPT_GUIDE_MODEL + LLM_CONCEPT_GUIDE_API_BASE to config.py + .env
  3. Write concept_guide_service.py (DB query + prompt build + LLM call + JSON parse)
  4. Write concept_guide.py route (POST /students/me/concept-guide)
  5. Register route in app/api/v1/__init__.py

Frontend (after backend):
  6. Write useConceptGuide hook
  7. Write ConceptGuidePanel.tsx (state machine: loading → ready → answered)
  8. Wire "Explain this →" button in SubtopicScoreRow (mastery < 0.7 only)
  9. Wire NextStepCard action in StudentDashboard to open guide

Tests:
  10. Unit: concept_guide_service — dominant modality derivation
  11. Unit: concept_guide_service — interests[:2] from empty, 1-item, 5-item arrays
  12. Unit: concept_guide_service — null mastery_score handled correctly
  13. Integration: POST /students/me/concept-guide with mock LLM → correct JSON parsed
  14. Integration: POST with rate limit exceeded → 429 returned
  15. Frontend: ConceptGuidePanel renders all three states (loading, ready, answered)
```

---

## Errata — What Must Be Fixed in kaihle-student-tasks-v2.md

ST-020 in v2 previously contained an introduced error from the cross-review pass (now corrected):

**Wrong (introduced in v2):**
```ts
interface ConceptGuideContext {
  interestCategory: string;  // "sports_movement" | "tech_gaming" | ...
}
const INTEREST_LABELS: Record<string, string> = { sports_movement: "sport and movement", ... };
```

**Correct (matches actual schema):**
```ts
interface ConceptGuideContext {
  interests: string[];  // TEXT[] from student_learning_profiles — already human-readable
                        // e.g. ["football", "music", "gaming"]
}
// No mapping needed. Pass interests.slice(0, 2).join(", ") directly into the prompt.
```

ST-020 in v2 also does not mention the backend endpoint, the LLM task registration,
or the environment variables. Those are fully specified in this document.
The implementation team should treat this architecture document as the authoritative
spec, with ST-020 v2 covering the frontend entry points and acceptance criteria only.
