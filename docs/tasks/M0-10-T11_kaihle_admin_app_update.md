# M0-10-T11 — Update apps/kaihle-admin to New API Paths
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T11
**Depends on:** M0-10-T7 (backend cutover must complete first)
**Parallel with:** M0-10-T8, T9, T10, T12
**Estimated effort:** 1 hour

---

## Pre-Flight Check

```bash
grep -rn "/admin/schools" frontend/apps/kaihle-admin/src/ --include="*.ts" --include="*.tsx"
```

Note: kaihle-admin is less likely to use old paths since its pages were scaffolded
after the architecture review (M0-9-T3), but the pre-flight check is mandatory.

---

## Path Substitutions

| Old path | New path |
|---|---|
| `/admin/schools` (prefix) | `/schools` |
| `/admin/platform/stats` | `/platform/stats` |

---

## New Hooks to Create

```typescript
// frontend/apps/kaihle-admin/src/hooks/useKaihleAdmin.ts
// (Update or create — may already exist from M0-9-T3 migration)
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const usePlatformStats = () =>
  useQuery({
    queryKey: ['kaihle-admin', 'platform-stats'],
    queryFn: () => apiClient.get('/platform/stats'),
    // Refetch every 5 minutes — this is a dashboard metric
    staleTime: 5 * 60 * 1000,
  })

export const useAllSchools = (page = 1, pageSize = 20) =>
  useQuery({
    queryKey: ['kaihle-admin', 'schools', page, pageSize],
    queryFn: () =>
      apiClient.get(`/schools?page=${page}&page_size=${pageSize}`),
  })

export const useImpersonateSchool = () =>
  useMutation({
    mutationFn: (schoolId: string) =>
      apiClient.post(`/platform/schools/${schoolId}/impersonate`, {}),
    // On success: store the impersonation token separately and redirect
    // to the school-admin app. Full implementation in M6.
  })
```

---

## Acceptance Criteria

- `grep -rn "/admin/schools" frontend/apps/kaihle-admin/src/` returns zero results
- `grep -rn "/admin/platform" frontend/apps/kaihle-admin/src/` returns zero results
- `pnpm dev:kaihle-admin` starts without TypeScript compilation errors
- All new hooks are importable without errors
- `tsc --noEmit` passes in `apps/kaihle-admin`

## Do NOT Touch

- Any backend file
- Any other app's frontend files
