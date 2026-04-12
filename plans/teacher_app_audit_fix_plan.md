# Teacher App Audit Fix Plan

**Scope:** `frontend/apps/teacher/` + `backend/app/api/v1/routes/assessments.py`
**Audit date:** 2026-04-12
**Reference docs:** `docs/design/DESIGN_SYSTEM.md`, `docs/CONSTITUTION.md`
**Type:** Bug fixes + design system compliance (no new features)

---

## Problem Summary

Three categories of issues found during full cross-reference audit:

1. **Missing routes** — 3 navigation links point to non-existent routes in `App.tsx`, causing silent navigation failures
2. **Missing backend APIs** — 2 frontend API calls have no corresponding backend routes
3. **Design system violations** — 15+ instances of non-brand colors, hardcoded px font sizes, emoji icons, incorrect focus ring colors

---

## Phase 1: Missing Routes (Critical)

### 1.1 `/teacher/classes/:classId/gap-map`

**Used by:** `ClassCard.tsx:68`, `PendingActionBanner.tsx:42`
**Current behavior:** Falls through to `/teacher/*` catch-all → renders `TeacherDashboard`. User sees dashboard with no indication anything went wrong.

**Fix in `App.tsx`:**
1. Import `GapMapPage` at top
2. Add to `TeacherContentShell`'s `useMemo` routes array:
   ```tsx
   { path: "classes/:classId/gap-map", element: <GapMapPage /> },
   ```

### 1.2 `/teacher/students/:studentId/profile`

**Used by:** `MyStudents.tsx:34` — `navigate(\`/teacher/students/${studentId}/profile\`)`
**Current behavior:** Same silent fallback to dashboard.

**Fix in `App.tsx`:**
1. Import `StudentProfilePage` at top
2. Add to `TeacherContentShell`'s `useMemo` routes array:
   ```tsx
   { path: "students/:studentId/profile", element: <StudentProfilePage /> },
   ```

### 1.3 `/teacher/classes/:classId/lesson-plans`

**Used by:** `ThisWeekCard.tsx:42` — `<Link to={\`/teacher/classes/${lessonPlan.classId}/lesson-plans\`}>`
**Current behavior:** Same silent fallback to dashboard.

**Fix:**
- If a lesson plans page exists: import it, add route to `TeacherContentShell`
- If not: create stub at `frontend/apps/teacher/src/pages/lesson-plans/LessonPlansPage.tsx` with "Coming soon" messaging, add route

---

## Phase 2: Missing Backend API Endpoints

### 2.1 `DELETE /api/v1/assessments/{assessment_id}`

**Called from:** `useClassAssessments.ts:30`
**Current behavior:** 405 Method Not Allowed or 404

**Add to `backend/app/api/v1/routes/assessments.py`:**

```python
@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a draft assessment. Only assessments with no student attempts can be deleted."""
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    # Teacher must own the class (or be admin)
    if current_user.role == UserRole.TEACHER:
        class_result = await db.execute(select(Class).where(Class.id == assessment.class_id))
        class_ = class_result.scalar_one_or_none()
        if class_ is None or class_.teacher_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role != UserRole.KAIHLE_ADMIN:
        if assessment.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Only allow deletion of assessments with no student attempts
    attempts_result = await db.execute(
        select(StudentAttempt).where(StudentAttempt.assessment_id == assessment_id)
    )
    if attempts_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete assessment that has student attempts. Close it instead.",
        )

    await db.delete(assessment)
    await db.commit()
```

### 2.2 `GET /api/v1/assessments/{assessment_id}/results`

**Called from:** `useAssessmentResults.ts:70-71`
**Current behavior:** 404. `AssessmentResultsPage` shows error state.

**Add schema to `backend/app/schemas/assessments.py`:**

```python
class StudentAttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    attempt_id: UUID = Field(..., alias="attemptId")
    student_id: UUID = Field(..., alias="studentId")
    student_name: str = Field(..., alias="studentName")
    score: float | None = Field(None, alias="score")
    status: str = Field(..., alias="status")
    submitted_at: datetime | None = Field(None, alias="submittedAt")

class AssessmentResultsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    assessment_id: UUID = Field(..., alias="assessmentId")
    assessment_name: str = Field(..., alias="assessmentName")
    assessment_type: str = Field(..., alias="assessmentType")
    total_students: int = Field(..., alias="totalStudents")
    attempts: list[StudentAttemptSummary] = Field(default_factory=list, alias="attempts")
```

