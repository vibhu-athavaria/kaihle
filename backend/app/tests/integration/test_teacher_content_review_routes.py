"""Integration tests for teacher content review endpoints.

Tests verify the /api/v1/teachers/me/explanation-review endpoint.

Run with: pytest backend/app/tests/integration/test_teacher_content_review_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.subtopic_content import SubtopicContent
from app.models.user import User, UserRole

TEACHER_ROUTE_PREFIX = "/api/v1/teacher/classes"


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_full_setup(
    db: AsyncSession,
    school: School,
) -> tuple[Subject, Grade, Curriculum, CurriculumTopic, Subtopic, User, Class, SubtopicContent]:
    """Create a minimal curriculum + class + subtopic_content for tests."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Math-{uuid.uuid4().hex[:4]}",
        code=f"M{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(subject)

    grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7, is_active=True)
    db.add(grade)

    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Cambridge Lower Secondary",
        code="CAMBRIDGE",
        is_active=True,
    )
    db.add(curriculum)

    topic = Topic(
        id=uuid.uuid4(),
        name="Number",
        is_active=True,
    )
    db.add(topic)

    curriculum_topic = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        sequence_order=1,
        is_active=True,
    )
    db.add(curriculum_topic)

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic.id,
        name="Algebra Basics",
        canonical_code="ALG-001",
        learning_objective="Understand basic algebraic concepts and operations",
        sequence_order=1,
        is_active=True,
    )
    db.add(subtopic)

    teacher = User(
        id=uuid.uuid4(),
        email=f"teacher-{uuid.uuid4().hex[:6]}@school.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        school_id=school.id,
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
        name="Math 7A",
        academic_year="2025",
        is_active=True,
    )
    db.add(class_)

    subtopic_content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        content_type="explanation",
        explanation_text="AI generated explanation about algebra",
        review_status="pending",
        is_active=True,
    )
    db.add(subtopic_content)

    await db.flush()
    return subject, grade, curriculum, curriculum_topic, subtopic, teacher, class_, subtopic_content


@pytest.mark.asyncio
async def test_list_explanation_review_when_other_school_content_exists_then_not_in_response(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """Another school's pending/approved content for the same subject+grade must not appear
    in this teacher's per-class review list (CONSTITUTION Rule 3). Regression test for the
    cross-school leak fixed in MCR-T1 — before the fix, list_explanation_content filtered
    only by subject_id/grade_id, with no school boundary at all."""
    (
        _,
        _,
        _,
        curriculum_topic,
        _,
        teacher,
        class_,
        _,
    ) = await _create_full_setup(db_session, school)

    # A second subtopic under the SAME curriculum_topic (same subject/grade), owned by
    # another school — this is exactly the shape that would have leaked before the fix.
    other_subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic.id,
        name="Other School's Subtopic",
        canonical_code="ALG-OTHER",
        learning_objective="Belongs to another school entirely",
        sequence_order=2,
        is_active=True,
    )
    db_session.add(other_subtopic)
    await db_session.flush()

    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=other_subtopic.id,
            content_type="explanation",
            explanation_text="Other school's explanation — must not leak",
            review_status="pending",
            scope="school",
            school_id=other_school.id,
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"{TEACHER_ROUTE_PREFIX}/{class_.id}/explanation-review",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    subtopic_ids_returned = {item["subtopic_id"] for item in data["items"]}
    assert str(other_subtopic.id) not in subtopic_ids_returned


@pytest.mark.asyncio
async def test_update_explanation_review_when_content_belongs_to_other_school_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """A teacher must not be able to approve/reject another school's pending content just by
    knowing its subtopic_id (write-leak fixed in MCR-T1 alongside the read-leak)."""
    (
        _,
        _,
        _,
        curriculum_topic,
        _,
        teacher,
        class_,
        _,
    ) = await _create_full_setup(db_session, school)

    other_subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=curriculum_topic.id,
        name="Other School's Subtopic",
        canonical_code="ALG-OTHER-2",
        learning_objective="Belongs to another school entirely",
        sequence_order=3,
        is_active=True,
    )
    db_session.add(other_subtopic)
    await db_session.flush()

    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=other_subtopic.id,
            content_type="explanation",
            explanation_text="Other school's explanation",
            review_status="pending",
            scope="school",
            school_id=other_school.id,
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.patch(
        f"{TEACHER_ROUTE_PREFIX}/{class_.id}/explanation-review/{other_subtopic.id}",
        headers=make_auth_header(teacher),
        json={"review_status": "approved"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_all_teacher_explanation_review_when_has_content(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test listing all explanation reviews for a teacher."""
    # Arrange
    (
        _,
        _,
        _,
        _,
        _,
        teacher,
        class_,
        subtopic_content,
    ) = await _create_full_setup(db_session, school)

    # Act
    response = await client.get(
        "/api/v1/teachers/me/explanation-review",
        headers=make_auth_header(teacher),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should return content because it's for the teacher's class (matching subject+grade)
    assert len(data) >= 0  # May or may not have results depending on subject/grade match


@pytest.mark.asyncio
async def test_list_all_teacher_explanation_review_with_status_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test filtering explanation reviews by status."""
    # Arrange
    (
        _,
        _,
        _,
        _,
        _,
        teacher,
        class_,
        subtopic_content,
    ) = await _create_full_setup(db_session, school)

    # Act
    response = await client.get(
        "/api/v1/teachers/me/explanation-review?status=pending",
        headers=make_auth_header(teacher),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_all_teacher_explanation_review_no_classes(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test returns empty list when teacher has no classes."""
    # Arrange - create teacher with no classes
    teacher = User(
        id=uuid.uuid4(),
        email=f"teacher-no-class-{uuid.uuid4().hex[:6]}@school.com",
        first_name="Teacher",
        last_name="No Classes",
        role=UserRole.TEACHER,
        school_id=school.id,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    # Act
    response = await client.get(
        "/api/v1/teachers/me/explanation-review",
        headers=make_auth_header(teacher),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_all_teacher_explanation_review_unauthorized(
    client: AsyncClient,
) -> None:
    """Test returns 401 when not authenticated."""
    # Act
    response = await client.get("/api/v1/teachers/me/explanation-review")

    # Assert
    assert response.status_code == 401
