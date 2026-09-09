"""Integration tests for mini-course API routes (M5-1-T2).

Tests verify real service calls through HTTP endpoints using a live test DB.
Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_mini_course_route.py -v
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.similarity import normalise_text
from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from app.models.llm_usage import LlmUsageEvent
from app.models.mini_course import MiniCourseChatMessage
from app.models.school import School
from app.models.subtopic_content import SubtopicContent
from app.models.user import User, UserRole
from app.services.mini_course_service import MiniCourseService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_curriculum_subtopic(db: AsyncSession) -> tuple[Subtopic, Topic]:
    """Create a minimal curriculum chain and return (subtopic, topic)."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Math-{uuid.uuid4().hex[:4]}",
        code=f"M{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Curr-{uuid.uuid4().hex[:4]}",
        code=f"C{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    topic = Topic(id=uuid.uuid4(), name="Algebra", is_active=True)
    db.add_all([subject, grade, curriculum, topic])
    await db.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=True,
    )
    db.add(ct)
    await db.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    db.add(subtopic)
    await db.flush()

    # Check questions resolve through the objective, so the fixture needs one.
    objective = LearningObjective(
        id=uuid.uuid4(),
        canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
        name="Solve linear equations",
        learning_objective="Solve linear equations",
        normalised_objective=normalise_text("Solve linear equations"),
        topic_id=topic.id,
        grade_id=grade.id,
        is_active=True,
    )
    db.add(objective)
    await db.flush()
    db.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))
    await db.commit()

    return subtopic, topic


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/students/me/subtopics/{subtopic_id}/course
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_route_when_authenticated_student_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET course endpoint returns 200 with the expected payload shape for a student."""
    subtopic, topic = await _create_curriculum_subtopic(db_session)

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["subtopic_id"] == str(subtopic.id)
    assert data["subtopic_name"] == "Linear Equations"
    assert data["topic_name"] == "Algebra"
    assert data["content_status"] in ("ready", "unavailable")
    assert "progress" in data
    assert "check_questions" in data


@pytest.mark.asyncio
async def test_get_course_route_when_unauthenticated_then_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET course endpoint returns 401 when no auth token is provided."""
    response = await client.get(
        f"/api/v1/students/me/subtopics/{uuid.uuid4()}/course",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_progress_route_when_valid_payload_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """POST progress endpoint returns 200 {"ok": true} when student marks progress."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    # First visit to create the progress row
    await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    response = await client.post(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course/progress",
        headers=make_auth_header(student),
        json={"explanation_accessed": True, "video_accessed": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_get_course_when_only_other_school_has_approved_content_then_content_status_unavailable(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """A school-scope explanation approved for another school must never leak to this school's
    students (CONSTITUTION Rule 3). Regression test for the cross-school visibility leak fixed
    in MCR-T1 — before the fix, this returned content_status="ready" with the other school's
    explanation text."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            content_type="explanation",
            explanation_text="Other school's explanation — must not leak",
            review_status="approved",
            scope="school",
            school_id=other_school.id,
            is_active=True,
        )
    )
    await db_session.commit()

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content_status"] == "unavailable"
    assert data["explanation"] is None


@pytest.mark.asyncio
async def test_get_course_when_own_school_has_approved_content_then_content_status_ready(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A school-scope explanation approved for THIS school is served normally — the fix in
    MCR-T1 only excludes other schools, it must not exclude the caller's own school."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            content_type="explanation",
            explanation_text="Own school's explanation",
            review_status="approved",
            scope="school",
            school_id=school.id,
            is_active=True,
        )
    )
    await db_session.commit()

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content_status"] == "ready"
    assert data["explanation"]["explanation_text"] == "Own school's explanation"


@pytest.mark.asyncio
async def test_get_course_route_when_teacher_role_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET course endpoint returns 403 for non-student roles."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST/GET /api/v1/students/me/subtopics/{subtopic_id}/chat (AI Tutor)
# ---------------------------------------------------------------------------


def _fake_llm_stream(deltas: list[str]) -> AsyncGenerator[MagicMock, None]:
    """Async generator mimicking litellm's streaming chunk shape (see test_llm_router.py)."""

    async def _chunks() -> AsyncGenerator[MagicMock, None]:
        for delta in deltas:
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=delta))]
            yield chunk
        final = MagicMock()
        final.choices = []
        final.usage = MagicMock(prompt_tokens=42, completion_tokens=7, total_tokens=49)
        yield final

    return _chunks()


async def _create_chat_student(db_session: AsyncSession, school: School) -> User:
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    return student


