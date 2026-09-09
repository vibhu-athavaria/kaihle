"""Integration tests for /api/v1/topics routes.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_topics_routes.py -v
"""

import random
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, CurriculumTopic, Grade, Subject, Subtopic, Topic
from app.models.interest_category import InterestCategory
from app.models.school import Class, School
from app.models.subtopic_content import SubtopicContent
from app.models.user import User, UserRole
from app.services.mini_course_generation_service import INTEREST_CATEGORIES


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(user_id=user.id, school_id=user.school_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def _create_topic_with_class(db: AsyncSession, school: School) -> tuple[Topic, Subtopic, Class, User]:
    """Create a minimal curriculum chain + a class + teacher owning that class."""
    subject = Subject(
        id=uuid.uuid4(), name=f"Math-{uuid.uuid4().hex[:4]}", code=f"M{uuid.uuid4().hex[:4]}", is_active=True
    )
    # level is unique AND constrained to 1-13 (grades_level_range) — a hardcoded value
    # collided once enough tests in this file ran back-to-back in the same session.
    # Get-or-create rather than always inserting: the level space is small enough that
    # collisions are expected, not just possible.
    grade_level = random.randint(1, 13)
    existing_grade = await db.execute(select(Grade).where(Grade.level == grade_level))
    grade = existing_grade.scalar_one_or_none()
    if grade is None:
        grade = Grade(id=uuid.uuid4(), name=f"Grade {grade_level}", level=grade_level, is_active=True)
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


async def _ensure_interest_categories(db: AsyncSession) -> None:
    """Create the 4 production interest categories if they don't already exist.

    interest_categories.name is a native Postgres enum column — the enum TYPE persists
    across the test suite's TRUNCATE-based isolation, but the table rows do not, so each
    test that needs them (like compute_gap_count's expected-total calculation) must
    re-seed them.
    """
    existing = await db.execute(select(InterestCategory.name))
    existing_names = {row[0] for row in existing.all()}
    for db_name, _, _ in INTEREST_CATEGORIES:
        if db_name not in existing_names:
            db.add(InterestCategory(id=uuid.uuid4(), name=db_name))
    await db.commit()


@pytest.mark.asyncio
async def test_get_course_status_when_partial_then_returns_partial_with_gaps_count(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """MCR-T3: a topic stuck at status="partial" reports how many items are still
    missing, computed live rather than trusted from the last generation run."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)
    await _ensure_interest_categories(db_session)

    topic.mini_course_status = "partial"
    # Only 1 of the 4 interest-category explanation variants exists for this subtopic —
    # 3 explanation gaps, plus 1 quiz gap (no quiz row at all).
    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            content_type="explanation",
            explanation_text="Sports-flavoured explanation",
            review_status="approved",
            scope="school",
            school_id=school.id,
            interest_category_id=(
                await db_session.execute(select(InterestCategory.id).where(InterestCategory.name == "sports_movement"))
            ).scalar_one(),
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/topics/{topic.id}/course-status",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["gaps_count"] == 4  # 3 missing explanation variants + 1 missing quiz


@pytest.mark.asyncio
async def test_get_course_status_when_ready_then_gaps_count_is_zero(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A "ready" topic never pays the cost of computing gaps — gaps_count stays 0
    without a live query, since there's nothing to report."""
    topic, _subtopic, _class, teacher = await _create_topic_with_class(db_session, school)
    topic.mini_course_status = "ready"
    await db_session.commit()

    response = await client.get(
        f"/api/v1/topics/{topic.id}/course-status",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["gaps_count"] == 0


@pytest.mark.asyncio
async def test_get_course_status_when_no_video_curated_then_video_coverage_zero_of_total(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """MCR-T4: video coverage is reported even for a topic with no video curated at
    all — the signal must be present, never silently omitted."""
    topic, _subtopic, _class, teacher = await _create_topic_with_class(db_session, school)
    topic.mini_course_status = "ready"
    await db_session.commit()

    response = await client.get(
        f"/api/v1/topics/{topic.id}/course-status",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["video_coverage"] == {"covered": 0, "total": 1}


@pytest.mark.asyncio
async def test_get_course_status_when_video_approved_then_covered_equals_total(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """An approved curriculum-scope video counts as covered; the video wasn't generated
    by this teacher's own school, but coverage is a global fact, not school-scoped."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)
    topic.mini_course_status = "ready"
    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            content_type="video",
            video_url="https://youtube.com/watch?v=abc123",
            review_status="approved",
            scope="curriculum",
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/topics/{topic.id}/course-status",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["video_coverage"] == {"covered": 1, "total": 1}


@pytest.mark.asyncio
async def test_get_course_status_when_video_pending_not_approved_then_not_counted_as_covered(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A pending (not yet KaihleAdmin-approved) video candidate must not count as
    coverage — only an approved video is a real, student-visible video."""
    topic, subtopic, _class, teacher = await _create_topic_with_class(db_session, school)
    topic.mini_course_status = "ready"
    db_session.add(
        SubtopicContent(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            content_type="video",
            video_url="https://youtube.com/watch?v=abc123",
            review_status="pending",
            scope="curriculum",
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/topics/{topic.id}/course-status",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["video_coverage"] == {"covered": 0, "total": 1}
