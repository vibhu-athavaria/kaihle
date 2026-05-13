# T2 — Backend Service & API Changes
**Branch:** `feat/diagnostic-enhancements-T2_feature/diagnostic-service-and-api`
**Parent:** `feat/diagnostic-enhancements-T1_migration/assessment-schema-v2`
**Executor:** Coding agent
**Status:** Blocked on T1

---

## What This Task Does

Updates `design_tier1_diagnostic` service method and its API endpoint to support:
1. **Prior-grade topic selection** — `topic_ids` may include topics from `class.grade.level - 1`.
2. **`questions_per_topic`** — uniform count applied to every selected topic; replaces the flat `question_count`.
3. **`DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY` constant** — 2 questions per difficulty level per topic.
4. **`time_limit_minutes`, `question_types`, `minimum_difficulty`, `maximum_difficulty`** — accepted in request, persisted to new columns.
5. **`assessment_topic_config` rows** — written atomically with the assessment.
6. **Topic availability check endpoint** — new GET endpoint so the UI can warn before submission.
7. **`create_assessment`** (non-diagnostic) — update to use new columns instead of `config`.

---

## Constants

Add to `assessment_service.py` (replace `MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT`):

```python
DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY = 2  # per topic per difficulty level
```

---

## Schema Changes (`backend/app/schemas/assessments.py`)

### Replace `DesignTier1DiagnosticRequest`

```python
class DesignTier1DiagnosticRequest(BaseModel):
    topic_ids: list[UUID] = Field(..., min_length=1)
    questions_per_topic: int = Field(2, ge=1, le=20)
    time_limit_minutes: int | None = Field(None, ge=1, le=300)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    deadline: datetime | None = None
```

### Replace `AssessmentCreateRequest`

```python
class AssessmentCreateRequest(BaseModel):
    title: str | None = None
    topic_ids: list[UUID]
    questions_per_topic: int = Field(2, ge=1, le=20)
    assessment_type: str = "PROGRESS_CHECK"
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])
    time_limit_minutes: int | None = Field(None, ge=1, le=300)
    deadline: datetime | None = None
```

### New response and endpoint schemas

```python
class TopicAvailability(BaseModel):
    curriculum_topic_id: UUID
    topic_name: str
    grade_level: int
    available_questions: int          # total in bank matching difficulty range
    per_difficulty_available: dict[int, int]  # {1: 3, 2: 2, 3: 5, ...}
    fulfillable: bool                 # True if available_questions >= questions_per_topic

class TopicAvailabilityRequest(BaseModel):
    topic_ids: list[UUID] = Field(..., min_length=1)
    questions_per_topic: int = Field(2, ge=1)
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])
```

---

## Service Changes (`backend/app/services/assessment_service.py`)

### New method: `check_topic_availability`

```python
async def check_topic_availability(
    self,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    topic_ids: list[uuid.UUID],
    questions_per_topic: int,
    minimum_difficulty: int,
    maximum_difficulty: int,
    question_types: list[str],
) -> list[TopicAvailability]:
```

- For each `topic_id`: query `question_bank` joined via `subtopics` → `curriculum_topics` filtered by `difficulty_level BETWEEN min AND max` and `question_type IN (question_types)`.
- Group counts by difficulty level.
- Return `TopicAvailability` for each topic with `fulfillable = available >= questions_per_topic`.
- Also resolves `grade_level` via `Grade.level` join for display.

### Updated `design_tier1_diagnostic`

Key logic changes:

1. **Validate topic grades** — each `topic_id` must belong to a `CurriculumTopic` whose `grade_id` resolves to `grade.level` of either `class_.grade.level` or `class_.grade.level - 1`. Raise `ValueError("Topic {id} does not belong to current or previous grade")` otherwise.

2. **Question sampling** — replace the flat pool approach with per-topic per-difficulty sampling:

```python
selected_ids = []
for topic_id in body.topic_ids:
    for difficulty in range(body.minimum_difficulty, body.maximum_difficulty + 1):
        topic_diff_questions = [questions matching topic + difficulty]
        selected_ids += rng.sample(topic_diff_questions, min(DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY, len(topic_diff_questions)))
```

3. **Persist `assessment_topic_config` rows** atomically with the assessment:

```python
for topic_id in body.topic_ids:
    db.add(AssessmentTopicConfig(
        assessment_id=assessment.id,
        curriculum_topic_id=topic_id,
        grade_id=<resolved grade_id for this topic>,
    ))
```

4. **Set new columns** on `Assessment`:
   - `questions_per_topic = body.questions_per_topic`
   - `question_count = len(selected_ids)`  ← actual total after sampling
   - `time_limit_minutes = body.time_limit_minutes`
   - `question_types = body.question_types`
   - `minimum_difficulty = body.minimum_difficulty`
   - `maximum_difficulty = body.maximum_difficulty`

5. **Remove** `diagnostic_topic_ids` and `config` writes (gone after T1).

### Updated `create_assessment` (non-diagnostic)

