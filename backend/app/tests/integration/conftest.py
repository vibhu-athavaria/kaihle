"""Shared fixtures for all integration tests.

All integration tests in this directory can use these fixtures
without importing them — pytest discovers conftest.py automatically.
"""

import os
import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment variables BEFORE importing app modules
# This is critical because app.core.database creates engine at import time
# ruff: noqa: E402
DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle_test"

# This suite creates, truncates and drops data. It must NEVER resolve to a working
# database. It previously fell back to DATABASE_URL, so running pytest in any shell
# that had sourced .env silently wiped the dev database — a single-step accident with
# no warning. The fallback is gone; only TEST_DATABASE_URL can override the default.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)

_test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if not _test_db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run integration tests against database {_test_db_name!r}: "
        "the name must end in '_test'. Set TEST_DATABASE_URL to a dedicated test "
        f"database (default: {DEFAULT_TEST_DATABASE_URL})."
    )

# Force, not setdefault: app.core.database builds its engine from DATABASE_URL at
# import time, so an inherited value would point the app at the real database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

import random
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base
from app.models.assessment import Assessment
from app.models.curriculum import (
    Curriculum,
    Grade,
    Subject,
    Topic,
)
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, School, SchoolCurriculum
from app.models.user import (
    StudentProfile,
    User,
    UserRole,
)

