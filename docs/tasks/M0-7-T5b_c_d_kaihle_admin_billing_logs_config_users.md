# M0-7-T5b — Kaihle Admin: Billing, Logs, Config & Users UI
**Milestone:** M0 · **Epic:** M0-7
**Authors:** Kramer (engineering) · Pixel (design)
**Depends on:** M0-9-T1 (kaihle-admin scaffold), M0-8-T4, M6-1-T4 (logs + trial extension endpoints)
**Covers:** Pages 4 (Billing) · 5 (Logs) · 6 (Config) · 7 (Users)
**Effort:** 5–6 hours total (these four pages are relatively lightweight)

> Vidhya note: These pages serve Kaihle's internal operator (Vibhu), not educators.
> Vidhya has no specific curriculum input here. Pixel and Kramer lead.

---

## Pixel — Design Philosophy for Kaihle Admin

The Kaihle Admin app is **surgical** — it is a tool for a single expert user. Vibhu opens this when something needs fixing or checking. There is no onboarding flow. There are no tooltips explaining what MRR is. It is an internal operator console, and it should look like one.

**Design tenets:**
- Inter font, always. Not Fraunces, not Lora. Nunito is also wrong here. Inter is the professional neutral.
- Cool gray background `#f8f9fb` — not warm cream, not the green-tinted school admin palette.
- Data density is acceptable. Vibhu is not a casual user. A 12-column subscription table is fine.
- The dark terminal for logs is intentional and correct. Don't soften it.
- Revenue numbers in `text-brand-primary` (green) — positive financial signal is a convention worth keeping.

---

## Page 4 — Platform Billing (`AdminBilling.tsx`)
**Route:** `/kaihle-admin/billing`

### Pixel — Component: RevenueKPIRow

```
Component: RevenueKPIRow
──────────────────────────────────────────────────────────
Layout:     grid-cols-4 gap-4 (2-col on mobile)
Card:       bg-white rounded-2xl border border-gray-200 p-5
Label:      font-inter text-[11px] uppercase tracking-widest text-gray-400
Value:      font-inter text-2xl font-bold
            MRR / ARR: text-brand-primary (#1a5c38)
            Past due:  text-red-600 if > 0, text-gray-400 if 0
            Trials expiring: text-amber-600 if > 0, text-gray-400 if 0
──────────────────────────────────────────────────────────
Revenue calculation (client-side):
  MRR = Σ (student_count × price_per_student_annual / 12) for ACTIVE paid schools
  ARR = MRR × 12
  Format: "$1,234" — Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
```

### Pixel — Component: SubscriptionsTable

```
Component: SubscriptionsTable
──────────────────────────────────────────────────────────
Table:      bg-white rounded-2xl border border-gray-200 overflow-hidden
Header:     bg-gray-50 border-b border-gray-200
            th: font-inter text-[11px] uppercase tracking-wide text-gray-400 px-4 py-3
Row:        font-inter text-sm text-gray-700 px-4 py-4
            border-b border-gray-50 hover:bg-gray-50 cursor-pointer
            transition-colors duration-75

Highlight rows:
  Past due:              border-l-[3px] border-red-400 bg-red-50/20
  Trial expiring < 3d:   border-l-[3px] border-amber-400 bg-amber-50/20
  Trial safe:            no highlight

Plan badge (rounded-full px-2.5 py-1 text-xs font-medium):
  TRIAL:   bg-yellow-50 text-yellow-700 border border-yellow-200
  STARTER: bg-blue-50   text-blue-700   border border-blue-200
  GROWTH:  bg-green-50  text-green-700  border border-green-200
  SCALE:   bg-purple-50 text-purple-700 border border-purple-200

Annual value: text-brand-primary font-medium (paid)
              text-gray-400 (trial — show "—")

Sort indicator: ▲▼ inline after header text, text-gray-300
                Active: text-brand-primary
──────────────────────────────────────────────────────────
Default sort: Annual value descending
Sortable:     Annual value · School name · Students · Status
Row click:    → /kaihle-admin/schools/{id}
```

