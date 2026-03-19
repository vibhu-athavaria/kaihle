# M0-10-T8 — Update apps/student to New API Paths
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T8
**Depends on:** M0-10-T7 (backend cutover must complete first)
**Parallel with:** M0-10-T9, T10, T11, T12
**Estimated effort:** 1–2 hours

---

## Context

M0-10-T7 renamed and restructured the backend routes. The student app's API client
hooks and React Query calls must now reference the new paths. This is a mechanical
update — no logic changes, only URL strings.

The student app calls very few existing endpoints at this stage (it was scaffolded
in M0-7-T3 with placeholder hooks). The primary concern is ensuring the onboarding
flow and any hardcoded API paths are updated, and that the new stub endpoints
(gap map, study plans, assessments, attempts) are wired into the React Query hooks
so M1 frontend work can start from a clean foundation.

---

## Pre-Flight Check

```bash
grep -rn "/admin/schools" frontend/apps/student/src/ --include="*.ts" --include="*.tsx"
grep -rn "/enroll" frontend/apps/student/src/ --include="*.ts" --include="*.tsx"
```

Record every file returned. Every file in the output must be updated in this task.

---

## Files to Modify

```
frontend/apps/student/src/hooks/useStudentDashboard.ts    ← update API paths
frontend/apps/student/src/hooks/useOnboardingStatus.ts    ← verify paths (onboarding unchanged)
frontend/packages/api-client/src/                         ← update any hardcoded paths
```

## Files to Create

```
frontend/apps/student/src/hooks/useGapMap.ts        ← new hook for gap map endpoints
frontend/apps/student/src/hooks/useStudyPlans.ts    ← new hook for study plan endpoints
frontend/apps/student/src/hooks/useAssessments.ts   ← new hook for assessment/attempt endpoints
```

---

## New Hooks to Create

These hooks wire the student app to the new stub endpoints. They will return empty
data now and populate with real data as M1–M3 implement the real business logic.
No frontend component changes are needed — the hooks handle loading and empty states.

### `useGapMap.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useMyGapMap = (subjectId: string) =>
  useQuery({
    queryKey: ['student', 'gap-map', subjectId],
    queryFn: () => apiClient.get(`/students/me/gap-map?subject_id=${subjectId}`),
    enabled: !!subjectId,
  })
```

### `useStudyPlans.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useMyStudyPlans = (filters?: { status?: string; subjectId?: string }) =>
  useQuery({
    queryKey: ['student', 'study-plans', filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters?.status) params.set('status', filters.status)
      if (filters?.subjectId) params.set('subject_id', filters.subjectId)
      return apiClient.get(`/students/me/study-plans?${params}`)
    },
  })
```

### `useAssessments.ts`

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useClassDiagnostic = (classId: string) =>
  useQuery({
    queryKey: ['student', 'diagnostic', classId],
    queryFn: () => apiClient.get(`/classes/${classId}/diagnostic`),
    enabled: !!classId,
  })

export const useAttempt = (attemptId: string) =>
  useQuery({
    queryKey: ['student', 'attempt', attemptId],
    queryFn: () => apiClient.get(`/attempts/${attemptId}`),
    enabled: !!attemptId,
  })

export const useSubmitAttempt = () =>
  useMutation({
    mutationFn: ({ attemptId, answers }: { attemptId: string; answers: object[] }) =>
      apiClient.post(`/attempts/${attemptId}/submit`, { answers }),
  })
```

---

## Path Updates to Apply

For any existing hook or component that references old paths, apply these substitutions.
The onboarding routes (`/onboarding/*`) have not changed — do not modify those.

| Old path | New path |
|---|---|
| `/admin/schools/{id}/classes` | `/schools/{id}/classes` |
| Any path ending in `/enroll` | Replace the call with `POST /classes/{id}/enrollments` |

---

## Acceptance Criteria

- `grep -rn "/admin/schools" frontend/apps/student/src/` returns zero results
- `grep -rn "/enroll" frontend/apps/student/src/` returns zero results
- `pnpm dev:student` starts without TypeScript compilation errors
- `useMyGapMap`, `useMyStudyPlans`, `useClassDiagnostic` are importable from their hook files
- `tsc --noEmit` passes in `apps/student`

## Do NOT Touch

- Any backend file
- Any other app's frontend files
- The onboarding hooks — `/onboarding/*` paths have not changed