# bcrypt is deliberately slow — ~310ms a call at the configured cost factor — and every
# user fixture hashed the same literal, which made it the single largest cost in the
# suite. Hashing once keeps the value a genuine bcrypt digest (verify_password still
# exercises the real algorithm) while paying for it once instead of hundreds of times.
TEST_PASSWORD = "correct-password"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(autouse=True)
def _mock_app_redis() -> Generator[None, None, None]:
    """Set a mock Redis on app.state for all integration tests.

    FastAPI lifespan does not run under ASGITransport, so app.state.redis is
    never set by startup. Any route that touches request.app.state.redis needs
    this fixture or it raises AttributeError.
    """
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    app.state.redis = mock_redis
    yield
    if hasattr(app.state, "redis"):
        del app.state._state["redis"]


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT for any user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    s = School(id=uuid.uuid4(), name="Test School", slug=f"test-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def other_school(db_session: AsyncSession) -> School:
    s = School(id=uuid.uuid4(), name="Other School", slug=f"other-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def school_admin(db_session: AsyncSession, school: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"sadmin-{uuid.uuid4().hex[:8]}@test.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, school: School) -> User:
    """Create a test user with password (TEACHER role)."""
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=TEST_PASSWORD_HASH,
        first_name="Test",
        last_name="User",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def student(db_session: AsyncSession, school: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def student_with_password(db_session: AsyncSession, school: School) -> User:
    u = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-pw-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=TEST_PASSWORD_HASH,
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": False},
    )
    yield engine
    await engine.dispose()


# One SELECT per table, unioned, naming only the tables that hold at least one row.
# Built once per session from the live catalogue — which covers tables created outside
# the model graph — and reused by every test. Each EXISTS on an empty table reads zero
# pages, making this ~23ms against ~360ms to truncate all 52 unconditionally.
_non_empty_probe_sql: str = ""


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _schema() -> AsyncGenerator[None, None]:
    """Build the schema once for the whole session.

    This used to run per test — 52 tables and every index rebuilt 617 times, about
    1.3s of pure DDL per test. Tests need a clean *dataset*, not a freshly created
    *schema*, and TRUNCATE gives the first at a fraction of the cost.

    Owns a short-lived engine of its own rather than sharing the function-scoped one:
    asyncpg connections are bound to the event loop that opened them, and this fixture
    runs on the session loop.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool, connect_args={"ssl": False})
    async with engine.begin() as conn:
        # CASCADE because some tables live outside the Python model graph
        # (e.g. student_attempt_subtopic_scores from M1-4-T3) and drop_all misses them.
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # pgvector lived in public and went with it.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        rows = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        global _non_empty_probe_sql  # noqa: PLW0603
        _non_empty_probe_sql = " UNION ALL ".join(
            f"SELECT '{name}' AS tbl WHERE EXISTS (SELECT 1 FROM public.\"{name}\")"
            for name in sorted(r[0] for r in rows.fetchall())
        )
    await engine.dispose()
    yield


@pytest_asyncio.fixture(scope="function")
async def db_session(engine: AsyncEngine, _schema: None) -> AsyncGenerator[AsyncSession, None]:
    """A session against an empty database, isolated from every other test.

    Isolation is by TRUNCATE rather than by an outer transaction that rolls back:
    services in this codebase call db.commit() directly, which would end such a
    transaction and silently leak state into the next test.

    Table names come from the live catalogue, not Base.metadata, so anything created
    outside the model graph is still cleared. RESTART IDENTITY resets sequences, so
    tests asserting on generated ids stay deterministic regardless of run order.
    """
    async with engine.begin() as conn:
        # Truncating all 52 tables unconditionally costs ~360ms because TRUNCATE
        # rewrites each table's file even when it is already empty. Asking which
        # tables actually hold rows costs ~23ms, and a typical test dirties only a
        # handful — so detect first, then truncate just those.
        rows = await conn.execute(text(_non_empty_probe_sql))
        dirty = [r[0] for r in rows.fetchall()]
        if dirty:
            quoted = ", ".join(f'public."{name}"' for name in dirty)
            await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))  # noqa: S608

    async_session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing API endpoints."""

    # Override database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    from app.core.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_school(db_session: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_school: School) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.STUDENT,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_student_profile(db_session: AsyncSession, test_user: User) -> StudentProfile:
    """Create a test student profile.

    Note: onboarding_diagnostic_status moved to class_enrollments in v2.1.
    """
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=test_user.id,
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def test_learning_profile(
    db_session: AsyncSession, test_user: User, test_school: School
) -> StudentLearningProfile:
    """Create a test learning profile."""
    profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=test_user.id,
        school_id=test_school.id,
        modality_scores={"visual": 0.8},
        work_style={"prefers_solo": True},
        questionnaire_version="v1",
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def test_curriculum(db_session: AsyncSession) -> Curriculum:
    """Create a test curriculum."""
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Test Curriculum {uuid.uuid4().hex[:8]}",
        code=f"TEST-{uuid.uuid4().hex[:6]}",
        description="Test curriculum description",
        is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()
    return curriculum


@pytest_asyncio.fixture
async def test_subject(db_session: AsyncSession) -> Subject:
    """Create a test subject."""
    subject = Subject(
        id=uuid.uuid4(),
        name="Test Subject",
        code=f"TS{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(subject)
    await db_session.commit()
    return subject


@pytest_asyncio.fixture
async def test_grade(db_session: AsyncSession) -> Grade:
    """Create a test grade."""
    # Use unique level to avoid constraint violations
    grade = Grade(
        id=uuid.uuid4(),
        name="Grade 7",
        level=random.randint(1, 13),
        is_active=True,
    )
    db_session.add(grade)
    await db_session.commit()
    return grade


@pytest_asyncio.fixture
async def test_topic(db_session: AsyncSession) -> Topic:
    """Create a test topic."""
    topic = Topic(
        id=uuid.uuid4(),
        name="Test Topic",
        canonical_code=f"TEST-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(topic)
    await db_session.commit()
    return topic


@pytest_asyncio.fixture
async def test_teacher(db_session: AsyncSession, test_school: School) -> User:
    """Create a test teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest_asyncio.fixture
async def test_class(
    db_session: AsyncSession,
    test_school: School,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
    test_teacher: User,
) -> Class:
    """Create a test class."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=test_teacher.id,
        name="Test Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


@pytest_asyncio.fixture
async def test_assessment(
    db_session: AsyncSession, test_class: Class, test_teacher: User, test_school: School
) -> Assessment:
    """Create a test assessment."""
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=test_school.id,
        class_id=test_class.id,
        created_by=test_teacher.id,
        title="Test Assessment",
        assessment_type="DIAGNOSTIC",
        status="DRAFT",
    )
    db_session.add(assessment)
    await db_session.commit()
    return assessment


@pytest_asyncio.fixture
async def school_curriculum(
    db_session: AsyncSession, test_school: School, test_curriculum: Curriculum
) -> SchoolCurriculum:
    """Create a school-curriculum subscription."""
    from app.models.school import SchoolCurriculum

    sub = SchoolCurriculum(
        school_id=test_school.id,
        curriculum_id=test_curriculum.id,
    )
    db_session.add(sub)
    await db_session.commit()
    return sub
