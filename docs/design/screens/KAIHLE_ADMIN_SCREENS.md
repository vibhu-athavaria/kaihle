# Kaihle Admin Role — Screen Design Specifications
**Design sprint:** March 2026  
**Personas:** Kramer (engineering focus) · Pixel (UI/UX) · Vidhya (information hierarchy)  
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.1  
**App:** `apps/kaihle-admin` · port 3005  
**Layout wrapper:** `AdminLayout`  
**Font:** Inter ONLY — no Fraunces, no Lora anywhere  
**Action color:** Green `#1a5c38`  
**Page background:** Cool `#f8f9fb`  
**Sidebar active state:** Gray fill + green dot (`bg-gray-100 text-role-admin-ink` + `w-1.5 h-1.5 rounded-full bg-brand-primary`)  
**Borders:** Neutral `#e2e8f0`

---

## Page inventory

| # | Page | Route | Task file | Status |
|---|---|---|---|---|
| 1 | Platform overview | `/kaihle-admin/overview` | `M0-7-T5` | ✅ Designed |
| 2 | Schools list | `/kaihle-admin/schools` | `M0-7-T5` | ✅ Designed |
| 3 | School detail | `/kaihle-admin/schools/:id` | `M0-7-T5` | ✅ Designed |
| 4 | Platform billing | `/kaihle-admin/billing` | None — NEW | ✅ Designed |
| 5 | System logs | `/kaihle-admin/logs` | None — NEW | ✅ Designed |
| 6 | Config | `/kaihle-admin/config` | None — NEW | ✅ Designed |
| 7 | Platform users | `/kaihle-admin/users` | None — NEW | 🔲 Pending |

---

## Architecture note

Per `M0-7-T5` and confirmed five-app separation: Kaihle Admin pages live in
`apps/kaihle-admin` (port 3005). The original task file noted these lived in
`apps/teacher` as an MVP simplification — that decision was superseded by the
five-app restructure in `CONSTITUTION.md`. Code must NOT go in `apps/teacher`.

---

## Sidebar navigation

```
Section: PLATFORM
  Overview   → /kaihle-admin/overview
  Schools    → /kaihle-admin/schools
  Users      → /kaihle-admin/users
  Billing    → /kaihle-admin/billing

Section: SYSTEM
  Logs       → /kaihle-admin/logs
  Config     → /kaihle-admin/config
```

Top nav right: `[+ Add school]` green button + avatar.

---

## 1. Platform Overview
**Route:** `/kaihle-admin/overview`  
**Task file:** `docs/tasks/M0-7-T5_kaihle_admin_ui.md`

### Layout (top to bottom)
1. KPI row: Total schools · Total students · MRR (green value) · Platform onboarding rate
2. System health bar: API uptime · Avg latency · Redis status · Celery workers · LLM provider status
3. Schools-at-a-glance table: name, status, plan, students, trial expiry (coloured urgency)
4. Recent activity feed: timestamped event log, newest first, limit 10

### Trial expiry coloring
- < 3 days: `bg-red-50 text-red-700` badge + ⚠ icon
- 3–7 days: `bg-amber-50 text-amber-700` badge
- > 7 days or paid: "—" muted

### Health bar
Always visible — shows live status from `GET /platform/stats`. LLM provider row
shows "OpenRouter (interim)" in amber until RunPod/vLLM is unblocked.

### Data sources
| Element | Endpoint |
|---|---|
| KPIs + health | `GET /api/v1/platform/stats` |
| Schools table | `GET /api/v1/schools?page_size=10&sort=trial_expiry_asc` |
| Recent activity | `GET /api/v1/platform/activity?limit=10` (or derived from platform stats) |

---

## 2. Schools List
**Route:** `/kaihle-admin/schools`  
**Task file:** `docs/tasks/M0-7-T5_kaihle_admin_ui.md`

### Layout
- Search input + status filter pills (All / Active / Trial)
- Full table: School name · Status badge · Plan · Students · Created date · Trial ends · Open link

### Status badges
- Active: `bg-green-50 text-green-700` + filled circle
- Trial (safe): `bg-yellow-50 text-yellow-700` + open circle
- Trial (expiring < 3 days): `bg-red-50 text-red-700` + ⚠
- Suspended: `bg-gray-50 text-gray-400`

