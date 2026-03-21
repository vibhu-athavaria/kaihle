# M2-1-T2 — Gap Map API Routes (Stub Replacement)
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T2
**Depends on:** M2-1-T1 (GapService methods must exist before routes call them)
**Blocks:** M2-1-T3 (teacher UI), M2-1-T4 (student UI)
**Estimated effort:** 3–4 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/gap_map.py` already exists. It was created by
M0-10-T2 as part of the API Contract Finalization phase. It contains four stub
implementations, each marked with a comment:

```python
# STUB — M0-10-T2 | Real implementation: M2-1-T2
# Replace this entire function body. Do not change the signature or response_model.
```

This task replaces those four function bodies with real service calls. It does not
create a new file. It does not register a new router (already done). It does not
change any route path, HTTP method, auth dependency, query parameter definition, or
response model. Those are frozen by CONSTITUTION Rule 19.

Before writing any code, open the existing file and read it. Identify the four stubs.
Replace only their bodies.

One important clarification about the parent role: parents do not call
`GET /students/{student_id}/gap-map`. That endpoint's auth rules cover Student,
Teacher, SchoolAdmin, and KaihleAdmin only. Parents access their child's gap data
through the parent portal endpoint `GET /parent/children/{student_id}/gap-map`
(stub in `routes/parent.py`, real implementation in M5-1-T2). Do not add parent
authorization logic here.

---

## User Story

As a teacher, I want to call a gap map endpoint and receive real aggregated mastery
data for my class so I can see which students need help with which subtopics.

---

## Files to Modify (NOT Create)

```
backend/app/api/v1/routes/gap_map.py         ← MODIFY: replace stub bodies only
backend/app/tests/integration/test_gap_map_routes.py  ← CREATE
```

---

## The Four Stubs to Replace

### Stub 1: `get_class_gap_map` — `GET /classes/{class_id}/gap-map`

Replace stub body with:

```python
service = GapService(db)
try:
    result = await service.get_class_gap_map(
        class_id=class_id,
        school_id=current_user.school_id,
        subject_id=subject_id,
    )
except ValueError as e:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# Teacher access check: must own the class
# (KaihleAdmin and SchoolAdmin bypass this — their school_id already scopes the query)
if current_user.role == UserRole.TEACHER:
    class_ = await db.scalar(
        select(Class).where(Class.id == class_id)
    )
    if class_ and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view gap maps for your own classes",
        )

return result
```

### Stub 2: `get_class_summary` — `GET /classes/{class_id}/summary`

Replace stub body with:

```python
service = GapService(db)
try:
    return await service.get_class_summary(
        class_id=class_id,
        school_id=current_user.school_id,
    )
except ValueError as e:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

### Stub 3: `get_my_gap_map` — `GET /students/me/gap-map`

The `/me` shortcut resolves to the authenticated student's own ID. Replace stub body
with:

```python
service = GapService(db)
return await service.get_student_gap_map(
    student_id=current_user.id,
    school_id=current_user.school_id,
    subject_id=subject_id,
)
```

### Stub 4: `get_student_gap_map` — `GET /students/{student_id}/gap-map`

This endpoint requires role-based authorization beyond what `require_full_access`
provides — specifically, a Teacher can only view students enrolled in their own
class, not any arbitrary student. Replace stub body with:

```python
# Authorization per role:
# STUDENT: can only view their own gap map
if current_user.role == UserRole.STUDENT:
    if current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only view their own gap map",
        )

# TEACHER: can only view students enrolled in one of their classes
elif current_user.role == UserRole.TEACHER:
    enrollment = await db.scalar(
        select(ClassEnrollment)
        .join(Class, Class.id == ClassEnrollment.class_id)
        .where(
            ClassEnrollment.student_id == student_id,
            Class.teacher_id == current_user.id,
            Class.school_id == current_user.school_id,
        )
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view gap maps for students in your classes",
        )

# SCHOOL_ADMIN: can view any student in own school — school_id scoping in service handles this
# KAIHLE_ADMIN: unrestricted — no extra check needed

service = GapService(db)
return await service.get_student_gap_map(
    student_id=student_id,
    school_id=current_user.school_id,
    subject_id=subject_id,
)
```