---

## Page 5 — System Logs (`AdminLogs.tsx`)
**Route:** `/kaihle-admin/logs`

### Pixel — LogPanel Component

This is the one page in the entire product with a **dark theme**. Pixel's take: this is correct and intentional. Log viewers have been dark since the terminal was invented. Changing this to match the rest of the app would be actively worse.

```
Component: LogPanel
──────────────────────────────────────────────────────────
Outer:       bg-white rounded-2xl border border-gray-200 overflow-hidden
Panel head:  bg-slate-800 px-4 py-2 flex items-center gap-2
             Three dots: w-3 h-3 rounded-full bg-red-400/60, bg-amber-400/60, bg-green-400/60
             Title: "kaihle-platform-logs" font-mono text-xs text-slate-400
             Right: Auto-scroll toggle (Switch component) font-inter text-xs text-slate-400
Panel body:  bg-slate-900 h-[560px] overflow-y-auto px-4 py-3
             (h-[360px] on screens < 768px)
```

### Pixel — LogLine Component

```
Component: LogLine
──────────────────────────────────────────────────────────
Row:         flex items-start gap-3 py-1.5 hover:bg-slate-800 rounded
             transition-colors duration-75 cursor-pointer (expand on click)
Timestamp:   font-mono text-[11px] text-slate-500 w-48 flex-shrink-0
             tabular-nums — CRITICAL for alignment across rows
Level badge: font-mono text-[11px] font-bold w-12 flex-shrink-0
  CRITICAL:  text-red-300 (boldest — platform emergency)
  ERROR:     text-red-400
  WARNING:   text-amber-400
  INFO:      text-green-400
  DEBUG:     text-slate-500
Service:     font-mono text-[11px] text-blue-400 w-24 flex-shrink-0
Message:     font-mono text-[12px] (level colour) flex-1 break-words
──────────────────────────────────────────────────────────
Expand on click (if entry.extra has keys):
  Expandable JSON block below the row
  bg-slate-950 text-slate-300 text-[11px] font-mono p-3 mt-1 rounded
  whitespace-pre-wrap
──────────────────────────────────────────────────────────
Pixel: tabular-nums on timestamp is non-negotiable.
Without it, timestamps jitter horizontally and the panel becomes
unreadable during rapid log output.
```

### Pixel — LogFilterBar Component

```
Component: LogFilterBar
──────────────────────────────────────────────────────────
Layout:     flex gap-3 items-center mb-3
Search:     flex-1 bg-white border border-gray-200 rounded-xl
            px-4 py-2 text-sm font-inter placeholder-gray-400
            focus: border-brand-primary ring-1 ring-brand-primary/20
            Debounced 300ms (not on every keypress)
Level:      <select> bg-white border border-gray-200 rounded-xl
            px-3 py-2 text-sm font-inter text-gray-600 w-36
Auto-scroll: flex items-center gap-2 text-sm font-inter text-gray-600
             Switch toggle (shared ui component)
```

---

## Page 6 — Config (`AdminConfig.tsx`)
**Route:** `/kaihle-admin/config`

### Pixel — ConfigSection + ConfigRow Components

```
Component: ConfigSection
──────────────────────────────────────────────────────────
Card:       bg-white rounded-2xl border border-gray-200 mb-4
Heading:    font-inter text-sm font-semibold text-gray-700 px-6 pt-5 pb-3
            border-b border-gray-100

Component: ConfigRow
──────────────────────────────────────────────────────────
Row:        flex items-center justify-between px-6 py-3.5
            border-b border-gray-50 last:border-0
Label:      font-inter text-sm text-gray-500
Value:      font-inter text-sm font-medium text-ink (or mono for env values)
Badge:      rounded-full px-2.5 py-1 text-xs font-medium
  green:   bg-green-50 text-green-700 border border-green-200
  amber:   bg-amber-50 text-amber-700 border border-amber-200
  red:     bg-red-50 text-red-600 border border-red-200
──────────────────────────────────────────────────────────
Three sections:
  LLM Provider — with RunPod amber "Blocked" badge (data-testid="runpod-status")
  Trial Settings — numeric values from platform/stats
  Rate Limits — numeric values from platform/stats

NO save buttons. NO edit forms. All read-only.
Pixel: adding edit controls to a config-from-env-vars page creates
a false affordance. Values are changed via deploy. Don't imply otherwise.
```

