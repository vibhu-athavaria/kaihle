# Teacher Role — Screen Design Specifications
**Design sprint:** March 2026  
**Personas:** Vidhya (information hierarchy) · Pixel (UI/UX) · Kramer (data map)  
**Design system:** `docs/design/DESIGN_SYSTEM.md` §5.3  
**App:** `apps/teacher` · port 3001  
**Layout wrapper:** `DashboardLayout variant="teacher"`  
**Action color:** Gold `#c9932a` — never green buttons  
**Heading font:** Fraunces · Body: Nunito  
**Sidebar active state:** Gold tint fill `bg-[#fffbeb] text-brand-gold-dark font-bold`

---

## Page inventory

| # | Page | Route | Status |
|---|---|---|---|---|
| 1 | Dashboard | `/teacher/dashboard` | ✅ Designed |
| 2 | Gap Map | `/teacher/classes/:classId/gap-map` | ✅ Designed |
| 3 | Assessments list | `/teacher/classes/:classId/assessments` | ✅ Designed |
| 4 | Assessment creation | `/teacher/assessments/new` | ✅ Designed |
| 5 | Assessment results — class | `/teacher/assessments/:id/results` | ✅ Designed |
| 6 | Assessment results — student | `/teacher/assessments/:id/results/:studentId` | ✅ Designed |
| 7 | Lesson plans list | `/teacher/classes/:classId/lesson-plans` | ✅ Designed |
| 8 | Lesson plan detail | `/teacher/lesson-plans/:planId` | ✅ Designed |
| 9 | Student lesson plan preview | `/teacher/lesson-plans/:planId/student/:studentId` | ✅ Designed |
| 10 | My students | `/teacher/classes/:classId/students` | 🔲 Pending |
| 11 | Student profile | `/teacher/students/:studentId` | 🔲 Pending |
| 12 | Settings | `/teacher/settings` | 🔲 Pending |

---

## 1. Dashboard
**Route:** `/teacher/dashboard`  


### Layout
- `DashboardLayout variant="teacher"` with `[+ Assessment]` gold button in topbar
- Three sections stacked vertically: Pending action banner → My classes grid → This week

### Sections

**Pending action banner** (`PendingActionBanner.tsx`)
- Gold background `#fffbeb`, amber border `#e8c97a`, warning icon
- Shows first matching condition only: students need study plans → unreviewed results → no assessments yet
- Hidden entirely when no pending actions
- CTA "Go to Gap Map →" — routes to gap map, NOT to a study plans page (study plans have no standalone teacher page)
- Sub-text clarifies: "Assign from the Gap Map → student panel"

**My classes grid** (`ClassCard.tsx`)
- 3-column grid (`grid-cols-3`), 1-col mobile, 2-col md
- Each card: subject colour dot · class name (Fraunces) · student count · mastery score with band colour
- Empty state (no assessments): shows "—" and "Create assessment →" link in gold
- Quick links below divider: "Gap map →" and "Assessments →"

**This week card**
- Shows if any class has a `GENERATED` or `EDITED` lesson plan
- Displays class name + focus subtopics (2 max)
- "View plan →" links to `/teacher/lesson-plans/:planId`
- Empty state: "Lesson plans generate every Monday at 6am."

### Data sources
| Element | Endpoint |
|---|---|
| Class list + mastery | `GET /api/v1/schools/{id}/classes?teacher_id=me` + `GET /classes/{id}/summary` |
| Pending actions | Derived from class data + `GET /classes/{id}/assessments?status=ACTIVE` |
| This week plan | `GET /classes/{id}/lesson-plans?page_size=1` per class (parallelised) |

---

## 2. Gap Map
**Route:** `/teacher/classes/:classId/gap-map`  


### Layout
- Full-width heatmap grid below subject tabs
- Subject tabs: one per enrolled subject (`Mathematics | Science | English`)
- Export CSV button in topbar right
- Breadcrumb back to Classes