---

## Frozen Contracts (Do Not Change These)

These are documented here for reference only — they are already in the file.

`GET /classes/{class_id}/gap-map` — query params: `subject_id` (UUID, required).
Auth: Teacher, SchoolAdmin, KaihleAdmin. Response: `ClassGapMap`.

`GET /classes/{class_id}/summary` — no query params. Auth: Teacher, SchoolAdmin,
KaihleAdmin. Response: `ClassSummary`.

`GET /students/me/gap-map` — query params: `subject_id` (UUID, required). Auth:
Student only. Response: `StudentGapMap`.

`GET /students/{student_id}/gap-map` — query params: `subject_id` (UUID, required).
Auth: Student (own), Teacher (own class students), SchoolAdmin, KaihleAdmin.
Response: `StudentGapMap`.

---

## Acceptance Criteria

All tests go in `test_gap_map_routes.py`. Each test description includes what to seed,
what to call, and what to assert.

`test_class_gap_map_when_teacher_owns_class_then_200_with_nodes` — Seed a class
assigned to teacher A with 3 enrolled students, each with `gap_state` rows. Authenticate
as teacher A. Call `GET /classes/{id}/gap-map?subject_id={uuid}`. Assert HTTP 200 and
`nodes` is non-empty with correct `class_average` values.

`test_class_gap_map_when_teacher_does_not_own_class_then_403` — Authenticate as teacher
B and call the gap map for a class belonging to teacher A. Assert HTTP 403.

`test_class_gap_map_when_student_role_then_403` — Authenticate as a student and call
`GET /classes/{id}/gap-map`. Assert HTTP 403.

`test_class_gap_map_when_missing_subject_id_then_422` — Call `GET /classes/{id}/gap-map`
with no `subject_id` query param. Assert HTTP 422 (FastAPI's required parameter
validation).

`test_class_gap_map_when_school_admin_other_school_then_404` — Authenticate as a
SchoolAdmin from school B, call the gap map for a class in school A. Assert HTTP 404
(the class is not found within the school — not a 403 that would leak the class exists).

`test_class_summary_when_teacher_owns_class_then_200` — Seed a class with 5 enrolled
students and gap states for 3. Assert HTTP 200 with `student_count=5` and
`assessed_student_count=3`.

`test_my_gap_map_when_authenticated_student_then_200_with_own_data` — Authenticate
as student A. Call `GET /students/me/gap-map?subject_id={uuid}`. Assert HTTP 200 and
every `StudentSubtopicScore` in the response belongs to student A (verify by checking
the `student_id` field in the `StudentGapMap` response equals student A's ID).

`test_student_gap_map_when_own_student_then_200` — Authenticate as a student and call
`GET /students/{own_id}/gap-map`. Assert HTTP 200.

`test_student_gap_map_when_different_student_then_403` — Authenticate as student A
and call `GET /students/{student_B_id}/gap-map`. Assert HTTP 403.

`test_student_gap_map_when_teacher_own_class_student_then_200` — Authenticate as a
teacher. Call the gap map for a student enrolled in one of their classes. Assert HTTP 200.

`test_student_gap_map_when_teacher_other_class_student_then_403` — Authenticate as
teacher A. Call the gap map for a student enrolled only in teacher B's class. Assert
HTTP 403.

`test_student_gap_map_when_parent_role_then_403` — Authenticate as a parent and call
`GET /students/{child_id}/gap-map`. Assert HTTP 403. (Parents use
`GET /parent/children/{id}/gap-map` instead — see M5-1-T2.)

---

## Do NOT Touch

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
call in `routes/gap_map.py` — these are frozen by CONSTITUTION Rule 19.
`backend/app/schemas/gap_map.py` — do not modify. `backend/app/main.py` — the
router is already registered; do not re-register.