**Add route to `backend/app/api/v1/routes/assessments.py`:**

```python
@router.get("/{assessment_id}/results", response_model=AssessmentResultsResponse)
async def get_assessment_results(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResultsResponse:
    """Return all student attempts for an assessment — used by the teacher results page."""
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    # Authorization
    if current_user.role != UserRole.KAIHLE_ADMIN:
        if assessment.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if current_user.role == UserRole.TEACHER:
            class_result = await db.execute(select(Class).where(Class.id == assessment.class_id))
            class_ = class_result.scalar_one_or_none()
            if class_ is None or class_.teacher_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Get all enrollments for the class
    enrollments_result = await db.execute(
        select(ClassEnrollment).where(ClassEnrollment.class_id == assessment.class_id)
    )
    enrollments = enrollments_result.scalars().all()
    total_students = len(enrollments)

    # Get all attempts for this assessment
    attempts_result = await db.execute(
        select(StudentAttempt).where(StudentAttempt.assessment_id == assessment_id)
    )
    attempts = attempts_result.scalars().all()
    attempt_map = {a.student_id: a for a in attempts}

    student_attempts = []
    for enrollment in enrollments:
        student = await db.get(User, enrollment.student_id)
        if student is None:
            continue
        attempt = attempt_map.get(enrollment.student_id)
        if attempt:
            student_attempts.append(StudentAttemptSummary(
                attempt_id=attempt.id,
                student_id=student.id,
                student_name=f"{student.first_name or ''} {student.last_name or ''}".strip() or student.email,
                score=attempt.overall_score,
                status=attempt.status,
                submitted_at=attempt.completed_at,
            ))
        else:
            student_attempts.append(StudentAttemptSummary(
                attempt_id=UUID(int=0),
                student_id=student.id,
                student_name=f"{student.first_name or ''} {student.last_name or ''}".strip() or student.email,
                score=None,
                status="NOT_STARTED",
                submitted_at=None,
            ))

    return AssessmentResultsResponse(
        assessment_id=assessment.id,
        assessment_name=assessment.name or "Untitled Assessment",
        assessment_type=assessment.assessment_type or "DIAGNOSTIC",
        total_students=total_students,
        attempts=student_attempts,
    )
```

---

## Phase 3: Design System Violations

### 3.1 Non-brand color replacements (12 instances)

Per DESIGN_SYSTEM.md §2 and §5.3:

| File | Line(s) | Current | Replacement |
|---|---|---|---|
| `ScoreDistributionChart.tsx` | 57 | `text-green-700` | `text-brand-green` |
| `ScoreDistributionChart.tsx` | 64 | `text-amber-600` | `text-brand-amber` |
| `ScoreDistributionChart.tsx` | 70 | `text-red-600` | `text-brand-red` |
| `ScoreDistributionChart.tsx` | 144 | `bg-amber-50 border border-amber-200` | `bg-brand-amber-light border border-brand-gold-mid` |
| `ScoreDistributionChart.tsx` | 145 | `text-amber-800` | `text-brand-gold-dark` |
| `QuestionBreakdown.tsx` | 38 | `bg-green-50 text-green-700` | `bg-brand-green-light text-brand-green` |
| `QuestionBreakdown.tsx` | 48 | `bg-red-50 text-red-700` | `bg-brand-red-light text-brand-red` |
| `QuestionBreakdown.tsx` | 55 | `bg-green-50 text-green-700` | `bg-brand-green-light text-brand-green` |
| `ResultsKPIRow.tsx` | 190 | `text-red-600` | `text-brand-red` |
| `LearningStyleCard.tsx` | 55 | `bg-amber-50 text-amber-700` | `bg-brand-amber-light text-brand-amber` |
| `GapMapPage.tsx` | 126 | `bg-red-50 text-red-600` | `bg-brand-red-light text-brand-red` |
| `GapMapPage.tsx` | 134 | `bg-gray-100` (skeleton) | `bg-brand-border` |

### 3.2 Focus ring color — Teacher = gold, not green (3 instances)

Per DESIGN_SYSTEM.md §5.3: "Gold is the action color. Green = mastery data ONLY."

| File | Line | Current | Replacement |
|---|---|---|---|
| `GapMapCell.tsx` | 29 | `focus-visible:ring-brand-primary` | `focus-visible:ring-brand-gold` |
| `StudentsTable.tsx` | 100 | `focus:ring-brand-primary` | `focus:ring-brand-gold` |
| `StudentsTable.tsx` | 107 | `focus:ring-brand-primary` | `focus:ring-brand-gold` |

