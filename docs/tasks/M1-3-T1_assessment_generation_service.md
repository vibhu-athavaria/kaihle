# M1-3-T1 — Assessment Generation Service (Tier 2)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T1
**Depends on:** M1-1-T1 (question_bank populated), M1-2-T1 (curriculum graph seeded), M0-2-T2 (ORM models)
**Blocks:** M1-3-T2 (routes call this service)
**Estimated effort:** 3–4 hours

---

## Context

This task builds the service layer for Tier 2 (teacher-created) assessments. Tier 1
diagnostic creation already exists in `app/tasks/onboarding_tasks.py` from M0-6-T2 —
do not touch that code here.

The question bank contains exclusively MCQ questions. There is no LLM fallback for
question generation. If the bank has insufficient questions for the requested
configuration, the service raises `InsufficientQuestionsError` and the route returns
HTTP 422. This is a known constraint of v1 — if it occurs, the teacher must adjust
their configuration (fewer questions, broader topic selection, or different difficulty
range).

Read `CONSTITUTION.md` Rule 2 (every table has `school_id`) and Rule 3 (all queries
filter by `school_id`) before writing any code. Every DB query in this service must
include `school_id` in its WHERE clause.

---

## User Story

As a teacher, I want to create an assessment for my class by configuring the topic,
question count, and difficulty range, so that the system selects appropriate questions
from the bank without me having to find them manually.

---

## Files to Create

```
backend/app/services/assessment_service.py    ← CREATE (new file)
backend/app/tests/unit/test_assessment_service.py
backend/app/tests/integration/test_assessment_generation.py
```

Note: `schemas/assessments.py` already exists from M0-10-T1. Import from it — do not
redefine `AssessmentResponse` or `AssessmentCreateRequest` here.

---

## Custom Exceptions

Define these at the top of `assessment_service.py`. They are imported by the route
handler in M1-3-T2 to map to HTTP status codes.

```python
class InsufficientQuestionsError(Exception):
    """Raised when the question bank has fewer questions than requested.

    Args:
        requested: Number of questions requested.
        available: Number of questions found matching the criteria.
        criteria: Dict describing the filter applied (subject, grade, topic, difficulty).
    """
    def __init__(self, requested: int, available: int, criteria: dict):
        self.requested = requested
        self.available = available
        self.criteria = criteria
        super().__init__(
            f"Requested {requested} questions but only {available} available "
            f"matching criteria: {criteria}"
        )

class TeacherNotClassOwnerError(Exception):
    """Raised when a teacher tries to create an assessment for a class they do not teach."""
    pass
```

---

## Service Class

```python
class AssessmentService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
```

---

## Method: `create_assessment`

Full signature:

```python
async def create_assessment(
    self,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    body: AssessmentCreateRequest,
) -> Assessment:
```

**Step-by-step logic. Implement exactly these steps in this order.**

**Step 1 — Verify teacher owns the class.**
Load the `Class` row for `body.class_id`. If not found or `class_.school_id != school_id`,
raise `ValueError("Class not found")`. If `class_.teacher_id != teacher_id`, raise
`TeacherNotClassOwnerError`. This check must use `school_id` in the query — a teacher
from a different school must get a 404, not a 403, to avoid leaking that the class exists.

```python
class_ = await self.db.scalar(
    select(Class).where(
        Class.id == body.class_id,
        Class.school_id == school_id,
        Class.is_active.is_(True),
    )
)
if not class_:
    raise ValueError("Class not found")
if class_.teacher_id != teacher_id:
    raise TeacherNotClassOwnerError()
```

**Step 2 — Build the question filter.**
Start from `QuestionBank` rows matching `subject_id` and `grade_id` from the class, with
`is_active = TRUE`. Then apply optional filters from the request:

If `body.topic_ids` is non-empty, add `QuestionBank.curriculum_topic_id.in_(body.topic_ids)`.
If `body.topic_ids` is empty (broad diagnostic sweep), no topic filter is applied — all
topics for the subject and grade are eligible.

Apply difficulty filter: `QuestionBank.difficulty_level.between(body.difficulty_min, body.difficulty_max)`.

```python
query = (
    select(QuestionBank)
    .where(
        QuestionBank.subject_id == class_.subject_id,
        QuestionBank.grade_id == class_.grade_id,
        QuestionBank.is_active.is_(True),
        QuestionBank.difficulty_level.between(
            body.difficulty_min, body.difficulty_max
        ),
    )
)
if body.topic_ids:
    query = query.where(QuestionBank.curriculum_topic_id.in_(body.topic_ids))
```

