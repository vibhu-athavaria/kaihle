# M0-10-T2b — Curriculum Read Endpoints
**Milestone:** M0 · **Epic:** M0-10 — API Contract Finalization · **Task:** T2b
**Depends on:** M0-10-T1 (schemas/curriculum.py must exist)
**Parallel with:** M0-10-T2, T3, T4, T5, T6
**Real data available from:** M1-2-T1 (curriculum graph seeding script)
**Estimated effort:** 2–3 hours

---

## Context

Unlike every other M0-10 stub task, the curriculum endpoints are **fully implementable
right now** — not just stubbable. The curriculum tables (`curricula`, `subjects`,
`grades`, `topics`, `curriculum_topics`, `subtopics`) are school-agnostic, read-only,
and populated by the `seed_curriculum_graph.py` script from M1-2-T1. There is no
business logic, no LLM, no Celery, and no school_id filter needed. The routes simply
query and return.

This makes these endpoints different from all other M0-10 tasks. Rather than writing
stubs that return empty data, we write real implementations that query the curriculum
tables. When the seeding script has not yet been run (during development before M1),
the endpoints correctly return empty lists — which is the accurate state of the
database, not a stub.

**Why this task is on the critical path:** The teacher assessment creation wizard
(`M1-3-T3`) calls `GET /subjects/{subject_id}/topics` to populate the topic selector
in Step 2. Without this endpoint, the wizard cannot function and M1-3-T3 is blocked.

All six endpoints are read-only and accessible to any authenticated user regardless
of role. Curriculum data is global — not school-scoped.

---

## User Story

