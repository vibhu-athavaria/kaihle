# M0-10-T1 — API Contract Foundation
**Milestone:** M0 · **Epic:** M0-10 — API Contract Finalization · **Task:** T1
**Depends on:** M0-8-T4 (shared UI components), M0-3-T3 (auth middleware)
**Blocks:** Every other M0-10 task — nothing in Group B or beyond may start until this passes
**Estimated effort:** 3–4 hours

---

## Context

This task establishes the foundation that every other M0-10 task builds on. It does
four things: adds the frozen contract rule to CONSTITUTION.md, defines all shared
Pydantic schemas that stub routes will import, fixes the CORS origins in main.py to
cover all five apps, and standardises the pagination envelope and error response
shapes so every endpoint in the platform returns consistent structures.

Read CONSTITUTION.md in full before starting. Read the complete endpoint list in
M0-10_brief.md so you understand what every schema will be used for.

---

## User Story

As a developer implementing any M0-10 stub route, I want shared schemas already
defined and importable so I can write a stub in ten minutes without inventing
inconsistent response shapes.

---

## Files to Create / Modify

```
docs/CONSTITUTION.md                          ← MODIFY: add frozen contract rule
backend/app/main.py                           ← MODIFY: CORS origins + router imports
backend/app/schemas/common.py                 ← CREATE: pagination envelope + error shape
backend/app/schemas/gap_map.py                ← CREATE
backend/app/schemas/assessments.py           ← CREATE
backend/app/schemas/attempts.py              ← CREATE
backend/app/schemas/lesson_plans.py          ← CREATE
backend/app/schemas/study_plans.py           ← CREATE
backend/app/schemas/parent.py                ← CREATE
backend/app/schemas/analytics.py             ← CREATE
backend/app/schemas/curriculum.py            ← CREATE
backend/app/tests/unit/test_schemas.py       ← CREATE: smoke tests for every schema
```

---

## CONSTITUTION.md Change

Add the following as Rule 19 in §4 Absolute Rules. Insert it after Rule 18
(Celery dead-letter log):

```markdown
**Rule 19 — API contracts are frozen once published.** Once an endpoint's path,
HTTP method, request body schema, and response body schema are defined in any
M0-10-T* task file, they are permanently frozen. Future milestones replace only
the stub function body with real business logic. They never change the path,
method, or schema shape. Any breaking change requires a new API version prefix
(`/api/v2/`) and an ADR entry in `docs/adr/`. This rule exists to guarantee that
frontend code written against a stub never needs to change when the real
implementation ships.
```

---

## CORS Fix in `main.py`

Replace the existing `allow_origins` list with all five app ports:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",   # apps/teacher
        "http://localhost:3002",   # apps/student
        "http://localhost:3003",   # apps/parent
        "http://localhost:3004",   # apps/school-admin  ← new
        "http://localhost:3005",   # apps/kaihle-admin  ← new
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## `schemas/common.py` — Shared Envelope Types

Every paginated list endpoint in the platform returns this exact shape. No exceptions.

```python
"""Shared Pydantic schemas used across all API domains."""

from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard pagination envelope. Every list endpoint returns this shape.

    Usage:
        response_model=Page[MyItemSchema]
    """
    data: list[T]
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)


class ErrorDetail(BaseModel):
    """Standard error response shape. Registered globally in M6-3-T2.

    All HTTP error responses use this shape — never raw strings.
    error_code is machine-readable for frontend switch statements.
    message is safe to display to end users.
    details holds field-level validation errors when applicable.
    """
    error_code: str
    message: str
    details: dict = Field(default_factory=dict)
```

---

## `schemas/gap_map.py`

