# M0-10-T9 — Update apps/teacher to New API Paths
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T9
**Depends on:** M0-10-T7 (backend cutover must complete first)
**Parallel with:** M0-10-T8, T10, T11, T12
**Estimated effort:** 1–2 hours

---

## Pre-Flight Check

Run before touching any file. Record every file returned — all must be updated.

```bash
grep -rn "/admin/schools" frontend/apps/teacher/src/ --include="*.ts" --include="*.tsx"
grep -rn "/enroll" frontend/apps/teacher/src/ --include="*.ts" --include="*.tsx"
```

---

## Path Substitutions

Apply to every file identified in the pre-flight check.

| Old path | New path |
|---|---|
| `/admin/schools` (prefix) | `/schools` |
| `/admin/schools/{id}/classes` | `/schools/{id}/classes` |
| `/admin/schools/{id}/classes/{cid}/enroll` | `/classes/{cid}/enrollments` |
| `/admin/schools/{id}/classes/{cid}/students` | `/classes/{cid}/enrollments` |

---

## New Hooks to Create

Create the following hooks so the teacher app can call the new stub endpoints
from M0-10-T2 through T5. These return empty data now and populate in M2–M4.

```typescript
// frontend/apps/teacher/src/hooks/useClassData.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useClassSummary = (classId: string) =>
  useQuery({
    queryKey: ['teacher', 'class-summary', classId],
    queryFn: () => apiClient.get(`/classes/${classId}/summary`),
    enabled: !!classId,
  })

export const useClassGapMap = (classId: string, subjectId: string) =>
  useQuery({
    queryKey: ['teacher', 'gap-map', classId, subjectId],
    queryFn: () =>
      apiClient.get(`/classes/${classId}/gap-map?subject_id=${subjectId}`),
    enabled: !!(classId && subjectId),
  })

export const useClassAssessments = (classId: string) =>
  useQuery({
    queryKey: ['teacher', 'assessments', classId],
    queryFn: () => apiClient.get(`/classes/${classId}/assessments`),
    enabled: !!classId,
  })

export const useClassLessonPlans = (classId: string) =>
  useQuery({
    queryKey: ['teacher', 'lesson-plans', classId],
    queryFn: () => apiClient.get(`/classes/${classId}/lesson-plans`),
    enabled: !!classId,
  })

export const useEnrollStudents = (classId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (studentIds: string[]) =>
      apiClient.post(`/classes/${classId}/enrollments`, { student_ids: studentIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'class', classId] })
    },
  })
}
```

---

## Acceptance Criteria

- `grep -rn "/admin/schools" frontend/apps/teacher/src/` returns zero results
- `grep -rn "/enroll" frontend/apps/teacher/src/` returns zero results
- `pnpm dev:teacher` starts without TypeScript compilation errors
- All new hooks are importable without errors
- `tsc --noEmit` passes in `apps/teacher`

## Do NOT Touch

- Any backend file
- Any other app's frontend files
