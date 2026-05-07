# Plan: Grade–Curriculum Direct Association

## Context

Currently, grades and curricula have **no direct relationship** in the schema. Their connection is only implicit — a grade is "in" a curriculum only when at least one `curriculum_topics` row (a 4-way join: curriculum + subject + grade + topic) exists. This means an admin cannot declare "Cambridge Lower Secondary covers Grades 6, 7, 8" without first adding topics.

There is already a perfect architectural analog: `curriculum_subjects` is a direct M:M junction table declaring "which subjects belong to a curriculum." Vibhu wants the same pattern for grades: a `curriculum_grades` junction table so Kaihle Admin can declare curriculum membership at grade creation/editing time, before any topics exist.

**Intended outcome:** When creating or editing a grade, Kaihle Admin selects one or more curricula. This creates rows in `curriculum_grades`. The grade form multi-select reflects current associations and allows adding/removing as new curricula are introduced.

---

## What Changes

### 1. Database — New junction table `curriculum_grades`

**File:** `docs/kaihle_v2_1_schema.sql` — append after `curriculum_subjects` block (line ~224)

```sql
CREATE TABLE curriculum_grades (
    curriculum_id   UUID    NOT NULL REFERENCES curricula (id) ON DELETE CASCADE,
    grade_id        UUID    NOT NULL REFERENCES grades (id)    ON DELETE CASCADE,
    sort_order      INT,
    PRIMARY KEY (curriculum_id, grade_id)
);

COMMENT ON TABLE curriculum_grades IS
    'Which grades belong to a curriculum.
     Mirrors curriculum_subjects pattern.
     Allows admin to declare grade coverage before topics are added.';
```

No `school_id` — this is global/school-agnostic like `curriculum_subjects`.

### 2. Alembic Migration

Generate via:
```bash
cd backend && alembic revision --autogenerate -m "add curriculum_grades junction table"
```

Review generated file to confirm: table creation, composite PK, FKs with CASCADE, sort_order column, secondary index on grade_id, and backfill block.

**Manually add to the generated migration's `upgrade()` function** (after table + index creation):

```python
# Secondary index for fast DELETE by grade_id during full-replace updates
op.create_index("idx_curriculum_grades_grade_id", "curriculum_grades", ["grade_id"])

# Backfill from curriculum_topics — derives existing grade–curriculum associations
# from real topic placements. Pure SQL, no service calls (Constitution Rule 9).
op.execute("""
    INSERT INTO curriculum_grades (curriculum_id, grade_id, sort_order)
    SELECT DISTINCT
        ct.curriculum_id,
        ct.grade_id,
        ROW_NUMBER() OVER (PARTITION BY ct.curriculum_id ORDER BY g.level)
    FROM curriculum_topics ct
    JOIN grades g ON g.id = ct.grade_id
    ON CONFLICT DO NOTHING
""")
```

**Downgrade function:**
```python
op.drop_index("idx_curriculum_grades_grade_id", table_name="curriculum_grades")
op.drop_table("curriculum_grades")
```

### 3. ORM Models

**File:** `backend/app/models/curriculum.py`

Add to `Curriculum` model:
```python
grades: Mapped[list["Grade"]] = relationship(
    "Grade",
    secondary="curriculum_grades",
    back_populates="curricula",
    order_by="curriculum_grades.c.sort_order",
)
```

Add to `Grade` model:
```python
curricula: Mapped[list["Curriculum"]] = relationship(
    "Curriculum",
    secondary="curriculum_grades",
    back_populates="grades",
)
```

### 4. Pydantic Schemas

**File:** `backend/app/schemas/curriculum.py`

**GradeCreate** — add optional field:
```python
curriculum_ids: list[UUID] = Field(default_factory=list, description="Curricula this grade belongs to")
```

**GradeUpdate** — add optional field:
```python
curriculum_ids: list[UUID] | None = Field(None, description="Replace curriculum associations (full replace, not append)")
```

