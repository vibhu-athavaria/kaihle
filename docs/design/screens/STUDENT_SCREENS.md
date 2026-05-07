# Student Role — Screen Design Specifications
**Design sprint:** March 2026 · **Updated:** March 2026 (v2.1 — sidebar layout)
**Personas:** Vidhya (information hierarchy) · Pixel (UI/UX) · Kramer (data map)
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.4
**App:** `apps/student` · port 3002
**Layout wrapper:** `StudentLayout` — left sidebar + top nav + content
**⚠️ Layout change v2.1:** Sidebar replaces top nav tabs + bottom nav (see §6 below)
**Action color:** Green `#1a5c38`
**Heading font:** Fraunces · Body: Nunito
**Page background:** `#f9fafb`
**Sidebar active state:** Green tint fill `bg-[#f0fdf4]` + green dot `bg-brand-primary`
**Reference mockup:** `docs/design/mockups/student_dashboard.html`

---

## Page inventory

| # | Page | Route | Status |
|---|---|---|---|---|
| 1 | Onboarding — questionnaire | `/student/onboarding/profile` | ✅ Designed |
| 2 | Dashboard | `/student/dashboard` | ✅ Designed |
| 3 | My Progress | `/student/my-progress` | ✅ Designed |
| 4 | Study Plans list | `/student/study-plans` | ✅ Designed |
| 5 | Study Plan detail | `/student/study-plans/:planId` | ✅ Designed |
| 6 | Take Assessment | `/student/assessments/:attemptId/take` | ✅ Designed |
| 7 | Assessment Results | `/student/assessments/:attemptId/results` | ✅ Designed |
| 8 | Settings | `/student/settings` | ✅ Designed |

---

## Navigation structure

### Sidebar (all screen sizes — sole navigation)

```
Section: LEARN
  Home          → /student/dashboard          (active: green tint + green dot)
  My progress   → /student/my-progress
  Study plans   → /student/study-plans
  Assessments   → /student/assessments

Section: CLASSES
  [Subject dot] [Class name]   → /student/classes/:classId/topics    (unlocked)
  [Lock icon]   [Class name]   → /student/classes/:classId/diagnostic (locked — amber text)
  (one item per enrolled class — dynamic list from useMyClasses())
```

Locked class items: show amber text `text-brand-gold`, lock emoji icon, route to diagnostic
rather than class topics. This is a visual cue only — a lock icon badge, not disabled state.

Profile card pinned at sidebar bottom:
- Avatar initials, student name, grade + curriculum string
- Click navigates to `/student/settings`

### Top nav

```
Left:  Greeting (font-sans medium) + grade/curriculum subtitle
       e.g. "Good morning, Aditya 👋" / "Cambridge IGCSE · Grade 9"
Right: Avatar (w-[28px] rounded-full) → /student/settings
```

No horizontal tabs in top nav. No bottom nav on any page.

### ❌ Deprecated patterns (DO NOT implement)

The following patterns from v1.0 / DESIGN_SYSTEM.md v2.0 are superseded:
- ~~Top nav bar with 4 horizontal tabs~~
- ~~Bottom nav bar `md:hidden` with Home/Progress/Study/Assessments items~~
- ~~Active state: `text-brand-primary` on bottom nav items~~

All navigation is now sidebar-based. Pages that previously referenced "Bottom nav: X tab active"
should be understood to mean "Sidebar: X nav item active."

---

## 1. Onboarding — Learning Profile Questionnaire
**Route:** `/student/onboarding/profile`
**Layout:** `OnboardingLayout` — full screen, NOT `StudentLayout`. NOT wrapped in `OnboardingRoute` guard (infinite loop risk).

### Gate logic (from actual OnboardingRouter.tsx)

```
GET /api/v1/onboarding/status
  learning_profile_complete = false → /student/onboarding/profile   (Gate 1 only)
  learning_profile_complete = true  → /student/dashboard
  // Gate 2 (per-class diagnostics) is NOT a redirect — shown on dashboard as locked cards
```

### Layout

- `OnboardingLayout` — Kaihle logo top-left, step counter top-right
- Progress indicator: "Question 3 of 6" (treat Q6–Q10 multi-select interests block as 1 question = 6 total)
- Progress bar: thin green strip below topbar, fills proportionally
- Fixed footer: Back + Next/Submit buttons

### Questionnaire structure (10 questions, ~5 minutes)

From `questionnaire_config.py`:

