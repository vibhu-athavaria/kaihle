# M6-1-T1 — Analytics Service & Routes

**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-1 — School Admin Analytics Dashboard
**Task ID:** M6-1-T1
**Depends on:** All prior milestones (analytics aggregates data from every feature)
**Blocks:** M6-1-T2 (UI needs these endpoints)

---

## User Story

As a school admin, I want to see a usage dashboard showing how many students are active, how assessments are performing, and what percentage of students have completed onboarding — so I can monitor platform adoption and report to leadership.

---

## What To Build

An analytics service that aggregates counts from across the platform into a single structured response. One API endpoint. All queries scoped by `school_id`.

---

## Files To Create / Modify

```
/backend/app/services/
  analytics_service.py          ← NEW

/backend/app/api/v1/routes/
  analytics.py                  ← NEW

/backend/app/schemas/
  analytics.py                  ← NEW — response schema

/backend/app/api/v1/
  router.py                     ← MODIFY — mount analytics router
```

---

## Analytics Response Schema (`schemas/analytics.py`)

```python
class SubjectMasteryAverage(BaseModel):
    subject_name: str
    avg_mastery: float              # 0.0–1.0
    student_count: int              # students with gap data for this subject

class ClassBreakdown(BaseModel):
    class_id: UUID
    class_name: str
    subject_name: str
    grade_name: str
    teacher_name: str
    student_count: int
    avg_mastery: float | None       # None if no assessments taken yet
    assessments_completed: int

class SchoolAnalytics(BaseModel):
    school_id: UUID
    school_name: str
    generated_at: datetime

    # Students
    total_students: int             # active users with role=STUDENT in this school
    active_students_last_7_days: int  # students with gap_state updated in last 7 days

    # Onboarding (NEW v2.1)
    onboarding_completion_rate: float  # 0.0–1.0 — % fully onboarded students
    students_pending_onboarding: int   # students with status != COMPLETED

    # Assessments
    assessments_completed: int      # COUNT student_attempts WHERE status=COMPLETED
    avg_mastery_by_subject: list[SubjectMasteryAverage]

    # Study Plans
    study_plans_assigned: int
    study_plans_completed: int

    # Teacher Copilot
    lesson_plans_generated: int
    lesson_plans_used: int

    # Parent Portal
    parent_reports_sent: int        # COUNT parent_report_snapshots

    # Class breakdown
    classes: list[ClassBreakdown]
```

---

## `analytics_service.py`

