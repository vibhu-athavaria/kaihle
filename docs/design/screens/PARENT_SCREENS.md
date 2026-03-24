# Parent Role — Screen Design Specifications
**Design sprint:** March 2026
**Authors:** Pixel (UI/UX) · Vidhya (information hierarchy) · Kramer (data map)
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.5
**App:** `apps/parent` · port 3003
**Task file:** `docs/tasks/M5/M5-1-T3_parent_portal_ui.md`

---

## Vidhya — The Pedagogical Foundation

**Why parents don't see numeric scores — and this is not dumbing it down.**

This is the single most important design decision in the entire parent portal, and it deserves a proper explanation.

A parent who sees "Emma scored 0.42 in Algebraic Fractions" has been given information they cannot usefully act on. They don't know:
- Whether 0.42 is typical for this stage of learning
- Whether 0.42 represents progress or regression
- What they should say to Emma that evening

A teacher who sees 0.42 reads: "Emma has foundational understanding but is inconsistent under test conditions. She needs more practice with procedure before the next checkpoint." The teacher has the professional training to convert a number into an instructional decision.

The parent portal converts that same 0.42 into: *"Emma is developing her skills in Algebra and would benefit from practising a few problems each evening."* This is actionable. This is what a good parent-teacher conference gives a parent in 10 minutes.

**The three things parents need:**

1. *"Is my child okay?"* — A traffic-light summary (Strong / Developing / Needs Work) answers this immediately. No numbers needed.

2. *"What changed this week?"* — The weekly narrative tells the story of progress, framed warmly and in plain language. Parents read this on their phone at 7pm. It must be readable in 30 seconds.

3. *"What can I do?"* — The narrative always ends with one specific, actionable next step. "Emma will be working on percentages next. Encouraging her to talk through how she solved a maths problem at dinner can reinforce her learning."

**Cambridge and IB context:** Both frameworks explicitly discourage sharing raw numeric scores with parents outside of official progress reports. Kaihle's parent portal embodies this principle continuously, not just at reporting time.

---

## Pixel — Design Philosophy

The parent app is the softest, warmest interface in the five-app system. Every other app serves a professional — a teacher, an admin, an internal operator. The parent app serves a human being who loves their child and is probably slightly anxious about whether they're okay at school.

**Design principles for this app:**

1. **Warm over clinical.** Cream background (`#fdf8f0`), Lora serif for all headings, generous line-height. This is a kitchen-table conversation, not a spreadsheet.

2. **Mobile-first, always.** Parents check this on their phone in the car at school pick-up. Every interaction must work perfectly at 375px with one thumb.

3. **Content, not chrome.** No heavy navigation, no sidebar, no bottom tabs. The parent has one job: read about their child. Get out of the way and let them do it.

4. **Traffic lights not heatmaps.** The teacher heatmap is a professional tool for data analysis. Parents need 🟢🟡🔴. Period.

5. **Celebrate progress.** When a subject is all Strong, show a small delight moment — a green celebration row. Parents notice when tools acknowledge their child's success.

---

## Page Inventory

| # | Page | Route | Task file | Status |
|---|---|---|---|---|
| 1 | Login | `/login` | Shared `LoginForm` (M0-3-T5) | ✅ Built |
| 2 | Password setup | `/parent/setup-password` | Shared `PasswordSetupForm` (M0-9-T4) | ✅ Built |
| 3 | Dashboard | `/parent/dashboard` | `M5/M5-1-T3_parent_portal_ui.md` | ✅ Designed |
| 4 | Child Progress | `/parent/children/:studentId/progress` | `M5/M5-1-T3_parent_portal_ui.md` | ✅ Designed |
| 5 | Settings | `/parent/settings` | `M0/M0-7-T6_parent_settings_ui.md` | 🔲 Pending |

---

## Layout System

```
ParentLayout:
  Top nav: max-w-2xl mx-auto px-4 h-14
    Left:  Kaihle wordmark (small, text-based, not full logo)
    Right: Child selector (if 2+ children) | Avatar → Settings
  Content: max-w-2xl mx-auto px-4 py-6
  Background: bg-role-parent-bg (#fdf8f0) — warm cream, all pages
  No sidebar. No bottom nav.
```

---

## Design Tokens (parent-specific)