```python
"""Gap map response schemas — used by M2-1-T2 real implementation."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class StudentGapScore(BaseModel):
    student_id: UUID
    student_name: str
    mastery_score: float | None   # None = this student has not yet been assessed
    last_assessed_at: datetime | None


class GapMapNode(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    class_average: float | None   # None = no students assessed on this subtopic yet
    student_count: int
    student_scores: list[StudentGapScore]


class ClassGapMap(BaseModel):
    class_id: UUID
    subject_id: UUID
    generated_at: datetime
    nodes: list[GapMapNode]


class StudentSubtopicScore(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    mastery_score: float | None
    last_assessed_at: datetime | None


class StudentGapMap(BaseModel):
    student_id: UUID
    subject_id: UUID
    generated_at: datetime
    scores: list[StudentSubtopicScore]


class ClassSummary(BaseModel):
    """Lightweight per-class mastery summary for teacher dashboard class cards.

    Distinct from ClassGapMap — this is the minimal data needed to render
    a class card with a mastery indicator. ClassGapMap is the full heatmap.
    """
    class_id: UUID
    avg_mastery: float | None     # None when no assessments have been taken
    student_count: int
    assessed_student_count: int   # students who have taken at least one assessment
    last_updated_at: datetime | None
```

---

## `schemas/assessments.py`

```python
"""Assessment schemas. Note: correct_answer is NEVER in student-facing responses."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class QuestionOption(BaseModel):
    key: str    # e.g. "a", "b", "c", "d"
    text: str


class AssessmentQuestion(BaseModel):
    """Student-facing question — no correct_answer field by design."""
    question_id: UUID
    question_text: str
    options: list[QuestionOption]


class AssessmentQuestionWithAnswer(AssessmentQuestion):
    """Teacher/admin-facing question — includes correct_answer for review."""
    correct_answer_key: str
    explanation: str | None


class AssessmentResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    assessment_type: str       # "DIAGNOSTIC" | "PROGRESS_CHECK"
    is_system_generated: bool  # True = Tier 1, False = Tier 2
    status: str                # "DRAFT" | "ACTIVE" | "CLOSED"
    topic_ids: list[UUID]
    question_count: int
    created_at: datetime
    published_at: datetime | None
    deadline: datetime | None


class AssessmentCreateRequest(BaseModel):
    title: str
    topic_ids: list[UUID]
    question_count: int = 20
    deadline: datetime | None = None
```

---

## `schemas/attempts.py`

```python
"""Student attempt schemas — the assessment-taking flow."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from app.schemas.assessments import AssessmentQuestion


class AttemptResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    student_id: UUID
    status: str                  # "NOT_STARTED" | "IN_PROGRESS" | "SUBMITTED"
    started_at: datetime | None
    submitted_at: datetime | None
    score: float | None          # None until submitted and scored
    questions: list[AssessmentQuestion]  # empty until attempt is started


class AnswerSubmitRequest(BaseModel):
    question_id: UUID
    selected_key: str            # the option key the student chose


class AttemptSubmitRequest(BaseModel):
    """Submit all answers at once — used when student clicks final Submit."""
    answers: list[AnswerSubmitRequest]


class AttemptResultResponse(BaseModel):
    attempt_id: UUID
    score: float                 # 0.0–1.0 e.g. 0.75 = 75%
    total_questions: int
    correct_count: int
    time_taken_seconds: int | None
    submitted_at: datetime
```

---

## `schemas/lesson_plans.py`

```python
"""Lesson plan schemas — AI-generated weekly plans for teachers."""

from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class LessonPlanResponse(BaseModel):
    id: UUID
    class_id: UUID
    week_start: date
    status: str                  # "GENERATED" | "EDITED" | "USED" | "ARCHIVED"
    generated_plan: dict | None  # full JSON structure from LLM
    teacher_edits: dict | None   # sparse delta — only fields teacher changed
    created_at: datetime


class LessonPlanEditRequest(BaseModel):
    """All fields optional — PATCH applies only the fields provided."""
    starter_10min: str | None = None
    group_a_activity: str | None = None
    group_b_activity: str | None = None
    group_c_activity: str | None = None
    plenary_10min: str | None = None
    homework: str | None = None
    teacher_notes: str | None = None


class LessonPlanStatusRequest(BaseModel):
    status: str   # "USED" | "ARCHIVED"
```

---