| Question group | Type | Maps to |
|---|---|---|
| Q1 — "When learning something new, I prefer to..." | Single select (4 options) | `modality_scores` |
| Q2 — "I remember things best when..." | Single select (4 options) | `modality_scores` |
| Q3 — "I prefer to study..." | Single select (2 options) | `work_style.prefers_solo` |
| Q4 — "I prefer study sessions that are..." | Single select (2 options) | `work_style.short_sessions` |
| Q5 — "When starting a new topic, I prefer to..." | Single select (2 options) | `work_style.concept_first` |
| Q6–Q10 — "Pick your interests" | Multi-select (10 options) | `interests[]` |

### Option card design (single select)

- 2×2 grid of cards
- Each card: icon (emoji in rounded square) + label text
- Unselected: `border-[1.5px] border-gray-200`, hover `border-green-200`
- Selected: `border-[1.5px] border-brand-primary bg-green-50` + green checkmark `bg-brand-primary` top-right
- Selection clears others in group (single select)

### Interest chips (multi-select)

- Pill chips, wrap layout
- Unselected: `border border-gray-200 text-gray-600`
- Selected: `border border-brand-primary bg-green-50 text-brand-primary`
- Toggle on click — multiple allowed

### Data sources

| Action | Endpoint |
|---|---|
| Load questionnaire | `GET /api/v1/onboarding/questionnaire` |
| Submit | `POST /api/v1/onboarding/questionnaire/submit` |
| After submit | `OnboardingRoute` guard auto-redirects to `/student/dashboard` |

### Key rules

- Re-submit is idempotent — updates existing profile, never creates duplicate row
- `completed_at` set on submit — profile becomes usable by AI features
- Settings page "Retake questionnaire" uses the same endpoint

---

## 2. Dashboard
**Route:** `/student/dashboard`
**Sidebar nav:** Home item active

### Layout (top to bottom in content area)

1. Greeting (Fraunces, time-of-day aware) + grade/curriculum meta
2. Subject score cards (grid, one per enrolled subject)
3. My classes (class cards, locked/unlocked per Gate 2)
4. What's waiting for you (next step cards, priority order)

### Subject score cards

- 3-column grid `grid-cols-3` on desktop, 1-col mobile
- Colored left border from mastery band: green/amber/red/gray
- Score: large font, mastery color
- Label: "Strong" / "Developing" / "Needs work" / "Not assessed"
- `score=null` → "–" not "0%"

### Class cards (Gate 2)

`DiagnosticStatus` drives rendering:
- `PENDING/IN_PROGRESS` → locked: `opacity-60`, footer "🔒 Start diagnostic →" amber text
- `COMPLETED` → unlocked: mastery shown, footer "View class →" green text

Two-column grid `grid-cols-2` on desktop, 1-col mobile.

### Next step card priority order (max 3 shown)

1. Active assessments due within 7 days
2. Study plans with status ACTIVE (not yet started)
3. Study plans with status IN_PROGRESS (started, not finished)
4. Weakest subject with no active study plan

Each next step card: white bg, border, emoji icon left, title + subtitle, action link right.

### Data sources

| Element | Endpoint |
|---|---|
| Subject scores | `GET /api/v1/students/me/gap-map` (aggregate by subject) |
| Class cards + lock state | `GET /api/v1/students/me/classes` → `onboarding_diagnostic_status` per class |
| Next steps — study plans | `GET /api/v1/students/me/study-plans?status=active,in_progress&limit=10` |
| Next steps — assessments | `GET /api/v1/classes/{classId}/assessments?status=ACTIVE&limit=5` |

---

## 3. My Progress
**Route:** `/student/my-progress`
**Sidebar nav:** My progress item active

### Layout

- Subject tabs below topnav (derive from enrolled classes, most-recently-active first)
- Overall score banner: large SVG ring, mastery band label, subtopic count breakdown bars
- Expandable topic groups (all expanded by default)
- Suggested next steps section at bottom

### Overall score banner

- SVG progress ring — stroke color from `getMasteryStyle(overallScore)`
- Right side: mini bar chart showing Strong/Developing/Needs Work/Not assessed counts

### Topic groups (`TopicProgressRow.tsx`)

- Header: chevron + topic name + avg badge (color from mastery band) + subtopic count
- Click header → toggle expand/collapse with CSS height transition
- Expanded by default

### Subtopic rows (`SubtopicProgressRow.tsx`)

- SVG mastery circle: colored stroke arc, percentage inside
- `score=null` → "–" inside circle (en-dash, not hyphen), "Not yet assessed" date text
- `aria-label` on circle required — color is never sole indicator
- Last assessed date (muted) or "Not yet assessed" (lighter muted)
- Status badge: pill, color from mastery band

### Suggested next steps (bottom of page)

- Checks `useMyStudyPlans()` defensively
- Plans exist: "You have N study plans waiting. Go to Study Plans →"
- No plans: "Your teacher will assign study plans for areas that need more work."


### Data sources

