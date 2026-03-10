"""Pytest configuration and fixtures for integration tests."""

import os

# Set test environment variables BEFORE importing app modules
# This is critical because app.core.database creates engine at import time
# ruff: noqa: E402
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

import random
import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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
from app.models.school import Class, School
from app.models.user import (
    OnboardingStatus,
    StudentProfile,
    User,
    UserRole,
)


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

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
    """Create a test student profile."""
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=test_user.id,
        onboarding_diagnostic_status=OnboardingStatus.PENDING,
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
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


@pytest_asyncio.fixture
async def test_assessment(db_session: AsyncSession, test_class: Class, test_teacher: User) -> Assessment:
    """Create a test assessment."""
    assessment = Assessment(
        id=uuid.uuid4(),
        class_id=test_class.id,
        created_by=test_teacher.id,
        title="Test Assessment",
        assessment_type="DIAGNOSTIC",
        status="DRAFT",
        is_system_generated=False,
        config={"num_questions": 10},
    )
    db_session.add(assessment)
    await db_session.commit()
    return assessment