### Create school flow
`[+ Add school]` opens `AdminCreateSchoolModal`:
- Fields: School name (required) · Slug (auto-derived from name, editable, validated: lowercase + hyphens only) · Country · City · Timezone dropdown · Admin first name · Admin last name · Admin email
- On submit: `POST /api/v1/schools` → then `POST /api/v1/schools/{id}/users` (creates school admin) → toast "School created · Magic link sent to {email}"

### Data sources
| Element | Endpoint |
|---|---|
| Schools list | `GET /api/v1/schools?status={filter}&page={n}` |
| Create school | `POST /api/v1/schools` + `POST /api/v1/schools/{id}/users` |

---

## 3. School Detail
**Route:** `/kaihle-admin/schools/:schoolId`  
**Task file:** `docs/tasks/M0-7-T5_kaihle_admin_ui.md`

### Topbar actions
- "Impersonate school admin" button — calls `POST /platform/schools/{id}/impersonate` → stores scoped JWT → redirects to school admin app as that school's admin. Implemented in M6.
- Back breadcrumb: Schools / {School name}

### Trial banner (TRIAL tier only)
Amber card: "⚠ Trial expires in N days — {date}" + student count vs limit + "Extend trial" green button → `AdminExtendTrialModal`

### Extend Trial Modal
```
Title: "Extend trial — {school name}"
Sub: Current expiry date + days remaining
Extension: pill selector — 7 days | 14 days | 30 days
Reason: textarea (required — stored in trial_extensions.reason audit table)
Buttons: Cancel · "Extend trial →" green
```

### Stats row (4 cards)
Students · Teachers · Assessments completed · Avg mastery

### Two-column layout
Left: School info (name, slug, country, city, timezone, created date — all editable inline)  
Right: Subscription info (plan badge, trial end or renewal date, student limit, trial extensions history, "Upgrade to paid" or "Change plan" green button)

### Change plan action
Opens a simple modal: current plan display + new plan dropdown (Trial → Starter → Growth → Scale) + billing cycle selector + student count input → calls `PATCH /api/v1/schools/{id}/subscription`.

### Data sources
| Element | Endpoint |
|---|---|
| School detail | `GET /api/v1/schools/{id}` |
| School analytics | `GET /api/v1/schools/{id}/analytics` |
| Extend trial | `POST /api/v1/admin/schools/{id}/trial-extension` |
| Change plan | `PATCH /api/v1/admin/schools/{id}` |
| Impersonate | `POST /api/v1/platform/schools/{id}/impersonate` (M6) |

---

## 4. Platform Billing
**Route:** `/kaihle-admin/billing`  
**Task file:** None — needs creating: `docs/tasks/M0-7-T5b_kaihle_admin_billing_ui.md`

### Layout (top to bottom)
1. Revenue KPI row: MRR · ARR · Past due count · Trials expiring within 7 days
2. All school subscriptions table: sortable by ARR value, highlights past-due rows in red
3. Columns: School · Plan · Students · Annual value · Payment status · Renewal date

### Revenue calculations (client-side)
- MRR = sum of `(student_count × price_per_student_annual) / 12` for ACTIVE paid schools
- ARR = sum of `student_count × price_per_student_annual` for ACTIVE paid schools
- Trial schools contribute $0 to MRR/ARR

### Design notes
- Revenue values in green `text-brand-primary` — money is positive
- Past-due rows: subtle red left border `border-l-2 border-red-300`
- No invoice download here — admin-level billing is aggregate view, not per-invoice

### Data sources
| Element | Endpoint |
|---|---|
| All subscriptions | `GET /api/v1/admin/schools?include=subscription` (or separate billing endpoint) |
| Platform stats | `GET /api/v1/platform/stats` |

---

## 5. System Logs
**Route:** `/kaihle-admin/logs`  
**Task file:** None — needs creating: `docs/tasks/M0-7-T5c_kaihle_admin_logs_ui.md`

