# School Admin App — Redesign Spec
**Date:** 2026-04-22
**Status:** Approved for implementation
**Personas:** Kramer (architecture), Pixel (UI/UX), Vidhya (education)
**Mockup source:** `.superpowers/brainstorm/98158-1776821185/content/` (locked files below)

---

## 1. Problem & Goal

The current school-admin app shows KPI counts (student count, teacher count, onboarding %) but provides no mastery signal. A school admin cannot tell from any current screen which classes are struggling, which students need support, or whether platform adoption is happening. This redesign gives admins a mastery-first view across all six screens without overloading list views with detail that belongs on drill-down pages.

---

## 2. Design Principles (locked for all screens)

### 2.1 Progressive Disclosure
List views show **one signal only** (mastery band dot + label). Detail views show the full story (per-subtopic bars, assessment history, study plan status). Never show float scores or per-subtopic data in a list row.

### 2.2 Sorted Worst-First
All class and student lists default to **ascending mastery** — Needs Work rows at the top. Admin attention flows to problems automatically.

### 2.3 Mastery Labels Only (no floats)
Admins see: **Needs Work · Developing · Strong · Not assessed**. The underlying 0.0–1.0 float is an internal mechanism; it never surfaces in admin-facing UI.

### 2.4 Three Class States
Every class card/row is in exactly one of:
| State | Visual | Condition |
|---|---|---|
| Setup needed | Amber row background, "Assign teacher" CTA | No teacher assigned |
| Diagnostic pending | Hollow circle indicator | Teacher + students enrolled, no completed diagnostic |
| Has mastery data | Coloured mastery dot + label | At least one student has completed the diagnostic |

### 2.5 Locked Shell (all screens)
Sidebar, topbar, and footer are **pixel-identical across every school-admin screen**. There is one `SchoolAdminLayout` wrapper — pages compose inside it and never redefine chrome. Any change to the shell requires updating the spec and all mockups.

**Typography (all screens):**
- Headings / page titles: `font-display` (Fraunces), `font-bold`
- Body, labels, nav items, buttons: `font-sans` (Nunito)
- No Inter, no Lora anywhere in school-admin

**Colours (all screens):**
- Page background: `#f5f7f1` (`role-school-bg`)
- All borders: `#d4e4d8` (`role-school-border`)
- Section labels: `#6b9e79` (`role-school-muted`)
- Primary action: `#1a5c38` (`brand-primary`) — green buttons only (School Admin, unlike Teacher which uses gold)
- Never raw hex in component files — token names only

**Sidebar structure:**
```
Width: 200px · bg-white · border-r border-role-school-border

Section: School
  Overview
  Users      (active on Users / Student Detail screens)
  Classes    (active on Classes / Gap Map screens)

Section: Admin
  Analytics
  Billing

Footer: [30px green avatar] Daniela A. · School Admin
```

**Sidebar active state:** `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg` (left green stripe)
**Sidebar inactive item:** `text-gray-500 font-semibold hover:bg-gray-50`

**Topbar:** `h-[50px] bg-white border-b border-role-school-border` — page title (Fraunces 17px bold) left, action button(s) right.

**Buttons (all screens):**
- Primary: `bg-brand-primary text-white rounded-full` (green)
- Secondary: `border border-role-school-border text-brand-primary rounded-full bg-white`
- No gold buttons anywhere in school-admin

---

## 3. Screen Inventory

| Screen | Route | Mockup file |
|---|---|---|
| Dashboard (Overview) | `/school-admin/dashboard` | `mockup-dashboard-v2.html` |
| Classes | `/school-admin/classes` | `mockup-classes-v3.html` |
| Class Gap Map | `/school-admin/classes/:classId/gap-map` | `mockup-gap-map.html` |
| Analytics | `/school-admin/analytics` | `mockup-analytics.html` |
| Users | `/school-admin/users` | `mockup-users-v2.html` |
| Student Detail | `/school-admin/users/students/:studentId` | `mockup-student-detail.html` |

---

## 4. Screen Specs

### 4.1 Dashboard
**Mockup:** `mockup-dashboard-v2.html`