| Token | Value | Usage |
|---|---|---|
| `bg-role-parent-bg` | `#fdf8f0` | Page background |
| `font-lora` | Lora serif | All headings, narrative text |
| `font-nunito` | Nunito sans | Labels, meta, badges |
| Traffic light strong | `#16a34a` | 🟢 Strong circle |
| Traffic light developing | `#f59e0b` | 🟡 Developing circle |
| Traffic light needs-work | `#ef4444` | 🔴 Needs Work circle |
| Traffic light not-assessed | `#d1d5db` | ⚪ Not yet assessed |

---

## 3. Dashboard
**Route:** `/parent/dashboard`

### Child Selector (conditional — 2+ children only)

```
Pixel: Use native <select> on mobile — do not fight the platform.
Styled dropdown on md: and above.
Placement: top of content area, below nav.
When hidden (single child): no empty space — content starts immediately.
```

### NarrativeCard component

```
Component: NarrativeCard
──────────────────────────────────────────────────────────
Card:       bg-white rounded-2xl shadow-sm p-6
Week label: font-nunito text-[11px] uppercase tracking-widest
            text-gray-400 mb-2
Narrative:  font-lora text-base leading-[1.75] text-gray-800
            Truncated at 3 lines: overflow-hidden
            with CSS line-clamp-3 (not JS)
            "Read more" chevron: text-brand-primary text-sm
            Toggled by <details> or controlled state — NO page navigation
Highlights: flex flex-wrap gap-2 mt-4
  Pill: bg-amber-50 text-amber-700 border border-amber-100
        rounded-full text-xs px-3 py-1 font-nunito font-medium
──────────────────────────────────────────────────────────
Empty state (no reports yet):
  Icon: 📖 (emoji, 40px, text-center, mb-3)
  Heading: "Your first update is coming" — font-lora text-lg
  Body: "Weekly updates appear here after your child completes their
         first diagnostic. This usually happens within a few days."
         font-nunito text-sm text-gray-500 leading-relaxed
  (Vidhya: warm, not alarming — no "Nothing yet" cold empty state)
──────────────────────────────────────────────────────────
Accessibility:
  aria-live="polite" on the card container — narratives update when
  child selector changes
  "Read more" toggle: aria-expanded + aria-controls
```

### SubjectOverviewCard component

```
Component: SubjectOverviewCard
──────────────────────────────────────────────────────────
Grid:       grid-cols-3 gap-3 (max 3 subjects in v1)
Card:       bg-white rounded-2xl border border-gray-100 p-4 text-center
            cursor-pointer active:scale-[0.98] transition-transform
Subject:    font-lora text-sm font-semibold text-ink mb-3
Circle:     w-12 h-12 mx-auto rounded-full flex items-center justify-center
            Strong:      bg-green-100 text-green-600
            Developing:  bg-amber-100 text-amber-600
            Needs Work:  bg-red-100 text-red-600
            Not assessed: bg-gray-100 text-gray-400
            Icon inside: plain emoji 🟢🟡🔴⚪ OR coloured dot — NOT text
Status:     font-nunito text-xs text-gray-500 mt-2
──────────────────────────────────────────────────────────
Accessibility:
  aria-label="{subject}: {status}" on card
  Do not use colour as sole indicator — status text always shown
  Tap → /parent/children/{id}/progress (that subject tab pre-selected)
```

---

## 4. Child Progress
**Route:** `/parent/children/:studentId/progress`

### Two-tab layout

```
Tabs: "Progress Map" | "Weekly Reports"
Tab nav: bg-white border-b border-gray-200 sticky top-14 (below ParentLayout nav)
Active: border-b-2 border-brand-primary text-brand-primary
Inactive: text-gray-500 hover:text-gray-700
```

### Progress Map tab — SimpleGapMap component

```
Component: SimpleGapMap
──────────────────────────────────────────────────────────
Vidhya: Topics only — do NOT show subtopics. Subtopics are too granular
        for a parent. A parent seeing "Algebraic Fractions" has no context.
        Show "Algebra" (topic level). Teachers see subtopics; parents see topics.

Legend row:
  flex gap-4 text-xs font-nunito text-gray-500 py-3 px-1
  🟢 Strong  🟡 Developing  🔴 Needs Work  ⚪ Not assessed

Subject accordion (one per subject):
  Header: font-lora text-base font-semibold text-ink
          flex items-center justify-between py-4 cursor-pointer
          Chevron rotates 90° on expand — CSS transition 200ms
  Body:   list of TopicTrafficLight rows

Celebration row (Pixel + Vidhya):
  When ALL topics in a subject are Strong:
    Show: "Great work in {subject}! 🌟"
    Style: text-brand-primary font-nunito text-sm py-3 px-1
    Do NOT show individual topic rows — celebrate the whole (Vidhya: positive framing)

Empty state (no gap data):
  "Progress data will appear here once your child completes
   their first assessment."
──────────────────────────────────────────────────────────
```

