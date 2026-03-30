# M0-7-T3-patch Consolidation Plan
**Date:** 2026-03-30
**Status:** Ready for execution

## Problem Statement

The M0-7-T3-patch sub-tasks implemented fixes across multiple files, but each sub-task was pushed to its own separate branch:

| Branch | Contains |
|--------|----------|
| `M0-7-T3-patch_fix/student-layout-v2-1-sidebar` | StudentLayout.tsx, index.ts exports, StudentLayout.test.tsx |
| `M0-7-T3-patch_fix/dashboard-hooks` | useStudentInfo.ts |
| `M0-7-T3-patch_fix/subject-scores-section` | SubjectScoresSection.tsx, useSubjectScores.ts |
| `M0-7-T3-patch_fix/class-card-data` | useMyClasses.ts (already had subjectId) |
| `M0-7-T3-patch_fix/next-steps-rendering` | StudentDashboard.tsx |
| `M0-7-T3-patch_fix/student-layout-v2-1-sidebar` (backend) | backend/app/api/v1/routes/students.py |

**Per AGENTS.md:** "A task is NOT complete until... Branch is pushed to origin. A Pull Request is opened against main with a title matching the branch name."

Multiple scattered PRs violate this requirement.

---

## Files That Need to Be Consolidated

### Frontend (packages/ui)
1. `packages/ui/src/layouts/StudentLayout.tsx` - v2.1 sidebar layout
2. `packages/ui/src/layouts/index.ts` - export StudentLayout
3. `packages/ui/src/layouts/__tests__/StudentLayout.test.tsx` - tests

### Frontend (apps/student)
4. `apps/student/src/hooks/useStudentInfo.ts` - student info hook
5. `apps/student/src/hooks/useMyClasses.ts` - enrolled classes hook
6. `apps/student/src/hooks/useSubjectScores.ts` - gap-map hook
7. `apps/student/src/pages/dashboard/SubjectScoresSection.tsx` - subject scores section
8. `apps/student/src/pages/dashboard/StudentDashboard.tsx` - main dashboard

### Backend
9. `backend/app/api/v1/routes/students.py` - N+1 fix (already has subjectId in response)

---

## Consolidation Strategy

### Step 1: Create consolidation branch
```bash
git checkout main
git pull origin main
git checkout -b M0-7-T3-patch_fix/student-dashboard
```

### Step 2: Cherry-pick commits from each scattered branch
```bash
# Get commit hashes from each branch (execute in code mode)
git cherry-pick <commit-from-student-layout-v2-1-sidebar>
git cherry-pick <commit-from-dashboard-hooks>
git cherry-pick <commit-from-subject-scores-section>
git cherry-pick <commit-from-class-card-data>
git cherry-pick <commit-from-next-steps-rendering>
git cherry-pick <commit-from-backend-fix>
```

### Step 3: Resolve conflicts if any
Each branch touched different files, so conflicts should be minimal.

### Step 4: Force push consolidated branch (optional - overwrite scattered branches)
```bash
git push origin M0-7-T3-patch_fix/student-dashboard --force
```

### Step 5: Open single PR
```
Title: M0-7-T3-patch_fix/student-dashboard
Body: Implements Fix 1-5 for M0-7-T3-patch:
- Fix 1: StudentLayout v2.1 sidebar (packages/ui)
- Fix 2: useStudentInfo hook + StudentDashboard uses StudentLayout
- Fix 3: SubjectScoresSection with onScoresResolved callback
- Fix 4: ClassCard data from useMyClasses()
- Fix 5: NextSteps always renders with EmptyNextSteps
```

---

## Alternative Strategy (If Cherry-pick Fails)

If cherry-picking proves difficult due to commit ordering or conflicts:

1. Manually verify all files exist on main with correct content
2. If files need updating, switch to code mode and make surgical edits
3. Commit all changes to single consolidation branch

---

## Verification Checklist

After consolidation:
- [ ] All 9 files above are committed to single branch
- [ ] Branch name matches pattern: `M0-7-T3-patch_fix/student-dashboard`
- [ ] Single PR opened against `main`
- [ ] PR title matches branch name
- [ ] `git status` is clean on the consolidation branch
- [ ] Tests pass

---

## Files Content Summary

### StudentLayout.tsx (packages/ui)
- Props: `activeNav`, `classes[]`, `studentName`, `gradeName`, `curriculumName`, `onLogout`
- Sidebar: 200px, LEARN nav, CLASSES dynamic, profile card
- Top nav: greeting + avatar

### useStudentInfo.ts (apps/student)
- Fetches `GET /api/v1/students/me/info`
- Returns: `id`, `first_name`, `last_name`, `grade_name`, `curriculum_name`, `school_id`

### useMyClasses.ts (apps/student)
- Already has `subjectId` and `subjectName` fields
- Returns: `StudentClassResponse[]` with full class details

### SubjectScoresSection.tsx (apps/student)
- Props: `subjects[]`, `onScoresResolved?` callback
- Renders grid of subject score cards
- Fires `onScoresResolved(scores[])` when all subjects resolve

### StudentDashboard.tsx (apps/student)
- Uses `StudentLayout` with proper props
- Renders `SubjectScoresSection` with `handleScoresResolved` callback
- Builds unique subjects from `classesData`
- `buildNextSteps()` includes subject scores for weakest-area logic
- Always renders "What's waiting for you" section (uses `EmptyNextSteps` if empty)

### useSubjectScores.ts (apps/student)
- `useSubjectGapMap(subjectId)` - fetches gap-map for one subject
- `aggregateSubjectMastery(gapMapData)` - averages mastery scores

### students.py (backend)
- `subject_id` field already in `StudentClassResponse`
- N+1 query fix applied
