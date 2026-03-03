# M0-2-T1 — Alembic Setup & Initial Migration (35 Tables)
**Milestone:** M0 — Foundations
**Epic:** M0-2 — Database & Migrations
**Task ID:** M0-2-T1
**Mode:** Code (MiniMax)
**Estimated effort:** 4–6 hours

---

## Context

This task creates the entire database schema in one Alembic migration. All 35 tables, 14 enums, and all indexes must be created from the canonical schema in `kaihle_v2_1_schema.sql`.

**CRITICAL:** `kaihle_v2_1_schema.sql` is the single source of truth for all column names, types, constraints, and indexes. If anything in this task file conflicts with the SQL file, the SQL file wins. Read it in full before writing any migration code.

**Depends on:** M0-1-T1 (pyproject.toml with Alembic installed), M0-1-T2 (PostgreSQL running with pgvector)

---

## User Story

As a developer, I want a versioned database schema so that schema changes are tracked, reversible, and applied consistently across environments.

---

## What To Build

### 1. Alembic Initialisation

```bash
cd /kaihle/backend
alembic init alembic
```

This creates:
- `/backend/alembic.ini`
- `/backend/alembic/env.py`
- `/backend/alembic/versions/` (empty)

---

### 2. `/kaihle/backend/alembic.ini`

Update the generated file — change `sqlalchemy.url` line:
```ini
sqlalchemy.url = %(DATABASE_URL)s
```
This allows the URL to come from the environment rather than being hardcoded.

---

### 3. `/kaihle/backend/alembic/env.py`

Replace the generated file with async-compatible version:

