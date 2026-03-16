# M0-8-T1 — Backend Critical Fixes
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes (must complete before M0-6-T4)
**Task ID:** M0-8-T1
**Depends on:** M0-2-T2 (models), M0-6-T2 (Celery tasks)
**Blocks:** M0-6-T4, and every task in M1+
**Estimated effort:** 3–4 hours

---

## Context

Two critical bugs found during the M0 audit that will cause runtime failures in M1
if not fixed now. Both must be resolved before any feature work begins.

---

## Fix 1 — `User.school_id` must be nullable (KaihleAdmin has no school)

### Problem

`User.school_id` is declared `nullable=False` in the ORM model and `NOT NULL` in
the migration. `create_access_token` already accepts `school_id: UUID | None` correctly,
but any attempt to create a KaihleAdmin user (who belongs to no school) will fail at
the DB INSERT with an `IntegrityError` — not a 409, an unhandled 500.

### Fix

**Step 1 — ORM model** (`backend/app/models/user.py`):

```python
# BEFORE
school_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("schools.id", ondelete="CASCADE"),
    nullable=False,
)

# AFTER
school_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("schools.id", ondelete="SET NULL"),
    nullable=True,
    # NULL is valid ONLY for KAIHLE_ADMIN role.
    # All other roles MUST have a school_id — enforced by CHECK constraint below.
)
```

**Step 2 — Alembic migration** (`backend/alembic/versions/003_user_school_id_nullable.py`):

```python
"""Make users.school_id nullable for KaihleAdmin users.

KaihleAdmin is a platform-level role with no school affiliation.
All other roles (STUDENT, TEACHER, SCHOOL_ADMIN, PARENT) must have school_id.
Enforced by CHECK constraint.

Revision ID: 003_user_school_id_nullable
Revises: 002_nullable_created_by
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "003_user_school_id_nullable"
down_revision: str | None = "002_nullable_created_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Make school_id nullable
    op.alter_column("users", "school_id",
                    existing_type=sa.UUID(),
                    nullable=True)
    # Change FK ON DELETE action from CASCADE to SET NULL
    op.drop_constraint("users_school_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_school_id_fkey", "users", "schools",
        ["school_id"], ["id"], ondelete="SET NULL"
    )
    # Add CHECK: only KAIHLE_ADMIN may have NULL school_id
    op.create_check_constraint(
        "chk_user_school_id_required",
        "users",
        "role = 'KAIHLE_ADMIN' OR school_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("chk_user_school_id_required", "users", type_="check")
    op.drop_constraint("users_school_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_school_id_fkey", "users", "schools",
        ["school_id"], ["id"], ondelete="CASCADE"
    )
    op.alter_column("users", "school_id",
                    existing_type=sa.UUID(),
                    nullable=False)
```

**Step 3 — Auth service** (`backend/app/services/auth_service.py`):

The `register()` method must handle KaihleAdmin registration where `school_id=None`:

```python
# Email uniqueness check: global for KaihleAdmin, per-school for everyone else
stmt = select(User).where(User.email == email)
if school_id is not None:
    stmt = stmt.where(User.school_id == school_id)
# If school_id is None (KaihleAdmin), check globally — already covered by the base filter
existing = await self.db.scalar(stmt)
if existing:
    raise ValueError("Email already registered")
```

**Step 4 — Schema** (`kaihle_v2_1_schema.sql`):

Add a note to the `users` table comment and update the `school_id` column definition:

```sql
-- In users table:
school_id   UUID    REFERENCES schools (id) ON DELETE SET NULL,
-- NULL is valid ONLY for KAIHLE_ADMIN. All other roles require school_id.
-- Enforced by: CHECK (role = 'KAIHLE_ADMIN' OR school_id IS NOT NULL)
```

---

## Fix 2 — Celery tasks must not use `asyncio.run()`

### Problem

Both `create_class_diagnostic_task` and `trigger_onboarding_diagnostics` call
`asyncio.run(_run())` inside synchronous Celery task functions. This will raise
`RuntimeError: This event loop is already running` when:
- Celery is configured with `gevent` or `eventlet` concurrency pools
- Tests use pytest-asyncio (which runs its own event loop)
- The task is called inside an already-running async context

### Fix

Replace `asyncio.run()` with a new event loop per call — the only safe pattern for
sync Celery tasks that need async database access:

**`backend/app/tasks/onboarding_tasks.py`** — update both tasks:

```python
# REPLACE this pattern (exists in both tasks):
try:
    run_result = asyncio.run(_run())

# WITH this pattern:
try:
    loop = asyncio.new_event_loop()
    try:
        run_result = loop.run_until_complete(_run())
    finally:
        loop.close()
```

Apply this change in:
- `create_class_diagnostic_task` — the `asyncio.run(_run())` call
- `trigger_onboarding_diagnostics` — the `asyncio.run(_run())` call

**Why not use `anyio` or a Celery async worker?**
`new_event_loop()` + `run_until_complete()` + `close()` is the safest minimal fix.
It creates an isolated event loop per task execution — no conflict with any external
event loop. A full async Celery migration is deferred to v2 (it requires changing the
Celery worker startup pattern).

---

## Files to Modify

```
backend/app/models/user.py                        ← Mapped[uuid.UUID | None], nullable=True
backend/app/services/auth_service.py              ← email uniqueness: school_id=None case
backend/app/tasks/onboarding_tasks.py             ← replace asyncio.run() in both tasks
backend/alembic/versions/003_user_school_id_nullable.py  ← CREATE new migration
backend/app/tests/unit/test_models.py             ← add tests for new constraint
backend/app/tests/integration/test_auth_routes.py ← add KaihleAdmin registration test
```

Also update `kaihle_v2_1_schema.sql` as the schema source of truth.

---

## Acceptance Criteria

- [ ] `alembic upgrade head` applies migration 003 without errors on a clean DB
- [ ] `alembic downgrade -1` reverts migration 003 cleanly (when no KaihleAdmin rows exist)
- [ ] Unit test: `User(role='KAIHLE_ADMIN', school_id=None)` is valid (no constraint violation)
- [ ] Unit test: `User(role='TEACHER', school_id=None)` raises `IntegrityError` (CHECK constraint)
- [ ] Integration test: `POST /api/v1/auth/register` with `role='KAIHLE_ADMIN'` and no `school_id` → creates user, returns 201
- [ ] Integration test: `POST /api/v1/auth/register` with `role='TEACHER'` and no `school_id` → 400 (validation error before DB)
- [ ] Unit test: `create_class_diagnostic_task` runs without `RuntimeError` when called from within an existing async context (pytest-asyncio)
- [ ] Unit test: `trigger_onboarding_diagnostics` runs without `RuntimeError` in the same condition
- [ ] `mypy app/` passes with zero errors after model change
- [ ] `alembic revision --autogenerate` detects zero schema differences after migration applied