```python
class AnalyticsService:

    async def get_school_analytics(self, school_id: UUID) -> SchoolAnalytics:
        school = await self._get_school(school_id)

        return SchoolAnalytics(
            school_id=school_id,
            school_name=school.name,
            generated_at=datetime.utcnow(),
            total_students=await self._count_total_students(school_id),
            active_students_last_7_days=await self._count_active_students(school_id),
            onboarding_completion_rate=await self._get_onboarding_rate(school_id),
            students_pending_onboarding=await self._count_pending_onboarding(school_id),
            assessments_completed=await self._count_completed_attempts(school_id),
            avg_mastery_by_subject=await self._avg_mastery_by_subject(school_id),
            study_plans_assigned=await self._count_study_plans(school_id),
            study_plans_completed=await self._count_completed_plans(school_id),
            lesson_plans_generated=await self._count_lesson_plans(school_id),
            lesson_plans_used=await self._count_used_lesson_plans(school_id),
            parent_reports_sent=await self._count_parent_reports(school_id),
            classes=await self._get_class_breakdown(school_id),
        )

    async def _get_onboarding_rate(self, school_id: UUID) -> float:
        """
        Onboarding completion rate =
          students WHERE onboarding_diagnostic_status = 'COMPLETED'
            AND EXISTS(learning_profile WHERE completed_at IS NOT NULL)
          / total_students
        """
        total = await self._count_total_students(school_id)
        if total == 0:
            return 0.0

        result = await self.session.execute(
            select(func.count(User.id))
            .join(StudentProfile, StudentProfile.user_id == User.id)
            .join(
                StudentLearningProfile,
                StudentLearningProfile.student_id == User.id,
                isouter=True
            )
            .where(User.school_id == school_id)
            .where(User.role == "STUDENT")
            .where(StudentProfile.onboarding_diagnostic_status == "COMPLETED")
            .where(StudentLearningProfile.completed_at.isnot(None))
        )
        completed = result.scalar_one()
        return round(completed / total, 4)

    async def _avg_mastery_by_subject(self, school_id: UUID) -> list[SubjectMasteryAverage]:
        """
        Average mastery_score per subject, across all gap_states for this school.
        JOIN gap_states → subtopics → curriculum_topics → curriculum_subjects → subjects
        """
        result = await self.session.execute(
            select(
                Subject.name.label("subject_name"),
                func.avg(GapState.mastery_score).label("avg_mastery"),
                func.count(distinct(GapState.student_id)).label("student_count"),
            )
            .join(Subtopic, Subtopic.id == GapState.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(CurriculumSubject, ...)
            .join(Subject, Subject.id == CurriculumSubject.subject_id)
            .where(GapState.school_id == school_id)
            .group_by(Subject.name)
            .order_by(Subject.name)
        )
        return [
            SubjectMasteryAverage(
                subject_name=row.subject_name,
                avg_mastery=round(float(row.avg_mastery), 4),
                student_count=row.student_count,
            )
            for row in result.all()
        ]
```

---

## Endpoint

### `GET /api/v1/schools/{school_id}/analytics`

**Auth:** SchoolAdmin (own school only), KaihleAdmin (any school)

**Response:** `SchoolAnalytics`

**Caching:** Cache in Redis with key `analytics:{school_id}`, TTL 5 minutes. Invalidate on any `PATCH /schools/{school_id}` call.

```python
@router.get("/schools/{school_id}/analytics", response_model=SchoolAnalytics)
async def get_school_analytics(
    school_id: UUID,
    current_user=Depends(get_current_user),
    session=Depends(get_async_session),
    redis=Depends(get_redis),
):
    # Role check
    if current_user.role == "SCHOOL_ADMIN":
        require_school_resource(school_id, current_user)
    elif current_user.role != "KAIHLE_ADMIN":
        raise HTTPException(status_code=403)

    # Check cache
    cache_key = f"analytics:{school_id}"
    cached = await redis.get(cache_key)
    if cached:
        return SchoolAnalytics.model_validate_json(cached)

    service = AnalyticsService(session)
    result = await service.get_school_analytics(school_id)

    await redis.setex(cache_key, 300, result.model_dump_json())
    return result
```

---

## Acceptance Criteria

- [ ] Integration test: school with 5 students, 2 completed assessments → `assessments_completed = 2`
- [ ] Integration test: 3 fully onboarded students out of 5 → `onboarding_completion_rate = 0.6`
- [ ] Integration test: `onboarding_completion_rate` = 0 when no students have completed both profile AND diagnostics
- [ ] Integration test: `avg_mastery_by_subject` returns one entry per subject with real data
- [ ] Integration test: SchoolAdmin calling with their own `school_id` → 200
- [ ] Integration test: SchoolAdmin calling with a different `school_id` → 403
- [ ] Integration test: KaihleAdmin calling any school → 200
- [ ] Integration test: Teacher role calling → 403
- [ ] Performance test: school with 500 students → response in < 1 second (with caching)
- [ ] Unit test: `_get_onboarding_rate` with 0 total students → returns 0.0 (no division by zero)

---

## Output (what M6-1-T2 needs)

- `GET /api/v1/schools/{school_id}/analytics` operational and tested
- `SchoolAnalytics` Pydantic schema importable for UI type generation
- Redis caching working (5-minute TTL)
