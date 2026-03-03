# M1-4-T2 — Answer Scoring Service
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T2
**Depends on:** M0-2-T2 (ORM models), LLM provider abstraction (M0-1-T1 sets up AI module structure)

---

## User Story
As the system, I want to score student answers immediately for MCQ and True/False questions, and asynchronously via LLM for short answer questions.

---

## Files to Create

```
backend/app/services/scoring_service.py
backend/app/tasks/scoring_tasks.py        # async LLM scoring Celery task
backend/app/ai/prompts/answer_scoring.jinja2
backend/tests/unit/test_scoring_service.py
backend/tests/integration/test_scoring_integration.py
```

---

## `scoring_service.py`

### `score_response(question, answer_given) → ScoringResult`

```python
@dataclass
class ScoringResult:
    is_correct: bool | None     # None when scored_by=PENDING
    score: float | None         # 0.0–1.0, None when PENDING
    scored_by: ScoredBy         # RULE | LLM | PENDING
    justification: str | None   # LLM-provided explanation, None for RULE
```

```python
def score_response(question: Question, answer_given: str) -> ScoringResult:
    if question.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
        return _score_by_rule(question, answer_given)
    elif question.question_type == QuestionType.SHORT_ANSWER:
        return _score_pending()   # queues LLM async task, returns PENDING
```

### Rule-based scoring (`_score_by_rule`):
```python
normalised_answer = answer_given.strip().lower()
normalised_correct = question.correct_answer.strip().lower()
is_correct = normalised_answer == normalised_correct
return ScoringResult(
    is_correct=is_correct,
    score=1.0 if is_correct else 0.0,
    scored_by=ScoredBy.RULE,
    justification=None
)
```

### Pending (short answer):
```python
return ScoringResult(is_correct=None, score=None, scored_by=ScoredBy.PENDING, justification=None)
# Caller stores response_id and queues: score_short_answer_async.delay(response_id)
```

---

## `scoring_tasks.py` — Celery Task

```python
@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def score_short_answer_async(self, response_id: str):
    """
    Scores a SHORT_ANSWER student_response via LLM.
    Updates student_responses row with final score.
    3-second timeout enforced.
    """
    response = load_response(response_id)
    question = load_question(response.question_id)

    try:
        result = await_llm_scoring(question, response.answer_given)  # 3s timeout
        update_response(response_id, score=result.score,
                        scored_by=ScoredBy.LLM,
                        llm_justification=result.justification)
    except TimeoutError:
        self.retry()   # retries up to 2 times, then marks PENDING permanently
```

---

## LLM Scoring Prompt (`answer_scoring.jinja2`)

```jinja2
You are a {{ curriculum_code }} {{ subject_name }} examiner.
Score the student answer from 0.0 to 1.0.
Return ONLY valid JSON — no preamble, no markdown.

Question: {{ question_text }}
Expected answer: {{ correct_answer }}
Student answer: {{ student_answer }}

{"score": 0.0-1.0, "justification": "one sentence max"}
```

Scoring rubric (inject in system prompt):
- 1.0 = fully correct
- 0.5–0.9 = partially correct (right idea, missing detail)
- 0.1–0.4 = shows understanding but incorrect
- 0.0 = wrong or blank

Provider: `task="answer_scoring"` → routes to Gemini 2.5 Flash with **3-second hard timeout**.

---

## Acceptance Criteria

- [ ] MCQ with correct answer → `{ is_correct: true, score: 1.0, scored_by: RULE }`
- [ ] MCQ with wrong answer → `{ is_correct: false, score: 0.0, scored_by: RULE }`
- [ ] Case-insensitive match: "True" == "true" → correct
- [ ] SHORT_ANSWER → returns `{ scored_by: PENDING, score: null }` immediately
- [ ] SHORT_ANSWER → LLM Celery task queued after response stored
- [ ] LLM task runs → response updated with score 0.0–1.0 and justification
- [ ] LLM timeout → task retries up to 2 times
- [ ] After 2 retries LLM still fails → response remains `scored_by=PENDING` (not crashed)
- [ ] Performance: 40 concurrent MCQ scores complete within 200ms total

---

## Tests to Write

```python
test_score_mcq_when_correct_answer_then_score_1_rule()
test_score_mcq_when_wrong_answer_then_score_0_rule()
test_score_mcq_when_case_different_then_still_correct()
test_score_true_false_when_correct_then_score_1()
test_score_short_answer_when_called_then_returns_pending()
test_score_short_answer_async_when_llm_returns_then_response_updated()
test_score_short_answer_async_when_timeout_then_retries()
test_score_short_answer_async_when_max_retries_then_stays_pending()
test_score_mcq_performance_when_40_concurrent_then_under_200ms()
```
