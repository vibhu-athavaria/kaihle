# School Admin Role — Screen Design Specifications
**Design sprint:** March 2026  
**Personas:** Vidhya (information hierarchy) · Pixel (UI/UX) · Kramer (data map)  
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.2  
**App:** `apps/school-admin` · port 3004  
**Layout wrapper:** `DashboardLayout variant="school-admin"`  
**Action color:** Green `#1a5c38`  
**Heading font:** Fraunces · Body: Nunito  
**Page background:** `#f5f7f1`  
**Sidebar active state:** Left green stripe `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary`  
**Borders:** Green-tinted `#d4e4d8` (role-school-border)

---

## Page inventory

| # | Page | Route | Status |
|---|---|---|---|---|
| 1 | Overview | `/school-admin/overview` | ✅ Designed |
| 2 | Users | `/school-admin/users` | ✅ Designed |
| 3 | Classes | `/school-admin/classes` | ✅ Designed |
| 4 | Class gap map | `/school-admin/classes/:id/gap-map` | ✅ Designed |
| 5 | Analytics | `/school-admin/analytics` | ✅ Designed |
| 6 | Billing | `/school-admin/billing` | ✅ Designed |
| 7 | Settings | `/school-admin/settings` | 🔲 Pending basic spec |

---

## Critical architecture note

School Admin pages live in `apps/school-admin` (port 3004) — NOT in `apps/teacher`.
This separation ensures proper role isolation per CONSTITUTION Rule 14.
Any code in `apps/teacher/src/pages/school-admin/` violates CONSTITUTION Rule 14
and must be migrated to `apps/school-admin/`.

---

## Sidebar navigation

```
Section: SCHOOL
  Overview     → /school-admin/overview
  Users        → /school-admin/users        (Teachers tab default)
  Classes      → /school-admin/classes

Section: ADMIN
  Analytics    → /school-admin/analytics
  Billing      → /school-admin/billing
```

Top nav right: `[Invite teacher]` green button + avatar.
Settings: accessible via avatar dropdown — not a sidebar item.

---

## 1. Overview
**Route:** `/school-admin/overview`  
**Status:** Previously designed — see design sprint session

### Sections (top to bottom)
1. KPI row: Teachers · Students · Onboarding % (3 cards)
2. Classes table: compact, max 10 rows, scroll if more, "Create class" button, mastery badge per class
3. Onboarding progress bar: `bg-brand-light` card, green fill, count detail, "View analytics →" link

### Data sources
| Element | Endpoint |
|---|---|
| KPIs | `GET /api/v1/schools/{id}/analytics` |
| Classes table | `GET /api/v1/schools/{id}/classes` |
| Onboarding progress | From analytics response |

---

## 2. Users
**Route:** `/school-admin/users`

### Layout
Role tabs (Teachers / Students / Parents) — pill toggle, `bg-gray-100` inactive, `bg-white shadow-sm` active.
Search input top-right.
Table: Name (avatar initials + full name + email) · Role-relevant column (Classes for teachers, Class for students) · Status · Actions

### User table per role

**Teachers:** Name + email · Classes assigned · Status badge · Actions (⋮ menu: Resend invite / Deactivate / Reactivate)

**Students:** Name + email · Class enrolled · Onboarding status · Actions (⋮)

**Parents:** Name + email · Linked children · Status · Actions

### Status badges
- Active: `bg-green-100 text-green-700` + green dot
- Invited: `bg-amber-100 text-amber-700` + open circle
- Inactive: `bg-gray-100 text-gray-500` + ✕

### Invite User Modal
Fields: First name · Last name · Email (validated) · Role (pre-filled from active tab, editable)
Actions: Cancel · "Send invite →" green button
On success: toast "Invite sent to {email}", row appears with Invited badge

### Data sources
| Element | Endpoint |
|---|---|
| User list | `GET /api/v1/schools/{id}/users?role=teacher|student|parent` |
| Invite | `POST /api/v1/schools/{id}/users` |
| Deactivate | `PATCH /api/v1/schools/{id}/users/{userId}` |

---

## 3. Classes
**Route:** `/school-admin/classes`

### Layout
Table: Class · Subject · Grade · Teacher · Students · Avg mastery
Click any row → right-side panel slides in (no page navigation)

### Class side panel (slide-in)
- Width: 320px, slides over content, overlay behind
- Dismiss: ✕ button, overlay click, Escape key
- Sections:
  - **Teacher:** Initials avatar + name + "Reassign" button (dropdown to select new teacher)
  - **Enrolled students:** Count + "N of limit" · Student name pills (first 4 + "+ N more") · "+ Enroll students" button
  - **Performance:** Class avg mastery badge + "View class gap map →" link
- Footer: "Deactivate class" red outline danger button

### Create Class Modal
Fields (with auto-suggest logic):
- Class name (required)
- Subject: dropdown (MATH / SCI / ENG / BIO / CHEM / PHY / ENGL)
- Grade: dropdown (6–12)
- Curriculum: auto-suggested from grade (6–8 → Cambridge Lower Secondary, 9–10 → IGCSE), overridable
- Teacher: dropdown of active teachers in school
Actions: Cancel · "Create class →" green

