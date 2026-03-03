# M0-6-T2 — Tier 1 Auto-Diagnostic Trigger (Celery Task)
**Milestone:** M0 · **Epic:** M0-6 (Student Onboarding) · **Task:** T2
**Depends on:** M0-2-T2 (ORM models), M0-2-T1 (DB migrations — `assessments.is_system_generated`)
**Called by:** M0-4-T3 (enrollment API fires this task)

---

## User Story
As the system, when a student is enrolled in a class, I want to automatically create one Tier 1 diagnostic assessment per subject so the student has something to take on their first login.

---

## Files to Create / Modify

```
backend/app/tasks/onboarding_tasks.py        # new file — Celery task
backend/app/services/assessment_service.py   # add: create_system_diagnostic()
backend/tests/unit/test_onboarding_tasks.py
backend/tests/integration/test_tier1_trigger.py
```

---

## Celery Task

```python
# backend/app/tasks/onboarding_tasks.py

from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def trigger_onboarding_diagnostics(self, student_id: str, class_id: str):
    """
    Fired on student enrollment.
    Creates one DIAGNOSTIC assessment per subject for this student's
    grade + curriculum. Marks is_system_generated=TRUE on each.
    Idempotent — safe to call multiple times.
    """
    ...
```

---

## Task Logic (Step by Step)

```
1. Load class: get curriculum_id, grade_id from classes table
2. Load student: verify student belongs to this school
3. Load subjects for this curriculum:
     SELECT subject_id FROM curriculum_subjects WHERE curriculum_id = ?
4. For each subject:
   a. Check idempotency:
        SELECT id FROM assessments
        WHERE class_id = ? AND is_system_generated = TRUE
          AND subject_id = ?   -- need subject_id on assessment or derive from questions
        If exists → skip this subject (do not create duplicate)
   b. Create assessment row:
        assessments INSERT {
          school_id,
          class_id,
          created_by = NULL,          -- system-created, no teacher owner
          assessment_type = 'DIAGNOSTIC',
          is_system_generated = TRUE,
          status = 'ACTIVE',          -- immediately active, student can start
          curriculum_topic_id = NULL, -- broad sweep, not topic-specific
          title = f"Onboarding Diagnostic — {subject_name} Grade {grade_level}",
          subject_id,
          grade_id,
        }
   c. Select questions:
        - Query question_bank WHERE subject_id = ? AND grade_id = ?
        - Sample up to 20 questions, weighted evenly across curriculum_topics
          (aim for at least 1 question per topic; backfill from largest topics if needed)
        - If total available < 20, use all available
   d. Insert assessment_selected_questions bridge rows
   e. Create student_attempts row:
        {
          assessment_id = new assessment.id,
          student_id,
          status = 'NOT_STARTED'
        }
5. After all subjects processed:
   UPDATE student_profiles
   SET onboarding_diagnostic_status = 'IN_PROGRESS'
   WHERE student_id = ?
   -- Only update if currently 'PENDING' (don't regress if already IN_PROGRESS/COMPLETED)
```

---

## Idempotency Rule
If `trigger_onboarding_diagnostics` is called again for the same student + class (e.g. re-enroll after accidental removal), it must NOT create duplicate assessments. Check per subject before inserting.

---

## Question Weighting Strategy

```python
# Distribute 20 questions across topics evenly
topics = get_curriculum_topics(curriculum_id, subject_id, grade_id)
per_topic = max(1, 20 // len(topics))
remainder = 20 - (per_topic * len(topics))

for topic in topics:
    n = per_topic + (1 if remainder > 0 else 0)
    remainder -= 1
    questions = sample_questions(topic_id=topic.id, n=n)
    selected.extend(questions)
```

---

## Key DB Fields Involved

```sql
-- assessments (v2.1 additions)
is_system_generated   BOOLEAN DEFAULT FALSE   -- set TRUE for Tier 1
created_by            UUID NULLABLE           -- NULL for system-generated

-- student_profiles (v2.1 addition)
onboarding_diagnostic_status  onboarding_status_enum DEFAULT 'PENDING'
```

---

## Acceptance Criteria

- [ ] Student enrolled in a class with 3 subjects → 3 `assessments` rows created, all with `is_system_generated=TRUE`
- [ ] Each assessment has `status='ACTIVE'` and `curriculum_topic_id=NULL`
- [ ] Each assessment has a matching `student_attempts` row with `status='NOT_STARTED'`
- [ ] Questions span all curriculum_topics for the subject+grade (not just one topic)
- [ ] Each assessment has ≤ 20 questions (or all available if bank has fewer)
- [ ] `student_profiles.onboarding_diagnostic_status` set to `'IN_PROGRESS'` after task completes
- [ ] Re-triggering for same student+class → no duplicate assessments created
- [ ] Task retries up to 3 times on DB error
- [ ] `created_by` is NULL on system-generated assessments

---

## Tests to Write

```python
test_trigger_when_3_subjects_then_3_assessments_created()
test_trigger_when_already_triggered_then_no_duplicates()
test_trigger_when_class_has_subject_then_questions_span_all_topics()
test_trigger_when_question_bank_has_5_questions_then_uses_all_5()
test_trigger_when_complete_then_onboarding_status_in_progress()
test_trigger_when_status_already_completed_then_status_not_regressed()
test_trigger_when_db_error_then_task_retries()
test_assessment_created_with_is_system_generated_true()
test_assessment_created_with_created_by_null()
```
