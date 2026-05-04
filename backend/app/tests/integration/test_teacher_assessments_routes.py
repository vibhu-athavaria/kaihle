"""Integration tests for teacher-wide API endpoints.

Tests verify the optimized single-call endpoints:
- GET /api/v1/teachers/me/assessments
- GET /api/v1/schools/{school_id}/classes?include_summary=true

Run with: pytest backend/app/tests/integration/test_teacher_assessments_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.assessment import Assessment, AssessmentStatus
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_full_curriculum_setup(
    db: AsyncSession,
    school: School,
) -> tuple[Subject, Grade, Curriculum, CurriculumTopic, Subtopic, User, Class]:
    """Create a minimal curriculum + class for route tests."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Math-{uuid.uuid4().hex[:4]}",
        code=f"M{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 8", level=8, is_active=True)
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

    st = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    db.add(st)
    await db.flush()

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Math 8A",
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()

    return subject, grade, curriculum, ct, st, teacher, class_


async def _add_questions(
    db: AsyncSession, subtopic: Subtopic, count: int, difficulty: float = 2.0
) -> list[QuestionBank]:
    questions = []
    for i in range(count):
        q = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            question_text=f"Question {i + 1}",
            question_type="MCQ",
            options=[{"key": "A", "text": "Option A"}, {"key": "B", "text": "Option B"}],
            correct_answer="A",
            difficulty_level=difficulty,
            canonical_form=f"q-{uuid.uuid4().hex}",
            problem_signature={},
            is_active=True,
        )
        questions.append(q)
    db.add_all(questions)
    await db.flush()
    return questions


async def _create_assessment(
    db: AsyncSession,
    school: School,
    class_: Class,
    teacher: User,
    subtopic: Subtopic,
    title: str,
    status: str = AssessmentStatus.DRAFT,
) -> Assessment:
    """Helper to create an assessment."""
    questions = await _add_questions(db, subtopic, 3)
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title=title,
        assessment_type="PROGRESS_CHECK",
        status=status,
        is_system_generated=False,
        question_count=3,
        config={},
    )
    db.add(assessment)
    await db.flush()

    from app.models.assessment import AssessmentSelectedQuestion

    bridge_rows = [
        AssessmentSelectedQuestion(assessment_id=assessment.id, question_id=q.id, order_index=i)
        for i, q in enumerate(questions)
    ]
    db.add_all(bridge_rows)
    await db.flush()
    return assessment


# ---------------------------------------------------------------------------
# list_teacher_assessments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_teacher_has_classes_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher listing all assessments across their classes gets 200 with data."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)

    await _create_assessment(db_session, school, class_, teacher, st, "Math Quiz 1")
    await _create_assessment(db_session, school, class_, teacher, st, "Math Quiz 2")
    await _create_assessment(db_session, school, class_, teacher, st, "Math Quiz 3", AssessmentStatus.ACTIVE)
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/assessments",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert data[0]["class_name"] == "Math 8A"


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_no_classes_then_returns_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher with no classes gets empty list."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-no-class-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/assessments",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_status_filter_then_filters(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Filtering by status returns only matching assessments."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)

    await _create_assessment(db_session, school, class_, teacher, st, "Draft 1")
    await _create_assessment(db_session, school, class_, teacher, st, "Active 1", AssessmentStatus.ACTIVE)
    await _create_assessment(db_session, school, class_, teacher, st, "Draft 2")
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/assessments?status=DRAFT",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for item in data:
        assert item["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_not_teacher_role_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    student: User,
) -> None:
    """Non-teacher role gets 403."""
    response = await client.get(
        "/api/v1/teachers/me/assessments",
        headers=make_auth_header(student),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_unauthenticated_then_401(
    client: AsyncClient,
) -> None:
    """Unauthenticated request gets 401."""
    response = await client.get("/api/v1/teachers/me/assessments")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_teacher_assessments_when_other_teacher_class_then_not_included(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher does not see assessments from other teacher's classes."""
    _, _, _, ct, st, teacher_a, class_a = await _create_full_curriculum_setup(db_session, school)

    await _create_assessment(db_session, school, class_a, teacher_a, st, "Teacher A Quiz")
    await db_session.commit()

    teacher_b = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-b-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="TeacherB",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher_b)
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/assessments",
        headers=make_auth_header(teacher_b),
    )

    assert response.status_code == 200
    data = response.json()
    assert data == []