@pytest.mark.asyncio
async def test_post_chat_route_when_stream_completes_then_persists_both_messages(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """The full SSE round trip must persist both the student's question and the AI's
    reply. Regression test for the closed-DB-session bug: the request-scoped `db`
    dependency is torn down as soon as the route function returns, but the streaming
    generator (and the AI-reply save inside it) only runs afterward, when Starlette
    drains the response body — so the AI's reply was silently never written."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    with (
        patch(
            "litellm.acompletion",
            new_callable=AsyncMock,
            return_value=_fake_llm_stream(["A variable ", "stores a value."]),
        ),
        patch("app.ai.providers.router.TASK_MODEL_MAP", {"explain_this": "test/model-a"}),
    ):
        response = await client.post(
            f"/api/v1/students/me/subtopics/{subtopic.id}/chat",
            headers=make_auth_header(student),
            json={"question": "What is a variable?"},
        )

    assert response.status_code == 200
    assert '"type": "done"' in response.text

    result = await db_session.execute(
        select(MiniCourseChatMessage)
        .where(MiniCourseChatMessage.student_id == student.id)
        .order_by(MiniCourseChatMessage.created_at.asc())
    )
    messages = result.scalars().all()

    assert len(messages) == 2
    assert messages[0].role == "student"
    assert messages[0].content == "What is a variable?"
    assert messages[1].role == "ai"
    assert messages[1].content == "A variable stores a value."


@pytest.mark.asyncio
async def test_post_chat_route_when_stream_completes_then_llm_usage_event_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Every AI Tutor turn must show up in llm_usage_events (the LLM Logs / cost admin
    pages), attributed to the student's school and the "api:students" component —
    not silently dropped and not NULL-attributed. Regression test for the same
    closed-session-timing bug affecting the request-scoped contextvars that
    `record_usage` reads for attribution."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    with (
        patch(
            "litellm.acompletion",
            new_callable=AsyncMock,
            return_value=_fake_llm_stream(["Hello there."]),
        ),
        patch("app.ai.providers.router.TASK_MODEL_MAP", {"explain_this": "test/model-a"}),
        patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
    ):
        response = await client.post(
            f"/api/v1/students/me/subtopics/{subtopic.id}/chat",
            headers=make_auth_header(student),
            json={"question": "Explain please"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(LlmUsageEvent).where(LlmUsageEvent.task == "explain_this").order_by(LlmUsageEvent.created_at.desc())
    )
    event = result.scalars().first()

    assert event is not None
    assert event.succeeded is True
    assert event.streamed is True
    assert event.school_id == school.id
    assert event.component == "api:students"


@pytest.mark.asyncio
async def test_get_chat_history_when_more_than_50_messages_then_returns_most_recent_50(
    db_session: AsyncSession,
    school: School,
) -> None:
    """Once a conversation passes 50 turns, the cap must keep the live end of the
    conversation, not pin the thread to its first 50 messages forever. Regression
    test for get_chat_history's previous ORDER BY created_at ASC LIMIT 50, which
    returned the OLDEST 50 messages instead of the most recent 50."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(55):
        db_session.add(
            MiniCourseChatMessage(
                id=uuid.uuid4(),
                student_id=student.id,
                subtopic_id=subtopic.id,
                school_id=school.id,
                role="student" if i % 2 == 0 else "ai",
                content=f"message {i}",
                created_at=base + timedelta(seconds=i),
            )
        )
    await db_session.commit()

    history = await MiniCourseService(db_session).get_chat_history(
        student_id=student.id, subtopic_id=subtopic.id, school_id=school.id
    )

    assert len(history.messages) == 50
    # Messages 0-4 are the oldest and must be dropped; 5-54 (the most recent 50) kept,
    # still returned oldest-first.
    assert history.messages[0].content == "message 5"
    assert history.messages[-1].content == "message 54"


@pytest.mark.asyncio
async def test_get_chat_history_when_messages_share_identical_timestamp_then_order_is_stable(
    db_session: AsyncSession,
    school: School,
) -> None:
    """Reproduces a real dev-DB state: several messages saved within one DB transaction
    share Postgres's per-transaction `now()` value bit-for-bit, so ORDER BY created_at
    alone has no defined tie-break order and can return a different sequence on every
    call. Regression test: ordering must additionally break ties on `id` so the result
    is deterministic and repeated calls agree with each other."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    tied_at = datetime(2026, 5, 30, 8, 34, 43, 989769, tzinfo=UTC)
    ids = sorted(uuid.uuid4() for _ in range(5))
    contents = ["Heill", "Can you help me with this?", "AI reply 1", "What do you mean?", "AI reply 2"]
    for msg_id, content in zip(ids, contents, strict=True):
        db_session.add(
            MiniCourseChatMessage(
                id=msg_id,
                student_id=student.id,
                subtopic_id=subtopic.id,
                school_id=school.id,
                role="student",
                content=content,
                created_at=tied_at,
            )
        )
    await db_session.commit()

    service = MiniCourseService(db_session)
    first = await service.get_chat_history(student_id=student.id, subtopic_id=subtopic.id, school_id=school.id)
    second = await service.get_chat_history(student_id=student.id, subtopic_id=subtopic.id, school_id=school.id)

    assert len(first.messages) == 5
    # Order matches ascending id (the tie-break key), and is identical across repeated
    # calls — the property that was missing before the (created_at, id) ordering fix.
    assert [m.content for m in first.messages] == contents
    assert [m.content for m in second.messages] == [m.content for m in first.messages]


@pytest.mark.asyncio
async def test_save_chat_message_when_called_then_created_at_reflects_real_time(
    db_session: AsyncSession,
    school: School,
) -> None:
    """save_chat_message must record the actual insert time, not a fixed value.

    Regression test for a schema-level bug found in the dev database: the live
    mini_course_chat_messages.created_at column default had been manually overridden
    to a frozen literal timestamp (fixed in migration 49eb7ee197b3), so every message
    that relied on the server default recorded the same identical past timestamp no
    matter when it was actually saved. Asserted against the DB server's own clock
    (not the test process's) since the two can drift a few seconds apart on a
    long-running local Docker VM — that drift is not the bug under test, and comparing
    against the test process's wall clock made this test flaky for the wrong reason.
    A frozen/stale default fails this in a way ordinary clock drift cannot: the row's
    created_at would be off by months, not seconds, and two sequential saves would tie
    instead of strictly increasing.
    """
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)
    service = MiniCourseService(db_session)

    db_now = (await db_session.execute(select(func.now()))).scalar_one()

    first = await service.save_chat_message(
        student_id=student.id, subtopic_id=subtopic.id, school_id=school.id, role="student", content="first"
    )
    second = await service.save_chat_message(
        student_id=student.id, subtopic_id=subtopic.id, school_id=school.id, role="ai", content="second"
    )

    # Within a minute of the DB's own clock, not months in the past like the frozen default.
    assert abs((first.created_at - db_now).total_seconds()) < 60
    # Two sequential saves must not tie — a frozen default would make first == second.
    assert second.created_at >= first.created_at


# ---------------------------------------------------------------------------
# Tests: POST /transfer-question and /grade-answer (Challenge Question) — LLM usage logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_transfer_question_route_when_llm_succeeds_then_llm_usage_event_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Challenge Question generation is a plain (non-streaming) LLM call through
    router.complete(), so it must show up in llm_usage_events the same as chat —
    attributed to the student's school and the "api:students" component."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="A generated challenge question about linear equations?"))]
    response.usage = MagicMock(prompt_tokens=50, completion_tokens=20, total_tokens=70)

    with (
        patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
        patch("app.ai.providers.router.TASK_MODEL_MAP", {"transfer_question": "test/model-a"}),
        patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
    ):
        api_response = await client.post(
            f"/api/v1/students/me/subtopics/{subtopic.id}/transfer-question",
            headers=make_auth_header(student),
        )

    assert api_response.status_code == 200
    assert api_response.json()["question_text"] == "A generated challenge question about linear equations?"

    result = await db_session.execute(
        select(LlmUsageEvent).where(LlmUsageEvent.task == "transfer_question").order_by(LlmUsageEvent.created_at.desc())
    )
    event = result.scalars().first()

    assert event is not None
    assert event.succeeded is True
    assert event.school_id == school.id
    assert event.component == "api:students"


@pytest.mark.asyncio
async def test_post_grade_answer_route_when_llm_succeeds_then_llm_usage_event_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Grading a Challenge Question answer is also a plain router.complete() call and
    must be logged the same way — this is the second half of the same feature the chat
    fix covers, and shares the same "log every LLM call" requirement."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)
    student = await _create_chat_student(db_session, school)

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content='{"grade": "correct", "feedback": "Nicely explained."}'))]
    response.usage = MagicMock(prompt_tokens=80, completion_tokens=15, total_tokens=95)

    with (
        patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
        patch("app.ai.providers.router.TASK_MODEL_MAP", {"grade_open_answer": "test/model-a"}),
        patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
    ):
        api_response = await client.post(
            f"/api/v1/students/me/subtopics/{subtopic.id}/grade-answer",
            headers=make_auth_header(student),
            json={"question_text": "Explain linear equations", "student_answer": "y = mx + b"},
        )

    assert api_response.status_code == 200
    assert api_response.json()["grade"] == "correct"

    result = await db_session.execute(
        select(LlmUsageEvent).where(LlmUsageEvent.task == "grade_open_answer").order_by(LlmUsageEvent.created_at.desc())
    )
    event = result.scalars().first()

    assert event is not None
    assert event.succeeded is True
    assert event.school_id == school.id
    assert event.component == "api:students"