### Data sources
| Element | Endpoint |
|---|---|
| Classes | `GET /api/v1/schools/{id}/classes` |
| Create class | `POST /api/v1/schools/{id}/classes` |
| Enroll students | `POST /api/v1/classes/{id}/enroll` |
| Reassign teacher | `PATCH /api/v1/classes/{id}` |
| Curricula for dropdown | `GET /api/v1/curricula` |
| Grades for dropdown | `GET /api/v1/grades` |

---

## 4. Class Gap Map (drill-down)
**Route:** `/school-admin/classes/:classId/gap-map`  
**Entry points:** Classes side panel "View class gap map →" link · Analytics class table row click

### Purpose
Read-only admin view of a single class's heatmap. Shows all students × all subtopics.
The school admin cannot assign study plans — that action belongs to the teacher.
This page is for visibility and oversight only.

### Layout
- Class selector dropdown (switch between school's classes)
- Subject tabs (one per subject the class is enrolled in)
- Heatmap grid: same pattern as teacher gap map (`M2-1-T3`) but read-only
- Legend below grid
- "Back to Analytics" or "Back to Classes" breadcrumb

### Heatmap differences from teacher view
- No "Assign Study Plan" button — admin cannot assign
- No CSV export — admin uses the analytics page for exports
- Cell click shows a simplified tooltip (student name + score + band) — no side panel
- Class average row pinned at bottom, same as teacher view

### Data sources
| Element | Endpoint |
|---|---|
| Gap map data | `GET /api/v1/classes/{classId}/gap-map?subject_id={id}` |

---

## 5. Analytics
**Route:** `/school-admin/analytics`

### View switcher: Overview | Class gap map

**Overview tab:**
- KPI row (4 cards): Total students · Active this week · Assessments completed · Onboarding rate
- Onboarding progress bar: wide, color transitions red→amber→green based on rate
- Mastery by subject bar chart (Recharts): one bar per subject, bar fill from mastery band
- Class breakdown table: sortable, default sort by avg mastery ascending (lowest first)
  - Columns: Class · Subject · Teacher · Students · Avg mastery (colored badge) · Assessments completed

**Class gap map tab:**
- Class selector dropdown
- Read-only heatmap (same as page 4 above)
- Accessible directly from class breakdown table row click

### Data sources
Single endpoint covers everything:
`GET /api/v1/schools/{schoolId}/analytics` — aggregated response used for all sections.

---

## 6. Billing
**Route:** `/school-admin/billing`

### Layout (top to bottom)

**Plan hero card:**
- Plan name (Growth / Starter / Scale / Trial) + status badge
- Details row: Students used/limit · Price per student/year · Billing cycle · Renewal date
- "Upgrade" or "Contact us" button (right side)

**Usage card:**
- Active students: N of limit
- Teachers: N (unlimited on most plans)
- Curricula active: N of limit
- Feature pills: Parent portal ✓ / AI lesson plans ✓ / API access / etc.

**Invoices list:**
- One row per invoice: Period · Students headcount · Amount · Status badge (Paid/Pending) · PDF download button
- Status badges: Paid = `bg-green-100 text-green-700` · Pending = `bg-amber-100 text-amber-700`

**Trial state (if TRIAL tier):**
- Amber alert banner at top: "Your trial expires in N days. Upgrade to continue."
- Upgrade CTA button

### Design rules
- School admin cannot change payment method or cancel subscription — these are Kaihle Admin functions
- Billing page is read-only for school admin (view plan + download invoices only)
- "Upgrade" button links to a contact/inquiry flow, not a self-serve checkout (v1)

### Data sources
| Element | Endpoint |
|---|---|
| Subscription details | `GET /api/v1/schools/{id}/subscription` (stub exists in M0-10-T6) |
| Invoices | `GET /api/v1/schools/{id}/invoices` (needs route) |

---

## 7. Settings *(pending design)*
**Route:** `/school-admin/settings`  
**Task file:** None

### Planned scope (basic, v1)
- School profile: school name, country, city, timezone (read-only, managed by Kaihle Admin)
- Admin account: display name + password change (same pattern as Teacher settings)
- Sign out

---

## Design rules enforced across all School Admin pages

| Rule | Detail |
|---|---|
| Left stripe active state | `border-l-[3px] border-brand-primary` — NOT gold tint (that's Teacher) |
| Green action buttons | All CTAs use `bg-brand-primary #1a5c38` |
| Green-tinted borders | `border-role-school-border #d4e4d8` on all cards |
| Section labels | `text-role-school-muted #6b9e79` — muted green, not gray |
| Mastery colors | Same thresholds as all roles: >0.7 Strong, 0.4–0.7 Developing, <0.4 Needs Work |
| No study plan assignment | Admin cannot assign study plans — teacher-only action |
| Class gap map is read-only | No side panel, no assign button |
| Analytics sorted by mastery ascending | Lowest-performing classes at top — admin attention directed to problems |
| App location | `apps/school-admin` — NOT `apps/teacher` (ADR-001) |

---



---

*Kaihle Design Sprint · School Admin Role · March 2026*  
*Next role: Kaihle Admin → Parent*