## `schemas/study_plans.py`

```python
"""Study plan schemas — personalised per-student gap remediation plans."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class StudyPlanResource(BaseModel):
    resource_id: UUID
    title: str
    resource_type: str           # "VIDEO" | "ARTICLE" | "INTERACTIVE"
    url: str
    source: str                  # "YOUTUBE" | "KHAN_ACADEMY" | "KAIHLE"
    duration_minutes: int | None
    is_watched: bool


class StudyPlanQuizQuestion(BaseModel):
    """Note: correct_answer is NEVER included — same rule as AssessmentQuestion."""
    question_index: int
    question_text: str
    options: list[dict]


class StudyPlanResponse(BaseModel):
    id: UUID
    student_id: UUID
    class_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    status: str                  # "GENERATING"|"ACTIVE"|"IN_PROGRESS"|"COMPLETED"
    resources: list[StudyPlanResource]
    quiz_questions: list[StudyPlanQuizQuestion]
    quiz_score: float | None     # None until quiz submitted
    created_at: datetime


class StudyPlanAssignRequest(BaseModel):
    subtopic_id: UUID
    student_ids: list[UUID] | None = Field(
        None,
        description="List of student UUIDs, or null to assign to all enrolled students"
    )


class StudyPlanAssignResponse(BaseModel):
    status: str = "generating"
    plans: list[dict]            # [{"plan_id": uuid, "student_id": uuid, "status": "GENERATING"}]


class QuizSubmitRequest(BaseModel):
    responses: list[dict]        # [{"question_index": int, "answer": str}]


class QuizSubmitResponse(BaseModel):
    score: float
    correct_count: int
    total_questions: int
    plan_status: str
```

---

## `schemas/parent.py`

```python
"""Parent portal schemas. CRITICAL: numeric mastery scores are never exposed here."""

from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class ChildSummary(BaseModel):
    student_id: UUID
    first_name: str
    last_name: str
    grade_name: str
    school_name: str
    subjects: list[str]


class TopicStatus(BaseModel):
    topic_name: str
    status: str           # "Strong" | "Developing" | "Needs Work" — plain language only
    status_label: str     # "green" | "amber" | "red"


class SubjectGapSummary(BaseModel):
    subject_name: str
    topics: list[TopicStatus]


class ParentGapMap(BaseModel):
    """Simplified gap map for parents. No mastery_score field — by design.

    Parents see plain-language labels only. The mastery_to_status() conversion
    happens in the service layer before this schema is populated.
    """
    student_name: str
    grade_name: str
    subjects: list[SubjectGapSummary]


class WeeklyReport(BaseModel):
    report_id: UUID
    week_start: date
    subject_name: str
    narrative: str
    highlights: list[str]
    created_at: datetime
```

---

## `schemas/analytics.py`

```python
"""Analytics schemas — school-level and platform-level usage data."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class ClassBreakdown(BaseModel):
    class_id: UUID
    class_name: str
    subject_name: str
    grade_name: str
    teacher_name: str
    student_count: int
    avg_mastery: float | None    # None if no assessments taken
    assessments_completed: int


class SchoolAnalytics(BaseModel):
    school_id: UUID
    school_name: str
    generated_at: datetime
    total_students: int
    active_students_last_7_days: int
    onboarding_completion_rate: float   # 0.0–1.0
    students_pending_onboarding: int
    assessments_completed: int
    study_plans_assigned: int
    study_plans_completed: int
    lesson_plans_generated: int
    lesson_plans_used: int
    classes: list[ClassBreakdown]


class PlatformStats(BaseModel):
    """KaihleAdmin view — platform-wide counts across all schools."""
    total_schools: int
    total_active_students: int
    total_teachers: int
    assessments_completed_last_7_days: int
    generated_at: datetime
```

---

## `schemas/curriculum.py`

