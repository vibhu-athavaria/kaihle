# M0-2-T2 — SQLAlchemy Async ORM Models
**Milestone:** M0 — Foundations
**Epic:** M0-2 — Database & Migrations
**Task ID:** M0-2-T2
**Mode:** Code (MiniMax)
**Estimated effort:** 4–5 hours

---

## Context

This task creates all SQLAlchemy ORM models that map to the 35 tables created in M0-2-T1. Models use SQLAlchemy 2.x `mapped_column()` syntax with full type annotations. All models inherit from a shared `Base` with `created_at` / `updated_at` mixins.

**CRITICAL:** Column names, types, and constraints must exactly match `kaihle_v2_1_schema.sql`. If this task file and the SQL file conflict, the SQL file wins.

**Depends on:** M0-2-T1 (tables must exist before models can be tested against DB)

---

## User Story

As a developer, I want typed SQLAlchemy models for every table so I can write type-safe database queries throughout the application.

---

## What To Build

### Base Class and Mixin

**`/backend/app/models/base.py`:**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
```

---

### Model Files

Create one file per domain in `/backend/app/models/`:

---

**`/backend/app/models/curriculum.py`** — covers:
`curricula`, `subjects`, `grades`, `topics`, `curriculum_subjects`, `curriculum_topics`, `subtopics`, `subtopic_prerequisites`, `topic_prerequisites`, `curriculum_chunks`

Key columns to include on `Subtopic`:
```python
class Subtopic(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subtopics"

    curriculum_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_topics.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    learning_objectives: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    sequence_order: Mapped[Optional[int]]
    difficulty_level: Mapped[Optional[int]]
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768))
    # Vector type from pgvector.sqlalchemy import Vector
```

---

**`/backend/app/models/school.py`** — covers:
`schools`, `school_curricula`, `classes`, `class_enrollments`

---

**`/backend/app/models/user.py`** — covers:
`users`, `student_profiles`, `teacher_profiles`, `parent_student`, `auth_tokens`

Key additions for v2.1 on `StudentProfile`:
```python
class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    # ... other columns from kaihle_v2_1_schema.sql ...
    onboarding_diagnostic_status: Mapped[str] = mapped_column(
        Enum("PENDING", "IN_PROGRESS", "COMPLETED", name="onboarding_status"),
        nullable=False,
        server_default="PENDING"
    )
```

---

**`/backend/app/models/onboarding.py`** — covers:
`student_learning_profiles` (NEW v2.1)

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class StudentLearningProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "student_learning_profiles"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    modality_scores: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    # Expected shape: {"visual": 0.8, "auditory": 0.3,
    #                  "reading_writing": 0.6, "kinesthetic": 0.5}

    work_style: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    # Expected shape: {"prefers_solo": True, "short_sessions": False,
    #                  "task_based": True, "group_learning": False,
    #                  "concept_first": False}

    interests: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    # e.g. ["football", "music", "gaming"]
    # Stored lowercase. Top 2 injected into quiz generation prompts.

    questionnaire_version: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="v1"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NULL means questionnaire not yet submitted. Non-null means complete.
```

---

**`/backend/app/models/assessment.py`** — covers:
`assessments`, `assessment_selected_questions`, `student_attempts`, `student_responses`

Key v2.1 addition on `Assessment`:
```python
class Assessment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assessments"

    # ... all columns from kaihle_v2_1_schema.sql ...

    is_system_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    # TRUE = Tier 1 (auto-created on student enrollment by Celery task)
    # FALSE = Tier 2 (manually created by teacher)
    # Determines whether submit triggers onboarding completion check
```

---

**`/backend/app/models/gap.py`** — covers:
`gap_states`

---

**`/backend/app/models/study_plan.py`** — covers:
`study_plans`, `study_plan_resources`, `study_plan_quizzes`

---

**`/backend/app/models/lesson_plan.py`** — covers:
`lesson_plans`

---

**`/backend/app/models/parent.py`** — covers:
`parent_report_snapshots`

---

