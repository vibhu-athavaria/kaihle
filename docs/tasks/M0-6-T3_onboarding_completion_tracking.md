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

### `check_and_update_onboarding_complete(student_id: UUID) → bool`

This method is called **after every Tier 1 student attempt submission** (from the attempt submit endpoint in M1-4-T1).

```
Logic:
1. Load all assessments WHERE is_system_generated=TRUE
   joined to student_attempts WHERE student_id = ?
2. Check: are ALL of those attempts in status='COMPLETED'?
   - If any attempt is NOT_STARTED or IN_PROGRESS → return False (not done yet)
   - If zero Tier 1 assessments exist for student → return False (edge case — enrollment task may not have run yet)
3. If all COMPLETED:
   UPDATE student_profiles
   SET onboarding_diagnostic_status = 'COMPLETED'
   WHERE student_id = ?
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
        await onboarding_service.check_and_update_onboarding_complete(current_user.id)

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

    # Check 2: Tier 1 diagnostics
    student_profile = await db.get(StudentProfile, current_user.id)
    if student_profile.onboarding_diagnostic_status != 'COMPLETED':
        raise HTTPException(403, {"redirect": "/student/onboarding/diagnostics"})
```

This dependency is applied to all student routes EXCEPT `/student/onboarding/*` and `/api/v1/onboarding/*`.

---

## Acceptance Criteria

- [ ] Student has 3 Tier 1 diagnostics, 2 completed → `check_and_update` returns False, status stays `IN_PROGRESS`
- [ ] Student completes final Tier 1 diagnostic → `check_and_update` returns True, `onboarding_diagnostic_status` = `'COMPLETED'`
- [ ] Calling `check_and_update` again after already COMPLETED → no DB update, returns True (idempotent)
- [ ] Student with zero Tier 1 assessments → returns False (no crash)
- [ ] After completion, student can access `/student/dashboard` without redirect
- [ ] Before completion, student attempting `/student/dashboard` gets 403 with `redirect` field

---

## Tests to Write

```python
test_check_completion_when_2_of_3_complete_then_returns_false()
test_check_completion_when_all_3_complete_then_returns_true_and_status_updated()
test_check_completion_when_already_completed_then_idempotent()
test_check_completion_when_no_tier1_assessments_then_returns_false()
test_onboarding_gate_when_profile_missing_then_403_with_redirect()
test_onboarding_gate_when_diagnostics_incomplete_then_403_with_redirect()
test_onboarding_gate_when_both_complete_then_request_passes_through()
test_onboarding_gate_when_teacher_role_then_no_gate_applied()
```
