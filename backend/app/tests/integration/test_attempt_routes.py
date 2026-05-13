"""Integration tests for attempt routes — M1-4-T1 real implementation.

These tests exercise the real AttemptService against a real test database.
Each test creates the necessary DB rows from scratch via the db_session fixture.

Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from unittest.mock import MagicMock, patch

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
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, ClassEnrollment, School
from app.models.user import User, UserRole


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Additional fixtures for attempt tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def curriculum(db_session: AsyncSession) -> Curriculum:
    c = Curriculum(
        id=uuid.uuid4(),
        name=f"Cambridge {uuid.uuid4().hex[:6]}",
        code=f"CAMB-{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest_asyncio.fixture
async def subject(db_session: AsyncSession) -> Subject:
    s = Subject(
        id=uuid.uuid4(),
        name=f"Math {uuid.uuid4().hex[:6]}",
        code=f"MATH{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def grade(db_session: AsyncSession) -> Grade:
    g = Grade(
        id=uuid.uuid4(),
        name="Grade 7",
        level=7,
        is_active=True,
    )
    db_session.add(g)
    await db_session.commit()
    return g


@pytest_asyncio.fixture
async def topic(db_session: AsyncSession) -> Topic:
    t = Topic(
        id=uuid.uuid4(),
        name=f"Topic {uuid.uuid4().hex[:6]}",
        canonical_code=f"TOP-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(t)
    await db_session.commit()
    return t


@pytest_asyncio.fixture
async def curriculum_topic(
    db_session: AsyncSession,
    curriculum: Curriculum,
    subject: Subject,
    grade: Grade,
    topic: Topic,
) -> CurriculumTopic:
    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=True,
        sequence_order=1,
    )
    db_session.add(ct)
    await db_session.commit()
    return ct


@pytest_asyncio.fixture
async def subtopic(
    db_session: AsyncSession,
    curriculum_topic: CurriculumTopic,
) -> Subtopic:
    st = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic.id,
        name="Test Subtopic",
        learning_objective="Learn testing",
        is_active=True,
    )
    db_session.add(st)
    await db_session.commit()
    return st


@pytest_asyncio.fixture
async def question(db_session: AsyncSession, subtopic: Subtopic) -> QuestionBank:
    q = QuestionBank(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        question_text="What is 1+1?",
        question_type="MCQ",
        options=[{"key": "A", "text": "2"}, {"key": "B", "text": "3"}],
        correct_answer="A",
        canonical_form="What is 1+1?",
        problem_signature={},
        source="bank",
        is_active=True,
    )
    db_session.add(q)
    await db_session.commit()
    return q


@pytest_asyncio.fixture
async def test_school_obj(db_session: AsyncSession) -> School:
    s = School(
        id=uuid.uuid4(),
        name="Attempt Test School",
        slug=f"attempt-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def teacher_user(db_session: AsyncSession, test_school_obj: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession, test_school_obj: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def class_obj(
    db_session: AsyncSession,
    test_school_obj: School,
    grade: Grade,
    subject: Subject,
    curriculum: Curriculum,
    teacher_user: User,
) -> Class:
    c = Class(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher_user.id,
        name="Test Class 7A",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest_asyncio.fixture
async def active_assessment(
    db_session: AsyncSession,
    class_obj: Class,
    test_school_obj: School,
    teacher_user: User,
) -> Assessment:
    a = Assessment(
        id=uuid.uuid4(),
        school_id=test_school_obj.id,
        class_id=class_obj.id,
        created_by=teacher_user.id,
        title="Test Active Assessment",
        assessment_type="DIAGNOSTIC",
        status=AssessmentStatus.ACTIVE,
    )
    db_session.add(a)
    await db_session.commit()
    return a


@pytest_asyncio.fixture
async def active_assessment_with_question(
    db_session: AsyncSession,
    active_assessment: Assessment,
    question: QuestionBank,
) -> Assessment:
    bridge = AssessmentSelectedQuestion(
        assessment_id=active_assessment.id,
        question_id=question.id,
        order_index=0,
    )
    db_session.add(bridge)
    await db_session.commit()
    return active_assessment


@pytest_asyncio.fixture
async def enrollment(
    db_session: AsyncSession,
    class_obj: Class,
    student_user: User,
) -> ClassEnrollment:
    e = ClassEnrollment(
        class_id=class_obj.id,
        student_id=student_user.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db_session.add(e)
    await db_session.commit()
    return e


@pytest_asyncio.fixture
async def student_attempt(
    db_session: AsyncSession,
    active_assessment: Assessment,
    student_user: User,
) -> StudentAttempt:
    a = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=active_assessment.id,
        student_id=student_user.id,
        status=AttemptStatus.NOT_STARTED,
    )
    db_session.add(a)
    await db_session.commit()
    return a


@pytest_asyncio.fixture
async def student_attempt_with_question(
    db_session: AsyncSession,
    active_assessment_with_question: Assessment,
    student_user: User,
) -> StudentAttempt:
    a = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=active_assessment_with_question.id,
        student_id=student_user.id,
        status=AttemptStatus.NOT_STARTED,
    )
    db_session.add(a)
    await db_session.commit()
    return a


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetClassDiagnosticReal:
    """GET /api/v1/classes/{class_id}/diagnostic — real DB implementation."""

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_enrolled_student_then_200_with_questions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        student_user: User,
        class_obj: Class,
        active_assessment_with_question: Assessment,
        student_attempt_with_question: StudentAttempt,
        enrollment: ClassEnrollment,
    ) -> None:
        """Enrolled student with existing attempt + question → 200 with question list."""
        response = await client.get(
            f"/api/v1/classes/{class_obj.id}/diagnostic",
            headers=_auth(student_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == str(student_user.id)
        assert data["assessment_id"] == str(active_assessment_with_question.id)
        assert data["status"] == AttemptStatus.NOT_STARTED
        assert len(data["questions"]) == 1
        # correct_answer must NOT be exposed to students
        q = data["questions"][0]
        assert "correct_answer" not in q or q.get("correct_answer") is None

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_no_active_assessment_then_404(
        self,
        client: AsyncClient,
        student_user: User,
    ) -> None:
        """No active system-generated assessment for class → 404."""
        response = await client.get(
            f"/api/v1/classes/{uuid.uuid4()}/diagnostic",
            headers=_auth(student_user),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_attempt_not_created_then_404(
        self,
        client: AsyncClient,
        student_user: User,
        class_obj: Class,
        active_assessment: Assessment,
        enrollment: ClassEnrollment,
        # NOTE: no student_attempt fixture — attempt row is absent
    ) -> None:
        """Assessment exists but student attempt not yet created → 404."""
        response = await client.get(
            f"/api/v1/classes/{class_obj.id}/diagnostic",
            headers=_auth(student_user),
        )

        assert response.status_code == 404


class TestSubmitResponseReal:
    """POST /api/v1/attempts/{attempt_id}/responses — real DB."""

    @pytest.mark.asyncio
    async def test_submit_response_when_valid_then_204(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        student_user: User,
        student_attempt_with_question: StudentAttempt,
        active_assessment_with_question: Assessment,
        question: QuestionBank,
    ) -> None:
        """Valid answer for a question in the assessment → 204."""
        body = {
            "question_id": str(question.id),
            "selected_key": "A",
        }

        response = await client.post(
            f"/api/v1/attempts/{student_attempt_with_question.id}/responses",
            headers=_auth(student_user),
            json=body,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_submit_response_when_duplicate_then_409(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        student_user: User,
        student_attempt_with_question: StudentAttempt,
        active_assessment_with_question: Assessment,
        question: QuestionBank,
    ) -> None:
        """Same question submitted twice → 409 on second attempt."""
        body = {
            "question_id": str(question.id),
            "selected_key": "A",
        }
        # First submission
        r1 = await client.post(
            f"/api/v1/attempts/{student_attempt_with_question.id}/responses",
            headers=_auth(student_user),
            json=body,
        )
        assert r1.status_code == 204

        # Second submission — same question
        r2 = await client.post(
            f"/api/v1/attempts/{student_attempt_with_question.id}/responses",
            headers=_auth(student_user),
            json=body,
        )
        assert r2.status_code == 409


class TestSubmitAttemptReal:
    """POST /api/v1/attempts/{attempt_id}/submit — real DB."""

    @pytest.mark.asyncio
    async def test_submit_attempt_when_valid_then_200_with_score(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        student_user: User,
        student_attempt_with_question: StudentAttempt,
        active_assessment_with_question: Assessment,
        question: QuestionBank,
    ) -> None:
        """Submit all answers → 200 with score in response."""
        body = {"answers": [{"question_id": str(question.id), "selected_key": "A"}]}

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            response = await client.post(
                f"/api/v1/attempts/{student_attempt_with_question.id}/submit",
                headers=_auth(student_user),
                json=body,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["attempt_id"] == str(student_attempt_with_question.id)
        assert data["score"] == 1.0
        assert data["correct_count"] == 1
        assert data["total_questions"] == 1
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_attempt_when_already_completed_then_409(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        student_user: User,
        student_attempt_with_question: StudentAttempt,
        active_assessment_with_question: Assessment,
        question: QuestionBank,
    ) -> None:
        """Submitting an already-completed attempt → 409."""
        body = {"answers": [{"question_id": str(question.id), "selected_key": "A"}]}

        # First submit
        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            r1 = await client.post(
                f"/api/v1/attempts/{student_attempt_with_question.id}/submit",
                headers=_auth(student_user),
                json=body,
            )
        assert r1.status_code == 200

        # Second submit — should fail
        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            r2 = await client.post(
                f"/api/v1/attempts/{student_attempt_with_question.id}/submit",
                headers=_auth(student_user),
                json=body,
            )
        assert r2.status_code == 409
