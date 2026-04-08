# M3-0-T2b — Teacher Explanation Review UI
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-0 — Content Infrastructure
**Task:** T2b
**Executor:** Coding agent
**Depends on:** M3-0-T1 (subtopic_content seeded with llm_explanation),
               M0-8-T7 (Modal component), M0-8-T6 (Toast system),
               M2-1-T3 (teacher gap map heatmap — explanation review links from here)
**Blocks:** M3-1-T2 (quiz generator uses approved_explanation as context)

> **App target:** `apps/teacher` ONLY.
> Load `DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
> Gold is the action color. Green = mastery only. Never green buttons.

---

## User Story

As a teacher, I want to review the AI-generated text explanation for each subtopic I
teach, make corrections where needed, and approve it — so that my students receive
accurate, quality explanations in their study packs.

---

## Context

`M3-0-T1` generated an LLM explanation for every subtopic. These explanations are
stored as `subtopic_content.llm_explanation` with `explanation_review_status = 'pending'`.

Teachers are not responsible for reviewing every subtopic in the platform — only
subtopics that belong to classes they teach. This scoping is critical for keeping
the review burden low.

The explanation review UI is embedded in two places:
1. **The Gap Map side panel** (M2-1-T3) — teacher clicks a subtopic cell, sees a
   "Review explanation" link in the panel
2. **A dedicated Review Queue page** — teacher can batch-review all pending
   explanations for their classes

The teacher reviews `llm_explanation`, edits if needed, and approves it. The approved
text is stored in `approved_explanation`. The `explanation_review_status` moves to
`'approved'`.

Teachers do NOT review videos — that is KaihleAdmin's responsibility (M3-0-T2a).

---

## Backend — API Endpoints

All new endpoints go in the existing `routes/subtopic_content.py` created by M3-0-T2a.
Add teacher-facing endpoints:

```python
# GET  /subtopic-content/explanation-queue
# Returns subtopics with pending explanations scoped to teacher's classes
# Query params: class_id (optional filter to one class)
# Auth: TEACHER role only

# GET  /subtopic-content/{subtopic_id}/explanation
# Returns explanation for one subtopic (teacher must teach a class with this subtopic)
# Auth: TEACHER role

# PATCH /subtopic-content/{subtopic_id}/explanation
# Submit approved explanation (with optional edits)
# Body: {"approved_explanation": "...", "explanation_review_status": "approved" | "rejected"}
# Auth: TEACHER role
```

### Service logic for teacher scoping

```python
async def get_teacher_explanation_queue(
    teacher_id: UUID,
    class_id: UUID | None,
    db: AsyncSession,
) -> list[SubtopicExplanationQueueItem]:
    """
    Returns subtopics with pending explanations for classes this teacher teaches.
    Scoped to teacher's school via class.teacher_id + class.school_id check.
    """
    query = (
        select(Subtopic, SubtopicContent, CurriculumTopic, Subject, Grade)
        .join(SubtopicContent, Subtopic.id == SubtopicContent.subtopic_id)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .join(Class, and_(
            Class.subject_id == Subject.id,
            Class.grade_id == Grade.id,
            Class.curriculum_id == CurriculumTopic.curriculum_id,
            Class.teacher_id == teacher_id,
        ))
        .where(SubtopicContent.explanation_review_status == 'pending')
    )
    if class_id:
        query = query.where(Class.id == class_id)
