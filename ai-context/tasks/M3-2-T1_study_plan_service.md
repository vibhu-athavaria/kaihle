# M3-2-T1 — Study Plan Service
**Milestone:** M3 · **Epic:** M3-2 · **Task:** T1
**Depends on:** M3-1-T1 (content curator), M3-1-T2 (quiz generator), M0-2-T2 (ORM models)

---

## User Story
As the system, I want to orchestrate the creation of a complete personalised study plan — resources + quiz — for a student's identified gap.

---

## Files to Create / Modify

```
backend/app/services/study_plan_service.py
backend/app/tasks/study_plan_tasks.py        # async Celery task for generation
backend/app/schemas/study_plan.py
backend/tests/unit/test_study_plan_service.py
backend/tests/integration/test_study_plan_creation.py
```

---

## Schemas

```python
class StudyPlanCreate(BaseModel):
    student_id: UUID
    subtopic_id: UUID
    class_id: UUID
    school_id: UUID
    assigned_by: UUID   # teacher_id

class StudyPlanResponse(BaseModel):
    id: UUID
    student_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    subject_name: str
    status: StudyPlanStatus       # GENERATING | ACTIVE | COMPLETED | ABANDONED
    resources: list[ResourceItem]
    quiz: QuizItem | None         # None while still GENERATING
    assigned_at: datetime
    assigned_by_name: str
```

---

## Service: `create_study_plan(config: StudyPlanCreate) → StudyPlanResponse`

```python
async def create_study_plan(config: StudyPlanCreate, db, redis) -> StudyPlanResponse:
    # 1. Create study_plans row with status='GENERATING'
    plan = StudyPlan(
        student_id=config.student_id,
        subtopic_id=config.subtopic_id,
        class_id=config.class_id,
        school_id=config.school_id,
        assigned_by=config.assigned_by,
        status=StudyPlanStatus.GENERATING,
    )
    db.add(plan)
    await db.flush()   # get plan.id

    # 2. Queue Celery task for async resource + quiz generation
    generate_study_plan_content.delay(str(plan.id))

    # 3. Return immediately (status=GENERATING)
    return StudyPlanResponse(id=plan.id, status="GENERATING", resources=[], quiz=None, ...)
```

---

## Celery Task: `generate_study_plan_content(plan_id)`

```python
@shared_task(bind=True, max_retries=2)
def generate_study_plan_content(self, plan_id: str):
    plan = load_plan(plan_id)
    subtopic = load_subtopic(plan.subtopic_id)
    mastery = get_student_mastery(plan.student_id, plan.subtopic_id)

    # 1. Curate resources (with learning profile weighting)
    resources = await curate_resources(subtopic, plan.student_id, plan.school_id, ...)
    if not resources:
        log.warning("no_resources_found", plan_id=plan_id, subtopic=subtopic.name)
        # Continue — plan created with 0 resources, quiz still generated

    # 2. Generate quiz (with interest injection)
    quiz = await generate_quiz(subtopic, mastery, plan.student_id, ...)

    # 3. Store resources in study_plan_resources
    for i, resource in enumerate(resources):
        db.add(StudyPlanResource(
            study_plan_id=plan.id,
            url=resource.url,
            title=resource.title,
            resource_type=resource.resource_type,
            alignment_score=resource.final_score,
            position=i + 1,
        ))

    # 4. Store quiz in study_plan_quizzes
    db.add(StudyPlanQuiz(
        study_plan_id=plan.id,
        questions=serialise(quiz.questions),
    ))

    # 5. Update plan status to ACTIVE
    plan.status = StudyPlanStatus.ACTIVE
    await db.commit()
```

---

## Service: `create_bulk_study_plans(class_id, subtopic_id, student_ids, assigned_by)`

Called when teacher assigns a plan to multiple students at once:
```python
plans = []
for student_id in student_ids:
    plan = await create_study_plan(StudyPlanCreate(
        student_id=student_id,
        subtopic_id=subtopic_id,
        class_id=class_id,
        ...
    ))
    plans.append(plan)
return plans
```

Each student gets their own individually personalised plan (different resources/quiz based on their profile).

---

## Service: `submit_quiz(plan_id, student_id, responses) → QuizResult`

```python
async def submit_quiz(plan_id, student_id, responses, db):
    plan = await validate_plan_ownership(plan_id, student_id)
    quiz = await load_quiz(plan_id)

    # Score each response
    results = []
    for resp in responses:
        question = quiz.questions[resp.question_index]
        scored = scoring_service.score_response(question, resp.answer)
        results.append(scored)

    # Update quiz record
    total_score = mean(r.score for r in results if r.score is not None)
    quiz.score = total_score
    quiz.submitted_at = now()

    # Update plan status
    plan.status = StudyPlanStatus.COMPLETED

    # Trigger gap state recalculation
    # Create a synthetic "attempt" context for gap_states update
    update_gap_state_from_quiz.delay(str(plan.id), str(plan.subtopic_id))

    return QuizResult(score=total_score, results=results)
```

---

## Acceptance Criteria

- [ ] `create_study_plan` returns immediately with `status=GENERATING`
- [ ] Celery task completes → plan status changes to `ACTIVE`, resources + quiz stored
- [ ] Resources reflect student's dominant modality (video for visual learners)
- [ ] Quiz prompt includes interests for students with non-empty interests
- [ ] Curator returns 0 resources → plan created with warning, quiz still generated
- [ ] `create_bulk_study_plans` for 5 students → 5 separate plans, each personalised
- [ ] Quiz submission → `study_plan_quizzes.score` updated, plan status `COMPLETED`
- [ ] Quiz submission triggers gap state update

---

## Tests to Write

```python
test_create_study_plan_returns_generating_status_immediately()
test_generate_task_when_complete_then_plan_status_active()
test_generate_task_when_student_visual_then_video_resources_stored()
test_generate_task_when_no_resources_then_plan_still_completes()
test_bulk_create_when_5_students_then_5_separate_plans()
test_submit_quiz_when_valid_then_score_stored_and_plan_completed()
test_submit_quiz_triggers_gap_state_update()
```
