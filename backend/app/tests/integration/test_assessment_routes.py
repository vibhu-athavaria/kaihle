"""Integration tests for Assessment API routes (M1-3-T2).

Tests verify real service calls through HTTP endpoints using a live test DB.
Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_assessment_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.assessment import Assessment, AssessmentSelectedQuestion, AssessmentStatus
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


async def _create_full_curriculum_setup(
    db: AsyncSession,
    school: School,
) -> tuple[Subject, Grade, Curriculum, CurriculumTopic, Subtopic, User, Class]:
    """Create a minimal curriculum + class for route tests."""
    subject = Subject(
        id=uuid.uuid4(), name=f"Math-{uuid.uuid4().hex[:4]}", code=f"M{uuid.uuid4().hex[:4]}", is_active=True
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 8", level=8, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(), name=f"Curr-{uuid.uuid4().hex[:4]}", code=f"C{uuid.uuid4().hex[:4]}", is_active=True
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
        academic_year="2026",
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


async def _create_draft_assessment(
    db: AsyncSession,
    school: School,
    class_: Class,
    teacher: User,
    subtopic: Subtopic,
    question_count: int = 3,
) -> Assessment:
    """Helper to create a draft assessment with bridge rows for transition tests."""
    questions = await _add_questions(db, subtopic, question_count)
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title="Test Assessment",
        assessment_type="PROGRESS_CHECK",
        status=AssessmentStatus.DRAFT,
        is_system_generated=False,
        question_count=question_count,
        config={},
    )
    db.add(assessment)
    await db.flush()

    bridge_rows = [
        AssessmentSelectedQuestion(assessment_id=assessment.id, question_id=q.id, order_index=i)
        for i, q in enumerate(questions)
    ]
    db.add_all(bridge_rows)
    await db.flush()
    return assessment


# ---------------------------------------------------------------------------
# list_class_assessments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_class_assessments_when_teacher_own_class_then_returns_200_with_page(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher listing assessments for their own class gets a 200 paginated response."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    assessment = await _create_draft_assessment(db_session, school, class_, teacher, st)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/classes/{class_.id}/assessments",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == str(assessment.id)
    assert data["data"][0]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_list_class_assessments_when_teacher_other_class_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher trying to list assessments for a class they don't own gets 403."""
    _, _, _, ct, st, _, class_ = await _create_full_curriculum_setup(db_session, school)

    # A different teacher
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/classes/{class_.id}/assessments",
        headers=make_auth_header(other_teacher),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_class_assessments_when_student_then_draft_excluded(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    student: User,
) -> None:
    """Students do not see DRAFT assessments in the list."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)

    # Create one DRAFT (teacher-created) and one ACTIVE assessment
    draft = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title="Draft Assessment",
        assessment_type="PROGRESS_CHECK",
        status=AssessmentStatus.DRAFT,
        is_system_generated=False,
        question_count=5,
        config={},
    )
    active = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title="Active Assessment",
        assessment_type="PROGRESS_CHECK",
        status=AssessmentStatus.ACTIVE,
        is_system_generated=False,
        question_count=5,
        config={},
    )
    db_session.add_all([draft, active])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/classes/{class_.id}/assessments",
        headers=make_auth_header(student),
    )

    assert response.status_code == 200
    data = response.json()
    returned_ids = [item["id"] for item in data["data"]]
    assert str(active.id) in returned_ids
    assert str(draft.id) not in returned_ids


# ---------------------------------------------------------------------------
# create_assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_assessment_when_teacher_owns_class_then_201_draft(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher creating an assessment for their class gets 201 with DRAFT status."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    await _add_questions(db_session, st, 10)
    await db_session.commit()

    payload = {
        "title": "My Progress Check",
        "topic_ids": [],
        "question_count": 5,
        "assessment_type": "PROGRESS_CHECK",
        "difficulty_min": 1.0,
        "difficulty_max": 5.0,
    }

    response = await client.post(
        f"/api/v1/classes/{class_.id}/assessments",
        json=payload,
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "DRAFT"
    assert data["is_system_generated"] is False
    assert data["title"] == "My Progress Check"
    assert data["question_count"] == 5


@pytest.mark.asyncio
async def test_create_assessment_when_teacher_does_not_own_class_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Teacher creating an assessment for a class they don't own gets 403."""
    _, _, _, ct, st, _, class_ = await _create_full_curriculum_setup(db_session, school)

    other_teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"other2-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    payload = {
        "title": "Unauthorized Check",
        "topic_ids": [],
        "question_count": 5,
        "assessment_type": "PROGRESS_CHECK",
    }

    response = await client.post(
        f"/api/v1/classes/{class_.id}/assessments",
        json=payload,
        headers=make_auth_header(other_teacher),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_assessment_when_insufficient_questions_then_422(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Creating assessment when question bank is too small gets 422 with available count."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    await _add_questions(db_session, st, 2)  # only 2 questions
    await db_session.commit()

    payload = {
        "title": "Too Big Check",
        "topic_ids": [],
        "question_count": 10,  # request more than available
        "assessment_type": "PROGRESS_CHECK",
    }

    response = await client.post(
        f"/api/v1/classes/{class_.id}/assessments",
        json=payload,
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["available"] == 2
    assert detail["requested"] == 10


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_assessment_when_different_school_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """Teacher from a different school cannot access assessment (404 from school_id filter)."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)

    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title="School A Assessment",
        assessment_type="PROGRESS_CHECK",
        status=AssessmentStatus.DRAFT,
        is_system_generated=False,
        question_count=5,
        config={},
    )
    db_session.add(assessment)

    # Teacher from other school
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other3-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/assessments/{assessment.id}",
        headers=make_auth_header(other_teacher),
    )

    # school_id mismatch → service raises ValueError → 404
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# publish_assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_when_draft_then_status_active(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Publishing a DRAFT assessment transitions it to ACTIVE."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    assessment = await _create_draft_assessment(db_session, school, class_, teacher, st)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/assessments/{assessment.id}/publish",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert data["published_at"] is not None


@pytest.mark.asyncio
async def test_publish_when_already_active_then_409(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Publishing an already ACTIVE assessment returns 409."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    assessment = await _create_draft_assessment(db_session, school, class_, teacher, st)

    # Manually set to ACTIVE
    assessment.status = AssessmentStatus.ACTIVE
    await db_session.commit()

    response = await client.post(
        f"/api/v1/assessments/{assessment.id}/publish",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# close_assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_when_active_then_200_with_closed_status(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Closing an ACTIVE assessment returns 200 with CLOSED status."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    assessment = await _create_draft_assessment(db_session, school, class_, teacher, st)

    # Set to ACTIVE first
    assessment.status = AssessmentStatus.ACTIVE
    await db_session.commit()

    response = await client.post(
        f"/api/v1/assessments/{assessment.id}/close",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_close_when_draft_then_409(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Closing a DRAFT assessment returns 409."""
    _, _, _, ct, st, teacher, class_ = await _create_full_curriculum_setup(db_session, school)
    assessment = await _create_draft_assessment(db_session, school, class_, teacher, st)
    await db_session.commit()

    # assessment is DRAFT — trying to close it should fail
    response = await client.post(
        f"/api/v1/assessments/{assessment.id}/close",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 409