**GradeAdminResponse** — add field:
```python
curriculum_ids: list[UUID] = Field(default_factory=list)
```

Also define a lightweight `GradeCurriculumSummary` for embedding in the response if needed.

### 5. Service Layer

**File:** `backend/app/services/curriculum_service.py`

In `create_grade()`:
- After inserting the grade row, if `curriculum_ids` is non-empty, bulk-insert rows into `curriculum_grades`
- Validate all curriculum_ids exist before insert (raise 422 with detail list if any are invalid)

In `update_grade()`:
- If `curriculum_ids` is provided (not None), do a full replace: delete existing `curriculum_grades` rows for this grade, insert new ones
- If `curriculum_ids` is None, leave associations untouched (partial update semantics)

### 6. API Routes

**File:** `backend/app/api/v1/routes/curriculum.py`

No route signature changes needed — schemas handle the new fields. The list grades endpoint (`GET /grades?curriculum_id=...`) can optionally be updated to query `curriculum_grades` instead of `curriculum_topics` for the filter — but this is a separate concern and not required for this plan.

### 7. Frontend — CreateGradeModal

**File:** `frontend/apps/kaihle-admin/src/components/curriculum/CreateGradeModal.tsx`

Add a multi-select curricula field:
- Fetch available curricula via existing `useCurricula()` hook (or equivalent)
- Render as a multi-select checklist (checkboxes, not a dropdown — matches the small list size ~3–5 curricula)
- Field label: "Curricula" / helper text: "Select all curricula this grade belongs to"
- `curriculum_ids: string[]` added to form state and submit payload
- Not required — grade can be created with no curricula selected

### 8. Frontend — EditGradeModal

**File:** `frontend/apps/kaihle-admin/src/components/curriculum/EditGradeModal.tsx`

Same multi-select checklist field as Create:
- Pre-populate from `grade.curriculum_ids` in the useEffect that seeds form state
- On submit, always send `curriculum_ids` (full replace semantics — whatever is checked becomes the new set)

---

## Files Modified

| File | Change |
|---|---|
| `docs/kaihle_v2_1_schema.sql` | Add `curriculum_grades` table definition |
| `backend/alembic/versions/<new>.py` | Auto-generated migration |
| `backend/app/models/curriculum.py` | Add M:M relationship on Grade + Curriculum |
| `backend/app/schemas/curriculum.py` | Add `curriculum_ids` to GradeCreate, GradeUpdate, GradeAdminResponse |
| `backend/app/services/curriculum_service.py` | Handle curriculum_ids in create/update |
| `frontend/apps/kaihle-admin/src/components/curriculum/CreateGradeModal.tsx` | Add curricula multi-select |
| `frontend/apps/kaihle-admin/src/components/curriculum/EditGradeModal.tsx` | Add curricula multi-select, pre-populate |

---

## Design Decisions

1. **Full replace on update** — when `curriculum_ids` is provided in PATCH, delete all existing rows and insert new. Simpler than diffing, and the list is small (typically ≤5 curricula per grade).
2. **`curriculum_ids` optional on create** — grade can exist without curricula (matches current behavior, no breaking change).
3. **No change to `curriculum_topics`** — this plan adds a declarative layer above it. The topic-level join is unaffected.
4. **Composite PK on `curriculum_grades`** — mirrors `curriculum_subjects`. No separate UUID PK needed.

---

## Verification

1. Run migration: `alembic upgrade head` — confirm `curriculum_grades` table created
2. Unit tests for `create_grade` with `curriculum_ids` — confirm rows in `curriculum_grades`
3. Unit tests for `update_grade` with `curriculum_ids` — confirm full replace behavior
4. Unit test for invalid `curriculum_ids` — confirm 422 returned
5. Manual: Create a grade in KaihleAdmin UI, select curricula, save — verify response includes `curriculum_ids`
6. Manual: Edit the grade, add a curriculum, save — verify association updated
7. Run: `pytest app/tests/unit/ -v && ruff check app/ && mypy app/`
