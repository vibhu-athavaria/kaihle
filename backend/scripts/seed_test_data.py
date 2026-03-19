"""Test data seeding script.

Creates grades, classes, teacher assignments, and student enrollments for testing.
Run after seed_curriculum_graph.py has been executed.

Usage (from project root):
    docker compose exec backend python -m scripts.seed_test_data
    # Or outside Docker:
    cd backend && python -m scripts.seed_test_data

Idempotent: re-running produces same result (uses ON CONFLICT DO NOTHING).
"""

import asyncio
import os
import sys
from pathlib import Path

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap path so we can import app modules when run as a script
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402

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
        # Get school
        result = await db.execute(select(text("SELECT id FROM schools LIMIT 1")))
        school_row = result.scalar_one_or_none()
        if not school_row:
            log.error("no_school_found", message="Please create a school first")
            return
        school_id = school_row

        # Get teacher
        result = await db.execute(select(text("SELECT id FROM users WHERE role = 'TEACHER' LIMIT 1")))
        teacher_row = result.scalar_one_or_none()
        if not teacher_row:
            log.error("no_teacher_found", message="Please create a teacher user first")
            return
        teacher_id = teacher_row

        # Get student
        result = await db.execute(select(text("SELECT id FROM users WHERE role = 'STUDENT' LIMIT 1")))
        student_row = result.scalar_one_or_none()
        if not student_row:
            log.error("no_student_found", message="Please create a student user first")
            return
        student_id = student_row

        # Create grades (global, not school-specific in this schema)
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

        # Get subject and curriculum IDs
        result = await db.execute(text("SELECT id, code FROM subjects WHERE code IN ('MATH', 'SCI', 'ENG')"))
        subjects = {row.code: str(row.id) for row in result.fetchall()}

        result = await db.execute(text("SELECT id FROM curricula WHERE code = 'igcse' LIMIT 1"))
        curriculum_id = str(result.scalar_one_or_none())

        if not curriculum_id:
            result = await db.execute(text("SELECT id FROM curricula LIMIT 1"))
            curriculum_id = str(result.scalar_one_or_none())

        # Create classes
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

        # Enroll student in all classes
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