```

### Schemas (add to `schemas/subtopic_content.py`)

```python
class ExplanationQueueItem(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    subject_code: str
    grade_level: int
    class_id: UUID
    class_name: str
    llm_explanation: str
    explanation_review_status: str

class ExplanationQueueResponse(BaseModel):
    items: list[ExplanationQueueItem]
    total: int
    pending_count: int

class ExplanationApprovalRequest(BaseModel):
    approved_explanation: str   # teacher's edited (or unedited) version
    explanation_review_status: str  # 'approved' | 'rejected'
```

---

## Frontend — New Pages & Components

### Files to Create

```
frontend/apps/teacher/src/pages/content/
  ExplanationReviewQueue.tsx    ← batch review queue for teacher's classes

frontend/apps/teacher/src/components/content/
  ExplanationReviewPanel.tsx    ← inline review panel (used in gap map side panel)
  ExplanationEditor.tsx         ← editable text area with character counter + approve button
```

### Files to Modify

```
frontend/apps/teacher/src/components/gap-map/
  GapMapSidePanel.tsx           ← add "Review Explanation" section (M2-1-T3 component)
```

### Routing — `App.tsx` in `apps/teacher`

```tsx
<Route path="content/explanations" element={<ExplanationReviewQueue />} />
```

### Sidebar — add Content section

In the teacher sidebar, add a **CONTENT** section after the existing sections:

```tsx
<SidebarSection label="CONTENT">
  <SidebarNavItem
    to="/teacher/content/explanations"
    icon={<FileText className="w-4 h-4" aria-hidden="true" />}
    label="Lesson Explanations"
    badge={pendingExplanationCount > 0 ? pendingExplanationCount : undefined}
  />
</SidebarSection>
```

Badge uses `brand-gold` background (teacher action color) when count > 0.

---

## Component Specifications

### `ExplanationReviewQueue.tsx`

**Route:** `/teacher/content/explanations`

```
Page title:   "Lesson Explanation Review"
Sub-label:    "Review AI-generated explanations for your classes"

Filter:       [All Classes ▾]  (dropdown by class name)

Table:
┌────────────────────────┬──────────┬───────┬──────────────┐
│ SUBTOPIC               │ CLASS    │ GRADE │ STATUS       │
├────────────────────────┼──────────┼───────┼──────────────┤
│ Forces and Motion      │ Grade 7  │ Gr.7  │ ● Pending    │
│ Algebraic Fractions    │ Grade 8  │ Gr.8  │ ● Pending    │
│ Cell Structure         │ Grade 9  │ Gr.9  │ ✓ Approved   │
└────────────────────────┴──────────┴───────┴──────────────┘

Row click → opens ExplanationEditor inline (not a navigation)
```

Clicking a pending row expands it inline to show the `ExplanationEditor`.

### `ExplanationEditor.tsx`

This is the core review component. It can be used both inline in the queue and
embedded in the gap map side panel.

```
┌─────────────────────────────────────────────────────────────┐
│  AI-Generated Explanation  [Edit ✎]                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Forces are pushes or pulls that act on an object.  │   │
│  │ Contact forces require physical touch — for example │   │
│  │ friction slows a sliding book. Non-contact forces   │   │
│  │ act at a distance, like gravity pulling you down    │   │
│  │ or magnetism attracting a paperclip. When forces    │   │
│  │ are balanced, objects stay still or move steadily.  │   │
│  │ Unbalanced forces cause acceleration.               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  147 / 200 words                                            │
│                                                             │
│  ⚠️  Review this explanation for accuracy.                  │
│     Edit if needed, then approve.                           │
│                                                             │
│  [✓ Approve]   [✗ Reject]   [Cancel]                       │
└─────────────────────────────────────────────────────────────┘
```

**Button Tailwind classes — enforced, no exceptions:**

```tsx
{/* Approve — gold primary action. NEVER green in the teacher app. */}
<button
  className="bg-brand-gold text-white text-sm font-semibold px-4 py-2
             rounded-full hover:bg-brand-gold-dark transition-colors
             focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2
             disabled:opacity-50 disabled:cursor-not-allowed"
  onClick={handleApprove}
>
  ✓ Approve
</button>

{/* Reject — outlined danger style */}
<button
  className="border border-red-300 text-red-600 text-sm font-semibold
             px-4 py-2 rounded-full hover:bg-red-50 transition-colors
             focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-2"
  onClick={handleReject}
>
  ✗ Reject
</button>

{/* Cancel — neutral secondary */}
<button
  className="border border-role-teacher-border text-brand-ink text-sm
             font-semibold px-4 py-2 rounded-full hover:bg-gray-50 transition-colors
             focus-visible:ring-2 focus-visible:ring-brand-border focus-visible:ring-offset-2"
  onClick={onCancel}
>
  Cancel
</button>
```

> ⚠️ **Design rule — no green buttons in teacher app.**
> `bg-brand-primary` and `bg-brand-green` are mastery colours only.
> All teacher CTAs use `bg-brand-gold`. Any green button here is a design violation.

When teacher clicks **Edit ✎**, the text area becomes editable (`contenteditable`
or `<textarea>`). Word counter updates in real time. Changes are highlighted with
a subtle amber left border `border-l-2 border-brand-gold`.

**Issue 9 fix — focus management on edit mode activation (WCAG 2.1):**

When the teacher clicks **Edit ✎** and the component switches to edit mode,
focus must programmatically move to the textarea. Without this, keyboard and
screen reader users lose their position.

```tsx
const textareaRef = useRef<HTMLTextAreaElement>(null)

const handleEditClick = () => {
  setIsEditing(true)
  // Focus must move to textarea after React re-renders
  requestAnimationFrame(() => {
    textareaRef.current?.focus()
    // Place cursor at end of text
    const len = textareaRef.current?.value.length ?? 0
    textareaRef.current?.setSelectionRange(len, len)
  })
}

// In JSX — attach ref to textarea
<textarea
  ref={textareaRef}
  className="w-full text-sm text-brand-ink leading-relaxed p-3
             border border-role-teacher-border rounded-lg resize-none
             focus:outline-none focus:ring-2 focus:ring-brand-gold focus:ring-offset-1"
  value={editedText}
  onChange={e => setEditedText(e.target.value)}
  aria-label={`Edit explanation for ${subtopicName}`}
  rows={8}
/>
```

When **Approve** or **Reject** completes and the component collapses, focus must
return to the row trigger (the subtopic name in the queue table) to maintain
keyboard navigation position. Pass a `triggerRef` prop for this purpose.

On **Approve**: PATCH endpoint called with the current text (edited or original).
Interest examples section (if present — see below) has its own separate approve action.

**Interest examples flag:** If the `llm_explanation` contains a section starting with
`[INTEREST EXAMPLE:` (a tag the LLM is instructed to include), render it in a
distinctly styled callout:

```
┌─ Interest Example ────────────────────────────────────────┐
│  🎯 If the student is interested in football, you might   │
│  say: "When a goalkeeper dives to stop a ball, they       │
│  apply an unbalanced force..."                            │
│  [✓ Approve example]  [✗ Reject example]                  │
└───────────────────────────────────────────────────────────┘
```

Interest examples are approved/rejected independently from the main explanation.

Props:
```tsx
interface ExplanationEditorProps {
  subtopicId: string
  subtopicName: string
  llmExplanation: string
  reviewStatus: 'pending' | 'approved' | 'rejected'
  onApprove: (text: string) => Promise<void>
  onReject: () => Promise<void>
  compact?: boolean   // true when used in side panel (reduces padding)
}
```

### `GapMapSidePanel.tsx` modification

After the existing student gap score and learning style section, add:

```tsx
{/* Subtopic explanation review — shown to teacher only */}
{canReviewExplanations && (
  <div className="mt-4 pt-4 border-t border-role-teacher-border">
    <div className="text-xs font-bold uppercase tracking-wide text-role-teacher-muted mb-2">
      Lesson Explanation
    </div>
    {explanationStatus === 'pending' ? (
      <ExplanationEditor
        subtopicId={selectedSubtopicId}
        subtopicName={selectedSubtopicName}
        llmExplanation={explanation}
        reviewStatus="pending"
        onApprove={handleApprove}
        onReject={handleReject}
        compact={true}
      />
    ) : (
      <div className="text-xs text-brand-body">
        ✓ Explanation approved
        <button className="text-brand-gold text-xs ml-2 hover:underline"
          onClick={openFullEditor}>
          Edit
        </button>
      </div>
    )}
  </div>
)}
```

---

## Acceptance Criteria

### Backend
- [ ] `GET /subtopic-content/explanation-queue` scoped to teacher's classes only
- [ ] Teacher from School A cannot see/edit subtopic content for School B classes
- [ ] `PATCH /subtopic-content/{id}/explanation` requires TEACHER role
- [ ] Approving sets `approved_explanation`, `explanation_reviewed_by`, `explanation_reviewed_at`
- [ ] Rejecting sets `explanation_review_status = 'rejected'`, does not set `approved_explanation`
- [ ] Teacher submitting different text → `approved_explanation` stores their edited version
- [ ] Pending count decreases after approval

### Frontend
- [ ] Queue loads teacher's pending explanations only (scoped to their classes)
- [ ] Clicking pending row expands ExplanationEditor inline
- [ ] Word counter updates in real time as teacher edits
- [ ] Interest example block renders distinctly with separate approve action
- [ ] Approve → row shows ✓ Approved, collapses, count badge decreases
- [ ] Reject → row shows ✗ Rejected status
- [ ] Gap Map side panel shows ExplanationEditor for pending subtopics
- [ ] Gap Map side panel shows "✓ approved" for already-reviewed subtopics
- [ ] Toast shown on API error
- [ ] Empty state shown when all explanations reviewed

---

## Tests to Write

```python
# backend/tests/unit/test_explanation_review.py
def test_explanation_queue_when_teacher_then_scoped_to_their_classes()
def test_explanation_queue_when_other_teacher_then_excludes_their_subtopics()
def test_approve_explanation_when_valid_then_stores_approved_text()
def test_approve_explanation_when_teacher_edits_then_stores_edited_version()
def test_approve_explanation_when_not_teacher_role_then_403()
def test_reject_explanation_when_valid_then_status_rejected()
def test_explanation_queue_count_when_all_approved_then_zero()
```

---

## Do NOT Touch

- `subtopic_content.videos` or video review status — that is M3-0-T2a (KaihleAdmin)
- `apps/kaihle-admin` — no teacher review UI goes there
- Any other teacher app pages — this task adds only the content review section

---

*Task M3-0-T2b · Pixel (UX/UI Lead) + Kramer (Technical Lead) · April 2026*