---

## Page 7 — Platform Users (`AdminUsers.tsx`)
**Route:** `/kaihle-admin/users`

### Pixel — PlatformUserTable

```
Component: PlatformUserTable
──────────────────────────────────────────────────────────
Same table base as SubscriptionsTable (consistent admin aesthetic)
Columns: Name + avatar initials | Role badge | School | Email | Status | Last active | Deactivate

Role badge (rounded-full px-2.5 py-1 text-xs font-medium):
  KAIHLE_ADMIN:  bg-purple-50  text-purple-700
  SCHOOL_ADMIN:  bg-blue-50    text-blue-700
  TEACHER:       bg-amber-50   text-amber-700
  STUDENT:       bg-green-50   text-green-700
  PARENT:        bg-pink-50    text-pink-600

Status:
  Active:   green dot w-2 h-2 rounded-full bg-green-500 inline
  Inactive: gray dot bg-gray-300

"Deactivate" link: text-red-500 text-xs hover:text-red-700
                   only shown for active users
──────────────────────────────────────────────────────────
Search: top of page, full-width, debounced 300ms
Role filter: dropdown alongside search
Pagination: 25 per page
```

### Pixel — DeactivateUserModal

```
Modal:      centered, max-w-md, bg-white rounded-2xl shadow-xl p-6
Title:      font-inter text-base font-semibold text-ink
Body:       font-inter text-sm text-gray-600 leading-relaxed mt-2
Buttons:    flex gap-3 justify-end mt-6
  Cancel:   border border-gray-200 text-gray-600 rounded-xl px-4 py-2 text-sm
  Confirm:  bg-red-600 text-white rounded-xl px-4 py-2 text-sm
            hover:bg-red-700 transition-colors

Pixel: Filled red for destructive confirm is correct — this is the one
case where filled red is appropriate because the action is irreversible.
Compare to Settings sign-out (reversible) which uses outlined red.
```

---

## Kramer — Engineering Spec

### Files

```
frontend/apps/kaihle-admin/src/pages/
  AdminBilling.tsx
  AdminLogs.tsx
  AdminConfig.tsx
  AdminUsers.tsx

frontend/apps/kaihle-admin/src/components/
  billing/RevenueKPIRow.tsx
  billing/SubscriptionsTable.tsx
  logs/LogFilterBar.tsx
  logs/LogPanel.tsx
  logs/LogLine.tsx
  config/ConfigSection.tsx
  config/ConfigRow.tsx
  users/PlatformUserTable.tsx
  users/DeactivateUserModal.tsx

frontend/apps/kaihle-admin/src/hooks/
  useAdminBilling.ts
  usePlatformLogs.ts
  usePlatformUsers.ts

frontend/apps/kaihle-admin/src/tests/
  admin-billing.spec.ts
  admin-logs.spec.ts
  admin-config.spec.ts
  admin-users.spec.ts
```

### Key implementation notes

**Revenue calc (billing):**
```typescript
const MRR = subs
  .filter(s => s.tier !== 'TRIAL' && s.payment_status === 'ACTIVE')
  .reduce((sum, s) => sum + (s.student_count * s.price_per_student_annual / 12), 0)
```

**Log auto-refresh:**
```typescript
refetchInterval: 10_000 // 10s
// When new data arrives + autoScroll=true:
useEffect(() => { if (autoScroll) panelRef.current?.scrollTo({ top: 999999 }) }, [logs])
```