**`/backend/app/models/billing.py`** — covers:
`subscription_plans`, `school_subscriptions`, `subscription_invoices`, `payments`, `trial_extensions`

---

**`/backend/app/models/__init__.py`** — import all models so Alembic can detect them:

```python
from app.models.base import Base
from app.models.curriculum import (
    Curriculum, Subject, Grade, Topic, CurriculumSubject,
    CurriculumTopic, Subtopic, SubtopicPrerequisite,
    TopicPrerequisite, CurriculumChunk,
)
from app.models.school import School, SchoolCurriculum, Class, ClassEnrollment
from app.models.user import (
    User, StudentProfile, TeacherProfile, ParentStudent, AuthToken
)
from app.models.onboarding import StudentLearningProfile
from app.models.assessment import (
    Assessment, AssessmentSelectedQuestion, StudentAttempt, StudentResponse
)
from app.models.gap import GapState
from app.models.study_plan import StudyPlan, StudyPlanResource, StudyPlanQuiz
from app.models.lesson_plan import LessonPlan
from app.models.parent import ParentReportSnapshot
from app.models.billing import (
    SubscriptionPlan, SchoolSubscription, SubscriptionInvoice,
    Payment, TrialExtension,
)

__all__ = [
    "Base",
    "Curriculum", "Subject", "Grade", "Topic", "CurriculumSubject",
    "CurriculumTopic", "Subtopic", "SubtopicPrerequisite",
    "TopicPrerequisite", "CurriculumChunk",
    "School", "SchoolCurriculum", "Class", "ClassEnrollment",
    "User", "StudentProfile", "TeacherProfile", "ParentStudent", "AuthToken",
    "StudentLearningProfile",
    "Assessment", "AssessmentSelectedQuestion", "StudentAttempt", "StudentResponse",
    "GapState",
    "StudyPlan", "StudyPlanResource", "StudyPlanQuiz",
    "LessonPlan",
    "ParentReportSnapshot",
    "SubscriptionPlan", "SchoolSubscription", "SubscriptionInvoice",
    "Payment", "TrialExtension",
]
```

---

### Update `alembic/env.py`

After models are created, update the import in `env.py`:

```python
from app.models import Base  # noqa: F401
target_metadata = Base.metadata
```

This enables `alembic revision --autogenerate` to detect future schema changes.

---

### Database Session Factory

**`/backend/app/core/database.py`:**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## Files To Create / Modify

```
/backend/app/models/base.py
/backend/app/models/curriculum.py
/backend/app/models/school.py
/backend/app/models/user.py
/backend/app/models/onboarding.py          ← NEW v2.1
/backend/app/models/assessment.py
/backend/app/models/gap.py
/backend/app/models/study_plan.py
/backend/app/models/lesson_plan.py
/backend/app/models/parent.py
/backend/app/models/billing.py
/backend/app/models/__init__.py
/backend/app/core/database.py
/backend/alembic/env.py                    ← MODIFY (add Base metadata import)
```

---

## Acceptance Criteria

- [ ] `mypy app/models/` passes with zero errors (strict mode)
- [ ] Unit test: `StudentLearningProfile()` can be instantiated with required fields
- [ ] Unit test: `Assessment()` defaults `is_system_generated` to `False`
- [ ] Unit test: `StudentProfile()` defaults `onboarding_diagnostic_status` to `"PENDING"`
- [ ] Integration test: every model can be written to and read from test database
- [ ] Integration test: `StudentLearningProfile` unique constraint on `student_id` raises `IntegrityError` on duplicate insert
- [ ] `alembic revision --autogenerate` detects zero schema changes after models are imported (models match migration exactly)

---

## Dependencies

- M0-2-T1 — all 35 tables must exist in the database

## Output (What Next Tasks Can Use)

- All ORM models importable from `app.models`
- `get_db()` dependency available for all route handlers
- `Base.metadata` available for `alembic --autogenerate`
- `StudentLearningProfile` model ready for M0-6-T1 (learning profile service)
- `Assessment.is_system_generated` field ready for M1-4-T1 (attempt submit logic)