### TopicTrafficLight component

```
Component: TopicTrafficLight
──────────────────────────────────────────────────────────
Row:        flex items-center gap-3 py-3 border-b border-gray-50 last:border-0
Circle:     w-4 h-4 rounded-full flex-shrink-0
            Strong:      bg-green-500   (NOT #16a34a — slightly lighter for parent warmth)
            Developing:  bg-amber-400
            Needs Work:  bg-red-400
            Not assessed: bg-gray-300
Topic:      font-nunito text-sm text-gray-800
Status:     font-nunito text-xs text-gray-400 ml-auto
──────────────────────────────────────────────────────────
Accessibility:
  aria-label="{topicName}: {status}"
  Circle: aria-hidden="true" (status text is the meaningful content)
  (Pixel: colour is NEVER the only indicator — status text always present)
```

### Weekly Reports tab — WeeklyReportAccordion

```
Component: WeeklyReportAccordion
──────────────────────────────────────────────────────────
Most recent: expanded by default
Each row:
  Header:  "Week of {date} · {subject}" — flex justify-between py-4
           font-nunito text-sm font-medium text-ink
           Chevron + date + subject
  Body:    font-lora text-sm leading-[1.75] text-gray-700 pb-4
           Highlights: bullet list (•) font-nunito text-xs text-gray-500 mt-3
  Footer:  "Generated automatically each Sunday" — text-xs text-gray-400
──────────────────────────────────────────────────────────
Pixel: Use <details>/<summary> HTML elements for native
accordion behaviour — this gets keyboard + AT support for free.
No JS toggle needed unless custom animation required.
──────────────────────────────────────────────────────────
Empty state (no reports yet — same as dashboard empty state):
  Warm message, not cold "No data"
```

---

## 5. Settings *(basic spec — pending full task)*
**Route:** `/parent/settings`
**Task file needed:** `docs/tasks/M0/M0-7-T6_parent_settings_ui.md`

### Sections (v1 minimum)

**Account:** Name (editable), Email (read-only "Managed by school"), Password (change inline)

**My children (read-only):**
List of linked children: name + grade + school name.
"To update child associations, contact your school admin."
(Vidhya: parents sometimes try to add or remove children themselves — set expectation clearly)

**Sign out:** Outlined red button, no confirmation dialog.

### Design rules
- Lora heading: "Settings"
- Narrow column consistent with other pages (`max-w-xl`)
- Same inline edit patterns as other settings pages

---

## Design Rules — All Parent Pages

| Rule | Rationale |
|---|---|
| No numeric mastery scores | Vidhya: parents cannot contextualise raw numbers; plain labels are more actionable |
| Warm cream background on all pages | Pixel: signals a safe, non-clinical space |
| Lora serif for headings + narrative | Pixel: editorial warmth, readable at medium sizes |
| Traffic lights at topic level (not subtopic) | Vidhya: subtopics are too granular for parents |
| Native `<select>` for child selector on mobile | Pixel: don't fight the platform |
| `<details>/<summary>` for accordions | Pixel: free keyboard + AT support |
| Celebration row when all topics Strong | Pixel + Vidhya: positive reinforcement matters |
| `aria-label` on every status circle | Pixel: colour is never the sole indicator |
| Max content width `max-w-2xl` | Pixel: comfortable reading column, not full-width noise |
| No bottom nav | Pixel: parents have 2 pages — sidebar and bottom nav are overkill |
| One actionable next step per narrative | Vidhya: parents need to know what to DO |

---

## API Calls — Complete List

```
GET /parent/children                          → child selector, dashboard
GET /parent/children/{id}/reports?page_size=1 → latest narrative card
GET /parent/children/{id}/reports?page_size=10 → full report accordion
GET /parent/children/{id}/gap-map             → progress map + subject overview
GET /users/me                                 → settings (name/email)
PATCH /users/me                               → settings (update name)
POST /auth/change-password                    → settings (password)
POST /auth/logout                             → settings (sign out)
```

No other endpoints. The parent app never calls student, teacher, or admin routes.

---

*Kaihle Design Sprint · Parent Role · March 2026*
*Pixel — UI/UX · Vidhya — Education · Kramer — Data architecture*