| Element | Endpoint |
|---|---|
| Gap profile data | `GET /api/v1/students/me/gap-map?subject_id={id}` via `useMyGapMap` |
| Study plans check | `GET /api/v1/students/me/study-plans` via `useMyStudyPlans` |

### Key rules

- Always use `/me` shortcut — never construct student ID in URL
- Score 0.4 exactly → Developing (not Needs Work) — inclusive boundary
- Score 0.7 exactly → Strong — inclusive boundary on the Strong side

---

## 4. Study Plans List
**Route:** `/student/study-plans`
**Sidebar nav:** Study plans item active

### Layout

- Page heading "Study plans" (Fraunces)
- Filter pills: All / Active / In progress / Completed
- Card list, one card per plan

### Plan card states

| Status | Card style | CTA |
|---|---|---|
| ACTIVE | White, green border accent | "Start plan →" green button |
| IN_PROGRESS | White, amber border accent | "Continue →" gold button |
| COMPLETED | Muted opacity, "Completed ✓" badge + quiz score | "Review" ghost button |

- Featured/newest active plan: gold border `border-[#e8c97a]` — same pattern as teacher lesson plans

### Empty state

"No study plans yet. Your teacher will assign them based on your assessment results."

### Data sources

| Element | Endpoint |
|---|---|
| Plans list | `GET /api/v1/students/me/study-plans` with optional `?status=` and `?subject_id=` |

---

## 5. Study Plan Detail
**Route:** `/student/study-plans/:planId`
**Sidebar nav:** Study plans item active

### Layout

Two-column grid (`grid-cols-[1fr_1fr]`): Resources left · Quiz right

### Resources section

- Header: "Learning resources" + "✨ Matched to your style" badge (always shown)
- Resource card: type icon (📹 VIDEO / 📄 ARTICLE / 🎮 INTERACTIVE) + title (2-line truncate) + source + duration
- Action button: "Watch" / "Read" / "Try" → opens URL in new tab
- "Mark as done" checkbox — optimistic update on tick, revert on failure
- Watched resources: green tint background `bg-green-50`, "Done ✓" in green

### Quiz section (right column)

- Soft gate: if no resources watched, show lock icon + "Complete at least one resource to unlock the quiz"
- Questions still in DOM but `opacity-40 pointer-events-none` — UX hint, not a security boundary
- All questions on single scrollable page (not paginated)
- MCQ: 2×2 grid on mobile, horizontal on desktop. Single select.
- SHORT_ANSWER: multi-line textarea, 300-char limit, character counter
- "Submit quiz" disabled until all questions answered

### Quiz results (post-submit)

- Score prominently displayed
- Per-question reveal: student answer + correct/incorrect + correct answer + explanation
- Score message: ≥0.8 "Great work! 🎉" green · ≥0.6 "Good effort!" amber · <0.6 "Keep practising" muted (never discouraging)
- Plan status → COMPLETED if score ≥ 0.8

### Data sources

| Element | Endpoint |
|---|---|
| Plan detail | `GET /api/v1/study-plans/{planId}` |
| Mark watched | `PATCH /api/v1/study-plans/{planId}/resources/{resourceId}/watched` |
| Submit quiz | `POST /api/v1/study-plans/{planId}/quiz/submit` |

---

## 6. Take Assessment
**Route:** `/student/assessments/:attemptId/take`
**Layout:** Full-screen assessment mode — NO `StudentLayout`. No sidebar, no nav.

### Flow

- Tier 1: attempt pre-created by `trigger_onboarding_diagnostics` Celery task — retrieved via `GET /classes/{classId}/diagnostic`
- Tier 2: attempt created lazily on first access — `GET /attempts/{attemptId}` (backend creates if not exists)
- Both tiers use identical UI — no component difference

### Topbar (assessment mode)

- Logo left
- Assessment name + "Question N of M · Class name" centre
- "Leave" right → confirmation dialog before exit

### Progress bar

- Thin bar below topbar — fills proportionally to answered questions

### Save indicator

- Below progress bar: "Saving..." → "Saved ✓" (inline, small, muted)
- Failure: "Save failed — check your connection" — never blocks student

### Question layout

- Q number (muted uppercase label)
- Question text (Fraunces, 18px)
- MCQ options: 2×2 grid mobile, horizontal row desktop
- Selected: `border-2 border-brand-primary bg-brand-primary/10`
- Unselected: `border border-role-student-border bg-white`

### Navigation

- Back/Next buttons in fixed footer
- Auto-save on Next: `POST /attempts/{id}/responses` silently in background
- Previously answered question → shows previous answer (local state, no API call)

### Submit flow

- Last question: Next replaced by "Submit assessment" button
- Unanswered questions: modal "You have left {n} question(s) unanswered. Submit anyway?"
- Loading overlay: "Submitting..." on confirm
- On success: navigate to results page

