"""Future School demo data seeder.

Idempotent — safe to re-run. Adds to the existing "future-school-bali" school:
  - 7 additional teachers (bringing total to 10), subject-assigned
  - Students to reach 10 per grade for grades 6–10 (tops up existing ones)
  - Missing classes: Math + SCI + ENG for grades 6–8, PHY/CHEM/BIO/Math/ENG for grade 10,
    ENG for grade 7, CHEM for grade 9
  - Enrollments linking every student to all classes in their grade
  - Student profiles and learning profiles (dashboard gate satisfied)
  - Teacher profiles for all new teachers

Usage (from project root):
    docker compose exec backend python -m scripts.seed_future_school_demo
"""

import asyncio
import datetime
import sys
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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

SCHOOL_SLUG = "future-school-bali"
DEMO_PASSWORD = "test1234!"

# ---------------------------------------------------------------------------
# 7 new teachers — subject-based specialties
# ---------------------------------------------------------------------------
# specialty key is used below to map teachers → class assignments
NEW_TEACHERS: list[dict[str, Any]] = [
    {
        "email": "sarah.chen@futureschool-demo.edu",
        "first_name": "Sarah",
        "last_name": "Chen",
        "specialty": "math_lower",
        "bio": "Lower Secondary Mathematics specialist with 8 years of experience.",
    },
    {
        "email": "james.park@futureschool-demo.edu",
        "first_name": "James",
        "last_name": "Park",
        "specialty": "sci_lower",
        "bio": "Integrated Science teacher, Cambridge Lower Secondary certified.",
    },
    {
        "email": "emma.wilson@futureschool-demo.edu",
        "first_name": "Emma",
        "last_name": "Wilson",
        "specialty": "eng_lower",
        "bio": "English Language teacher passionate about literacy across all grades.",
    },
    {
        "email": "michael.torres@futureschool-demo.edu",
        "first_name": "Michael",
        "last_name": "Torres",
        "specialty": "chem",
        "bio": "Chemistry educator with a background in industrial research.",
    },
    {
        "email": "priya.singh@futureschool-demo.edu",
        "first_name": "Priya",
        "last_name": "Singh",
        "specialty": "phy_igcse",
        "bio": "IGCSE Physics teacher, 10 years in international school settings.",
    },
    {
        "email": "david.osei@futureschool-demo.edu",
        "first_name": "David",
        "last_name": "Osei",
        "specialty": "bio_igcse",
        "bio": "Biology specialist with focus on IGCSE extended curriculum.",
    },
    {
        "email": "lisa.chang@futureschool-demo.edu",
        "first_name": "Lisa",
        "last_name": "Chang",
        "specialty": "math_igcse",
        "bio": "IGCSE Mathematics teacher with strong data literacy focus.",
    },
]

