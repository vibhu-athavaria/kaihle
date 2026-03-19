# M0-9-T5 — Per-Class Diagnostic Content Gate
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T5
**Depends on:** M0-6-T3 (onboarding completion tracking), M0-6-T4 (onboarding UI), M0-3-T3 (auth middleware)
**Blocks:** M1 must not begin until this task is complete
**Estimated effort:** 3–4 hours

---

## Context

The current implementation gates the entire student dashboard globally — a student
cannot access their dashboard at all until every enrolled class has a completed
Tier 1 diagnostic. This contradicts the authoritative product spec, which defines
two independent gates:

- Gate 1 (global): Dashboard is inaccessible until the learning profile questionnaire
  is complete. Once complete, the student sees their dashboard with all class cards.
- Gate 2 (per-class): Each class card independently shows locked/unlocked state.
  Class content (topics, lesson plans, resources, quizzes) is inaccessible for a
  specific class until that class's Tier 1 diagnostic is complete. A student with
  two enrolled classes can access Class B's content even if Class A's diagnostic
  is still pending.

This task implements Gate 2 correctly on both the backend (API dependency that checks
per-enrollment diagnostic status) and the frontend (class card locked state + routing).

Read `CONSTITUTION.md` Rule 11 (two-layer student onboarding gate) before writing
any code.

---

## User Story

As a student with two enrolled classes, if I have completed the Tier 1 diagnostic for
Mathematics but not for English, I want to be able to access Mathematics topics and
resources immediately while seeing a "complete diagnostic" prompt on my English class
card — without being blocked from my dashboard entirely.

---

## Files to Create / Modify

```
backend/app/core/deps.py                                    ← ADD require_diagnostic_complete
backend/app/api/v1/routes/student_content.py               ← CREATE (or modify existing class content routes)
backend/app/tests/integration/test_diagnostic_gate.py      ← CREATE

frontend/apps/student/src/components/ClassCard.tsx          ← MODIFY: add locked/unlocked states
frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx  ← MODIFY: use per-class status
frontend/apps/student/src/pages/onboarding/OnboardingRouter.tsx ← MODIFY: update gating logic
frontend/apps/student/src/tests/diagnostic-gate.spec.ts     ← CREATE
```

---

## Backend Changes

### `require_diagnostic_complete` dependency (`backend/app/core/deps.py`)

Add a new FastAPI dependency that checks whether a student has completed the Tier 1
diagnostic for a specific class before allowing access to that class's content:

```python
async def require_diagnostic_complete(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> ClassEnrollment:
    """Gate class content access behind Tier 1 diagnostic completion.

    Checks class_enrollments.onboarding_diagnostic_status for the specific
    (student_id, class_id) pair. Returns the enrollment row on success.
    Raises 403 with a structured error body if diagnostic is not yet COMPLETED.

    Only applies to STUDENT role. Teachers and admins bypass this gate.
    """
    # Teachers and admins bypass the gate entirely
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN):
        return None  # Caller ignores the return value for non-student roles

    result = await db.execute(
        select(ClassEnrollment).where(
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.student_id == current_user.id,
            ClassEnrollment.is_active.is_(True),
        )
    )
    enrollment = result.scalar_one_or_none()

    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not enrolled in this class",
        )

    if enrollment.onboarding_diagnostic_status != OnboardingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "DIAGNOSTIC_INCOMPLETE",
                "message": "Complete the diagnostic assessment to access class content.",
                "class_id": str(class_id),
                "diagnostic_status": enrollment.onboarding_diagnostic_status,
            },
        )

    return enrollment
```

### Apply the gate to class content routes

Identify all routes that return class content (topics, lesson plans, resources, quizzes)
and apply `require_diagnostic_complete` as a dependency. These routes are likely in
`backend/app/api/v1/routes/` — the exact file depends on how class content routes were
structured in earlier milestones. Typical endpoints that need gating:

```python
# All of these need: Depends(require_diagnostic_complete)
GET /api/v1/classes/{class_id}/topics
GET /api/v1/classes/{class_id}/topics/{topic_id}
GET /api/v1/classes/{class_id}/topics/{topic_id}/resources
GET /api/v1/classes/{class_id}/topics/{topic_id}/lesson-plan
GET /api/v1/classes/{class_id}/topics/{topic_id}/quizzes
```

The diagnostic itself is NOT gated — students must be able to access
`GET /api/v1/classes/{class_id}/diagnostic` to take the assessment that unlocks content.
Do not apply this dependency to the diagnostic endpoint.

### Update `GET /api/v1/onboarding/status` response

The `OnboardingStatusResponse` schema currently returns `diagnostics_by_class` as
a list of per-class status objects. Verify the existing endpoint returns this structure
correctly — it is the data source the student dashboard and `OnboardingRouter` use
to determine which class cards are locked vs unlocked.

The student dashboard (Gate 1) only needs `learning_profile_complete` from this response
to decide whether to show the dashboard at all. The per-class locked/unlocked state
(Gate 2) is determined by `diagnostics_by_class[n].status` for each enrolled class.

---

## Frontend Changes

### `OnboardingRouter` update (`frontend/apps/student/src/pages/onboarding/OnboardingRouter.tsx`)