### Layout
- Filter row: text search input + level dropdown (All / ERROR / WARN / INFO / DEBUG)
- Dark terminal-style log panel: `bg-slate-900 text-slate-200 font-mono text-xs`
- Each log line: `timestamp · [LEVEL] · service · message`
- Level coloring: ERROR = `text-red-400`, WARN = `text-amber-400`, INFO = `text-green-400`, DEBUG = `text-slate-400`
- Auto-scroll to bottom (latest first or oldest first toggle)
- Pagination or infinite scroll — load 100 lines, "Load more" button

### Key log sources to surface
From `structlog` structured logging:
- `celery.beat` — scheduled task fires
- `litellm` — LLM calls, timeouts, retries, model used, duration
- `auth` — login events, token refreshes, failed logins
- `billing` — trial expiry warnings, limit hits
- `gap_states` — calculation completions
- `assessments` — attempt submissions, scoring

### Data sources
| Element | Endpoint |
|---|---|
| Log stream | `GET /api/v1/platform/logs?level={filter}&q={search}&limit=100&offset={n}` |

---

## 6. Config
**Route:** `/kaihle-admin/config`  
**Task file:** None — needs creating: `docs/tasks/M0-7-T5d_kaihle_admin_config_ui.md`

### Sections (read-only display in v1 — no in-app editing, values come from env vars)

**LLM Provider**
- Active provider: OpenRouter (interim) — amber warning until RunPod ready
- Model: `qwen/qwen3-5-35b-a3b`
- RunPod status: "Blocked — awaiting vLLM nightly build for Qwen3.5MoeForConditionalGeneration"
- Fallback model: Claude Sonnet 4.6
- Fix: `VLLM_NIGHTLY=true` env var (noted as identified fix in memory)

**Trial Settings** (from `billing.py` constants — read-only display)
- Trial duration: 15 days
- Trial student limit: 30
- Warning threshold: 7 days remaining

**Rate Limits** (from `slowapi` config — read-only display)
- Login: 10 req/min per IP
- Magic link: 3 req/min per email
- Assessment responses: 60 req/min per user
- LLM routes: 20 req/min per school

### Design notes
- Config is read-only in v1 — all values are environment variables, not DB-stored
- Editable config management (e.g. feature flags) is a v2 concern
- No save buttons — display only
- Amber callout on RunPod status noting the known fix

---

## 7. Platform Users *(pending design)*
**Route:** `/kaihle-admin/users`  
**Task file:** None

### Planned scope
- Search across ALL users on the platform (cross-school)
- Columns: Name · Role · School · Email · Status · Last active
- Filter by role (KaihleAdmin / SchoolAdmin / Teacher / Student / Parent)
- Row click: view user detail (read-only)
- Admin can deactivate any user platform-wide
- Used primarily for support/debugging — "find user X's account"

---

## Design rules enforced across all Kaihle Admin pages

| Rule | Detail |
|---|---|
| Inter only | No Fraunces, no Lora — every text element uses Inter |
| Gray fill + green dot active state | Never gold tint (Teacher) or left stripe (School Admin) |
| Cool background | `#f8f9fb` — slightly cooler than other roles |
| Neutral borders | `#e2e8f0` — no green tint on cards |
| No role-specific language | Labels are system-level: "Schools", "Platform", "System" |
| MRR/revenue in green | Financial positive values use `text-brand-primary` |
| Trial urgency coloring | Red < 3 days, amber < 7 days — consistent across all admin views |
| Impersonation is M6 | `POST /platform/schools/{id}/impersonate` stub exists but returns 501 until M6 |
| Logs page is dark theme | Terminal aesthetic, `bg-slate-900` — exception to the neutral card rule |

---

## Open task files needed

| Page | Suggested task file |
|---|---|
| Platform billing | `docs/tasks/M0/M0-7-T5b_kaihle_admin_billing_ui.md` |
| System logs | `docs/tasks/M0/M0-7-T5c_kaihle_admin_logs_ui.md` |
| Config | `docs/tasks/M0/M0-7-T5d_kaihle_admin_config_ui.md` |
| Platform users | `docs/tasks/M0/M0-7-T5e_kaihle_admin_users_ui.md` |

---

*Kaihle Design Sprint · Kaihle Admin Role · March 2026*  
*Next role: Parent*