# ---------------------------------------------------------------------------
# Students — only new ones needed to top up each grade to 10
# ---------------------------------------------------------------------------
# Grade 6: 0 existing → add 10
# Grade 7: 3 existing → add 7
# Grade 8: 0 existing → add 10
# Grade 9: 7 existing → add 3
# Grade 10: 0 existing → add 10
STUDENTS_BY_GRADE: dict[int, list[tuple[str, str, str]]] = {
    6: [
        ("Oliver", "Bennett", "oliver.bennett@futureschool-demo.edu"),
        ("Sofia", "Martinez", "sofia.martinez@futureschool-demo.edu"),
        ("Aiden", "Nguyen", "aiden.nguyen@futureschool-demo.edu"),
        ("Zara", "Ibrahim", "zara.ibrahim@futureschool-demo.edu"),
        ("Lucas", "Kim", "lucas.kim@futureschool-demo.edu"),
        ("Yuki", "Tanaka", "yuki.tanaka@futureschool-demo.edu"),
        ("Noah", "Williams", "noah.williams@futureschool-demo.edu"),
        ("Aliya", "Petrov", "aliya.petrov@futureschool-demo.edu"),
        ("Marcus", "Thompson", "marcus.thompson@futureschool-demo.edu"),
        ("Cleo", "Nkosi", "cleo.nkosi@futureschool-demo.edu"),
    ],
    7: [
        ("Lily", "Chen", "lily.chen@futureschool-demo.edu"),
        ("Ethan", "Brown", "ethan.brown@futureschool-demo.edu"),
        ("Maya", "Patel", "maya.patel@futureschool-demo.edu"),
        ("Ravi", "Krishnan", "ravi.krishnan@futureschool-demo.edu"),
        ("Chloe", "Adams", "chloe.adams@futureschool-demo.edu"),
        ("Diego", "Silva", "diego.silva@futureschool-demo.edu"),
        ("Hannah", "Lee", "hannah.lee@futureschool-demo.edu"),
    ],
    8: [
        ("Jack", "Murphy", "jack.murphy@futureschool-demo.edu"),
        ("Isabelle", "Dubois", "isabelle.dubois@futureschool-demo.edu"),
        ("Kai", "Nakamura", "kai.nakamura@futureschool-demo.edu"),
        ("Fatima", "Hassan", "fatima.hassan@futureschool-demo.edu"),
        ("Ryan", "OBrien", "ryan.obrien@futureschool-demo.edu"),
        ("Elena", "Ivanova", "elena.ivanova@futureschool-demo.edu"),
        ("Sam", "Taylor", "sam.taylor@futureschool-demo.edu"),
        ("Ananya", "Iyer", "ananya.iyer@futureschool-demo.edu"),
        ("Felix", "Wagner", "felix.wagner@futureschool-demo.edu"),
        ("Nadia", "Al-Rashid", "nadia.alrashid@futureschool-demo.edu"),
    ],
    9: [
        ("Tyler", "Brooks", "tyler.brooks@futureschool-demo.edu"),
        ("Jasmine", "Wu", "jasmine.wu@futureschool-demo.edu"),
        ("Stefan", "Horvath", "stefan.horvath@futureschool-demo.edu"),
    ],
    10: [
        ("Emma", "Clarke", "emma.clarke@futureschool-demo.edu"),
        ("Benjamin", "Adeyemi", "benjamin.adeyemi@futureschool-demo.edu"),
        ("Sara", "Jensen", "sara.jensen@futureschool-demo.edu"),
        ("Kenji", "Watanabe", "kenji.watanabe@futureschool-demo.edu"),
        ("Camille", "Dupont", "camille.dupont@futureschool-demo.edu"),
        ("Arjun", "Mehta", "arjun.mehta@futureschool-demo.edu"),
        ("Nora", "Lindqvist", "nora.lindqvist@futureschool-demo.edu"),
        ("Hassan", "Abdi", "hassan.abdi@futureschool-demo.edu"),
        ("Valentina", "Cruz", "valentina.cruz@futureschool-demo.edu"),
        ("Patrick", "Okafor", "patrick.okafor@futureschool-demo.edu"),
    ],
}

GRADE_AGE = {6: 11, 7: 12, 8: 13, 9: 14, 10: 15}

# ---------------------------------------------------------------------------
# Classes to create (only the ones not yet present)
# Tuple: (display_name, subject_code, grade_level, teacher_specialty, curriculum_code)
# teacher_specialty "eng_existing" → assign to the existing English Teacher
# ---------------------------------------------------------------------------
CLASS_DEFINITIONS: list[tuple[str, str, int, str, str]] = [
    # Grade 6 — all three missing
    ("Math", "MATH", 6, "math_lower", "cambridge_lower"),
    ("Science", "SCI", 6, "sci_lower", "cambridge_lower"),
    ("English", "ENG", 6, "eng_lower", "cambridge_lower"),
    # Grade 7 — only English missing
    ("English", "ENG", 7, "eng_lower", "cambridge_lower"),
    # Grade 8 — all three missing
    ("Math", "MATH", 8, "math_lower", "cambridge_lower"),
    ("Science", "SCI", 8, "sci_lower", "cambridge_lower"),
    ("English", "ENG", 8, "eng_lower", "cambridge_lower"),
    # Grade 9 — only Chemistry missing
    ("Chemistry", "CHEM", 9, "chem", "igcse"),
    # Grade 10 — all missing
    ("Math", "MATH", 10, "math_igcse", "igcse"),
    ("Physics", "PHY", 10, "phy_igcse", "igcse"),
    ("Chemistry", "CHEM", 10, "chem", "igcse"),
    ("Biology", "BIO", 10, "bio_igcse", "igcse"),
    ("English", "ENG", 10, "eng_existing", "igcse"),
]


def get_database_url() -> str:
    db_url = settings.database_url
    if not db_url:
        db_url = "postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle"
    return db_url


async def upsert_user(
    db: AsyncSession,
    *,
    school_id: str,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    hashed_pw: str,
) -> str:
    """Insert user if not exists; return the user's UUID as a string."""
    await db.execute(
        text("""
            INSERT INTO users (id, school_id, email, hashed_password, first_name, last_name, role, is_active)
            VALUES (gen_random_uuid(), :school_id, :email, :hashed_password, :first_name, :last_name, :role, true)
            ON CONFLICT (email) DO NOTHING
        """),
        {
            "school_id": school_id,
            "email": email,
            "hashed_password": hashed_pw,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
        },
    )
    result = await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
    return str(result.scalar_one())