**Step 3 — Sample questions with topic distribution.**
Load all matching question IDs (do not load full question content yet — just IDs and
`curriculum_topic_id`). If fewer than `body.question_count` are available, raise
`InsufficientQuestionsError` with the criteria dict for diagnostics.

Otherwise, select `body.question_count` questions using weighted random sampling that
aims for even topic distribution. The algorithm is: group question IDs by
`curriculum_topic_id`, then round-robin sample from each group until the requested
count is reached. This avoids producing an assessment that only covers one topic.

```python
rows = (await self.db.execute(
    select(QuestionBank.id, QuestionBank.curriculum_topic_id).where(...)
)).all()

if len(rows) < body.question_count:
    raise InsufficientQuestionsError(
        requested=body.question_count,
        available=len(rows),
        criteria={
            "subject_id": str(class_.subject_id),
            "grade_id": str(class_.grade_id),
            "topic_ids": [str(t) for t in body.topic_ids],
            "difficulty_min": body.difficulty_min,
            "difficulty_max": body.difficulty_max,
        },
    )

selected_ids = _sample_with_topic_distribution(rows, body.question_count)
```

**Step 4 — Create the Assessment row inside a transaction.**
This step and Step 5 must be atomic. If the bridge rows fail, the assessment row must
also be rolled back. Use the session's existing transaction — do not open a new one.

```python
assessment = Assessment(
    id=uuid.uuid4(),
    school_id=school_id,
    class_id=body.class_id,
    created_by=teacher_id,
    assessment_type=body.assessment_type,
    is_system_generated=False,   # ALWAYS False for teacher-created assessments
    status="DRAFT",              # Teacher must explicitly publish — never auto-publish
    title=_generate_title(body, class_),
    question_count=body.question_count,
    deadline=body.deadline,
)
self.db.add(assessment)
await self.db.flush()   # get assessment.id without committing
```

**Step 5 — Create the bridge rows.**

```python
bridge_rows = [
    AssessmentSelectedQuestion(
        assessment_id=assessment.id,
        question_id=qid,
        position=idx,
    )
    for idx, qid in enumerate(selected_ids, start=1)
]
self.db.add_all(bridge_rows)
# Caller commits — this service does not commit directly
```

**Step 6 — Return the Assessment model.**

```python
return assessment
```

---

## Method: `get_assessment`

Full signature:

```python
async def get_assessment(
    self,
    assessment_id: uuid.UUID,
    school_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    requesting_user_role: str,
) -> tuple[Assessment, list[QuestionBank]]:
```

Loads the assessment and its questions. The tuple is `(Assessment, questions)` where
`questions` is the list of `QuestionBank` rows in the order defined by
`assessment_selected_questions.position`.

Multi-tenancy check: `assessment.school_id == school_id`. If not, raise `ValueError`.

For `STUDENT` role: the returned `QuestionBank` rows must have `correct_answer_key`
set to `None` before being returned. This stripping happens in this method — the route
handler passes the role here and trusts the service to return the right shape.

For `TEACHER`, `SCHOOL_ADMIN`, `KAIHLE_ADMIN` roles: return full rows including
`correct_answer_key`.

---

## Method: `publish_assessment`

Full signature:

```python
async def publish_assessment(
    self,
    assessment_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    deadline: datetime | None,
) -> Assessment:
```

Rules enforced before changing status:
- Assessment must exist and `school_id` must match.
- `assessment.created_by == teacher_id` (teacher can only publish their own assessments).
- `assessment.status == "DRAFT"` — raising `ValueError("Cannot publish: status is {status}")` otherwise.
- At least one `AssessmentSelectedQuestion` row must exist for this assessment.

On success: set `assessment.status = "ACTIVE"`, `assessment.deadline = deadline`,
`assessment.published_at = datetime.now(timezone.utc)`.

---

## Method: `close_assessment`

Full signature:

```python
async def close_assessment(
    self,
    assessment_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> Assessment:
```

Assessment must be in `ACTIVE` status. Set `status = "CLOSED"`. No new attempts are
accepted after this — enforced in the attempt service by checking assessment status.

---

## Helper: `_generate_title`

```python
def _generate_title(body: AssessmentCreateRequest, class_: Class) -> str:
    """Generate a human-readable title for the assessment."""
    # Examples:
    # AssessmentType.DIAGNOSTIC     → "Diagnostic — Mathematics Grade 9"
    # AssessmentType.TOPIC_SPECIFIC → "Topic Assessment — Mathematics Grade 9"
    # AssessmentType.PROGRESS_CHECK → "Progress Check — Mathematics Grade 9"
    ...
```