As a teacher creating an assessment, I want to browse the curriculum topic list for
my class's subject so I can select which topics the assessment should cover. As a
student, I want to know which subjects and curricula I am enrolled in. As the system,
I want a single authoritative source for curriculum structure that all features read from.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/curriculum.py       ← CREATE
backend/app/main.py                           ← MODIFY: register router
backend/app/tests/integration/test_curriculum_routes.py  ← CREATE
```

Note: `schemas/curriculum.py` already exists from M0-10-T1. Import from it.

---

## Route File: `routes/curriculum.py`

```python
"""Curriculum API routes — global read-only data.

These endpoints expose the curriculum hierarchy that was seeded by
seed_curriculum_graph.py (M1-2-T1). All authenticated users can read
curriculum data regardless of role — it is school-agnostic.

No school_id filtering. No pagination on small lists (curricula, grades,
subjects). Pagination applied to topics and subtopics which can be larger.

These are fully implemented routes — not stubs. The data is static and
seeded once. If the tables are empty (seed script not yet run), the
endpoints correctly return empty lists.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.schemas.curriculum import (
    CurriculumResponse,
    GradeResponse,
    SubjectResponse,
    SubtopicResponse,
    TopicResponse,
)

router = APIRouter(tags=["curriculum"])


@router.get("/curricula", response_model=list[CurriculumResponse])
async def list_curricula(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CurriculumResponse]:
    """List all available curricula (e.g. Cambridge Lower Secondary, IGCSE).

    Returns all active curricula. Typically 2 rows in v1.
    """
    rows = await db.scalars(
        select(Curriculum)
        .where(Curriculum.is_active.is_(True))
        .order_by(Curriculum.name)
    )
    return [
        CurriculumResponse(
            id=c.id,
            name=c.name,
            code=c.code,
            is_active=c.is_active,
        )
        for c in rows
    ]


@router.get("/curricula/{curriculum_id}", response_model=CurriculumResponse)
async def get_curriculum(
    curriculum_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurriculumResponse:
    """Get a single curriculum by ID."""
    from fastapi import HTTPException, status
    curriculum = await db.scalar(
        select(Curriculum).where(Curriculum.id == curriculum_id)
    )
    if not curriculum:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curriculum not found",
        )
    return CurriculumResponse(
        id=curriculum.id,
        name=curriculum.name,
        code=curriculum.code,
        is_active=curriculum.is_active,
    )


@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(
    curriculum_id: UUID | None = Query(
        None,
        description="Filter grades by curriculum (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GradeResponse]:
    """List all grades, optionally filtered by curriculum.

    Without filter: returns all 7 grades (6–12).
    With curriculum_id: returns only grades that have content in that curriculum.
    """
    if curriculum_id:
        # Return only grades that have curriculum_topics rows for this curriculum
        rows = await db.scalars(
            select(Grade)
            .join(
                CurriculumTopic,
                CurriculumTopic.grade_id == Grade.id,
            )
            .where(CurriculumTopic.curriculum_id == curriculum_id)
            .distinct()
            .order_by(Grade.level)
        )
    else:
        rows = await db.scalars(
            select(Grade).order_by(Grade.level)
        )
    return [
        GradeResponse(
            id=g.id,
            name=g.name,
            level=g.level,
            curriculum_id=curriculum_id,  # None if no filter applied
        )
        for g in rows
    ]


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    curriculum_id: UUID | None = Query(
        None,
        description="Filter subjects by curriculum (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubjectResponse]:
    """List all subjects, optionally filtered by curriculum.

    Without filter: returns all 7 subjects.
    With curriculum_id: returns only subjects available in that curriculum.
    """
    if curriculum_id:
        rows = await db.scalars(
            select(Subject)
            .join(
                CurriculumSubject,
                CurriculumSubject.subject_id == Subject.id,
            )
            .where(CurriculumSubject.curriculum_id == curriculum_id)
            .order_by(CurriculumSubject.sort_order, Subject.name)
        )
    else:
        rows = await db.scalars(
            select(Subject).order_by(Subject.name)
        )
    return [
        SubjectResponse(id=s.id, name=s.name, code=s.code)
        for s in rows
    ]


@router.get(
    "/subjects/{subject_id}/topics",
    response_model=list[TopicResponse],
)
async def list_subject_topics(
    subject_id: UUID,
    curriculum_id: UUID | None = Query(
        None,
        description="Filter topics by curriculum (recommended for accurate results)",
    ),
    grade_id: UUID | None = Query(
        None,
        description="Filter topics by grade level (optional)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TopicResponse]:
    """List topics for a subject.

    Used by the teacher assessment creation wizard (Step 2: Select Topics).
    Filter by curriculum_id and grade_id to get the topics relevant to a
    specific class. Without filters, returns all topics for the subject
    across all curricula and grades (may contain duplicates by topic name
    across grade levels).

    Results are ordered by sequence_order within each grade.
    """
    query = (
        select(Topic, CurriculumTopic)
        .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
        .where(CurriculumTopic.subject_id == subject_id)
    )
    if curriculum_id:
        query = query.where(CurriculumTopic.curriculum_id == curriculum_id)
    if grade_id:
        query = query.where(CurriculumTopic.grade_id == grade_id)

    query = query.order_by(CurriculumTopic.sequence_order, Topic.name)
    rows = (await db.execute(query)).all()

    return [
        TopicResponse(
            id=topic.id,
            name=topic.name,
            subject_id=subject_id,
            grade_id=ct.grade_id,
            order=ct.sequence_order or 0,
        )
        for topic, ct in rows
    ]


@router.get(
    "/topics/{topic_id}/subtopics",
    response_model=list[SubtopicResponse],
)
async def list_topic_subtopics(
    topic_id: UUID,
    curriculum_id: UUID | None = Query(None),
    grade_id: UUID | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubtopicResponse]:
    """List subtopics for a topic.

    Optionally filter by curriculum_id and grade_id to get subtopics for
    a specific curriculum-topic-grade combination. Results ordered by
    sequence_order.
    """
    query = (
        select(Subtopic)
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .where(CurriculumTopic.topic_id == topic_id)
    )
    if curriculum_id:
        query = query.where(CurriculumTopic.curriculum_id == curriculum_id)
    if grade_id:
        query = query.where(CurriculumTopic.grade_id == grade_id)

    query = query.order_by(Subtopic.sequence_order, Subtopic.name)
    rows = await db.scalars(query)

    return [
        SubtopicResponse(
            id=s.id,
            name=s.name,
            topic_id=topic_id,
            order=s.sequence_order or 0,
        )
        for s in rows
    ]
```

---

## `main.py` Registration

```python
from app.api.v1.routes import curriculum   # add to imports

app.include_router(curriculum.router, prefix="/api/v1")
```

---

## Acceptance Criteria

**Before M1-2-T1 seed script runs (empty curriculum tables):**

- `GET /api/v1/curricula` returns `200` with `[]` — not a 404 or 500
- `GET /api/v1/grades` returns `200` with `[]`
- `GET /api/v1/subjects` returns `200` with `[]`
- `GET /api/v1/subjects/{any_uuid}/topics` returns `200` with `[]`
- `GET /api/v1/topics/{any_uuid}/subtopics` returns `200` with `[]`
- Unauthenticated request returns `401` — these endpoints require a valid JWT

**After M1-2-T1 seed script runs (real curriculum data present):**

- `GET /api/v1/curricula` returns 2 items: Cambridge Lower Secondary and Cambridge IGCSE
- `GET /api/v1/grades` returns 7 items: Grade 6 through Grade 12
- `GET /api/v1/grades?curriculum_id={lower_id}` returns 3 items: Grades 6, 7, 8
- `GET /api/v1/grades?curriculum_id={igcse_id}` returns 2 items: Grades 9, 10
- `GET /api/v1/subjects` returns 7 items: MATH, SCI, ENG, BIO, CHEM, PHY, ENGL
- `GET /api/v1/subjects?curriculum_id={lower_id}` returns 3 items: MATH, SCI, ENG
- `GET /api/v1/subjects/{math_id}/topics?curriculum_id={lower_id}&grade_id={g6_id}` returns the Mathematics Grade 6 topics (Number, Algebra, Geometry, etc.)
- Topics are returned in `sequence_order` order, not alphabetically
- `GET /api/v1/topics/{number_topic_id}/subtopics` returns the subtopics for that topic in sequence order

**Integration tests — `test_curriculum_routes.py`**

`test_list_curricula_when_seeded_then_returns_two_curricula` — Seed both curricula.
Assert HTTP 200, response length is 2, both have non-null `id`, `name`, `code`.

`test_list_grades_when_curriculum_filter_then_only_correct_grades` — Seed the full
curriculum graph. Call with `?curriculum_id={igcse_id}`. Assert exactly 2 grades
returned (9 and 10) and Grade 6 is not in the response.

`test_list_subjects_when_curriculum_filter_then_only_correct_subjects` — Call with
`?curriculum_id={lower_id}`. Assert MATH, SCI, ENG are present and BIO, CHEM, PHY,
ENGL are not.

`test_list_topics_when_grade_and_curriculum_filter_then_correct_topics` — Call
`GET /subjects/{math_id}/topics?curriculum_id={lower_id}&grade_id={g7_id}`.
Assert only Mathematics Grade 7 topics are returned.

`test_list_topics_ordered_by_sequence_order` — Seed topics with explicit
`sequence_order` values. Assert the response list is ordered by `sequence_order`
ascending.

`test_list_subtopics_when_topic_id_then_correct_subtopics_returned` — Call
`GET /topics/{algebra_id}/subtopics`. Assert the response contains subtopics
for Algebra only, in `sequence_order`.

`test_all_curriculum_endpoints_when_no_auth_then_401` — Call each of the six
endpoints without an Authorization header. Assert HTTP 401 for all.

`test_get_curriculum_when_invalid_id_then_404` — Call `GET /curricula/{random_uuid}`
where the UUID does not exist. Assert HTTP 404.

---

## Do NOT Touch

`backend/app/schemas/curriculum.py` — frozen from M0-10-T1. Import from it.
Any existing route file. Any migration file — the curriculum tables already exist
from M0-2-T1.