### 3.3 Hardcoded px font sizes (9 instances)

Per DESIGN_SYSTEM.md §10: "No font-size in px — always rem via Tailwind text scale"

| File | Line(s) | Current | Replacement |
|---|---|---|---|
| `ResultsKPIRow.tsx` | 30 | `text-[11px]` | `text-xs` (0.75rem) |
| `ResultsKPIRow.tsx` | 97,108,116,124,140,153,171,189 | `text-[28px]` | `text-3xl` (1.875rem) |

Note: `tracking-[0.08em]` on line 30 stays — it's letter-spacing, not font size.

### 3.4 Emoji icons → Lucide React

Per DESIGN_SYSTEM.md §4: "Lucide React only."

| File | Line(s) | Current | Replacement |
|---|---|---|---|
| `LearningStyleTag.tsx` | 1-5, 27 | Emoji: 👁 👂 📖 🤲 | Lucide: `Eye`, `Headphones`, `Book`, `Hand` |

Empty-state decorative emojis (📊 in `GapMapPage.tsx`, 📋 in `StudentsTable.tsx`, `AssessmentResultsPage.tsx`) are acceptable — non-interactive decoration per §4 empty state pattern.

### 3.5 Already compliant (verified, no changes needed)

- ✅ `getMasteryStyle()` from `@kaihle/types` used correctly everywhere
- ✅ No `@apply` in component files (§10)
- ✅ Google Fonts import in `index.css` correct (§3)
- ✅ Tailwind config tokens match design system (§2)
- ✅ Card `rounded-2xl` consistent
- ✅ `aria-hidden="true"` on decorative icons
- ✅ `aria-label` on interactive elements and mastery indicators
- ✅ Font families: `font-display` (Fraunces) for headings, `font-sans` (Nunito) for body

---

## Phase 4: Double Layout Wrapping

### 4.1 `AssessmentResultsPage` and `StudentResultDetailPage`

**Problem:** Both wrap content in `<DashboardLayout variant="teacher">` but are already rendered inside `TeacherShell` which provides the same layout. Result: **double sidebar + double top nav**.

**Fix (Option A — recommended):** Remove `DashboardLayout` wrapper from both page components. Keep only the page content (back link, header, body). The route structure already provides the layout.

**Affected files:**
- `frontend/apps/teacher/src/pages/assessments/AssessmentResultsPage.tsx` — remove `DashboardLayout` wrapper (~lines 142-159)
- `frontend/apps/teacher/src/pages/assessments/StudentResultDetailPage.tsx` — remove `DashboardLayout` wrapper (~lines 164-170)

Both pages already have their own header sections with back links, so removing the outer `DashboardLayout` won't lose any navigation.

---

## Execution Order

| Step | Phase | Effort | Risk |
|---|---|---|---|
| 1 | Phase 1 (routes) | 10 min | Low |
| 2 | Phase 2.1 (DELETE assessment) | 20 min | Low |
| 3 | Phase 2.2 (GET assessment results) | 30 min | Medium |
| 4 | Phase 4 (double layout) | 10 min | Low |
| 5 | Phase 3.1 (color replacements) | 20 min | Low |
| 6 | Phase 3.2 (focus rings) | 5 min | Low |
| 7 | Phase 3.3 (px → rem) | 5 min | Low |
| 8 | Phase 3.4 (emoji → Lucide) | 15 min | Low |

**Total estimated effort:** ~2 hours

---

## Testing Checklist

- [ ] Click "Gap Map →" on ClassCard → navigates to gap map page
- [ ] Click student in MyStudents → navigates to student profile page
- [ ] Click "View plan →" on ThisWeekCard → navigates to lesson plans page
- [ ] Delete draft assessment → returns 204, removes from list
- [ ] View assessment results → loads student attempt data (not 404)
- [ ] Assessment results page → single sidebar + single top nav
- [ ] Student results detail page → single sidebar + single top nav
- [ ] Error states use brand-red colors
- [ ] Focus rings on gap map cells and student table use gold
- [ ] KPI values use `text-3xl`
- [ ] Learning style tags show Lucide icons
- [ ] Reteach banner uses brand-amber-light / brand-gold-dark
- [ ] `pnpm test` passes
- [ ] `pnpm typecheck` passes
- [ ] `pytest app/tests/unit/` passes
