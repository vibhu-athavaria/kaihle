# App Isolation Rule — Five Apps, Five Roles, Zero Cross-Contamination

## The Rule

This monorepo contains five separate frontend apps. Each serves exactly one role.
Placing role-specific code in the wrong app is a **critical violation** — stop immediately if you catch yourself doing this.

| App | Port | Role | Directory |
|---|---|---|---|
| teacher | 3001 | TEACHER only | `apps/teacher/` |
| student | 3002 | STUDENT only | `apps/student/` |
| parent | 3003 | PARENT only | `apps/parent/` |
| school-admin | 3004 | SCHOOL_ADMIN only | `apps/school-admin/` |
| kaihle-admin | 3005 | KAIHLE_ADMIN only | `apps/kaihle-admin/` |

## Absolute Prohibitions

- School Admin pages **MUST NOT** live in `apps/teacher/`
- Kaihle Admin pages **MUST NOT** live in `apps/teacher/`
- No app may import directly from another app's `src/` directory
- Role-specific components **MUST NOT** be placed in `packages/ui/` (shared components only)

## Shared Code Lives in `packages/`

| Package | Purpose |
|---|---|
| `packages/ui/` | Shared Tailwind components — used by ALL roles |
| `packages/api-client/` | Shared Axios instance + typed hooks |
| `packages/auth/` | tokenStore, useAuth, PrivateRoute, RoleRoute, OnboardingRoute, PasswordSetupRoute |
| `packages/types/` | Shared TypeScript interfaces + `getMasteryStyle()` |

Any component or utility needed by more than one app belongs in `packages/`, not in any `apps/` directory.

## Before Writing Any Frontend File

Ask: "Does this belong to exactly one role?" 
- Yes → put it in that role's `apps/{role}/src/` directory
- Used by multiple roles → put it in `packages/`
- Unsure → ask before creating the file
