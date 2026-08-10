"""Integration tests for adaptive question selection — GET /attempts/{id}/next-question.

Exercises the real AttemptService and adaptive_selector against a real test database.

Question -> topic resolution goes through the learning objective bridge, so these
fixtures wire subtopic_objectives + learning_objectives. Fixtures that only set
question_bank.subtopic_id will NOT be reachable by adaptive selection — that column
is NULL for every remapped question (see app/services/question_selection.py).

Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentStatus,
    AttemptStatus,
    StudentAttempt,
)
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User, UserRole

QUESTION_COUNT = 6
DIFFICULTIES = [1, 2, 3, 4, 5]


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, school_id=user.school_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def adaptive_scope(db_session: AsyncSession) -> dict[str, object]:
    """Build a two-topic curriculum scope with a full 1-5 difficulty ladder per topic.

    Returns a dict of the created rows keyed for readability in tests.
    """
    curriculum = Curriculum(id=uuid.uuid4(), name="Adaptive Test Curriculum", code=f"ADP-{uuid.uuid4().hex[:6]}")
    subject = Subject(id=uuid.uuid4(), name="Adaptive Math", code=f"AMTH-{uuid.uuid4().hex[:6]}")
    grade = Grade(id=uuid.uuid4(), name="Adaptive Grade 7", level=7)
    db_session.add_all([curriculum, subject, grade])
    await db_session.flush()

    topics: list[CurriculumTopic] = []
    questions_by_topic: dict[uuid.UUID, list[QuestionBank]] = {}

    for topic_index in range(2):
        topic = Topic(id=uuid.uuid4(), name=f"Adaptive Topic {topic_index}")
        db_session.add(topic)
        await db_session.flush()

        curriculum_topic = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
            is_active=True,
        )
        db_session.add(curriculum_topic)
        await db_session.flush()

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=curriculum_topic.id,
            name=f"Adaptive Subtopic {topic_index}",
            learning_objective="Adapt",
            is_active=True,
        )
        db_session.add(subtopic)
        await db_session.flush()

        objective = LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"ADP-{uuid.uuid4().hex[:10]}",
            name=f"Adaptive Objective {topic_index}",
            learning_objective="Adapt to difficulty",
            topic_id=topic.id,
        )
        db_session.add(objective)
        await db_session.flush()

        db_session.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))

        made: list[QuestionBank] = []
        for difficulty in DIFFICULTIES:
            question = QuestionBank(
                id=uuid.uuid4(),
                learning_objective_id=objective.id,
                question_text=f"T{topic_index} D{difficulty}: pick A",
                question_type="MCQ",
                options=[{"key": "A", "text": "right"}, {"key": "B", "text": "wrong"}],
                correct_answer="A",
                difficulty_level=difficulty,
                canonical_form=f"t{topic_index}d{difficulty}",
                problem_signature={},
                source="bank",
                is_active=True,
            )
            db_session.add(question)
            made.append(question)

        topics.append(curriculum_topic)
        questions_by_topic[curriculum_topic.id] = made

    await db_session.commit()
    return {
        "curriculum": curriculum,
        "subject": subject,
        "grade": grade,
        "topics": topics,
        "questions_by_topic": questions_by_topic,
    }


@pytest_asyncio.fixture
async def test_school_obj(db_session: AsyncSession) -> School:
    school = School(
        id=uuid.uuid4(),
        name="Adaptive Test School",
        slug=f"adaptive-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest_asyncio.fixture
async def teacher_user(db_session: AsyncSession, test_school_obj: School) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        email=f"adaptive-teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Adaptive",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession, test_school_obj: School) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        email=f"adaptive-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Adaptive",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def class_obj(
    db_session: AsyncSession,
    adaptive_scope: dict[str, object],
    test_school_obj: School,
    teacher_user: User,
) -> Class:
    curriculum: Curriculum = adaptive_scope["curriculum"]  # type: ignore[assignment]
    subject: Subject = adaptive_scope["subject"]  # type: ignore[assignment]
    grade: Grade = adaptive_scope["grade"]  # type: ignore[assignment]
    klass = Class(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher_user.id,
        name="Adaptive Class 7A",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(klass)
    await db_session.commit()
    return klass


@pytest_asyncio.fixture
async def adaptive_attempt(
    db_session: AsyncSession,
    adaptive_scope: dict[str, object],
    test_school_obj: School,
    teacher_user: User,
    student_user: User,
    class_obj: Class,
) -> dict[str, object]:
    """An ACTIVE diagnostic over the adaptive scope, with a NOT_STARTED attempt."""
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        class_id=class_obj.id,
        created_by=teacher_user.id,
        title="Adaptive Diagnostic",
        assessment_type="DIAGNOSTIC",
        status=AssessmentStatus.ACTIVE,
        question_count=QUESTION_COUNT,
        minimum_difficulty=1,
        maximum_difficulty=5,
    )
    db_session.add(assessment)
    await db_session.flush()

    questions_by_topic: dict[uuid.UUID, list[QuestionBank]] = adaptive_scope["questions_by_topic"]  # type: ignore[assignment]
    order_index = 0
    for questions in questions_by_topic.values():
        for question in questions:
            db_session.add(
                AssessmentSelectedQuestion(
                    assessment_id=assessment.id,
                    question_id=question.id,
                    order_index=order_index,
                )
            )
            order_index += 1

    attempt = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        student_id=student_user.id,
        status=AttemptStatus.NOT_STARTED,
    )
    db_session.add(attempt)
    await db_session.commit()
    return {"assessment": assessment, "attempt": attempt}


async def _next_question(client: AsyncClient, attempt_id: uuid.UUID, user: User) -> dict[str, Any]:
    response = await client.get(f"/api/v1/attempts/{attempt_id}/next-question", headers=_auth(user))
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _answer(
    client: AsyncClient,
    attempt_id: uuid.UUID,
    user: User,
    question_id: str,
    correct: bool,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/attempts/{attempt_id}/responses",
        headers=_auth(user),
        json={"question_id": question_id, "selected_key": "A" if correct else "B"},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


@pytest.mark.asyncio
async def test_next_question_when_first_call_then_returns_mid_difficulty_question(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]

    payload = await _next_question(client, attempt.id, student_user)

    assert payload["complete"] is False
    assert payload["answered_count"] == 0
    assert payload["question_count"] == QUESTION_COUNT
    question: dict[str, Any] = payload["question"]
    assert question["difficulty_level"] == 3


@pytest.mark.asyncio
async def test_next_question_when_served_then_includes_subtopic_name(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    # The student-facing badge shows which subtopic is being tested, so the name
    # must survive the objective-path join rather than falling back to "".
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]

    payload = await _next_question(client, attempt.id, student_user)
    question: dict[str, Any] = payload["question"]

    assert question["subtopic_name"].startswith("Adaptive Subtopic")


@pytest.mark.asyncio
async def test_next_question_when_called_twice_without_answering_then_returns_same_question(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]

    first = await _next_question(client, attempt.id, student_user)
    second = await _next_question(client, attempt.id, student_user)

    assert first["question"]["question_id"] == second["question"]["question_id"]


@pytest.mark.asyncio
async def test_next_question_when_answered_correctly_twice_then_difficulty_increases(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]
    seen: list[int] = []

    # Answer everything correctly. Two topics alternate, so each topic needs two
    # correct answers before its own ladder steps up.
    for _ in range(4):
        payload = await _next_question(client, attempt.id, student_user)
        question: dict[str, Any] = payload["question"]
        seen.append(int(question["difficulty_level"]))
        await _answer(client, attempt.id, student_user, str(question["question_id"]), correct=True)

    final = await _next_question(client, attempt.id, student_user)
    final_question: dict[str, Any] = final["question"]

    assert seen[:2] == [3, 3]  # both topics start mid-range
    assert int(final_question["difficulty_level"]) > 3


@pytest.mark.asyncio
async def test_next_question_when_answered_incorrectly_then_difficulty_decreases(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]

    first = await _next_question(client, attempt.id, student_user)
    first_question: dict[str, Any] = first["question"]
    await _answer(client, attempt.id, student_user, str(first_question["question_id"]), correct=False)

    # Second call serves the OTHER topic (least-answered), so answer that wrong too.
    second = await _next_question(client, attempt.id, student_user)
    second_question: dict[str, Any] = second["question"]
    await _answer(client, attempt.id, student_user, str(second_question["question_id"]), correct=False)

    third = await _next_question(client, attempt.id, student_user)
    third_question: dict[str, Any] = third["question"]

    assert int(third_question["difficulty_level"]) < 3


@pytest.mark.asyncio
async def test_next_question_when_question_count_reached_then_returns_complete(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]

    served: set[str] = set()
    for _ in range(QUESTION_COUNT):
        payload = await _next_question(client, attempt.id, student_user)
        question: dict[str, Any] = payload["question"]
        served.add(str(question["question_id"]))
        await _answer(client, attempt.id, student_user, str(question["question_id"]), correct=True)

    final = await _next_question(client, attempt.id, student_user)

    assert len(served) == QUESTION_COUNT  # never repeated a question
    assert final["complete"] is True
    assert final["question"] is None
    assert final["answered_count"] == QUESTION_COUNT


@pytest.mark.asyncio
async def test_submit_response_when_answer_correct_then_returns_scoring_payload(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]
    payload = await _next_question(client, attempt.id, student_user)
    question: dict[str, Any] = payload["question"]

    result = await _answer(client, attempt.id, student_user, str(question["question_id"]), correct=True)

    assert result["scored"] is True
    assert result["is_correct"] is True
    assert result["next_question_available"] is True


@pytest.mark.asyncio
async def test_submit_response_when_answer_wrong_then_reports_incorrect(
    client: AsyncClient,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]
    payload = await _next_question(client, attempt.id, student_user)
    question: dict[str, Any] = payload["question"]

    result = await _answer(client, attempt.id, student_user, str(question["question_id"]), correct=False)

    assert result["is_correct"] is False


@pytest.mark.asyncio
async def test_next_question_when_other_student_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    adaptive_attempt: dict[str, object],
    test_school_obj: School,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]
    intruder = User(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        email=f"intruder-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Nosy",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(intruder)
    await db_session.commit()

    response = await client.get(f"/api/v1/attempts/{attempt.id}/next-question", headers=_auth(intruder))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_next_question_when_attempt_missing_then_returns_404(
    client: AsyncClient,
    student_user: User,
) -> None:
    response = await client.get(f"/api/v1/attempts/{uuid.uuid4()}/next-question", headers=_auth(student_user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_next_question_when_attempt_completed_then_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    adaptive_attempt: dict[str, object],
    student_user: User,
) -> None:
    attempt: StudentAttempt = adaptive_attempt["attempt"]  # type: ignore[assignment]
    attempt.status = AttemptStatus.COMPLETED
    db_session.add(attempt)
    await db_session.commit()

    response = await client.get(f"/api/v1/attempts/{attempt.id}/next-question", headers=_auth(student_user))

    assert response.status_code == 409
