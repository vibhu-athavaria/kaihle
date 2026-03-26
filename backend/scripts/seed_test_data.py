"""Test data seeding script.

Creates schools, users, grades, classes, teacher assignments, and student enrollments for testing.
Run after seed_curriculum_graph.py has been executed.

Usage (from project root):
    docker compose exec backend python -m scripts.seed_test_data
    # Or outside Docker:
    cd backend && python -m scripts.seed_test_data

Idempotent: re-running produces same result (uses ON CONFLICT DO NOTHING).
"""

import asyncio
import datetime
import os
import sys
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap path so we can import app modules when run as a script
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()


def get_database_url() -> str:
    """Get database URL from settings or environment."""
    db_url = settings.database_url
    if not db_url:
        db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        # Default for local Docker
        db_url = "postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle"
    return db_url


async def seed_test_data() -> None:
    """Seed test data for development/testing."""
    db_url = get_database_url()
    log.info("connecting_to_database", url=db_url.replace("//", "//***:***@"))

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # -------------------------------------------------------------------
        # 1. Create school
        # -------------------------------------------------------------------
        result = await db.execute(text("SELECT id FROM schools LIMIT 1"))
        school_row = result.scalar_one_or_none()
        if not school_row:
            result = await db.execute(
                text("""
                    INSERT INTO schools (id, name, slug, address, city, country, timezone, contact_email, status)
                    VALUES (gen_random_uuid(), :name, :slug, :address, :city, :country, :timezone, :contact_email, 'active')
                    ON CONFLICT (slug) DO NOTHING
                    RETURNING id
                """),
                {
                    "name": "Kaihle Test School",
                    "slug": "kaihle-test-school",
                    "address": "123 Education Lane",
                    "city": "Singapore",
                    "country": "Singapore",
                    "timezone": "Asia/Singapore",
                    "contact_email": "admin@kaihle-test.com",
                },
            )
            school_id = result.scalar_one_or_none()
            if not school_id:
                # School already exists, get its ID
                result = await db.execute(text("SELECT id FROM schools WHERE slug = 'kaihle-test-school'"))
                school_id = result.scalar_one()
            log.info("school_created", school_id=str(school_id))
        else:
            school_id = school_row
            log.info("school_exists", school_id=str(school_id))

        await db.commit()

        # -------------------------------------------------------------------
        # 2. Create users (teacher, student, school_admin, parent)
        # -------------------------------------------------------------------
        test_password = hash_password("Test1234!")

        users_data = [
            {
                "email": "teacher@kaihle.com",
                "first_name": "John",
                "last_name": "Teacher",
                "role": "TEACHER",
            },
            {
                "email": "student@kaihle.com",
                "first_name": "Jane",
                "last_name": "Student",
                "role": "STUDENT",
            },
            {
                "email": "admin@kaihle.com",
                "first_name": "Admin",
                "last_name": "User",
                "role": "SCHOOL_ADMIN",
            },
            {
                "email": "parent@kaihle.com",
                "first_name": "Parent",
                "last_name": "User",
                "role": "PARENT",
            },
        ]

        user_ids = {}
        for user_data in users_data:
            result = await db.execute(
                text("""
                    INSERT INTO users (id, school_id, email, hashed_password, first_name, last_name, role, is_active)
                    VALUES (gen_random_uuid(), :school_id, :email, :hashed_password, :first_name, :last_name, :role, true)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id
                """),
                {
                    "school_id": str(school_id),
                    "email": user_data["email"],
                    "hashed_password": test_password,
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "role": user_data["role"],
                },
            )
            user_id = result.scalar_one_or_none()
            if not user_id:
                # User already exists, get their ID
                result = await db.execute(
                    text("SELECT id FROM users WHERE email = :email"), {"email": user_data["email"]}
                )
                user_id = result.scalar_one()
            user_ids[user_data["role"]] = user_id
            log.info("user_created", email=user_data["email"], role=user_data["role"])

        await db.commit()

        teacher_id = user_ids["TEACHER"]
        student_id = user_ids["STUDENT"]

        # -------------------------------------------------------------------
        # 3. Create teacher profile
        # -------------------------------------------------------------------
        await db.execute(
            text("""
                INSERT INTO teacher_profiles (id, user_id, qualifications, experience_years, bio, hire_date)
                VALUES (gen_random_uuid(), :user_id, :qualifications, :experience_years, :bio, :hire_date)
                ON CONFLICT (user_id) DO NOTHING
            """),
            {
                "user_id": str(teacher_id),
                "qualifications": '{"degree": "B.Ed", "certification": "Cambridge Certified"}',
                "experience_years": 5,
                "bio": "Experienced mathematics and science teacher with a passion for student-centered learning.",
                "hire_date": datetime.date(2024, 1, 15),
            },
        )
        log.info("teacher_profile_created")

        # -------------------------------------------------------------------
        # 4. Create student profile
        # -------------------------------------------------------------------
        await db.execute(
            text("""
                INSERT INTO student_profiles (id, user_id, grade_id, age, is_learning_profile_complete)
                VALUES (gen_random_uuid(), :user_id, NULL, 14, false)
                ON CONFLICT (user_id) DO NOTHING
            """),
            {
                "user_id": str(student_id),
            },
        )
        log.info("student_profile_created")

        await db.commit()

        # -------------------------------------------------------------------
        # 5. Create grades (global, not school-specific in this schema)
        # -------------------------------------------------------------------
        grades_data = [
            ("Grade 6", 6),
            ("Grade 7", 7),
            ("Grade 8", 8),
            ("Grade 9", 9),
            ("Grade 10", 10),
        ]

        for name, level in grades_data:
            await db.execute(
                text("""
                    INSERT INTO grades (id, name, level, is_active)
                    VALUES (gen_random_uuid(), :name, :level, true)
                    ON CONFLICT (level) DO NOTHING
                """),
                {"name": name, "level": level},
            )

        await db.commit()
        log.info("grades_ready")

        # Get grade IDs
        result = await db.execute(text("SELECT id, level FROM grades ORDER BY level"))
        grades = {row.level: str(row.id) for row in result.fetchall()}

        # -------------------------------------------------------------------
        # 6. Get subject and curriculum IDs
        # -------------------------------------------------------------------
        result = await db.execute(text("SELECT id, code FROM subjects WHERE code IN ('MATH', 'SCI', 'ENG')"))
        subjects = {row.code: str(row.id) for row in result.fetchall()}

        result = await db.execute(text("SELECT id FROM curricula WHERE code = 'igcse' LIMIT 1"))
        curriculum_id = str(result.scalar_one_or_none())

        if not curriculum_id:
            result = await db.execute(text("SELECT id FROM curricula LIMIT 1"))
            curriculum_id = str(result.scalar_one_or_none())

        if not curriculum_id:
            log.error("no_curriculum_found", message="Please run seed_curriculum_graph.py first")
            return

        # -------------------------------------------------------------------
        # 7. Link school to curriculum
        # -------------------------------------------------------------------
        await db.execute(
            text("""
                INSERT INTO school_curricula (school_id, curriculum_id, is_primary)
                VALUES (:school_id, :curriculum_id, true)
                ON CONFLICT (school_id, curriculum_id) DO NOTHING
            """),
            {"school_id": str(school_id), "curriculum_id": curriculum_id},
        )
        log.info("school_curriculum_linked")

        await db.commit()

        # -------------------------------------------------------------------
        # 8. Create classes
        # -------------------------------------------------------------------
        classes_data = [
            ("Mathematics 9B", "MATH", grades[9]),
            ("Science 8A", "SCI", grades[8]),
            ("English 10C", "ENG", grades[10]),
        ]

        class_ids = []
        for name, subject_code, grade_id in classes_data:
            subject_id = subjects.get(subject_code)
            if not subject_id:
                continue

            result = await db.execute(
                text("""
                    INSERT INTO classes (id, name, subject_id, curriculum_id, grade_id, school_id, teacher_id, academic_year, is_active)
                    VALUES (gen_random_uuid(), :name, :subject_id, :curriculum_id, :grade_id, :school_id, :teacher_id, '2025-2026', true)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {
                    "name": name,
                    "subject_id": subject_id,
                    "curriculum_id": curriculum_id,
                    "grade_id": grade_id,
                    "school_id": str(school_id),
                    "teacher_id": str(teacher_id),
                },
            )
            row = result.scalar_one_or_none()
            if row:
                class_ids.append(str(row))
                log.info("created_class", name=name)

        await db.commit()

        # Get all class IDs if none were created
        if not class_ids:
            result = await db.execute(text("SELECT id FROM classes"))
            class_ids = [str(row.id) for row in result.fetchall()]

        log.info("classes_ready", count=len(class_ids))

        # -------------------------------------------------------------------
        # 9. Enroll student in all classes
        # -------------------------------------------------------------------
        enrolled_count = 0
        for class_id in class_ids:
            await db.execute(
                text("""
                    INSERT INTO class_enrollments (class_id, student_id, is_active)
                    VALUES (:class_id, :student_id, true)
                    ON CONFLICT DO NOTHING
                """),
                {"class_id": class_id, "student_id": str(student_id)},
            )
            enrolled_count += 1

        await db.commit()

        log.info(
            "seed_complete",
            school_id=str(school_id),
            classes=len(class_ids),
            enrollments=enrolled_count,
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_test_data())
