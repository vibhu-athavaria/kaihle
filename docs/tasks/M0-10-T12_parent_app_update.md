# M0-10-T12 — Update apps/parent to New API Paths
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T12
**Depends on:** M0-10-T7 (backend cutover must complete first)
**Parallel with:** M0-10-T8, T9, T10, T11
**Estimated effort:** 1 hour

---

## Pre-Flight Check

```bash
grep -rn "/admin/schools" frontend/apps/parent/src/ --include="*.ts" --include="*.tsx"
grep -rn "/enroll" frontend/apps/parent/src/ --include="*.ts" --include="*.tsx"
```

The parent app likely has zero references to school or enrollment paths since parents
do not manage school data. Run the check anyway — if output is empty, no path updates
are needed and this task is solely about creating the new hooks.

---

## New Hooks to Create

The parent app has no existing API hooks for child progress data (the backend stubs
were created in M0-10-T6). Create the full set of parent data hooks here.

```typescript
// frontend/apps/parent/src/hooks/useParentData.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useMyChildren = () =>
  useQuery({
    queryKey: ['parent', 'children'],
    queryFn: () => apiClient.get('/parent/children'),
  })

export const useChildReports = (studentId: string, page = 1) =>
  useQuery({
    queryKey: ['parent', 'reports', studentId, page],
    queryFn: () =>
      apiClient.get(`/parent/children/${studentId}/reports?page=${page}&page_size=10`),
    enabled: !!studentId,
  })

export const useChildGapMap = (studentId: string) =>
  useQuery({
    queryKey: ['parent', 'gap-map', studentId],
    queryFn: () => apiClient.get(`/parent/children/${studentId}/gap-map`),
    enabled: !!studentId,
    // NOTE: the response from this endpoint contains NO numeric mastery scores.
    // Only plain-language labels ("Strong", "Developing", "Needs Work").
    // Do not try to display percentages from this data — the backend intentionally
    // omits them for the parent-facing API.
  })
```

---

## Acceptance Criteria

- `grep -rn "/admin/schools" frontend/apps/parent/src/` returns zero results
- `pnpm dev:parent` starts without TypeScript compilation errors
- All three new hooks are importable without errors
- `tsc --noEmit` passes in `apps/parent`
- The comment in `useChildGapMap` is present — it is documentation for future
  developers reminding them of the no-scores constraint

## Do NOT Touch

- Any backend file
- Any other app's frontend files