The current `OnboardingRouter` blocks access to the dashboard if any diagnostic is
incomplete (`diagnostics_complete = false`). This needs to change so that it only
blocks on the learning profile:

```tsx
// CURRENT (incorrect):
if (!status.learning_profile_complete) → /student/onboarding/profile
if (!status.diagnostics_complete) → /student/onboarding/diagnostics  // ← REMOVE THIS GATE
else → /student/dashboard

// CORRECT:
if (!status.learning_profile_complete) → /student/onboarding/profile
else → /student/dashboard
// Diagnostic status is shown per-class on the dashboard, not as a global blocker
```

The `DiagnosticHub` page (`/student/onboarding/diagnostics`) still exists as a
convenience — a student can navigate there from a locked class card. But it is no
longer an automatic redirect from `OnboardingRouter`. Remove the automatic redirect
to `/student/onboarding/diagnostics` from `OnboardingRouter`.

### `ClassCard` component update (`frontend/apps/student/src/components/ClassCard.tsx`)

Update the `ClassCard` component to support independent locked/unlocked states per
enrollment, plus the three alert types defined in the spec:

```tsx
type DiagnosticStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'

interface ClassCardProps {
  classId: string
  className: string
  subjectName: string
  gradeName: string
  teacherName: string
  diagnosticStatus: DiagnosticStatus
  hasNewMessages: boolean          // alert: new teacher message on classboard
  hasNewProgressCheck: boolean     // alert: new Tier 2 assessment published
  topicCount: number
}
```

Card rendering logic based on `diagnosticStatus`:

When `diagnosticStatus` is `PENDING` or `IN_PROGRESS`, the card shows a locked state.
The card body is rendered at reduced opacity (`opacity-60`). A banner at the bottom
of the card reads "Complete diagnostic to unlock" with a chevron-right icon. Clicking
anywhere on the card routes to the diagnostic assessment page
(`/student/classes/{classId}/diagnostic`), not to the class content. The subject icon
shows a lock overlay.

When `diagnosticStatus` is `COMPLETED`, the card shows a normal unlocked state.
Clicking the card routes to `/student/classes/{classId}/topics`. Alert badges appear
in the top-right corner of the card: a message icon badge if `hasNewMessages` is true,
an assessment icon badge if `hasNewProgressCheck` is true. Both badges can be shown
simultaneously.

The diagnostic alert (locked state) takes visual precedence over message and progress
check alerts — if the diagnostic is not completed, do not show message or progress
check badges. There is nothing actionable about those alerts until the student has
access to the class.

### `StudentDashboard` update

Pass `diagnosticStatus`, `hasNewMessages`, and `hasNewProgressCheck` from the
`OnboardingStatusResponse` (for diagnostic status) and any notification API response
(for message and assessment alerts — these will be stubbed as `false` until the
classboard messaging system is built in a later milestone) to each `ClassCard`.

---

## Tests to Write

### Backend integration tests (`test_diagnostic_gate.py`)

```python
test_class_topics_when_diagnostic_pending_then_returns_403()
test_class_topics_when_diagnostic_in_progress_then_returns_403()
test_class_topics_when_diagnostic_completed_then_returns_200()
test_diagnostic_endpoint_when_diagnostic_pending_then_returns_200()
  # diagnostic taking must never be gated
test_class_topics_when_teacher_role_then_bypasses_gate()
test_class_topics_when_school_admin_role_then_bypasses_gate()
test_class_topics_when_student_not_enrolled_then_returns_404()
```

### Frontend E2E tests (`diagnostic-gate.spec.ts`)

Tests run against `http://localhost:3002`.

```
test: student with completed learning profile but no diagnostics sees dashboard
  (not redirected to /student/onboarding/diagnostics)
test: student dashboard shows locked class card for incomplete diagnostic
test: clicking locked class card routes to diagnostic page, not class content
test: student dashboard shows unlocked class card after diagnostic completion
test: student can access class topics after diagnostic completion
test: student cannot access class topics before diagnostic completion
  (direct URL navigation → 403 response handled gracefully)
```

---

## Acceptance Criteria

- Student with completed learning profile but no diagnostics reaches `/student/dashboard` — not blocked by `OnboardingRouter`
- Dashboard shows locked class cards for classes with incomplete diagnostics
- Dashboard shows unlocked class cards for classes with completed diagnostics
- Clicking a locked class card routes to the diagnostic, not to class content
- `GET /api/v1/classes/{class_id}/topics` returns 403 with `code: DIAGNOSTIC_INCOMPLETE` when diagnostic is not yet completed
- `GET /api/v1/classes/{class_id}/diagnostic` returns 200 regardless of diagnostic status
- Teacher and school admin can access class topics regardless of student diagnostic status
- A student enrolled in two classes can access Class B content independently if Class B diagnostic is complete, even if Class A diagnostic is pending
- All integration tests pass
- All E2E tests pass

---

## Do NOT Touch

- `OnboardingRoute` guard — it handles Gate 1 (learning profile) and must not be changed
- The Tier 1 diagnostic creation Celery tasks — they are correct and unaffected
- Any backend routes that do not return class content (auth, school management, user management, onboarding questionnaire)
