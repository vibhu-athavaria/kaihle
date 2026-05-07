# Student App Sprint — Master Plan
> Reviewed by: Kramer (Engineering) · Pixel (UX/UI) · Vidhya (Pedagogy)
> All decisions are final. Task files are self-contained. Claude Code can execute each independently.

---

## What We Are Building

Five focused improvements that take the student app from a read-only progress tracker to a useful daily learning tool. Every feature maps to a real student need confirmed in code review.

---

## Task Files (execute in order)

| File | What it does | Deps |
|---|---|---|
| `ST-A-dashboard-actions.md` | Fix dead NextStep buttons + streak placeholder | none |
| `ST-B-study-plans-list.md` | Build Study Plans list page (real data, not empty state) | none |
| `ST-C-study-plan-detail.md` | Build Study Plan detail page (resources + quiz) | ST-B merged |
| `ST-D-concept-guide-panel.md` | Move ConceptGuide to right-side sliding panel | none |
| `ST-E-results-page-split.md` | Split assessment results: diagnostic vs formative copy | none |

All five can be branched from `main` independently. ST-C depends on ST-B being merged first (shares list-page hook).

---

## What We Are NOT Building in This Sprint

- Streak counter backend (streak bar shows "Coming soon" placeholder — see ST-A)
- `/student/classes/:classId/topics` route (backend is a stub — blocked externally)  
- Multi-turn chat history for Concept Guide (single-session only for MVP)
- Study plan generation by student (teacher-initiated only)
- Notifications

---

## Design Decisions (locked, no agent reasoning required)

**Sidebar:** Study Plans is a nav item. Badge shows count of ACTIVE + IN_PROGRESS plans.

**Concept Guide panel:** Slides in from right, 360px wide, overlays content (does not push layout). Triggered from SubtopicScoreRow ("Explain this →") and Study Plan detail. Single session — no history stored. Session closes when student closes the panel.

**Study Plans routing:** `/student/study-plans` = list. `/student/study-plans/:planId` = detail. Detail is a separate route, not inline accordion.

**Post-assessment results:** Branch on assessment type. Diagnostic → existing copy ("Diagnostic complete!"). Formative → "Assessment submitted. Your progress has been updated." + CTA to My Progress.

**NextStep cards:** Each type maps to a fixed route. No onAction prop — use `useNavigate` directly in the card.

**Streak:** UI placeholder only. Backend `streakDays` returns null — show "🔥 Streak coming soon" greyed out. No backend work in this sprint.