**KPI strip (4 cards):**
- Total students · Total teachers · Onboarding rate · Active this week

**At-Risk Students widget:**
- Rows: student avatar (first name + initial) · worst mastery label · subject count
- Format: "Aisha M. — Needs Work · 2 subjects"
- No float scores. Subject count conveys urgency gradient (2 subjects > 1 subject).
- Sorted: most subjects at Needs Work first.

**Classes needing attention widget:**
- Lists classes in Setup Needed or Diagnostic Pending state
- Single mastery dot + class name + teacher name (or "No teacher assigned")

**Data source:** `GET /api/v1/schools/{schoolId}/analytics` (M6-1-T1 stub — needs implementation)

---

### 4.2 Classes
**Mockup:** `mockup-classes-v3.html`

**Toolbar (locked — do not change between iterations):**
- Search input · "Needs attention" filter pill · "All grades" filter pill · "All subjects" filter pill · class count

**Table columns:** Class · Subject · Grade · Teacher · Mastery · Students · chevron

**Row states:** See §2.4. Setup-needed rows use `#fffbeb` background.

**Legend bar (below table):** Needs Work · Developing · Strong · Diagnostic pending · Setup needed — labels only, no float ranges.

**Clicking a row:** navigates to the Class Gap Map screen.

**Data source:** `GET /api/v1/schools/{schoolId}/classes` with `include_summary=true` param (already returns `avg_mastery`, `students_below_threshold` — unused by current frontend).

---

### 4.3 Class Gap Map
**Mockup:** `mockup-gap-map.html`

**Topbar addition:** breadcrumb (`Classes › 8A — Mathematics`) + read-only badge ("Read only — contact teacher to update").

**Heatmap:** subtopics as rows · students as columns (same orientation as teacher gap map — do NOT transpose for MVP).

**Cell display:** mastery band label only ("Needs Work" / "Developing" / "Strong" / "—"). No float. No percentage. Admin sees labels; teacher sees label + percentage (see §6.1).

**Legend:** Needs Work · Developing · Strong · Not assessed — no float ranges.

**Data source:** `GET /api/v1/classes/{classId}/gap-map` (already implemented in `GapService`)

---

### 4.4 Analytics
**Mockup:** `mockup-analytics.html`

**Period selector:** "This week / This month / This term" tabs in topbar. Sends `?from=DATE&to=DATE` to backend. Term maps to school-configured date ranges (TBD in implementation — use academic calendar or hardcoded ranges for MVP).

**KPI strip (4 cards):** Active students · Assessments completed · Study plans active · Onboarding rate

**Subject mastery bars:** Horizontal bars per subject coloured by band. Labels only (Needs Work / Developing / Strong). No floats.

**Onboarding funnel:** Invited → Password set → Profile complete → Diagnostic done. Drop-off chips between steps show admin where students are getting stuck.

**Class breakdown table:** sorted worst-first · columns: Class · Subject · Teacher · Mastery (dot + label) · At-risk chip · Students · Assessments this month · chevron.

**Data source:** `GET /api/v1/schools/{schoolId}/analytics` (M6-1-T1 stub). Period filtering requires `?from=DATE&to=DATE` query params — not yet implemented. MVP can ship with "This month" as the only active option; week/term are greyed out until backend supports them.

---

### 4.5 Users — Students Tab
**Mockup:** `mockup-users-v2.html`

**Role tabs:** Students (default) · Teachers · Parents. Each tab shows its user count.

**Filter pills:** All students · Needs attention (N) · Diagnostic pending (N) · Not yet logged in (N)

**Table columns:** Student (avatar + "First L." + grade) · Classes (count: "2 classes") · Lowest mastery (worst class band + "· N classes" count) · Diagnostic · Last active · chevron

**Avatar format:** First initial + last initial (e.g. "AM" for Aisha Mohammed).
**Name format:** First name + first letter of last name + period (e.g. "Aisha M.").

**Enrolled classes column:** Always show count ("2 classes"), never chip list. Chip list breaks at 4+ classes. Full class list is on the Student Detail page.

