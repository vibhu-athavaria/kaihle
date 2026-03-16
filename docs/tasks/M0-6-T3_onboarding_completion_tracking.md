# M0-6-T3 — Onboarding Completion Tracking Service
**Milestone:** M0 · **Epic:** M0-6 (Student Onboarding) · **Task:** T3
**Depends on:** M0-6-T1 (learning profile service), M0-6-T2 (Tier 1 trigger)
**Called by:** M1-4-T1 (attempt submit endpoint calls this after Tier 1 submission)

---

## User Story
As the system, when a student submits their last Tier 1 diagnostic, I want to automatically mark their onboarding as complete so the dashboard gate is lifted.

---

## Files to Create / Modify

```
backend/app/services/onboarding_service.py   # extend — add check_and_update_onboarding_complete()
backend/tests/unit/test_onboarding_completion.py
backend/tests/integration/test_onboarding_gate_lift.py
```

---

## Service Method

### `check_and_update_onboarding_complete(student_id: UUID, class_id: UUID) → bool`

This method is called **after every Tier 1 student attempt submission** (from the attempt submit endpoint in M1-4-T1).

```
Logic:
1. Find the Tier 1 diagnostic assessment for this class_id (is_system_generated=TRUE)
2. Check: is the student_attempt for this assessment in status='COMPLETED'?
   - If NOT_COMPLETED → return False (not done yet)
   - If no Tier 1 assessment exists for this class → return False (edge case)
3. If completed:
   UPDATE class_enrollments
   SET onboarding_diagnostic_status = 'COMPLETED'
   WHERE class_id = ? AND student_id = ?
   AND onboarding_diagnostic_status != 'COMPLETED'  -- idempotent guard
   Return True
```

Returns `True` if status was just set to COMPLETED, `False` otherwise.

---

## Where This Is Called

In `POST /api/v1/attempts/{attempt_id}/submit` (M1-4-T1):

```python
async def submit_attempt(attempt_id, current_user, db):
    attempt = await attempt_service.submit(attempt_id, current_user.id)

    # Trigger gap state calculation (always)
    calculate_gap_states.delay(str(attempt_id))

    # NEW v2.1: Check onboarding completion if Tier 1
    assessment = await assessment_service.get(attempt.assessment_id)
    if assessment.is_system_generated:
        await onboarding_service.check_and_update_onboarding_complete(
            current_user.id,
            assessment.class_id
        )

    return attempt
```

**Important:** This is called in the request handler (not async Celery task) because it's a fast DB check (no LLM). The latency impact is negligible.

---

## Onboarding Gate Middleware (Reminder from M0-3-T3)

The `require_onboarding_complete` FastAPI dependency checks BOTH conditions:

```python
async def require_onboarding_complete(current_user, db):
    if current_user.role != 'STUDENT':
        return  # only gates students

    # Check 1: learning profile
    profile = await db.get(StudentLearningProfile, current_user.id)
    if not profile or profile.completed_at is None:
        raise HTTPException(403, {"redirect": "/student/onboarding/profile"})

    # Check 2: Tier 1 diagnostics (v2.1: from class_enrollments)
    # Student is fully onboarded when ALL active class_enrollments are COMPLETED
    status = await get_diagnostic_onboarding_status(current_user.id)
    if status != 'COMPLETED':
        raise HTTPException(403, {"redirect": "/student/onboarding/diagnostics"})
```

This dependency is applied to all student routes EXCEPT `/student/onboarding/*` and `/api/v1/onboarding/*`.

---

## Acceptance Criteria

- [ ] Student has 3 classes with Tier 1 diagnostics, 2 completed → `check_and_update` returns False, statuses stay `IN_PROGRESS` for incomplete classes
- [ ] Student completes final Tier 1 diagnostic → `check_and_update` returns True, `class_enrollments.onboarding_diagnostic_status` = `'COMPLETED'` for that class
- [ ] Calling `check_and_update` again after already COMPLETED → no DB update, returns True (idempotent)
- [ ] Student with zero class enrollments → returns False (no crash)
- [ ] After all enrollments completed, student can access `/student/dashboard` without redirect
- [ ] Before all enrollments completed, student attempting `/student/dashboard` gets 403 with `redirect` field

---

## Tests to Write

```python
test_check_completion_when_2_of_3_classes_complete_then_returns_false()
test_check_completion_when_all_classes_complete_then_returns_true_and_status_updated()
test_check_completion_when_already_completed_then_idempotent()
test_check_completion_when_no_class_enrollments_then_returns_false()
test_onboarding_gate_when_profile_missing_then_403_with_redirect()
test_onboarding_gate_when_diagnostics_incomplete_then_403_with_redirect()
test_onboarding_gate_when_both_complete_then_request_passes_through()
test_onboarding_gate_when_teacher_role_then_no_gate_applied()
```
