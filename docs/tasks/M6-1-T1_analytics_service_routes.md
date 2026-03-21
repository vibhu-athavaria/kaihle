# M6-1-T1 — Analytics Service + Routes (Stub Replacement)
**Milestone:** M6 · **Epic:** M6-1 · **Task:** T1
**Depends on:** All M1–M5 milestones complete (analytics reads from every feature table)
**Blocks:** M6-1-T2 (analytics dashboard UI calls these endpoints)
**Estimated effort:** 4–5 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/analytics.py` **already exists**. It was created
by M0-10-T6. It contains three stub implementations, each marked:

```python
# STUB — M0-10-T6 | Real implementation: M6-1-T1
# Replace this entire function body. Do not change the signature or response_model.
```

This task replaces those three stub bodies with real service calls. It does **not**
create a new file. It does **not** change any route path, HTTP method, auth
dependency, or response model. Those are frozen by CONSTITUTION Rule 19.

Before writing any code, open the existing file and read every stub. The three stubs
are `get_school_analytics`, `get_platform_stats`, and `impersonate_school`.

Read CONSTITUTION.md Rule 3 (every query must filter by `school_id`) and Rule 12
(KaihleAdmin bypass must be explicit) before writing the service methods.

Redis caching applies to the analytics endpoints — these queries can be expensive
on large classes. Cache with TTL 5 minutes per `school_id`.

---

## User Story

As a school admin, I want a usage analytics dashboard showing how my school is
progressing through onboarding, assessments, and study plans. As KaihleAdmin, I
want platform-wide stats across all schools.

---

## Files to Modify / Create

```
backend/app/api/v1/routes/analytics.py      ← MODIFY: replace stub bodies only
backend/app/services/analytics_service.py   ← CREATE
backend/app/tests/integration/test_analytics_routes.py  ← CREATE
```

---

## `AnalyticsService` — Full Method Signatures

### `get_school_analytics`

```python
async def get_school_analytics(
    self,
    school_id: uuid.UUID,
) -> SchoolAnalytics:
    """Aggregate all usage metrics for one school.

    This method runs multiple COUNT/AVG queries against the feature tables.
    Results are cached in Redis with key 'analytics:{school_id}' and TTL 300s.

    Args:
        school_id: The school to aggregate for. All queries filter by this.
    """
```

Compute the following fields for `SchoolAnalytics`. Each computation is a separate
DB query — do not try to combine them into one monster query. Clarity and correctness
matter more than minimising round-trips here, since the result is cached.

`total_students`: `SELECT COUNT(*) FROM users WHERE school_id = ? AND role = 'STUDENT' AND is_active = TRUE`

`active_students_last_7_days`: Count distinct `student_id` values from `gap_states`
where `last_assessed_at >= now() - interval '7 days'` and `school_id = ?`.

`onboarding_completion_rate`: Count students where `student_profiles.is_learning_profile_complete = TRUE`
AND all their class enrollments have `onboarding_diagnostic_status = 'COMPLETED'`.
Divide by `total_students`. Return as float 0.0–1.0.

`students_pending_onboarding`: `total_students - students_fully_onboarded`.

`assessments_completed`: `SELECT COUNT(*) FROM student_attempts WHERE school_id = ? AND status = 'COMPLETED'`

`study_plans_assigned`: `SELECT COUNT(*) FROM study_plans WHERE school_id = ?`

`study_plans_completed`: `SELECT COUNT(*) FROM study_plans WHERE school_id = ? AND status = 'COMPLETED'`

`lesson_plans_generated`: `SELECT COUNT(*) FROM lesson_plans WHERE school_id = ?`

`lesson_plans_used`: `SELECT COUNT(*) FROM lesson_plans WHERE school_id = ? AND status = 'USED'`

`classes`: One `ClassBreakdown` per class in the school. Each breakdown includes the
teacher's name, the student count, the average mastery score across all `gap_states`
for that class, and the count of completed assessments for that class.

### `get_platform_stats`

```python
async def get_platform_stats(self) -> PlatformStats:
    """Aggregate platform-wide stats across all schools. KaihleAdmin only.

    No school_id filter — reads across the entire database.
    Cached with key 'analytics:platform' and TTL 300s.
    """