**Lowest mastery column:** Shows the student's worst-performing class band, not an average. Append "· N classes" when student has >1 class at that band.

**Row background:** `#fffbeb` for Needs Work rows.

**Clicking a row:** navigates to Student Detail.

**Diagnostic badge:** "Completed" (no tick icon) · "Pending" (amber) · greyed out if not applicable.

**Data source:** `GET /api/v1/schools/{schoolId}/users?role=STUDENT` — needs mastery summary added to response.

---

### 4.6 Student Detail
**Mockup:** `mockup-student-detail.html`

**Topbar:** breadcrumb only (`Users › Students › Aisha M.`). No action buttons.

**Hero card:** avatar · full first name + last initial · grade · curriculum · enrolled since date · stat strip (classes count · Needs Work class count · assessments count · last active).

**Mastery by class (grid):** 2-column card grid. Each card: class name · teacher name · mastery band badge · subtopic mini-bars (subtopic name · coloured progress bar · band label). Bars use `brand-red / brand-amber / brand-green` — no float values shown.

**Study plan strip:** plan title · assigned date · resources completed progress · "Active" status dot.

**Recent assessments table:** Assessment name · Class · Date · Score (band badge) · Type (Diagnostic / Progress check). Newest first.

**Data sources:**
- Student profile: `GET /api/v1/students/{studentId}` (exists)
- Gap map per class: `GET /api/v1/classes/{classId}/gap-map` (exists — filter to single student)
- Attempt history: `GET /api/v1/students/{studentId}/attempts` (needs scoping for school-admin role)
- Study plans: `GET /api/v1/students/{studentId}/study-plans` (exists)

---

## 5. API Gap Summary

| Need | Endpoint | Status |
|---|---|---|
| Dashboard + Analytics KPIs | `GET /schools/{id}/analytics` | Stub — implement in M6-1-T1 |
| Period filtering | `?from=DATE&to=DATE` on analytics endpoint | Missing — add in M6-1-T1 |
| Classes with mastery | `GET /schools/{id}/classes?include_summary=true` | Param exists, frontend not using it |
| Gap map (read-only) | `GET /classes/{id}/gap-map` | Implemented |
| Users with mastery | `GET /schools/{id}/users?role=STUDENT` | Needs `worst_mastery` field added |
| Student detail — attempts | `GET /students/{id}/attempts` (school-admin scope) | Needs role-based access added |
| Onboarding funnel counts | New aggregation on `/schools/{id}/analytics` | Missing |

---

## 6. Shared Component Changes

### 6.1 GapMapCell — extract to `packages/ui`

**Current location:** `frontend/apps/teacher/src/components/gap-map/GapMapCell.tsx`
**Move to:** `frontend/packages/ui/src/components/GapMapCell.tsx`

**New props:**
```typescript
interface GapMapCellProps {
  masteryScore: number | null
  studentName: string
  subtopicName: string
  display?: 'label' | 'percent' | 'both'  // default: 'label'
  readOnly?: boolean                        // default: false
  onClick?: () => void
}
```

- `display="label"` — admin view: shows "Needs Work" / "Developing" / "Strong"
- `display="both"` — teacher view: shows "Dev · 64%"
- `readOnly=true` — removes click handler and hover state (admin gap map)

Teacher app imports from `@kaihle/ui` after extraction. No behaviour change for teacher.

---

## 7. Implementation Notes

- **Do not show float values anywhere in admin UI.** Use `getMasteryStyle(score)` from `@kaihle/types` for all mastery colouring.
- **Mastery boundary:** `score = 0.7` → Developing. `score = 0.71` → Strong. Never round.
- **Term date ranges** for the Analytics period selector are undefined in the schema. For MVP, grey out "This term" tab and show only "This week" and "This month" as active. File a follow-up task to add `academic_terms` table.
- **School-admin gap map is read-only.** Admin has no route to edit mastery — only teachers can assign assessments. The "Read only" badge in the topbar makes this clear.
- **Student Detail subtopic bars** use percentage width derived from `mastery_score * 100` for the visual bar, but show only the band label as text. Pixel values, not mastery floats, power the bar widths.
