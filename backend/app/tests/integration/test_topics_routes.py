"""Integration tests for /api/v1/topics routes.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_topics_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, CurriculumTopic, Grade, Subject, Subtopic, Topic
from app.models.school import Class, School
from app.models.subtopic_content import SubtopicContent
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(user_id=user.id, school_id=user.school_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def _create_topic_with_class(db: AsyncSession, school: School) -> tuple[Topic, Subtopic, Class, User]:
    """Create a minimal curriculum chain + a class + teacher owning that class."""
    subject = Subject(
        id=uuid.uuid4(), name=f"Math-{uuid.uuid4().hex[:4]}", code=f"M{uuid.uuid4().hex[:4]}", is_active=True
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7, is_active=True)
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
        sequence_order=1,
        is_active=True,
    )
    db.add(ct)
    await db.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        canonical_code="ALG-001",
        learning_objective="Solve linear equations",
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
    await db.commit()

    return topic, subtopic, class_, teacher


async def _reload(db: AsyncSession, content_id: uuid.UUID) -> SubtopicContent:
    """Re-select by id in a fresh query — the API call runs in a separate request-scoped
    session, so refreshing the original Python object doesn't see its commit."""
    result = await db.execute(select(SubtopicContent).where(SubtopicContent.id == content_id))
    row = result.scalar_one()
    return row


@pytest.mark.asyncio
async def test_review_topic_variant_when_content_belongs_to_other_school_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
) -> None:
    """A teacher must not be able to review — or, via the scope-claim side effect, HIJACK —
    another school's SubtopicContent row just by knowing its content_id. Before this fix,
    review_topic_variant fetched by content_id with no ownership check at all, and for a
    TEACHER caller unconditionally rewrote scope='school' + school_id=<caller's school>,
    letting any teacher reassign ownership of any row (including another school's) to
    themselves."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)

    other_school_content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        content_type="explanation",
        explanation_text="Other school's explanation",
        review_status="pending",
        scope="school",
        school_id=other_school.id,
        is_active=True,
    )
    db_session.add(other_school_content)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/topics/{topic.id}/variants/{other_school_content.id}/review",
        headers=make_auth_header(teacher),
        json={"review_status": "approved"},
    )

    assert response.status_code == 403

    reloaded = await _reload(db_session, other_school_content.id)
    assert reloaded.review_status == "pending"
    assert reloaded.scope == "school"
    assert reloaded.school_id == other_school.id


@pytest.mark.asyncio
async def test_review_topic_variant_when_own_school_content_then_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A teacher can still review their own school's row — the fix must not over-block."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)

    own_content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        content_type="explanation",
        explanation_text="Own school's explanation",
        review_status="pending",
        scope="school",
        school_id=school.id,
        is_active=True,
    )
    db_session.add(own_content)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/topics/{topic.id}/variants/{own_content.id}/review",
        headers=make_auth_header(teacher),
        json={"review_status": "approved"},
    )

    assert response.status_code == 200
    reloaded = await _reload(db_session, own_content.id)
    assert reloaded.review_status == "approved"


@pytest.mark.asyncio
async def test_review_topic_variant_when_curriculum_scope_then_teacher_claims_for_own_school(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Existing, intentional behavior preserved: a teacher approving a curriculum-scope row
    claims it for their own school (documented in review_topic_variant's inline comment)."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)

    curriculum_content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        content_type="explanation",
        explanation_text="Curriculum explanation",
        review_status="pending",
        scope="curriculum",
        school_id=None,
        is_active=True,
    )
    db_session.add(curriculum_content)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/topics/{topic.id}/variants/{curriculum_content.id}/review",
        headers=make_auth_header(teacher),
        json={"review_status": "approved"},
    )

    assert response.status_code == 200
    reloaded = await _reload(db_session, curriculum_content.id)
    assert reloaded.review_status == "approved"
    assert reloaded.scope == "school"
    assert reloaded.school_id == school.id