```

`total_schools`: `SELECT COUNT(*) FROM schools WHERE status = 'active'`

`total_active_students`: `SELECT COUNT(*) FROM users WHERE role = 'STUDENT' AND is_active = TRUE`

`total_teachers`: `SELECT COUNT(*) FROM users WHERE role = 'TEACHER' AND is_active = TRUE`

`assessments_completed_last_7_days`: Count `student_attempts` where `status = 'COMPLETED'`
and `completed_at >= now() - interval '7 days'`.

### `issue_impersonation_token`

```python
async def issue_impersonation_token(
    self,
    school_id: uuid.UUID,
    kaihle_admin_id: uuid.UUID,
) -> dict:
    """Issue a scoped JWT for KaihleAdmin to browse a school as its admin.

    The token has scope='impersonation' and carries the target school_id.
    It is valid for 2 hours only (much shorter than a normal access token).
    The issuing admin's ID is recorded in the token for audit logging.
    """
    from app.core.security import create_access_token
    token = create_access_token(
        subject=str(kaihle_admin_id),
        extra_claims={
            "scope": "impersonation",
            "impersonated_school_id": str(school_id),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
        expires_delta=timedelta(hours=2),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "impersonated_school_id": str(school_id),
        "expires_in_seconds": 7200,
    }
```

---

## Redis Caching Pattern

Add caching to both analytics methods. Check the Redis cache first; if a hit, return
the cached result directly without touching the DB:

```python
async def get_school_analytics(self, school_id: uuid.UUID) -> SchoolAnalytics:
    cache_key = f"analytics:{school_id}"
    cached = await self.redis.get(cache_key)
    if cached:
        return SchoolAnalytics.model_validate_json(cached)

    # ... run DB queries ...

    result = SchoolAnalytics(...)
    await self.redis.setex(cache_key, 300, result.model_dump_json())
    return result
```

The `AnalyticsService` constructor takes both `db: AsyncSession` and
`redis: Redis` parameters. The route handlers inject both dependencies.

---

## The Three Stubs to Replace

### `get_school_analytics` — `GET /schools/{school_id}/analytics`

Replace the zero-value stub:

```python
redis = request.app.state.redis
service = AnalyticsService(db, redis)
# KaihleAdmin bypass per CONSTITUTION Rule 12
if current_user.role != UserRole.KAIHLE_ADMIN:
    if current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Access denied")
return await service.get_school_analytics(school_id=school_id)
```

### `get_platform_stats` — `GET /platform/stats`

Replace the zero-value stub:

```python
redis = request.app.state.redis
service = AnalyticsService(db, redis)
return await service.get_platform_stats()
```

### `impersonate_school` — `POST /platform/schools/{school_id}/impersonate`

Replace the 501 stub:

```python
service = AnalyticsService(db, request.app.state.redis)
# Verify the target school exists
school = await db.scalar(select(School).where(School.id == school_id))
if not school:
    raise HTTPException(status_code=404, detail="School not found")
return await service.issue_impersonation_token(
    school_id=school_id,
    kaihle_admin_id=current_user.id,
)
```

---

## Acceptance Criteria

**Integration tests — `test_analytics_routes.py`**

`test_school_analytics_when_school_admin_own_school_then_200_with_correct_counts` —
Seed a school with 5 students (3 fully onboarded), 10 completed assessments, and 2
completed study plans. Call `GET /schools/{id}/analytics` as the school admin. Assert
HTTP 200 and verify `total_students == 5`, `assessments_completed == 10`,
`study_plans_completed == 2`. Assert `onboarding_completion_rate == 0.6`.

`test_school_analytics_when_school_admin_other_school_then_403` — Call as a school
admin for a school they don't belong to. Assert HTTP 403.

`test_school_analytics_when_kaihle_admin_any_school_then_200` — Call as KaihleAdmin
for any school. Assert HTTP 200 (the bypass allows this).

`test_school_analytics_is_cached_after_first_call` — Call the endpoint twice. Assert
the Redis mock was called with `get` on the second call and the DB was only queried
once.

`test_school_analytics_classes_breakdown_includes_all_classes` — Seed two classes.
Assert the `classes` list in the response has exactly two entries.

`test_platform_stats_when_kaihle_admin_then_200_with_correct_totals` — Seed two
schools with five students each. Call `GET /platform/stats` as KaihleAdmin. Assert
`total_schools == 2` and `total_active_students == 10`.

`test_platform_stats_when_teacher_then_403` — Call as a teacher. Assert HTTP 403.

`test_impersonate_when_kaihle_admin_then_200_with_token` — Call
`POST /platform/schools/{id}/impersonate` as KaihleAdmin. Assert HTTP 200 and the
response contains an `access_token` string and `impersonated_school_id` matching the
target school.

`test_impersonate_when_school_not_found_then_404` — Call with a non-existent school
UUID. Assert HTTP 404.

`test_impersonate_when_school_admin_then_403` — Call as a school admin. Assert HTTP 403.

`test_onboarding_completion_rate_when_no_students_then_0_0` — Seed a school with no
students. Assert `onboarding_completion_rate == 0.0` (no division by zero crash).

---

## Do NOT Touch

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
in `routes/analytics.py`. The `schemas/analytics.py` file. `backend/app/main.py` —
router already registered.