```python
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import all models so Alembic can detect them
# (models are added in M0-2-T2 — for now this import is a placeholder)
# from app.models import *  # noqa: F401, F403

config = context.config

# Override sqlalchemy.url from environment variable
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set to None until models are imported in M0-2-T2
target_metadata = None

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### 4. Create Migration: `001_initial_schema.py`

```bash
alembic revision -m "initial_schema"
```

Then populate the generated file at `/backend/alembic/versions/001_initial_schema.py`.

**The migration must create all tables in this exact order** (to satisfy FK dependencies):

```
1.  Extensions (vector, pgcrypto, pg_trgm)
2.  Enums (all 14)
3.  curricula
4.  subjects
5.  grades
6.  topics
7.  curriculum_subjects
8.  curriculum_topics
9.  subtopics
10. subtopic_prerequisites
11. topic_prerequisites
12. curriculum_chunks
13. schools
14. school_curricula
15. users
16. student_profiles
17. teacher_profiles
18. auth_tokens
19. classes
20. class_enrollments
21. parent_student
22. student_learning_profiles   ← NEW v2.1
23. assessments                 ← includes is_system_generated column
24. assessment_selected_questions
25. student_attempts
26. student_responses
27. gap_states
28. study_plans
29. study_plan_resources
30. study_plan_quizzes
31. lesson_plans
32. parent_report_snapshots
33. subscription_plans
34. school_subscriptions
35. subscription_invoices
36. payments
37. trial_extensions
38. alembic_version             ← managed by Alembic automatically
```

**The migration `upgrade()` function must:**

```python
def upgrade() -> None:
    # 1. Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. Enums — create all 14
    op.execute("""
        CREATE TYPE assessment_type AS ENUM (
            'DIAGNOSTIC', 'TOPIC_SPECIFIC', 'PROGRESS_CHECK', 'FINAL'
        )
    """)
    op.execute("""
        CREATE TYPE assessment_status AS ENUM ('DRAFT', 'ACTIVE', 'CLOSED')
    """)
    op.execute("""
        CREATE TYPE attempt_status AS ENUM (
            'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED'
        )
    """)
    op.execute("""
        CREATE TYPE question_type AS ENUM ('MCQ', 'TRUE_FALSE', 'SHORT_ANSWER')
    """)
    op.execute("""
        CREATE TYPE scored_by AS ENUM ('RULE', 'LLM', 'PENDING')
    """)
    op.execute("""
        CREATE TYPE study_plan_status AS ENUM (
            'GENERATING', 'ACTIVE', 'COMPLETED', 'ABANDONED'
        )
    """)
    op.execute("""
        CREATE TYPE resource_type AS ENUM ('VIDEO', 'ARTICLE', 'INTERACTIVE')
    """)
    op.execute("""
        CREATE TYPE lesson_plan_status AS ENUM (
            'GENERATED', 'EDITED', 'USED', 'ARCHIVED'
        )
    """)
    op.execute("""
        CREATE TYPE user_role AS ENUM (
            'STUDENT', 'TEACHER', 'SCHOOL_ADMIN', 'PARENT', 'KAIHLE_ADMIN'
        )
    """)
    op.execute("""
        CREATE TYPE subscription_tier AS ENUM (
            'TRIAL', 'STARTER', 'GROWTH', 'SCALE'
        )
    """)
    op.execute("""
        CREATE TYPE subscription_status AS ENUM (
            'ACTIVE', 'PAST_DUE', 'CANCELLED', 'EXPIRED'
        )
    """)
    op.execute("""
        CREATE TYPE payment_status AS ENUM (
            'PENDING', 'SUCCEEDED', 'FAILED', 'REFUNDED', 'DISPUTED'
        )
    """)
    op.execute("""
        CREATE TYPE auth_token_type AS ENUM ('MAGIC_LINK', 'REFRESH')
    """)
    op.execute("""
        CREATE TYPE onboarding_status AS ENUM (
            'PENDING', 'IN_PROGRESS', 'COMPLETED'
        )
    """)

    # 3–38. Tables — use op.create_table() for each table
    # Copy exact column definitions from kaihle_v2_1_schema.sql
    # Below are the two NEW v2.1 additions that are NOT in the SQL file yet:

    # student_learning_profiles (NEW v2.1 — not yet in kaihle_v2_1_schema.sql)
    op.create_table(
        "student_learning_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("modality_scores", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("work_style", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("interests", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("questionnaire_version", sa.String(10), nullable=False,
                  server_default="v1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # assessments table must include is_system_generated (NEW v2.1)
    # When creating the assessments table, add this column:
    sa.Column("is_system_generated", sa.Boolean(), nullable=False,
              server_default=sa.false())

    # student_profiles must include onboarding_diagnostic_status (NEW v2.1)
    # When creating student_profiles, add this column:
    sa.Column("onboarding_diagnostic_status",
              sa.Enum("PENDING", "IN_PROGRESS", "COMPLETED",
                      name="onboarding_status"),
              nullable=False,
              server_default="PENDING")

    # After ALL tables created — create indexes
    # Copy all index definitions from kaihle_v2_1_schema.sql §12
    # IMPORTANT: Do NOT create ivfflat indexes on embedding columns here.
    # Those require data to exist first. Add a comment noting they must be
    # created manually after embedding data is loaded:
    #   CREATE INDEX CONCURRENTLY idx_subtopics_embedding
    #   ON subtopics USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);
```

**The `downgrade()` function must:**

```python
def downgrade() -> None:
    # Drop tables in REVERSE order (to satisfy FK dependencies)
    tables = [
        "trial_extensions", "subscription_invoices", "school_subscriptions",
        "subscription_plans", "parent_report_snapshots", "lesson_plans",
        "study_plan_quizzes", "study_plan_resources", "study_plans",
        "gap_states", "student_responses", "student_attempts",
        "assessment_selected_questions", "assessments",
        "student_learning_profiles", "parent_student", "class_enrollments",
        "classes", "auth_tokens", "teacher_profiles", "student_profiles",
        "users", "school_curricula", "schools", "curriculum_chunks",
        "subtopic_prerequisites", "topic_prerequisites", "subtopics",
        "curriculum_topics", "curriculum_subjects", "topics",
        "grades", "subjects", "curricula",
    ]
    for table in tables:
        op.drop_table(table)

    # Drop enums in reverse order
    enums = [
        "onboarding_status", "auth_token_type", "payment_status",
        "subscription_status", "subscription_tier", "user_role",
        "lesson_plan_status", "resource_type", "study_plan_status",
        "scored_by", "question_type", "attempt_status",
        "assessment_status", "assessment_type",
    ]
    for enum in enums:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
```

---

## Key v2.1 Column Additions (Not Yet in kaihle_v2_1_schema.sql)

These two columns are additions introduced in v2.1 and must be included:

**On `assessments` table:**
```sql
is_system_generated  BOOLEAN  NOT NULL  DEFAULT FALSE
```
Comment: `TRUE = Tier 1 (system-triggered on enrollment). FALSE = Tier 2 (teacher-created).`

**On `student_profiles` table:**
```sql
onboarding_diagnostic_status  onboarding_status  NOT NULL  DEFAULT 'PENDING'
```
Comment: `Tracks Tier 1 diagnostic completion. Set to COMPLETED by onboarding_service.check_and_update_onboarding_complete().`

---

## Indexes to Create

Create all indexes from `kaihle_v2_1_schema.sql` §12 EXCEPT:
- `idx_subtopics_embedding` (ivfflat) — deferred, requires embedding data
- `idx_curriculum_chunks_embedding` (ivfflat) — deferred, requires embedding data

Add these two as comments in the migration with instructions:
```python
# DEFERRED INDEXES — run manually after embedding data is loaded:
# CREATE INDEX CONCURRENTLY idx_subtopics_embedding
#   ON subtopics USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);
# CREATE INDEX CONCURRENTLY idx_curriculum_chunks_embedding
#   ON curriculum_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);
```

Additional v2.1 indexes to create:
```sql
CREATE UNIQUE INDEX idx_slp_student ON student_learning_profiles(student_id);
CREATE INDEX idx_slp_school ON student_learning_profiles(school_id);
CREATE INDEX idx_assessments_system_generated ON assessments(is_system_generated);
```

---

## Files To Create / Modify

```
/kaihle/backend/alembic.ini                              ← MODIFY (update sqlalchemy.url)
/kaihle/backend/alembic/env.py                          ← REPLACE with async version
/kaihle/backend/alembic/versions/001_initial_schema.py  ← CREATE
```

---

## Acceptance Criteria

- [ ] `alembic upgrade head` runs without errors on a clean database
- [ ] `alembic downgrade -1` reverses the migration cleanly with no errors
- [ ] Migration can be applied and reversed 3× consecutively without errors
- [ ] After upgrade: `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'` returns 35+ (35 tables + alembic_version)
- [ ] `SELECT extname FROM pg_extension WHERE extname = 'vector'` returns one row
- [ ] `assessments` table has `is_system_generated` column with DEFAULT FALSE
- [ ] `student_profiles` table has `onboarding_diagnostic_status` column with DEFAULT 'PENDING'
- [ ] `student_learning_profiles` table exists with all columns from §2.12 of `kaihle_product_plan_v2_1.md`
- [ ] `onboarding_status` enum exists with values PENDING, IN_PROGRESS, COMPLETED

---

## Dependencies

- M0-1-T1 — Alembic in `pyproject.toml`
- M0-1-T2 — PostgreSQL with pgvector running

## Output (What Next Tasks Can Use)

- All 35 tables and 14 enums exist in the database
- M0-2-T2 can now create SQLAlchemy ORM models that map to these tables
- M1-1-T1 (question bank import) can resolve `subtopic_id` once curriculum tables are populated
