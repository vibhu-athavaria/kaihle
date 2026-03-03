# M3-1-T2 — Quiz Generator (with Interest Injection)
**Milestone:** M3 · **Epic:** M3-1 · **Task:** T2
**Depends on:** M1-2-T2 (curriculum_chunks + subtopic embeddings), M0-6-T1 (learning profile)

---

## User Story
As the system, I want to generate a personalised 5-question practice quiz for a student's gap, using their personal interests to make the question scenarios feel relevant.

---

## Files to Create

```
backend/app/ai/quiz_generator.py
backend/app/ai/prompts/study_plan_quiz.jinja2
backend/tests/unit/test_quiz_generator.py
backend/tests/integration/test_quiz_generation.py
```

---

## Main Function

```python
async def generate_quiz(
    subtopic: Subtopic,
    student_mastery: float,   # current mastery score 0.0–1.0
    student_id: UUID,
    db: AsyncSession,
) -> GeneratedQuiz:
    """
    Generates 5 questions (4 MCQ + 1 SHORT_ANSWER) calibrated to student mastery.
    Injects student interests into prompt if available.
    LLM: Gemini 2.5 Flash, task="question_generation", max 8s.
    """
```

---

## Step-by-Step Logic

### 1. Load RAG Context
```python
# Get 3 most relevant curriculum_chunks for this subtopic
chunks = await rag_retriever.get_top_k(
    query_embedding=subtopic.embedding,
    k=3,
    filter={"subtopic_id": subtopic.id}
)
rag_context = "\n\n".join([c.content for c in chunks])
```

### 2. Load Student Interests
```python
profile = await db.get(StudentLearningProfile, student_id)
interests = profile.interests if profile and profile.interests else []
top_2_interests = interests[:2]   # use first 2 only
```

### 3. Determine Difficulty Label
```python
if student_mastery < 0.4:
    difficulty_label = "foundational — focus on basic recall and understanding"
elif student_mastery < 0.7:
    difficulty_label = "developing — include application and simple problem solving"
else:
    difficulty_label = "advanced — focus on analysis, evaluation, and novel problems"
```

### 4. Build and Call LLM
Use Jinja2 template (see below). Call via `get_provider(task="question_generation")`.

**Hard timeout: 8 seconds.** On timeout → retry once → raise `QuizGenerationError`.

### 5. Parse and Validate Output
```python
raw_json = extract_json(llm_response.content)
questions = [QuizQuestion(**q) for q in raw_json["questions"]]
assert len(questions) == 5
assert sum(1 for q in questions if q.type == "MCQ") == 4
assert sum(1 for q in questions if q.type == "SHORT_ANSWER") == 1
```
If validation fails → retry once with same prompt. If second failure → raise `QuizGenerationError`.

---

## Prompt Template (`study_plan_quiz.jinja2`)

```jinja2
System: You are an educational content creator for {{ curriculum_code }} {{ subject_name }}.
        Generate a 5-question practice quiz.
        Return ONLY valid JSON — no preamble, no markdown fences.

Student mastery: {{ mastery_pct }}% on: {{ subtopic_name }}.
Difficulty calibration: {{ difficulty_label }}.

Learning objectives:
{{ learning_objectives }}

Curriculum context:
{{ rag_context }}

{% if top_2_interests %}
Personalisation: Where it fits naturally, frame question scenarios using topics this
student finds interesting: {{ top_2_interests | join(', ') }}.
Do NOT force the interest — academic accuracy is always the priority.
Only use if the scenario genuinely fits the subtopic.
{% endif %}

Generate exactly 5 questions: 4 MCQ and 1 SHORT_ANSWER.
MCQ must have exactly 4 options (A, B, C, D).

Return JSON:
{
  "questions": [
    {
      "question_text": "...",
      "type": "MCQ",
      "options": [
        {"key": "A", "text": "..."},
        {"key": "B", "text": "..."},
        {"key": "C", "text": "..."},
        {"key": "D", "text": "..."}
      ],
      "correct_answer": "B",
      "explanation": "..."
    },
    {
      "question_text": "...",
      "type": "SHORT_ANSWER",
      "options": null,
      "correct_answer": "...",
      "explanation": "..."
    }
  ]
}
```

---

## Output Schema

```python
@dataclass
class QuizQuestion:
    question_text: str
    type: QuestionType          # MCQ | SHORT_ANSWER
    options: list[dict] | None  # [{"key":"A","text":"..."}] for MCQ, None for SHORT_ANSWER
    correct_answer: str
    explanation: str

@dataclass
class GeneratedQuiz:
    subtopic_id: UUID
    questions: list[QuizQuestion]   # always 5
    generated_at: datetime
    interests_used: list[str]       # track which interests were injected
```

---

## Acceptance Criteria

- [ ] Student with `interests=["football","music"]` → prompt contains "football" and "music"
- [ ] Student with empty interests → prompt does NOT contain personalisation section
- [ ] Student with no profile → quiz generated without error (no personalisation section)
- [ ] `student_mastery=0.2` → prompt contains "foundational"
- [ ] `student_mastery=0.5` → prompt contains "developing"
- [ ] `student_mastery=0.8` → prompt contains "advanced"
- [ ] Output has exactly 5 questions: 4 MCQ + 1 SHORT_ANSWER
- [ ] Each MCQ has exactly 4 options
- [ ] LLM returns invalid JSON → retry once → if still invalid → raise error
- [ ] LLM timeout → retry once → raise error

---

## Tests to Write

```python
test_generate_quiz_when_interests_present_then_prompt_includes_interests()
test_generate_quiz_when_no_interests_then_prompt_has_no_personalisation_section()
test_generate_quiz_when_no_profile_then_quiz_generated_successfully()
test_generate_quiz_when_mastery_low_then_prompt_has_foundational()
test_generate_quiz_when_mastery_high_then_prompt_has_advanced()
test_generate_quiz_when_valid_llm_response_then_5_questions_returned()
test_generate_quiz_when_invalid_json_then_retry_once()
test_generate_quiz_when_timeout_then_retry_and_raise()
test_generated_quiz_has_4_mcq_and_1_short_answer()
```