---

## Helper: `_sample_with_topic_distribution`

```python
def _sample_with_topic_distribution(
    rows: list[Row],    # rows of (id, curriculum_topic_id)
    n: int,
) -> list[uuid.UUID]:
    """Sample n question IDs with balanced topic distribution.

    Groups by curriculum_topic_id, then round-robins through groups.
    Within each group, selection is random (random.shuffle).
    Returns a flat list of n question UUIDs.
    """
    ...
```

---

## Acceptance Criteria

**Unit tests — `test_assessment_service.py`**

Each test description specifies what to assert, not just the test name.

`test_create_when_valid_config_then_draft_assessment_created` — Call `create_assessment`
with a valid config and a teacher who owns the class. Assert that the returned
`Assessment` has `status="DRAFT"`, `is_system_generated=False`, and that the DB
contains exactly `body.question_count` rows in `assessment_selected_questions` for
that assessment.

`test_create_when_teacher_not_class_owner_then_raises_teacher_not_class_owner_error` —
Call `create_assessment` with a `teacher_id` that is not `class_.teacher_id`. Assert
that `TeacherNotClassOwnerError` is raised and no `Assessment` row is created.

`test_create_when_insufficient_questions_then_raises_insufficient_questions_error` —
Set up a question bank with only 3 rows matching the criteria but request 10 questions.
Assert `InsufficientQuestionsError` is raised with `available=3` and `requested=10`.

`test_create_when_diagnostic_type_no_topic_ids_then_questions_span_multiple_topics` —
Create an assessment with `assessment_type=DIAGNOSTIC` and `topic_ids=[]`. Assert that
the selected questions come from at least 2 different `curriculum_topic_id` values.

`test_create_when_difficulty_range_narrow_then_only_matching_questions_selected` —
Populate the bank with 20 easy questions (difficulty 1.0–2.0) and 20 hard ones
(difficulty 4.0–5.0). Request `difficulty_min=1.0, difficulty_max=2.5`. Assert all
selected questions have `difficulty_level <= 2.5`.

`test_create_always_sets_is_system_generated_false` — Call `create_assessment` with any
valid config. Assert `assessment.is_system_generated is False`. This cannot be overridden
by any field in `AssessmentCreateRequest`.

`test_publish_when_draft_then_status_becomes_active` — Create a draft assessment, call
`publish_assessment`, assert `status="ACTIVE"` and `published_at` is not None.

`test_publish_when_already_active_then_raises_value_error` — Call `publish_assessment`
on an already-ACTIVE assessment. Assert `ValueError` is raised containing the word
"status".

`test_publish_when_different_teacher_then_raises_value_error` — Call `publish_assessment`
with a `teacher_id` different from the assessment creator. Assert `ValueError` raised.

`test_close_when_active_then_status_becomes_closed` — Publish an assessment then close it.
Assert `status="CLOSED"`.

`test_close_when_draft_then_raises_value_error` — Attempt to close a DRAFT assessment.
Assert `ValueError` raised.

`test_get_when_student_role_then_correct_answer_key_is_none` — Call `get_assessment`
with `requesting_user_role="STUDENT"`. Assert that every question in the returned list
has `correct_answer_key=None`.

`test_get_when_teacher_role_then_correct_answer_key_is_present` — Same setup, but with
`requesting_user_role="TEACHER"`. Assert every question has a non-None `correct_answer_key`.

`test_sample_distribution_when_3_topics_10_questions_then_each_topic_represented` —
Call `_sample_with_topic_distribution` with 3 topics × 6 questions each, requesting 10.
Assert the result contains questions from all 3 topics.

**Integration tests — `test_assessment_generation.py`**

`test_full_creation_flow_when_valid_then_assessment_and_bridge_rows_in_db` — Uses a
real test DB session. Call `create_assessment`, commit, then query the DB directly.
Assert one `Assessment` row with correct fields and `question_count` bridge rows.

`test_create_and_publish_flow_then_status_transitions_correctly` — Create then publish.
Assert DB row has `status="ACTIVE"` and `published_at` is populated.

---

## Do NOT Touch

- `backend/app/tasks/onboarding_tasks.py` — Tier 1 creation lives there, not here.
- `backend/app/schemas/assessments.py` — Schema is frozen from M0-10-T1. Import from it.
- Any existing route file.
- Any existing migration file.