- Replace `config_` dict write with direct column assignments.
- Persist `assessment_topic_config` rows for `body.topic_ids` (grade = `class_.grade_id`).
- Replace `body.difficulty_min/max` references with `body.minimum_difficulty/maximum_difficulty`.
- Replace flat `body.question_count` with `body.questions_per_topic * len(body.topic_ids)` as total.

---

## Route Changes (`backend/app/api/v1/routes/assessments.py`)

### New endpoint: topic availability check

```
POST /classes/{class_id}/assessments/topic-availability
Request: TopicAvailabilityRequest
Response: list[TopicAvailability]
Auth: require_role(TEACHER)
```

This is a read-only query — POST (not GET) because the request body has a list of topic IDs and filter params that exceed query-string ergonomics.

### `design_tier1_diagnostic` route

Update to pass new body fields to the service. No structural change to the route itself.

---

## Acceptance Criteria

- [ ] `POST /classes/{class_id}/diagnostics/tier1` accepts `questions_per_topic`, `time_limit_minutes`, `question_types`, `minimum_difficulty`, `maximum_difficulty`.
- [ ] Topics from `class.grade.level - 1` are accepted; topics from any other grade return 422.
- [ ] `assessment_topic_config` rows are created for every selected topic, with correct `grade_id`.
- [ ] Question sampling selects exactly `DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY` per difficulty level per topic (or fewer if bank is short).
- [ ] `POST /classes/{class_id}/assessments/topic-availability` returns correct per-topic counts and `fulfillable` flags.
- [ ] Existing ACTIVE/CLOSED diagnostic cannot be replaced (existing guard unchanged).
- [ ] `create_assessment` (non-diagnostic) no longer writes `config`; all fields go to typed columns.
- [ ] All tests pass; service coverage >= 90%.

---

## TDD Spec

**Test file:** `backend/app/tests/unit/test_assessment_service_tier1.py` (extend existing)

```python
def test_design_tier1_diagnostic_when_previous_grade_topics_included_then_accepted():
    # Arrange: mock class grade_level=8; topic_ids include one topic from grade 7, one from grade 8
    # Act: await service.design_tier1_diagnostic(...)
    # Assert: no exception raised; assessment_topic_config has rows for both grade_ids

def test_design_tier1_diagnostic_when_topic_from_wrong_grade_then_raises_value_error():
    # Arrange: mock class grade_level=8; topic_ids include a topic from grade 6
    # Act: await service.design_tier1_diagnostic(...)
    # Assert: ValueError raised with message containing topic id

def test_design_tier1_diagnostic_when_bank_has_2_per_difficulty_then_selects_2_per_difficulty_per_topic():
    # Arrange: 3 topics, 5 difficulty levels, 5 questions each in bank
    # Act: await service.design_tier1_diagnostic(questions_per_topic=2, min_diff=1, max_diff=5)
    # Assert: len(selected_ids) == 3 topics * 5 levels * 2 = 30

def test_design_tier1_diagnostic_when_bank_short_on_difficulty_then_uses_available():
    # Arrange: 1 topic, difficulty level 3 has only 1 question (not 2)
    # Act: await service.design_tier1_diagnostic(...)
    # Assert: no InsufficientQuestionsError; result includes the 1 available question for level 3

def test_check_topic_availability_when_topic_has_enough_then_fulfillable_true():
    # Arrange: topic with 10 questions at difficulty 1–5
    # Act: await service.check_topic_availability(topic_ids=[...], questions_per_topic=2, ...)
    # Assert: result[0].fulfillable == True, result[0].available_questions >= 2

def test_check_topic_availability_when_topic_short_then_fulfillable_false():
    # Arrange: topic with 1 question total
    # Act: await service.check_topic_availability(topic_ids=[...], questions_per_topic=5, ...)
    # Assert: result[0].fulfillable == False

def test_create_assessment_when_called_then_no_config_column_written():
    # Arrange: valid AssessmentCreateRequest
    # Act: await service.create_assessment(...)
    # Assert: assessment.config does not exist (AttributeError or no attribute)
    # Assert: assessment.minimum_difficulty == body.minimum_difficulty
```

**Integration test file:** `backend/app/tests/integration/test_teacher_assessments_routes.py` (extend)

```python
def test_topic_availability_endpoint_when_valid_topics_then_returns_per_topic_counts():
    # Arrange: seeded question bank, teacher auth token, class_id
    # Act: POST /classes/{class_id}/assessments/topic-availability
    # Assert: 200, response contains TopicAvailability for each topic_id

def test_design_tier1_diagnostic_when_prior_grade_topic_then_201_and_topic_config_persisted():
    # Arrange: class grade 8, topic from grade 7 in bank
    # Act: POST /classes/{class_id}/diagnostics/tier1 with prior-grade topic_id
    # Assert: 201; assessment_topic_config row exists with grade_id = grade 7
```

---

## Files Changed

```
backend/app/schemas/assessments.py
backend/app/services/assessment_service.py
backend/app/api/v1/routes/assessments.py
backend/app/tests/unit/test_assessment_service_tier1.py     ← extended
backend/app/tests/unit/test_assessment_service.py           ← update config assertions
backend/app/tests/integration/test_teacher_assessments_routes.py  ← extended
```