### Grid (`GapMapGrid.tsx`)
- HTML `<table>` for accessibility + sticky columns
- Rows = curriculum subtopics, grouped by topic with section headers (`<tr colSpan>`)
- Columns = students (order from first node's `student_scores`)
- Sticky first column (subtopic name)
- Cells: `w-36 h-36` colour squares — no text inside, `aria-label` for screen readers
- Class average column pinned at right — bold, colour by mastery band
- Mastery colours: `#fee2e2` Needs Work · `#fef3c7` Developing · `#dcfce7` Strong · `#f3f4f6` Not assessed
- Legend below grid

### Cell interaction → Side panel (Option A — confirmed)
- Clicking any cell opens `StudentSidePanel` (right-side drawer, 380px, slides over grid)
- Panel shows:
  - **Header:** Student name, grade, class name, ✕ close
  - **Selected subtopic:** Subtopic name, mastery %, band badge, last assessed date
  - **Learning profile** (loads async from second API call): dominant modality icon + label, interest tags (pill badges `bg-gray-100`)
  - If profile not yet completed: "Learning profile not yet completed." (no crash, no skeleton forever)
- **Two action buttons at panel bottom:**
  - Primary gold: "Assign study plan for this subtopic" → `AssignStudyPlanModal`
  - Secondary ghost: "View full profile →" → navigates to `/teacher/students/:studentId`
- Dismiss: ✕ button, Escape key, or overlay click

### Data sources
| Element | Endpoint |
|---|---|
| Heatmap data | `GET /api/v1/classes/{classId}/gap-map?subject_id={id}` via `useClassGapMap` |
| Learning profile (deferred) | `GET /api/v1/onboarding/learning-profile?student_id={id}` — called on cell click only |

### Design rules
- No green buttons anywhere on this page — green is mastery data only
- Export CSV is an outline button, not gold (it's a secondary utility action)
- Study plan assignment modal is gold CTA (teacher taking action)

---

## 3. Assessments List
**Route:** `/teacher/classes/:classId/assessments`

### Layout
- Filter tabs (All / Active / Draft / Closed) — pill toggle style, not underline tabs
- Count label right-aligned
- Table card: `bg-white border rounded-10`
- `[+ Create assessment]` gold button in topbar right

### Table columns
`Title` · `Type` · `Status` · `Questions` · `Deadline` · `Submitted` · `Actions`

### Status badges
| Status | Style |
|---|---|
| Draft | `bg-gray-100 text-gray-600` + gray dot |
| Active | `bg-green-100 text-green-700` + green dot |
| Closed | `bg-slate-100 text-slate-600` + slate dot |

### Type badges
| Type | Style |
|---|---|
| Diagnostic | `bg-blue-50 text-blue-700` |
| Topic specific | `bg-purple-50 text-purple-700` |
| Progress check | `bg-orange-50 text-orange-700` |
| Final | `bg-gray-50 text-gray-600` |

### Actions per status
| Status | Available actions |
|---|---|
| Active | Results · Close |
| Draft | Edit (gold outline) · Delete (red outline) |
| Closed | Results |

### Data sources
| Element | Endpoint |
|---|---|
| Assessment list | `GET /api/v1/classes/{classId}/assessments?status={filter}` |

---

## 4. Assessment Creation Wizard
**Route:** `/teacher/assessments/new`

### 5-step wizard

**Step indicator** — in topbar, not sidebar. Steps: Setup → Topics → Configure → Preview → Publish  
Completed steps: green checkmark `bg-brand-primary text-white`  
Active step: gold `bg-brand-gold text-white`  
Pending steps: `bg-gray-100 text-gray-400`

**Step 1 — Setup**
- Class dropdown (teacher's own classes only)
- 4 assessment type cards in 2×2 grid — icon, name, one-line description
- DIAGNOSTIC and FINAL skip Step 2 (no topic selection needed)
- Next disabled until both class and type selected

**Step 2 — Topics** *(TOPIC_SPECIFIC and PROGRESS_CHECK only)*
- Checklist of curriculum topics for selected class subject/grade
- Each item shows topic name + available question count
- At least one required to proceed

**Step 3 — Configure**
- Question count slider: 5–30, default 10, live readout
- Difficulty range: two number inputs (1.0–5.0, step 0.5)
- Deadline date picker: optional
- Next always enabled (all fields have valid defaults)

**Step 4 — Preview**
- Calls `POST /classes/{classId}/assessments` on mount
- Loading skeleton: "Selecting questions from the bank..."
- Question list: question text + MCQ badge + remove ✕ button
- Question count badge updates on removal
- 422 error state: "Not enough questions — broaden your topic selection."

**Step 5 — Publish**
- Summary card: class, type, topics, question count, difficulty, deadline, visible to N students
- Green info banner: "Students will see this immediately on publish."
- Two actions: "Save as draft" (stays on page) · "Publish now" (`bg-brand-primary green` — confirming success, not an action button, hence green not gold per design system)

### Data sources
| Step | Endpoint |
|---|---|
| Step 1 class list | `GET /api/v1/schools/{id}/classes?teacher_id=me` |
| Step 2 topics | `GET /api/v1/subjects/{id}/topics` |
| Step 4 create draft | `POST /api/v1/classes/{classId}/assessments` |
| Step 5 publish | `POST /api/v1/assessments/{id}/publish` |

---

## 5 & 6. Assessment Results
**Route (class):** `/teacher/assessments/:id/results`  
**Route (student):** `/teacher/assessments/:id/results/:studentId`  
  

### Class overview view (Page 5)

**KPI row** (4 cards)
- Submitted (N of 28) · Class average (%) · Highest score (name) · Needs attention (count below 40%)

**Score distribution bar chart**
- 4 bands: Strong 70%+ · Developing · Needs work · Not submitted
- Horizontal bars proportional to student count
- Colours match mastery band tokens

**Student table**
- Columns: Student · Score (coloured pill) · Band · Submitted date · Action
- Submitted rows: "View answers →" link → navigates to student detail
- Not submitted rows: "Pending" label, no action link
- Search input top right

### Student detail view (Page 6)

**URL:** `/teacher/assessments/:id/results/:studentId`  
**Back button** returns to class overview

**Student header card**
- Avatar initials · Student name · Assessment name · Class
- Score ring (SVG circle): colour from `getMasteryStyle()` — red/amber/green
- Ring shows: percentage, band label, "N of M correct", "Class avg: X%"

**Question-by-question breakdown**
- Each question row: ✓/✕ icon (green/red circle) · Q number · Question text · Answer row
- Answer row: "Given: [answer] ✕" in red if wrong, "Correct: [answer]" in green
- If correct: single "Answer: [answer] ✓" in green, no "Correct:" needed
- "+ N more questions" pagination if > 6 shown

### Data sources
| Element | Endpoint |
|---|---|
| Class overview | `GET /api/v1/classes/{classId}/assessments` + `GET /api/v1/attempts/{id}/results` per student |
| Student detail | `GET /api/v1/attempts/{attemptId}/results` |

### Open items
- Assessment results page needs design specification.
- Teacher results endpoint returns `correct_answer_key` (unlike student endpoint which strips it).

---

## 7. Lesson Plans List
**Route:** `/teacher/classes/:classId/lesson-plans`

### Layout
- List of plan cards, newest first
- Each card: week-of date block · status badge · focus subtopics · action buttons

### Card states
| Status | Badge style | Gold border | Actions |
|---|---|---|---|
| GENERATED | `bg-amber-50 text-amber-700` | Yes (latest only) | Mark as used · View plan |
| EDITED | `bg-green-50 text-green-700` | No | Mark as used · View |
| USED | `bg-green-50 text-green-700` (tick) | No | View · Archive |
| ARCHIVED | `bg-gray-100 text-gray-400` | No | View |

- Most recent GENERATED or EDITED plan: `border-brand-gold border-[1.5px]`
- If generated within last 24 hours: "New ✨" badge (`bg-amber-100 text-amber-700`)

### Empty state
"No lesson plans generated yet. Plans are generated automatically every Monday morning."

### Data sources
| Element | Endpoint |
|---|---|
| Plans list | `GET /api/v1/classes/{classId}/lesson-plans` via `useClassLessonPlans` |
| Status update | `PATCH /api/v1/lesson-plans/{planId}/status` |

---

## 8. Lesson Plan Detail
**Route:** `/teacher/lesson-plans/:planId`

### Two-tab layout
Tabs in subheader below topbar: `Class plan` (gold active underline) · `Students (N)`

### Tab 1 — Class plan

**Topbar actions:** Edit sections · Regenerate (danger outline) · Mark as used (green outline)

**Content layout:** `grid-cols-[1fr_220px]` — sections column + groups sidebar

**Lesson sections** (5 cards, `LessonEditor.tsx`)
- Starter (10 min) · Group A activity (20 min) · Group B activity (20 min) · Group C activity (20 min) · Plenary (10 min)
- Phase dot colours: Starter = amber `#f59e0b` · Groups = gold `#c9932a` · Plenary = green `#16a34a` · Homework = indigo `#6366f1`
- Edit mode: all cards show `<textarea>` simultaneously, "Save changes" button appears at bottom
- "Edit" button is gold outline — toggling edit mode is a teacher action

**Groups sidebar** (`StudentGroupPanel.tsx`)
- Group A count + focus description · Group B · Group C
- AI model name + generation timestamp at bottom

**Regenerate modal**
- "Regenerate this lesson plan? Your edits will be lost. This takes about 30 seconds."
- Cancel · Regenerate (gold)
- On confirm: plan area replaced by skeleton "Generating your new plan..." — polls every 5s

### Tab 2 — Students

**Header note:** "Each student has a personalised plan based on their group and learning profile."

**Student table columns:**  
`Student` · `Group` (A/B/C badge) · `Learning style` (modality tag) · `Weakest subtopic` (mastery %) · `Action`

- Group badges: A = amber · B = blue · C = green
- Modality tags: small pill with emoji icon + label
- Weakest subtopic coloured by mastery band
- Action: "Preview plan →" gold pill → navigates to student lesson plan preview page

### Data sources
| Element | Endpoint |
|---|---|
| Plan content | `GET /api/v1/lesson-plans/{planId}` (merged: `generated_plan` + `teacher_edits`) |
| Save edits | `PATCH /api/v1/lesson-plans/{planId}` |
| Regenerate | `POST /api/v1/lesson-plans/{planId}/regenerate` |
| Status update | `PATCH /api/v1/lesson-plans/{planId}/status` |
| Student list + profile | Derived from `generated_plan.student_groups` + `GET /onboarding/learning-profile?student_id={id}` per student |

---

## 9. Student Lesson Plan Preview
**Route:** `/teacher/lesson-plans/:planId/student/:studentId`  


### Purpose
Read-only teacher view of exactly what lesson experience one student receives — their group activity only, with explicit personalisation rationale. No editing. No class-level sections from other groups.

### Layout
- Breadcrumb: Lesson plans › Week of [date] › Students › [Student name]
- "Teacher preview — read only" badge in topbar right (pill, gray, eye icon)
- Full-width student profile card at top
- `grid-cols-[1fr_240px]` below: lesson sections left · rationale sidebar right

### Student profile card
- Avatar initials · Student name · Class · Grade · Curriculum
- Tags row: Group badge · Modality tag · Interest tags (pill, blue) · Mastery tags for focus subtopics (red/amber)

### Personalisation callout (full width, amber background)
Plain-language explanation: group placement reason, modality match, interest usage.  
Example: "Aisha is in Group A because her mastery on this week's focus subtopics is below 40%..."

### Lesson sections (student-specific view)
Show only sections relevant to this student:
- **Starter** — whole class version (gray badge "Whole class")
- **Main activity** — this student's group only (gold border `border-brand-gold`, amber badge "Group A — [Name]'s activity")
- **Plenary** — whole class version
- **Homework** — whole class version
- Groups B and C activities are NOT shown — irrelevant to this student

Personalisation highlight box inside relevant sections:  
`border-l-3 border-brand-gold bg-amber-50` — explains specific personalisation choice in that section (interest used, modality framing, simplified exit ticket, etc.)

### Rationale sidebar
Cards per personalisation dimension:
1. **Group placement** — mastery threshold explanation
2. **Learning modality** — 4-bar chart (visual/auditory/reading/kinesthetic percentages), dominant highlighted in gold
3. **Focus subtopics** — names + mastery % for the two lowest
4. **Interests used** — which interests were injected and where (starter / quiz scenarios)

**Student navigation** at sidebar bottom:  
`← Prev student` · "1 of 28" · `Next student →`  
Navigation is client-side only — no API call, cycles through the class roster.

### Data sources
| Element | Endpoint |
|---|---|
| Plan content | `GET /api/v1/lesson-plans/{planId}` |
| Student learning profile | `GET /api/v1/onboarding/learning-profile?student_id={studentId}` |

### Open items
- Route pattern `/teacher/lesson-plans/:planId/student/:studentId` needs registering in `apps/teacher/src/App.tsx`.

---

## 10. My Students *(pending design)*
**Route:** `/teacher/classes/:classId/students`  
**Task file:** None

### Planned content
- Class roster table
- Per-student: name, mastery per subject, learning style tag, last active
- Row click → Student Profile page
- Search and sort

---

## 11. Student Profile *(pending design)*
**Route:** `/teacher/students/:studentId`  
**Task file:** None  
**Entry points:** Gap Map side panel "View full profile →" · My Students row click

### Planned content
- Student info header: name, grade, class(es), learning profile tags
- Subject mastery cards (same 3-card pattern as student dashboard, read-only)
- Full gap map for that student by subject (reuses `GET /students/{id}/gap-map`)
- Learning profile detail: full modality bars, work style preferences, interest tags
- Study plan history: assigned plans, status, subtopics covered
- Assessment history: attempts, scores, trend

---

## 12. Settings *(pending design)*
**Route:** `/teacher/settings`  
**Task file:** None

### Scope (confirmed with Vibhu — basic only, rest deferred)
- Account section: display name, email (read-only with "Change email" flow), password change
- Password change: current password → new password → confirm (inline form, no page navigation)
- No notification preferences, no class preferences in v1

---

## Design rules enforced across all Teacher pages

| Rule | Detail |
|---|---|
| No green buttons | Green = mastery data only. All action CTAs use gold `#c9932a` |
| "Publish now" exception | Uses `bg-brand-primary` green — this is confirming success, per design system §5.3 Buttons |
| Sidebar active state | Gold tint fill only — NO left stripe (that is School Admin) |
| Fraunces headings | All page titles, class names, student names |
| Study plans nav item | Shown dimmed with note "Assign from Gap Map →" — no standalone teacher study plans page |
| Mastery thresholds | >0.7 Strong `#16a34a` · 0.4–0.7 Developing `#f59e0b` · <0.4 Needs Work `#ef4444` |
| Side panel navigation | Option A: shallow panel for quick action, full Student Profile page for deep-dive |
| Assessment results | Option A: class overview → navigate to new page per student |

---



---

*Kaihle Design Sprint · Teacher Role · March 2026*  
*Next role: Student → School Admin → Kaihle Admin → Parent*
