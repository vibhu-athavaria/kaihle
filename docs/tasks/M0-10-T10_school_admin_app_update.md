# M0-10-T10 — Update apps/school-admin to New API Paths
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T10
**Depends on:** M0-10-T7 (backend cutover must complete first)
**Parallel with:** M0-10-T8, T9, T11, T12
**Estimated effort:** 1–2 hours

---

## Pre-Flight Check

```bash
grep -rn "/admin/schools" frontend/apps/school-admin/src/ --include="*.ts" --include="*.tsx"
grep -rn "/enroll" frontend/apps/school-admin/src/ --include="*.ts" --include="*.tsx"
```

---

## Path Substitutions

| Old path | New path |
|---|---|
| `/admin/schools` (prefix) | `/schools` |
| `/admin/schools/{id}/classes` | `/schools/{id}/classes` |
| `/admin/schools/{id}/classes/{cid}/enroll` | `/classes/{cid}/enrollments` |
| `/admin/schools/{id}/classes/{cid}/students` | `/classes/{cid}/enrollments` |

---

## New Hooks to Create

```typescript
// frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
// (Update or create this file — it may already exist from M0-9-T2 migration)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useSchoolAnalytics = (schoolId: string) =>
  useQuery({
    queryKey: ['school-admin', 'analytics', schoolId],
    queryFn: () => apiClient.get(`/schools/${schoolId}/analytics`),
    enabled: !!schoolId,
  })

export const useSchoolClasses = (schoolId: string) =>
  useQuery({
    queryKey: ['school-admin', 'classes', schoolId],
    queryFn: () => apiClient.get(`/schools/${schoolId}/classes`),
    enabled: !!schoolId,
  })

export const useCreateClass = (schoolId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (classData: object) =>
      apiClient.post(`/schools/${schoolId}/classes`, classData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['school-admin', 'classes', schoolId] })
    },
  })
}

export const useEnrollStudents = (classId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (studentIds: string[]) =>
      apiClient.post(`/classes/${classId}/enrollments`, { student_ids: studentIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['school-admin', 'class', classId] })
    },
  })
}
```

---

## Acceptance Criteria

- `grep -rn "/admin/schools" frontend/apps/school-admin/src/` returns zero results
- `grep -rn "/enroll" frontend/apps/school-admin/src/` returns zero results
- `pnpm dev:school-admin` starts without TypeScript compilation errors
- All new hooks are importable without errors
- `tsc --noEmit` passes in `apps/school-admin`

## Do NOT Touch

- Any backend file
- Any other app's frontend files