### Data sources

| Element | Endpoint |
|---|---|
| Load attempt + questions | `GET /api/v1/attempts/{attemptId}` |
| Auto-save answer | `POST /api/v1/attempts/{attemptId}/responses` |
| Submit | `POST /api/v1/attempts/{attemptId}/submit` |

---

## 7. Assessment Results
**Route:** `/student/assessments/:attemptId/results`
**Layout:** Full-screen centred — uses `StudentLayout` but no sidebar item is active

### Layout (centred, full screen)

1. "Submitted ✓" green pill badge
2. Large SVG score ring (120px) — stroke color from `getMasteryStyle(score)`
3. "N of M correct" below ring
4. "Diagnostic complete!" banner (amber, shown after EVERY submission — harmless for Tier 2)
5. "Back to dashboard" green button

### Score ring colors

- `score > 0.7` → green `#16a34a`
- `0.4 ≤ score ≤ 0.7` → amber `#f59e0b`
- `score < 0.4` → red `#ef4444`

### Diagnostic complete banner

Always shown, unconditionally — do NOT check `is_system_generated` on frontend (field not in `AttemptResultResponse`).

### No "View detailed answers" in v1

Per spec: security concern with caching correct answers client-side. Deferred to v2.

### Data sources

| Element | Endpoint |
|---|---|
| Result data | Router state (from submit mutation) OR `GET /api/v1/attempts/{attemptId}/results` if page visited directly |

---

## 8. Settings
**Route:** `/student/settings`
**Layout:** `StudentLayout` — no sidebar item active (settings reached via avatar)

### Layout

- Full page — max width `640px`, centred in content area
- 3 sections: Account · Learning profile · Account actions

### Account section

- Name: editable inline (Edit link → expand form row)
- Email: read-only, "Managed by school" note
- Password: Change link → inline expand with 3 fields (current, new, confirm)
- Inline edit: save/cancel buttons, no page navigation

### Learning profile section

Shows current profile data (read-only display):
- Modality bars (4 dimensions, dominant highlighted in gold `#c9932a` to match lesson plan rationale)
- Interest tags (pill badges)
- Completed date

"Retake questionnaire" button — routes back to `/student/onboarding/profile`
Note below button: "Updating your profile improves future personalisation. ~5 minutes."

### Account actions section

- Sign out (danger button, red border — not background)
- No account deletion in v1

### Data sources

| Element | Endpoint |
|---|---|
| Display profile | `GET /api/v1/onboarding/learning-profile` (student's own) |
| Update name | `PATCH /api/v1/users/me` |
| Change password | `POST /api/v1/auth/change-password` |
| Retake profile | Routes to `/student/onboarding/profile` → `POST /api/v1/onboarding/questionnaire/submit` (idempotent) |

---

## Design rules enforced across all Student pages

| Rule | Detail |
|---|---|
| Sidebar is the sole nav | `StudentLayout` includes left sidebar — NO top nav tabs, NO bottom nav |
| Active state: green tint + green dot | `bg-[#f0fdf4] text-brand-primary` + dot `bg-brand-primary` |
| Classes section in sidebar | Dynamically listed from `useMyClasses()` — unlocked green dot, locked amber lock icon |
| Locked class items | Route to diagnostic page, amber text `text-brand-gold`, lock icon — not disabled |
| Profile card at sidebar bottom | Avatar initials, name, grade — click goes to settings |
| Always use `/me` shortcuts | Never construct student ID in URLs (`/students/me/gap-map` not `/students/{id}/gap-map`) |
| `score=null` → "–" | Never "0%" — use en-dash character for unassessed |
| `aria-label` on every mastery circle | Color is never the only indicator — CONSTITUTION Rule 9 |
| Green action color | `#1a5c38` for all buttons — not gold (that's Teacher only) |
| Questionnaire is idempotent | Re-submit updates, never creates duplicate `student_learning_profiles` row |
| No streak badge | Removed per product decision |
| Gate 1 only in OnboardingRouter | `OnboardingRoute` checks `learning_profile_complete` only — diagnostic is Gate 2 on dashboard |
| Diagnostic complete banner always shown | Never check `is_system_generated` on frontend — banner is harmless for Tier 2 |
| Assessment + Study plan pages: no special layout | Both use `StudentLayout` with sidebar — not full-screen, except Take Assessment |
| Take Assessment: no sidebar | Uses custom full-screen layout — `StudentLayout` is NOT used on this page |

---



---

*Kaihle Design Sprint · Student Role · March 2026*
*v2.1 update: Sidebar layout replaces top nav tabs + bottom nav. Reference mockup: `docs/design/mockups/student_dashboard.html`*
*Next role: School Admin → Kaihle Admin → Parent*
