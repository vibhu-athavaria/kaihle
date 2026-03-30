# Parent Role — Screen Design Specifications
**Design sprint:** March 2026 · **Updated:** March 2026 (v2.1 — sidebar layout)
**Authors:** Pixel (UI/UX) · Vidhya (information hierarchy) · Kramer (data map)
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.5
**App:** `apps/parent` · port 3003
**Layout wrapper:** `ParentLayout` — left sidebar + top nav + content
**⚠️ Layout change v2.1:** Sidebar replaces minimal top nav only (see Layout System below)
**Task file:** `docs/tasks/M5/M5-1-T3_parent_portal_ui.md`
**Sidebar active state:** Warm cream tint `bg-[#fdf8f0]` + gold dot `bg-brand-gold`
**Reference mockup:** `docs/design/mockups/parent_dashboard.html`

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

1. **Warm over clinical.** Cream background (`#fdf8f0`), Lora serif for all headings and narrative, warm sand borders. This is a kitchen-table conversation, not a spreadsheet.

2. **Mobile-first, always.** Parents check this on their phone in the car at school pick-up. Every interaction must work perfectly at 375px.

3. **Sidebar keeps it oriented without overwhelming.** Three nav items is all a parent needs. The sidebar provides consistent wayfinding without cluttering the content area. Child switching lives in the sidebar, not scattered across pages.

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
  Shell:    flex h-screen overflow-hidden bg-[#fdf8f0]

  Sidebar:  w-[200px] flex-shrink-0 bg-white border-r border-[#e8dcc8]
    Logo row:   h-[50px] px-4 border-b border-[#e8dcc8]
                font-['Lora'] italic text-[15px] font-semibold text-[#2c1a0e]
                "Kaihle" wordmark
    Nav:        see Navigation structure below
    Children:   inline child selector card (see §Child Selector below)
    Profile:    mt-auto border-t border-[#e8dcc8] px-3.5 py-3
                Avatar + parent name + "Parent" role label

  Top nav:  h-[50px] bg-white border-b border-[#e8dcc8]
            px-[18px] flex items-center justify-between
    Left:   Greeting (font-['Lora'] medium text-[13px] text-[#2c1a0e])
            + child name/grade subtitle (font-sans text-[10px] text-[#a08060])
    Right:  Avatar → settings

  Content:  flex-1 overflow-y-auto bg-[#fdf8f0] p-[18px]
            max-w-none (no narrow column constraint — sidebar handles layout width)
```

**No bottom nav. No horizontal nav tabs in top nav. Sidebar is the sole navigation.**

---

## Design Tokens (parent-specific)

| Token | Value | Usage |
|---|---|---|
| `bg-role-parent-bg` | `#fdf8f0` | Page background + active nav tint |
| `border-role-parent-border` | `#e8dcc8` | All borders — warm sand |
| `text-role-parent-ink` | `#2c1a0e` | Primary text — espresso |
| `text-role-parent-muted` | `#a08060` | Secondary text — warm taupe |
| `font-lora` | Lora serif | All headings, narrative text, sidebar logo |
| `font-nunito` | Nunito sans | Labels, meta, badges, nav items |
| Active nav dot | `#c9932a` | Gold dot on active sidebar item |
| Traffic light strong | `#16a34a` | 🟢 Strong circle |
| Traffic light developing | `#f59e0b` | 🟡 Developing circle |
| Traffic light needs-work | `#ef4444` | 🔴 Needs Work circle |
| Traffic light not-assessed | `#d1d5db` | ⚪ Not yet assessed |

---

## Navigation structure

### Sidebar

```
Section: OVERVIEW
  Home             → /parent/dashboard                               (active: cream tint + gold dot)
  Progress map     → /parent/children/:studentId/progress?tab=map
  Weekly reports   → /parent/children/:studentId/progress?tab=reports

Section: CHILDREN
  [Child selector inline card — see below]
```

Active state: `bg-[#fdf8f0] text-[#2c1a0e] font-semibold` + `w-[6px] h-[6px] rounded-full bg-brand-gold` dot before label.

Settings: accessed via avatar in top nav — NOT a sidebar item.

### Child Selector (in sidebar — Section: CHILDREN)

Shown for ALL parents regardless of child count (single child parents see a single non-interactive row — confirms which child's data is shown).

```
Inline card: bg-[#fdf8f0] border border-[#e8dcc8] rounded-[8px]
             mx-[10px] mt-[10px] p-[9px]

Label: "Switch child" — text-[9px] font-bold uppercase tracking-[0.5px] text-[#a08060] mb-1

Per child row: flex items-center gap-2 py-[5px]
               border-b border-[#f5ead0] last:border-0
               cursor-pointer (multi-child) or cursor-default (single child)

  Avatar:  w-[22px] h-[22px] rounded-full text-[9px] font-bold flex-shrink-0
           Each child gets a distinct warm background:
             Child 1: bg-brand-green-light text-brand-primary
             Child 2: bg-amber-100 text-amber-700
             Child 3: bg-violet-100 text-violet-700
             (etc. — cycle through warm/non-harsh palettes)

  Name:    text-[11px] font-medium text-[#2c1a0e]
  Grade:   text-[9px] text-[#a08060]

  Active indicator: w-[5px] h-[5px] rounded-full bg-brand-primary ml-auto
                    (shows on currently selected child only)
```

When child switches: update `studentId` in all downstream React Query keys. Store in component state — not URL params. URL at `/parent/dashboard` stays consistent.

**Implementation note:** Unlike v1.0 spec which placed this as a `<select>` at the top of page content, the child selector now lives entirely in the sidebar. No `<select>` element appears in the content area.

---

## 3. Dashboard
**Route:** `/parent/dashboard`
**Sidebar nav:** Home item active

### Content area (no narrow column — sidebar handles layout)

Two main sections stacked vertically:

1. **Latest update** → `NarrativeCard` showing most recent weekly report
2. **Subject overview** → 2-column grid of `SubjectOverviewCard` components
3. **Topic detail** (optional, expanded below subject grid) → `TopicTrafficLight` rows for selected subject

### NarrativeCard component

```
Component: NarrativeCard
──────────────────────────────────────────────────────────
Card:       bg-white rounded-2xl border-[1.5px] border-[#e8dcc8] p-5
Week label: font-sans text-[9px] uppercase tracking-[0.8px]
            text-[#a08060] flex items-center gap-2
            Green dot (w-[7px] h-[7px] rounded-full bg-brand-primary) + label + date right-aligned
Narrative:  font-['Lora'] text-sm leading-[1.7] text-[#2c1a0e]
            Truncated at 3 lines with CSS line-clamp-3
            "Read full report →" — font-sans text-[10px] font-bold text-brand-gold
Highlights: flex flex-wrap gap-2 mt-3
  Pill: bg-brand-green-light border border-brand-mid rounded-full
        text-[9px] font-semibold text-brand-green px-3 py-1 font-sans
──────────────────────────────────────────────────────────
Empty state (no reports yet):
  Icon: 📖 emoji, text-center
  Heading: "Your first update is coming" — font-['Lora'] text-lg text-[#2c1a0e]
  Body: "Weekly updates appear here after your child completes their first diagnostic."
        font-sans text-sm text-[#a08060] leading-relaxed
──────────────────────────────────────────────────────────
Accessibility:
  aria-live="polite" on the card container — narratives update when child switches
  "Read full report" toggle: aria-expanded + aria-controls
```

### SubjectOverviewCard component

```
Component: SubjectOverviewCard
──────────────────────────────────────────────────────────
Grid:       grid-cols-2 gap-2 (2-column, not 3 — parent sees fewer subjects than student)
Card:       bg-white border border-[#e8dcc8] rounded-[10px] p-[10px]
            cursor-pointer active:scale-[0.98] transition-transform
Subject:    font-['Lora'] text-[11px] font-semibold text-[#2c1a0e] mb-2
Traffic:    flex gap-1 flex-wrap
  Circle:   w-[10px] h-[10px] rounded-full — Strong #16a34a, Developing #f59e0b,
            Needs Work #ef4444, Not assessed #d1d5db
Link:       font-sans text-[9px] font-bold text-brand-gold mt-[6px] block
            "View progress →"
──────────────────────────────────────────────────────────
Accessibility:
  aria-label="{subject}: {overall status}" on card
  Individual traffic light circles: aria-hidden="true" (status text label provides meaning)
  Tap → /parent/children/{studentId}/progress?tab=map&subject={subjectId}
```

---

## 4. Child Progress
**Route:** `/parent/children/:studentId/progress`
**Sidebar nav:** Progress map or Weekly reports active (based on current tab)

### Two-tab layout

```
Tabs: "Progress Map" | "Weekly Reports"
Tab nav: bg-white border-b border-[#e8dcc8] sticky (below ParentLayout top nav)
Active: border-b-2 border-brand-primary text-brand-primary font-semibold
Inactive: text-[#a08060] hover:text-[#2c1a0e]
```

### Progress Map tab — SimpleGapMap component

```
Component: SimpleGapMap
──────────────────────────────────────────────────────────
Vidhya: Topics only — do NOT show subtopics. Subtopics are too granular
        for a parent. A parent seeing "Algebraic Fractions" has no context.
        Show "Algebra" (topic level). Teachers see subtopics; parents see topics.

Legend row:
  flex gap-4 text-xs font-sans text-[#a08060] py-3 px-1
  🟢 Strong  🟡 Developing  🔴 Needs Work  ⚪ Not assessed

Subject accordion (one per subject):
  Header: font-['Lora'] text-base font-semibold text-[#2c1a0e]
          flex items-center justify-between py-4 cursor-pointer
          Chevron rotates 90° on expand — CSS transition 200ms
  Body:   list of TopicTrafficLight rows

Celebration row (Pixel + Vidhya):
  When ALL topics in a subject are Strong:
    Show: "Great work in {subject}! 🌟"
    Style: text-brand-primary font-sans text-sm py-3 px-1
    Do NOT show individual topic rows — celebrate the whole subject

Empty state (no gap data):
  "Progress data will appear here once your child completes their first assessment."
──────────────────────────────────────────────────────────
```

### TopicTrafficLight component

```
Component: TopicTrafficLight
──────────────────────────────────────────────────────────
Row:        flex items-center gap-3 py-3 border-b border-[#f5ead0] last:border-0
            bg-white border border-[#e8dcc8] rounded-[8px] px-3 mb-1
Circle:     w-[10px] h-[10px] rounded-full flex-shrink-0
            Strong:       #16a34a
            Developing:   #f59e0b
            Needs Work:   #ef4444
            Not assessed: #d1d5db
Topic:      font-['Lora'] text-sm text-[#2c1a0e]
Status:     font-sans text-[10px] font-semibold ml-auto
            ts-green #16a34a / ts-amber #c9932a / ts-red #ef4444
──────────────────────────────────────────────────────────
Accessibility:
  aria-label="{topicName}: {status}" on each row
  Circle: aria-hidden="true" (status text is the meaningful content)
```

### Weekly Reports tab — WeeklyReportAccordion

```
Component: WeeklyReportAccordion
──────────────────────────────────────────────────────────
Most recent: expanded by default on tab load
Each row:
  Collapsed header: "Week of {date} · {subject}"
    font-sans text-sm font-medium text-[#2c1a0e] flex justify-between py-4
    Chevron + date left, subject right
  Expanded body:
    font-['Lora'] text-sm leading-[1.7] text-[#2c1a0e] pb-4
    Highlights bullet list: font-sans text-xs text-[#a08060] mt-3
  Footer: "Generated automatically each Sunday"
    font-sans text-xs text-[#a08060]
──────────────────────────────────────────────────────────
Pixel: Use <details>/<summary> HTML elements for native accordion —
free keyboard + AT support, no JS toggle needed.
──────────────────────────────────────────────────────────
Empty state: warm message — not cold "No data"
  "Weekly updates will appear here after your child's first diagnostic."
```

---

## 5. Settings *(basic spec — pending full task)*
**Route:** `/parent/settings`
**Task file needed:** `docs/tasks/M0/M0-7-T6_parent_settings_ui.md`
**Sidebar nav:** No item active (accessed via avatar)

### Sections (v1 minimum)

**Account:** Name (editable), Email (read-only "Managed by school"), Password (change inline)

**My children (read-only):**
List of linked children: name + grade + school name.
"To update child associations, contact your school admin."
(Vidhya: parents sometimes try to add or remove children themselves — set expectation clearly)

**Sign out:** Red outline button, no confirmation dialog.

### Design rules

- Lora heading: "Settings"
- Content area max-width consistent with other pages
- Same inline edit patterns as other settings pages in the platform

---

## API Calls — Complete List

```
GET /parent/children                           → child selector (sidebar), dashboard
GET /parent/children/{id}/reports?page_size=1  → latest narrative card (dashboard)
GET /parent/children/{id}/reports?page_size=10 → full report accordion (progress page)
GET /parent/children/{id}/gap-map              → progress map + subject overview
GET /users/me                                  → settings (name/email)
PATCH /users/me                                → settings (update name)
POST /auth/change-password                     → settings (password)
POST /auth/logout                              → settings (sign out)
```

No other endpoints. The parent app never calls student, teacher, or admin routes directly.

---

## Design Rules — All Parent Pages

| Rule | Rationale |
|---|---|
| Sidebar is the sole nav | `ParentLayout` includes left sidebar — NO minimal top nav only, NO bottom nav |
| Active state: cream tint + gold dot | `bg-[#fdf8f0]` + dot `bg-brand-gold` — distinguishes from Student (green dot) |
| Child selector lives in sidebar | NOT in page content area — sidebar section "CHILDREN" contains it |
| Warm cream background on all pages | Pixel: signals a safe, non-clinical space |
| Lora serif for headings + narrative | Pixel: editorial warmth, readable at medium sizes |
| No numeric mastery scores anywhere | Vidhya: parents cannot contextualise raw numbers; plain labels are actionable |
| Traffic lights at topic level (not subtopic) | Vidhya: subtopics are too granular for parents |
| `<details>/<summary>` for accordions | Pixel: free keyboard + AT support |
| Celebration row when all topics Strong | Pixel + Vidhya: positive reinforcement matters |
| `aria-label` on every status circle | Pixel: colour is never the sole indicator |
| One actionable next step per narrative | Vidhya: parents need to know what to DO |
| All borders use `#e8dcc8` warm sand | Pixel: visual coherence across warm palette |
| Lora in sidebar logo | Parent is the only role with Lora in the sidebar wordmark |

---

*Kaihle Design Sprint · Parent Role · March 2026*
*v2.1 update: Sidebar layout replaces minimal top nav. Child selector moved from page content to sidebar. Reference mockup: `docs/design/mockups/parent_dashboard.html`*
*Pixel — UI/UX · Vidhya — Education · Kramer — Data architecture*