async def seed() -> None:
    db_url = get_database_url()
    log.info("connecting_to_database", url=db_url.replace("//", "//***:***@"))

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    hashed_pw = hash_password(DEMO_PASSWORD)

    async with async_session() as db:
        # ── Resolve school ────────────────────────────────────────────────
        result = await db.execute(
            text("SELECT id FROM schools WHERE slug = :slug"),
            {"slug": SCHOOL_SLUG},
        )
        school_id = str(result.scalar_one())
        log.info("school_resolved", school_id=school_id)

        # ── Resolve curricula ─────────────────────────────────────────────
        result = await db.execute(text("SELECT code, id FROM curricula"))
        curricula: dict[str, str] = {row.code: str(row.id) for row in result.fetchall()}

        # ── Resolve subjects ──────────────────────────────────────────────
        result = await db.execute(text("SELECT code, id FROM subjects"))
        subjects: dict[str, str] = {row.code: str(row.id) for row in result.fetchall()}

        # ── Resolve grades ────────────────────────────────────────────────
        result = await db.execute(text("SELECT level, id FROM grades ORDER BY level"))
        grades: dict[int, str] = {row.level: str(row.id) for row in result.fetchall()}

        # ── Section 1: Create new teachers ───────────────────────────────
        log.info("section_teachers_start")
        teacher_by_specialty: dict[str, str] = {}

        # Also pre-load the existing English Teacher for G10 English assignment
        result = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "vaibhavathavaria+eng.teacher@gmail.com"},
        )
        existing_eng_teacher = result.scalar_one_or_none()
        if existing_eng_teacher:
            teacher_by_specialty["eng_existing"] = str(existing_eng_teacher)

        for t in NEW_TEACHERS:
            teacher_id = await upsert_user(
                db,
                school_id=school_id,
                email=t["email"],
                first_name=t["first_name"],
                last_name=t["last_name"],
                role="TEACHER",
                hashed_pw=hashed_pw,
            )
            teacher_by_specialty[t["specialty"]] = teacher_id

            # Teacher profile
            await db.execute(
                text("""
                    INSERT INTO teacher_profiles
                        (id, user_id, qualifications, experience_years, bio, hire_date)
                    VALUES
                        (gen_random_uuid(), :user_id, :quals, :exp, :bio, :hire_date)
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {
                    "user_id": teacher_id,
                    "quals": '{"degree": "B.Ed", "certification": "Cambridge Certified"}',
                    "exp": 7,
                    "bio": t["bio"],
                    "hire_date": datetime.date(2023, 8, 1),
                },
            )
            log.info("teacher_ready", name=f"{t['first_name']} {t['last_name']}", email=t["email"])

        await db.commit()

        # ── Section 2: Create missing classes ────────────────────────────
        log.info("section_classes_start")
        # Index existing classes by (subject_code, grade_level) to avoid duplicates
        result = await db.execute(
            text("""
                SELECT s.code AS subject_code, g.level AS grade_level, c.id AS class_id
                FROM classes c
                JOIN subjects s ON c.subject_id = s.id
                JOIN grades g ON c.grade_id = g.id
                WHERE c.school_id = :school_id
            """),
            {"school_id": school_id},
        )
        existing_classes: dict[tuple[str, int], str] = {
            (row.subject_code, row.grade_level): str(row.class_id) for row in result.fetchall()
        }

        # classes_by_grade: grade_level → list of class UUIDs (for enrollment)
        classes_by_grade: dict[int, list[str]] = {}
        for (subj_code, grade_level), class_id in existing_classes.items():
            classes_by_grade.setdefault(grade_level, []).append(class_id)

        for class_name, subj_code, grade_level, teacher_specialty, curriculum_code in CLASS_DEFINITIONS:
            key = (subj_code, grade_level)
            if key in existing_classes:
                log.info("class_already_exists", name=class_name, grade=grade_level, subject=subj_code)
                continue

            subject_id = subjects.get(subj_code)
            curriculum_id = curricula.get(curriculum_code)
            grade_id = grades.get(grade_level)
            teacher_id = teacher_by_specialty.get(teacher_specialty)

            if not all([subject_id, curriculum_id, grade_id, teacher_id]):
                log.warning(
                    "class_skip_missing_ref",
                    name=class_name,
                    subject_id=subject_id,
                    curriculum_id=curriculum_id,
                    grade_id=grade_id,
                    teacher_id=teacher_id,
                )
                continue

            result = await db.execute(
                text("""
                    INSERT INTO classes
                        (id, name, subject_id, curriculum_id, grade_id, school_id, teacher_id, academic_year, is_active)
                    VALUES
                        (gen_random_uuid(), :name, :subject_id, :curriculum_id, :grade_id, :school_id, :teacher_id, '2025-2026', true)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {
                    "name": class_name,
                    "subject_id": subject_id,
                    "curriculum_id": curriculum_id,
                    "grade_id": grade_id,
                    "school_id": school_id,
                    "teacher_id": teacher_id,
                },
            )
            new_class_id = result.scalar_one_or_none()
            if new_class_id:
                classes_by_grade.setdefault(grade_level, []).append(str(new_class_id))
                log.info("class_created", name=class_name, grade=grade_level, subject=subj_code)

        await db.commit()

        # ── Section 3: Create students ────────────────────────────────────
        log.info("section_students_start")

        for grade_level, students in STUDENTS_BY_GRADE.items():
            grade_id = grades.get(grade_level)
            if not grade_id:
                log.warning("grade_not_found", level=grade_level)
                continue

            for first_name, last_name, email in students:
                student_id = await upsert_user(
                    db,
                    school_id=school_id,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role="STUDENT",
                    hashed_pw=hashed_pw,
                )

                # Student profile
                await db.execute(
                    text("""
                        INSERT INTO student_profiles
                            (id, user_id, grade_id, age, is_learning_profile_complete)
                        VALUES
                            (gen_random_uuid(), :user_id, :grade_id, :age, true)
                        ON CONFLICT (user_id) DO NOTHING
                    """),
                    {
                        "user_id": student_id,
                        "grade_id": grade_id,
                        "age": GRADE_AGE[grade_level],
                    },
                )

                # Learning profile (required by dashboard gate)
                await db.execute(
                    text("""
                        INSERT INTO student_learning_profiles
                            (id, student_id, school_id, modality_scores, work_style,
                             interests, questionnaire_version, completed_at)
                        VALUES
                            (gen_random_uuid(), :student_id, :school_id,
                             '{"visual": 0.6, "auditory": 0.5, "reading_writing": 0.5, "kinesthetic": 0.4}',
                             '{"prefers_solo": false, "short_sessions": true, "task_based": true, "concept_first": false}',
                             ARRAY['science', 'technology'],
                             'v1',
                             NOW())
                        ON CONFLICT (student_id) DO NOTHING
                    """),
                    {"student_id": student_id, "school_id": school_id},
                )

                log.info(
                    "student_ready",
                    name=f"{first_name} {last_name}",
                    grade=grade_level,
                    email=email,
                )

        await db.commit()

        # ── Section 4: Enroll ALL students in their grade's classes ──────
        log.info("section_enrollments_start")

        # Reload all students with their grades (existing + new)
        result = await db.execute(
            text("""
                SELECT u.id AS student_id, sp.grade_id
                FROM users u
                JOIN student_profiles sp ON sp.user_id = u.id
                WHERE u.school_id = :school_id AND u.role = 'STUDENT'
            """),
            {"school_id": school_id},
        )
        all_students = result.fetchall()

        # grade_id → grade_level lookup
        grade_level_by_id = {v: k for k, v in grades.items()}

        enrollments_added = 0
        for row in all_students:
            student_id = str(row.student_id)
            grade_level = grade_level_by_id.get(str(row.grade_id))
            if grade_level is None:
                continue

            class_ids_for_grade = classes_by_grade.get(grade_level, [])
            for class_id in class_ids_for_grade:
                result = await db.execute(
                    text("""
                        INSERT INTO class_enrollments (class_id, student_id, is_active)
                        VALUES (:class_id, :student_id, true)
                        ON CONFLICT DO NOTHING
                        RETURNING class_id
                    """),
                    {"class_id": class_id, "student_id": student_id},
                )
                if result.scalar_one_or_none():
                    enrollments_added += 1

        await db.commit()
        log.info("enrollments_added", count=enrollments_added)

        # ── Summary ───────────────────────────────────────────────────────
        result = await db.execute(
            text("SELECT COUNT(*) FROM users WHERE school_id = :s AND role = 'TEACHER'"),
            {"s": school_id},
        )
        teacher_count = result.scalar_one()

        result = await db.execute(
            text("SELECT COUNT(*) FROM users WHERE school_id = :s AND role = 'STUDENT'"),
            {"s": school_id},
        )
        student_count = result.scalar_one()

        result = await db.execute(
            text("SELECT COUNT(*) FROM classes WHERE school_id = :s AND is_active = true"),
            {"s": school_id},
        )
        class_count = result.scalar_one()

        log.info(
            "seed_complete",
            school=SCHOOL_SLUG,
            teachers=teacher_count,
            students=student_count,
            classes=class_count,
            enrollments_added=enrollments_added,
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