**Platform users stub endpoint:** `GET /platform/users` needs to be added to `routes/platform.py` as a stub returning `Page[UserSummary]` with empty data. Add it alongside this UI task.

### API Calls

| Page | Endpoint |
|---|---|
| Billing | `GET /api/v1/schools?include=subscription&page_size=100` |
| Logs | `GET /api/v1/platform/logs?level=&q=&limit=100&offset=` |
| Config | `GET /api/v1/platform/stats` (config embedded in response) |
| Users | `GET /api/v1/platform/users?q=&role=&page=` (stub needed) |
| Deactivate | `DELETE /api/v1/schools/{schoolId}/users/{userId}` |

---

## Playwright E2E

```typescript
// Billing
test('billing_four_kpi_cards_visible', ...)
test('billing_mrr_arr_in_brand_primary_green', ...)              // Pixel
test('billing_past_due_row_has_red_left_border', ...)             // Pixel
test('billing_trial_expiring_row_has_amber_border', ...)          // Pixel
test('billing_revenue_formatted_with_dollar_sign', ...)           // Pixel
test('billing_sort_by_annual_value_default', ...)
test('billing_inter_font_not_fraunces', ...)                      // Pixel
test('billing_row_click_navigates_to_school_detail', ...)

// Logs
test('logs_panel_has_dark_slate_background', ...)                 // Pixel
test('logs_timestamp_uses_tabular_nums', ...)                     // Pixel
test('logs_level_filter_shows_only_that_level', ...)
test('logs_search_debounced_300ms', ...)                          // Pixel
test('logs_line_click_expands_extra_fields', ...)                 // Pixel
test('logs_auto_scrolls_to_bottom_on_refresh', ...)               // Pixel

// Config
test('config_three_sections_visible', ...)
test('config_runpod_status_has_red_badge', ...)
test('config_no_save_or_edit_buttons', ...)                       // Pixel (no false affordance)
test('config_all_values_from_api_not_hardcoded', ...)             // Kramer

// Users
test('users_role_badges_correct_colour_per_role', ...)            // Pixel
test('users_deactivate_modal_shows_filled_red_confirm', ...)      // Pixel
test('users_search_debounced', ...)
test('users_inter_font_throughout', ...)                          // Pixel
```

---

## Acceptance Criteria

**All four pages:**
- [ ] Inter font only — no Fraunces, no Lora, no Nunito (Pixel)
- [ ] `AdminLayout` wrapper — never `DashboardLayout` (Kramer)
- [ ] Code lives in `apps/kaihle-admin/` — not `apps/teacher/` (Kramer)

**Billing:**
- [ ] MRR/ARR calculated client-side, formatted with `$` (Pixel)
- [ ] Revenue values in `text-brand-primary` green (Pixel)
- [ ] Past-due rows: red left border (Pixel)
- [ ] Trial expiring < 3 days: amber left border (Pixel)
- [ ] Default sort: annual value descending (Kramer)

**Logs:**
- [ ] Panel has `bg-slate-900` dark theme (Pixel)
- [ ] Timestamps use `tabular-nums` — no jitter (Pixel)
- [ ] Level colours correct per severity (Pixel)
- [ ] Line-click expands extra JSON fields (Pixel)
- [ ] Auto-scroll to bottom on data refresh (Pixel)
- [ ] Search debounced 300ms (Pixel)

**Config:**
- [ ] Three sections: LLM Provider, Trial Settings, Rate Limits (Kramer)
- [ ] RunPod row has red "Blocked" badge with `data-testid` (Kramer)
- [ ] NO save buttons or edit controls (Pixel — no false affordance)
- [ ] All values sourced from `GET /platform/stats` (Kramer)

**Users:**
- [ ] Role badges correct colour per role (Pixel)
- [ ] Deactivate confirm button is filled red (Pixel)
- [ ] Search debounced (Pixel)
- [ ] Empty state renders gracefully (Pixel)