```python
"""Curriculum schemas — global read-only data, no school_id."""

from uuid import UUID
from pydantic import BaseModel


class GradeResponse(BaseModel):
    id: UUID
    name: str          # e.g. "Grade 9"
    level: int         # e.g. 9
    curriculum_id: UUID


class SubjectResponse(BaseModel):
    id: UUID
    name: str          # e.g. "Mathematics"
    code: str          # e.g. "MATH"


class TopicResponse(BaseModel):
    id: UUID
    name: str
    subject_id: UUID
    grade_id: UUID
    order: int


class SubtopicResponse(BaseModel):
    id: UUID
    name: str
    topic_id: UUID
    order: int


class CurriculumResponse(BaseModel):
    id: UUID
    name: str          # e.g. "Cambridge IGCSE"
    code: str          # e.g. "igcse"
    is_active: bool
```

---

## Unit Tests (`tests/unit/test_schemas.py`)

Write a smoke test that instantiates every schema with valid minimal data and
asserts the instance is created without error. This confirms that the schema
definitions are syntactically correct and importable before any route uses them.

```python
"""Smoke tests — verify every schema can be instantiated with valid data."""
import uuid
from datetime import datetime, date
from app.schemas.common import Page, ErrorDetail
from app.schemas.gap_map import ClassGapMap, StudentGapMap, ClassSummary
from app.schemas.assessments import AssessmentResponse, AssessmentQuestion
from app.schemas.attempts import AttemptResponse, AttemptResultResponse
from app.schemas.lesson_plans import LessonPlanResponse
from app.schemas.study_plans import StudyPlanResponse, StudyPlanAssignResponse
from app.schemas.parent import ParentGapMap, WeeklyReport, ChildSummary
from app.schemas.analytics import SchoolAnalytics, PlatformStats
from app.schemas.curriculum import GradeResponse, SubjectResponse

class TestSchemaInstantiation:
    def test_page_schema(self):
        p = Page[dict](data=[], total=0, page=1, page_size=20)
        assert p.total == 0

    def test_class_gap_map_empty_nodes(self):
        g = ClassGapMap(
            class_id=uuid.uuid4(), subject_id=uuid.uuid4(),
            generated_at=datetime.utcnow(), nodes=[]
        )
        assert g.nodes == []

    def test_attempt_response_not_started(self):
        a = AttemptResponse(
            id=uuid.uuid4(), assessment_id=uuid.uuid4(),
            student_id=uuid.uuid4(), status="NOT_STARTED",
            started_at=None, submitted_at=None, score=None, questions=[]
        )
        assert a.status == "NOT_STARTED"

    def test_parent_gap_map_has_no_mastery_score_field(self):
        g = ParentGapMap(student_name="Emma", grade_name="Grade 9", subjects=[])
        assert not hasattr(g, "mastery_score")

    def test_school_analytics_zero_values(self):
        s = SchoolAnalytics(
            school_id=uuid.uuid4(), school_name="Test",
            generated_at=datetime.utcnow(), total_students=0,
            active_students_last_7_days=0, onboarding_completion_rate=0.0,
            students_pending_onboarding=0, assessments_completed=0,
            study_plans_assigned=0, study_plans_completed=0,
            lesson_plans_generated=0, lesson_plans_used=0, classes=[]
        )
        assert s.total_students == 0
```

---

## Acceptance Criteria

- `from app.schemas.common import Page, ErrorDetail` imports without error
- `from app.schemas.gap_map import ClassGapMap, ClassSummary` imports without error
- All other schema files import without error
- `pytest app/tests/unit/test_schemas.py` passes with zero failures
- `mypy app/schemas/` passes with zero errors
- `GET /docs` shows updated API description with correct CORS note
- `http://localhost:3004` (school-admin app) can reach the backend without CORS errors
- `http://localhost:3005` (kaihle-admin app) can reach the backend without CORS errors
- CONSTITUTION.md contains Rule 19 (frozen contract rule) in §4

---

## Do NOT Touch

- Any existing route files (`auth.py`, `schools.py`, `users.py`, `onboarding.py`)
- Any existing schema files (`school.py`, `user.py`, `auth.py`)
- Any existing integration tests
- Any frontend files
