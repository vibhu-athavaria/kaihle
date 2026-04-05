# M1-5-T1 — Assessment Questions Review & Edit Page (KaihleAdmin)

**Milestone:** M1 — KaihleAdmin Content Tools  
**Task:** T1 — Assessment Questions review and edit page  
**Executor:** Coding agent  
**Depends on:** M0-10 (API stubs merged, main.py CORS updated)  
**Status:** Ready to implement  

---

## Context

KaihleAdmin needs a paginated, filterable view of all questions in the question bank, with full inline editing via a modal dialog. The platform admin (Vibhu) must be able to correct question content **and** reassign a question's curriculum context (curriculum / grade / subject / topic / subtopic) without re-seeding.

**Architecture note on curriculum reassignment:** Curriculum context is stored as a single FK — `QuestionBank.subtopic_id`. All curriculum metadata (curriculum, grade, subject, topic, subtopic) derives from that join path. Changing curriculum context therefore means changing `subtopic_id` to a subtopic that belongs to the target `CurriculumTopic`. The PATCH endpoint accepts `subtopic_id` as the single field for this. The edit modal exposes cascading dropdowns (curriculum → grade → subject → topic → subtopic) as the UX to discover the correct subtopic_id.

The page lives under a new **Content** section in the KaihleAdmin sidebar and is accessible only to `KAIHLE_ADMIN` role.

---

## Scope

### Backend
- `GET /api/v1/question-bank` — paginated, filterable question list (read)
- `PATCH /api/v1/question-bank/{question_id}` — partial update of any field (edit)
- New schemas: `QuestionBankResponse`, `QuestionBankListResponse`, `QuestionBankUpdateRequest`
- Helper endpoints for populating filter/edit dropdowns (if not already present):
  - `GET /api/v1/curricula` — list of `{id, name}`
  - `GET /api/v1/grades` — list of `{id, name}`
  - `GET /api/v1/subjects` — list of `{id, name}`
  - `GET /api/v1/topics` — list of `{id, name}`
  - `GET /api/v1/subtopics?topic_id=<id>` — filtered list of `{id, name}`
  - `GET /api/v1/curriculum-topics` — list of `{id, name}`
  - **Check the live API before implementing** — only create these if they do not already exist.
- Register `question_bank` router in `backend/app/main.py`

### Frontend (`frontend/apps/kaihle-admin`)
- Add **Content** sidebar section with **Assessment Questions** nav link
- New page: `src/pages/AdminQuestionReview.tsx`
- New route: `path="question-bank"` in `App.tsx`
- Filter bar: cascading dropdowns + question_type + text search — all state in URL params
- Questions table with edit button per row, loading skeleton, empty state, pagination
- Edit modal: two-section form — **Curriculum Context** (cascading dropdowns) + **Content** (all editable fields)

---

## Design Specification — Pixel

> **Pixel's approach:** The edit modal is a focused overlay — white card, centered, max-width 600px, with a clear two-section layout. Curriculum context section first (structural), content section second (editorial), sticky footer for Save/Cancel.

### KaihleAdmin design tokens (DO NOT deviate)

| Token | Value | Usage |
|---|---|---|
| Font | Inter / system-ui | All text |
| Page bg | `#f8f9fb` | Body |
| Card bg | `#ffffff` | All cards |
| Card border | `border border-[#eaecf0]` | All cards |
| Section label | 9px, `#9ca3af`, uppercase, tracking-widest, bold | Sidebar sections, page labels |
| Table header | 8px, `#9ca3af`, uppercase, tracking-wider, bold | Column headers |
| Table text | 10px, `#374151` | Cell content |
| Primary action | `#1a5c38` | Sidebar active dot, focus rings, Save button, active page btn |
| Sidebar active bg | `#f3f4f6` | Active nav item bg |
| Active dot | 6px circle `#1a5c38` | Sidebar active prefix |
| Row hover | `#fafafa` | Table row hover |
| Border radius | `rounded-lg` (8px) cards; `rounded-md` (6px) inputs | — |
| Overlay | `bg-black/40` | Modal backdrop |

### Sidebar addition

Add **Content** section between Platform and System sections:

```
── Content ──────────────────────────────────────
  📝  Assessment Questions
      active: green dot + bg-[#f3f4f6] + text-[#111827] font-medium
      inactive: pl-6 text-[#6b7280]
```

### Page layout

```
┌─ Top nav ──────────────────────────────────────────────────────────────┐
│  Assessment Questions                                       [VA avatar] │
└────────────────────────────────────────────────────────────────────────┘
┌─ Filter bar (bg white, border, rounded-lg, p-3) ───────────────────────┐
│  CURRICULUM▾  GRADE▾  SUBJECT▾  TOPIC▾  SUBTOPIC▾  CURR.TOPIC▾  TYPE▾ │
│  [🔍 Search question text…]                               [Clear all]  │
└────────────────────────────────────────────────────────────────────────┘
┌─ Table card (bg white, border, rounded-lg, overflow-hidden) ───────────┐
│  Assessment Questions                 Showing 1–20 of 847 questions    │
│  QUESTION │ TYPE │ CURRIC │ GR │ SUBJ │ TOPIC │ SUBTOPIC │ DIFF │ EDIT │
│  text...  │ pill │        │    │      │       │          │ Easy │  ✏   │
│                                           [←] [1] [2] [3] [4] [5] [→] │
└────────────────────────────────────────────────────────────────────────┘
```

**Edit button:** rightmost column, header "Edit". `w-7 h-7 rounded border border-[#eaecf0] bg-white text-[#6b7280] hover:bg-[#f3f4f6]`

### Edit modal layout

```
┌─ Backdrop (fixed inset-0, bg-black/40, flex items-center justify-center) ──┐
│  ┌─ Modal (bg-white, rounded-lg, w-full max-w-[600px], shadow-xl) ────────┐ │
│  │  ┌─ Header (px-5 py-4, border-b) ─────────────────────────────────┐   │ │
│  │  │  Edit Question                              [✕ close btn]       │   │ │
│  │  └────────────────────────────────────────────────────────────────┘   │ │
│  │  ┌─ Body (overflow-y-auto, max-h-[70vh], px-5 py-4) ──────────────┐   │ │
│  │  │  ── CURRICULUM CONTEXT ────────────────────────── section label  │   │ │
│  │  │  Current: Cambridge Lower → Grade 7 → Math → … (read-only text) │   │ │
│  │  │  [Curriculum ▾]  [Grade ▾]  [Subject ▾]  [Topic ▾]  [Subtopic▾] │   │ │
│  │  │                                                                   │   │ │
│  │  │  ── CONTENT ──────────────────────────────── section label       │   │ │
│  │  │  Question Text *   [textarea 4 rows]                             │   │ │
│  │  │  Question Type *   [MCQ / TRUE_FALSE / SHORT_ANSWER ▾]           │   │ │
│  │  │  Correct Answer *  [textarea 2 rows]                             │   │ │
│  │  │  Explanation       [textarea 3 rows, nullable]                   │   │ │
│  │  │  Difficulty        [number input 1.0–5.0, nullable]              │  │ │
│  │  │  Active            [toggle — green on, gray off]                 │   │ │
│  │  └────────────────────────────────────────────────────────────────┘   │ │
│  │  ┌─ Footer (border-t, px-5 py-4, flex justify-end gap-2) ─────────┐   │ │
│  │  │  [error text if any]            [Cancel]  [Save changes]        │   │ │
│  │  └────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### Modal field specs

**Section labels:** `text-[9px] font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3`

**Field label:** `text-[10px] text-[#374151] font-medium mb-1`  
Required `*` → `text-[#ef4444]`

**All inputs / selects / textareas:**
```
border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2
focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full
```

**Active toggle:**
```
OFF: bg-[#e5e7eb] knob bg-white
ON:  bg-[#1a5c38] knob bg-white
Size: h-5 w-9, knob h-4 w-4, transition-transform
role="switch" aria-checked={isActive}
```

**Buttons:**
```
Cancel:       border border-[#eaecf0] bg-white text-[#374151] text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#f3f4f6]
Save changes: bg-[#1a5c38] text-white text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#155231]
              disabled (saving): opacity-60 cursor-not-allowed, text becomes "Saving…"
              disabled (empty required fields): opacity-60 cursor-not-allowed
```

**Save error:** `text-[10px] text-[#ef4444] text-right role="alert"` above the buttons.

**On success:** modal closes; table row updates to reflect new values (optimistic local state update, no re-fetch needed).

### Modal cascade rules

```
Changing Curriculum → reset Grade, Subject, Topic, Subtopic dropdowns
Changing Grade      → reset Subject, Topic, Subtopic
Changing Subject    → reset Topic, Subtopic
Changing Topic      → reset Subtopic; trigger subtopic fetch filtered by topic_id
```

On open: all dropdowns start at "Unchanged" (empty value). Current context displayed as read-only text above dropdowns.

### Question type pills (table)

```
MCQ          → bg-blue-50   text-blue-700
TRUE_FALSE   → bg-purple-50 text-purple-700
SHORT_ANSWER → bg-amber-50  text-amber-700
9px font-semibold px-1.5 py-0.5 rounded
```

### Difficulty (table)

```
≥ 0.7      → "Hard"  text-[#ef4444]
0.4–0.69   → "Med"   text-[#f59e0b]
< 0.4      → "Easy"  text-[#16a34a]
null       → "—"     text-[#9ca3af]
```

---

## Backend Implementation

### File: `backend/app/schemas/question_bank.py` (CREATE)

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionBankResponse(BaseModel):
    id: UUID
    question_text: str
    question_type: str
    correct_answer: str
    explanation: str | None
    difficulty_level: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    # Curriculum context (from join)
    curriculum_name: str | None
    subject_name: str | None
    grade_name: str | None
    topic_name: str | None
    subtopic_name: str | None
    curriculum_topic_id: UUID | None

    model_config = {"from_attributes": True}


class QuestionBankListResponse(BaseModel):
    questions: list[QuestionBankResponse]
    total: int
    page: int
    page_size: int


class QuestionBankUpdateRequest(BaseModel):
    """
    All fields optional — PATCH semantics.
    Omitted fields are not updated.
    Pass subtopic_id to reassign curriculum context (must exist in DB).
    Nullable fields (explanation, difficulty_level) can be explicitly set to null to clear them.
    """
    question_text: str | None = None
    question_type: str | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    difficulty_level: float | None = Field(None, ge=1.0, le=5.0)
    is_active: bool | None = None
    subtopic_id: UUID | None = None
```

### File: `backend/app/api/v1/routes/question_bank.py` (CREATE)

```python
"""
Question Bank API — KaihleAdmin question browser and editor.
All routes require KAIHLE_ADMIN role.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.curriculum import (
    Curriculum, CurriculumTopic, Grade, QuestionBank, Subject, Subtopic, Topic,
)
from app.models.user import UserRole
from app.schemas.question_bank import (
    QuestionBankListResponse, QuestionBankResponse, QuestionBankUpdateRequest,
)

router = APIRouter(prefix="/question-bank", tags=["question-bank"])


def _base_query():
    """SELECT with all joins for curriculum context."""
    return (
        select(
            QuestionBank,
            Curriculum.name.label("curriculum_name"),
            Subject.name.label("subject_name"),
            Grade.name.label("grade_name"),
            Topic.name.label("topic_name"),
            Subtopic.name.label("subtopic_name"),
            CurriculumTopic.id.label("curriculum_topic_id"),
        )
        .join(Subtopic, QuestionBank.subtopic_id == Subtopic.id)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .join(Curriculum, CurriculumTopic.curriculum_id == Curriculum.id)
        .join(Subject, CurriculumTopic.subject_id == Subject.id)
        .join(Grade, CurriculumTopic.grade_id == Grade.id)
        .join(Topic, CurriculumTopic.topic_id == Topic.id)
    )


def _to_response(row) -> QuestionBankResponse:
    qb, curriculum_name, subject_name, grade_name, topic_name, subtopic_name, ct_id = row
    return QuestionBankResponse(
        id=qb.id,
        question_text=qb.question_text,
        question_type=qb.question_type,
        correct_answer=qb.correct_answer,
        explanation=qb.explanation,
        difficulty_level=qb.difficulty_level,
        is_active=qb.is_active,
        created_at=qb.created_at,
        updated_at=qb.updated_at,
        curriculum_name=curriculum_name,
        subject_name=subject_name,
        grade_name=grade_name,
        topic_name=topic_name,
        subtopic_name=subtopic_name,
        curriculum_topic_id=ct_id,
    )


@router.get("", response_model=QuestionBankListResponse)
async def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    curriculum_id: UUID | None = Query(None),
    grade_id: UUID | None = Query(None),
    subject_id: UUID | None = Query(None),
    topic_id: UUID | None = Query(None),
    subtopic_id: UUID | None = Query(None),
    curriculum_topic_id: UUID | None = Query(None),
    question_type: str | None = Query(None),
    search: str | None = Query(None),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankListResponse:
    """Paginated, filterable question list. KAIHLE_ADMIN only."""
    query = _base_query()

    if curriculum_id:       query = query.where(Curriculum.id == curriculum_id)
    if grade_id:            query = query.where(Grade.id == grade_id)
    if subject_id:          query = query.where(Subject.id == subject_id)
    if topic_id:            query = query.where(Topic.id == topic_id)
    if subtopic_id:         query = query.where(Subtopic.id == subtopic_id)
    if curriculum_topic_id: query = query.where(CurriculumTopic.id == curriculum_topic_id)
    if question_type:       query = query.where(QuestionBank.question_type == question_type)
    if search:              query = query.where(QuestionBank.question_text.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()

    return QuestionBankListResponse(
        questions=[_to_response(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.patch("/{question_id}", response_model=QuestionBankResponse)
async def update_question(
    question_id: UUID,
    payload: QuestionBankUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionBankResponse:
    """
    Partial update of a question. KAIHLE_ADMIN only.
    Pass subtopic_id to reassign curriculum context.
    Omitted fields are unchanged.
    """
    question = await db.get(QuestionBank, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if payload.subtopic_id is not None:
        if not await db.get(Subtopic, payload.subtopic_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="subtopic_id does not exist",
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)

    row = (await db.execute(_base_query().where(QuestionBank.id == question_id))).one_or_none()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to reload question after update")

    return _to_response(row)
```

### Edit: `backend/app/main.py`

Add import:
```python
from app.api.v1.routes import question_bank
```

Add router:
```python
app.include_router(question_bank.router, prefix="/api/v1")
```

### Helper endpoints — check live API first

Before implementing, verify the following endpoints exist and return `list[{id: UUID, name: str}]`:
- `GET /api/v1/curricula`
- `GET /api/v1/grades`
- `GET /api/v1/subjects`
- `GET /api/v1/topics`
- `GET /api/v1/subtopics` with optional `?topic_id=<uuid>` filter
- `GET /api/v1/curriculum-topics`

**Only create endpoints that do not already exist.** If shape differs from `{id, name}`, write a `doubt.md` before adapting.

---

## Frontend Implementation

### File: `frontend/apps/kaihle-admin/src/pages/AdminQuestionReview.tsx` (CREATE)

```tsx
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "../lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface QuestionRow {
  id: string;
  question_text: string;
  question_type: "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER";
  correct_answer: string;
  explanation: string | null;
  difficulty_level: number | null;
  is_active: boolean;
  curriculum_name: string | null;
  subject_name: string | null;
  grade_name: string | null;
  topic_name: string | null;
  subtopic_name: string | null;
  curriculum_topic_id: string | null;
}

interface QuestionListResponse {
  questions: QuestionRow[];
  total: number;
  page: number;
  page_size: number;
}

interface FilterOption {
  id: string;
  name: string;
}

const QUESTION_TYPES = ["MCQ", "TRUE_FALSE", "SHORT_ANSWER"] as const;

const TYPE_PILL: Record<string, string> = {
  MCQ: "bg-blue-50 text-blue-700",
  TRUE_FALSE: "bg-purple-50 text-purple-700",
  SHORT_ANSWER: "bg-amber-50 text-amber-700",
};

function difficultyLabel(val: number | null) {
  if (val === null) return { label: "—", cls: "text-[#9ca3af]" };
  if (val >= 0.7) return { label: "Hard", cls: "text-[#ef4444]" };
  if (val >= 0.4) return { label: "Med", cls: "text-[#f59e0b]" };
  return { label: "Easy", cls: "text-[#16a34a]" };
}

// ── Main page ──────────────────────────────────────────────────────────────

export function AdminQuestionReview() {
  const [searchParams, setSearchParams] = useSearchParams();
  const curriculumId      = searchParams.get("curriculum_id") ?? "";
  const gradeId           = searchParams.get("grade_id") ?? "";
  const subjectId         = searchParams.get("subject_id") ?? "";
  const topicId           = searchParams.get("topic_id") ?? "";
  const subtopicId        = searchParams.get("subtopic_id") ?? "";
  const curriculumTopicId = searchParams.get("curriculum_topic_id") ?? "";
  const questionType      = searchParams.get("question_type") ?? "";
  const search            = searchParams.get("search") ?? "";
  const page              = parseInt(searchParams.get("page") ?? "1", 10);

  const [curriculums, setCurriculums]           = useState<FilterOption[]>([]);
  const [grades, setGrades]                     = useState<FilterOption[]>([]);
  const [subjects, setSubjects]                 = useState<FilterOption[]>([]);
  const [topics, setTopics]                     = useState<FilterOption[]>([]);
  const [subtopics, setSubtopics]               = useState<FilterOption[]>([]);
  const [curriculumTopics, setCurriculumTopics] = useState<FilterOption[]>([]);
  const [data, setData]                         = useState<QuestionListResponse | null>(null);
  const [loading, setLoading]                   = useState(false);
  const [error, setError]                       = useState<string | null>(null);
  const [editingQuestion, setEditingQuestion]   = useState<QuestionRow | null>(null);

  useEffect(() => {
    apiClient.get("/api/v1/curricula").then(r => setCurriculums(r.data)).catch(() => {});
    apiClient.get("/api/v1/grades").then(r => setGrades(r.data)).catch(() => {});
    apiClient.get("/api/v1/subjects").then(r => setSubjects(r.data)).catch(() => {});
    apiClient.get("/api/v1/topics").then(r => setTopics(r.data)).catch(() => {});
    apiClient.get("/api/v1/subtopics").then(r => setSubtopics(r.data)).catch(() => {});
    apiClient.get("/api/v1/curriculum-topics").then(r => setCurriculumTopics(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (curriculumId)      params.set("curriculum_id", curriculumId);
    if (gradeId)           params.set("grade_id", gradeId);
    if (subjectId)         params.set("subject_id", subjectId);
    if (topicId)           params.set("topic_id", topicId);
    if (subtopicId)        params.set("subtopic_id", subtopicId);
    if (curriculumTopicId) params.set("curriculum_topic_id", curriculumTopicId);
    if (questionType)      params.set("question_type", questionType);
    if (search)            params.set("search", search);
    params.set("page", String(page));
    params.set("page_size", "20");

    setLoading(true);
    setError(null);
    apiClient
      .get(`/api/v1/question-bank?${params}`)
      .then(r => setData(r.data))
      .catch(() => setError("Failed to load questions. Please try again."))
      .finally(() => setLoading(false));
  }, [curriculumId, gradeId, subjectId, topicId, subtopicId, curriculumTopicId, questionType, search, page]);

  const setFilter = useCallback((key: string, value: string) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value); else next.delete(key);
      next.set("page", "1");
      if (key === "curriculum_id") {
        ["grade_id", "subject_id", "topic_id", "subtopic_id", "curriculum_topic_id"].forEach(k => next.delete(k));
      } else if (key === "grade_id") {
        ["subject_id", "topic_id", "subtopic_id", "curriculum_topic_id"].forEach(k => next.delete(k));
      } else if (key === "subject_id") {
        ["topic_id", "subtopic_id", "curriculum_topic_id"].forEach(k => next.delete(k));
      }
      return next;
    });
  }, [setSearchParams]);

  const handleSaveSuccess = (updated: QuestionRow) => {
    setData(prev =>
      prev ? { ...prev, questions: prev.questions.map(q => q.id === updated.id ? updated : q) } : prev
    );
    setEditingQuestion(null);
  };

  const totalPages = data ? Math.ceil(data.total / 20) : 1;
  const from = data && data.total > 0 ? (page - 1) * 20 + 1 : 0;
  const to   = data ? Math.min(page * 20, data.total) : 0;

  return (
    <>
      <div className="p-4 flex flex-col gap-3">
        <p className="text-[9px] font-bold uppercase tracking-widest text-[#9ca3af]">Content</p>

        {/* Filter bar */}
        <div className="bg-white border border-[#eaecf0] rounded-lg p-3 flex flex-wrap gap-2 items-end">
          <FilterSelect label="Curriculum"  value={curriculumId}      onChange={v => setFilter("curriculum_id", v)}       options={curriculums} />
          <FilterSelect label="Grade"       value={gradeId}           onChange={v => setFilter("grade_id", v)}            options={grades} />
          <FilterSelect label="Subject"     value={subjectId}         onChange={v => setFilter("subject_id", v)}          options={subjects} />
          <FilterSelect label="Topic"       value={topicId}           onChange={v => setFilter("topic_id", v)}            options={topics} />
          <FilterSelect label="Subtopic"    value={subtopicId}        onChange={v => setFilter("subtopic_id", v)}         options={subtopics} />
          <FilterSelect label="Curr. Topic" value={curriculumTopicId} onChange={v => setFilter("curriculum_topic_id", v)} options={curriculumTopics} />
          <div className="flex flex-col gap-0.5">
            <label className="text-[8px] uppercase tracking-wide text-[#9ca3af] font-bold">Type</label>
            <select value={questionType} onChange={e => setFilter("question_type", e.target.value)}
              className="border border-[#eaecf0] rounded text-[11px] text-[#374151] bg-white px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]">
              <option value="">All types</option>
              {QUESTION_TYPES.map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-0.5 flex-1 min-w-[180px]">
            <label className="text-[8px] uppercase tracking-wide text-[#9ca3af] font-bold">Search</label>
            <input type="text" placeholder="Search question text…" value={search}
              onChange={e => setFilter("search", e.target.value)}
              className="border border-[#eaecf0] rounded text-[11px] text-[#374151] bg-white px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full" />
          </div>
          <button onClick={() => setSearchParams({})}
            className="text-[10px] text-[#6b7280] hover:text-[#374151] underline self-end pb-[7px]">
            Clear all
          </button>
        </div>

        {/* Table card */}
        <div className="bg-white border border-[#eaecf0] rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#f3f4f6] flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#111827]">Assessment Questions</span>
            {data && (
              <span className="text-[10px] text-[#6b7280]">
                {data.total === 0 ? "No questions" : `Showing ${from}–${to} of ${data.total.toLocaleString()} questions`}
              </span>
            )}
          </div>

          {error && <div className="p-6 text-center text-[11px] text-[#ef4444]" role="alert">{error}</div>}

          {loading && !data && (
            <div className="p-4 flex flex-col gap-2" aria-label="Loading questions">
              {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-8 bg-[#f3f4f6] rounded animate-pulse" />)}
            </div>
          )}

          {!loading && !error && data?.questions.length === 0 && (
            <div className="p-10 text-center text-[11px] text-[#9ca3af]">No questions match your filters.</div>
          )}

          {data && data.questions.length > 0 && (
            <table className="w-full border-collapse text-[10px]">
              <thead>
                <tr>
                  {["Question", "Type", "Curriculum", "Grade", "Subject", "Topic", "Subtopic", "Difficulty", "Edit"].map(h => (
                    <th key={h} className="text-left px-4 py-1.5 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af] border-b border-[#f3f4f6]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.questions.map(q => {
                  const diff = difficultyLabel(q.difficulty_level);
                  return (
                    <tr key={q.id} className="border-b border-[#f9f9f9] last:border-b-0 hover:bg-[#fafafa]">
                      <td className="px-4 py-2 text-[#374151] max-w-[240px]"><p className="line-clamp-2 leading-snug">{q.question_text}</p></td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold ${TYPE_PILL[q.question_type] ?? ""}`}>
                          {q.question_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-[#374151]">{q.curriculum_name ?? "—"}</td>
                      <td className="px-4 py-2 text-[#374151]">{q.grade_name ?? "—"}</td>
                      <td className="px-4 py-2 text-[#374151]">{q.subject_name ?? "—"}</td>
                      <td className="px-4 py-2 text-[#374151]">{q.topic_name ?? "—"}</td>
                      <td className="px-4 py-2 text-[#374151]">{q.subtopic_name ?? "—"}</td>
                      <td className={`px-4 py-2 font-semibold ${diff.cls}`}>{diff.label}</td>
                      <td className="px-4 py-2">
                        <button onClick={() => setEditingQuestion(q)} aria-label={`Edit question ${q.id}`}
                          className="w-7 h-7 rounded border border-[#eaecf0] bg-white flex items-center justify-center text-[#6b7280] hover:bg-[#f3f4f6] hover:text-[#374151] transition-colors">
                          ✏
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {data && totalPages > 1 && (
            <div className="px-4 py-2.5 border-t border-[#f3f4f6] flex items-center justify-end gap-1">
              <PageBtn label="←" disabled={page === 1}
                onClick={() => setSearchParams(prev => { const n = new URLSearchParams(prev); n.set("page", String(page - 1)); return n; })} />
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(p => (
                <PageBtn key={p} label={String(p)} active={p === page}
                  onClick={() => setSearchParams(prev => { const n = new URLSearchParams(prev); n.set("page", String(p)); return n; })} />
              ))}
              <PageBtn label="→" disabled={page >= totalPages}
                onClick={() => setSearchParams(prev => { const n = new URLSearchParams(prev); n.set("page", String(page + 1)); return n; })} />
            </div>
          )}
        </div>
      </div>

      {editingQuestion && (
        <EditQuestionModal
          question={editingQuestion}
          allCurriculums={curriculums}
          allGrades={grades}
          allSubjects={subjects}
          allTopics={topics}
          onClose={() => setEditingQuestion(null)}
          onSaveSuccess={handleSaveSuccess}
        />
      )}
    </>
  );
}

// ── Edit modal ─────────────────────────────────────────────────────────────

function EditQuestionModal({ question, allCurriculums, allGrades, allSubjects, allTopics, onClose, onSaveSuccess }: {
  question: QuestionRow;
  allCurriculums: FilterOption[];
  allGrades: FilterOption[];
  allSubjects: FilterOption[];
  allTopics: FilterOption[];
  onClose: () => void;
  onSaveSuccess: (updated: QuestionRow) => void;
}) {
  const [selectedCurriculumId, setSelectedCurriculumId] = useState("");
  const [selectedGradeId, setSelectedGradeId]           = useState("");
  const [selectedSubjectId, setSelectedSubjectId]       = useState("");
  const [selectedTopicId, setSelectedTopicId]           = useState("");
  const [selectedSubtopicId, setSelectedSubtopicId]     = useState("");
  const [subtopicOptions, setSubtopicOptions]           = useState<FilterOption[]>([]);
  const [questionText, setQuestionText]                 = useState(question.question_text);
  const [questionType, setQuestionType]                 = useState(question.question_type);
  const [correctAnswer, setCorrectAnswer]               = useState(question.correct_answer);
  const [explanation, setExplanation]                   = useState(question.explanation ?? "");
  const [difficultyLevel, setDifficultyLevel]           = useState(question.difficulty_level !== null ? String(question.difficulty_level) : "");
  const [isActive, setIsActive]                         = useState(question.is_active);
  const [saving, setSaving]                             = useState(false);
  const [saveError, setSaveError]                       = useState<string | null>(null);

  useEffect(() => {
    if (!selectedTopicId) { setSubtopicOptions([]); setSelectedSubtopicId(""); return; }
    apiClient.get(`/api/v1/subtopics?topic_id=${selectedTopicId}`)
      .then(r => setSubtopicOptions(r.data)).catch(() => setSubtopicOptions([]));
  }, [selectedTopicId]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    const payload: Record<string, unknown> = {};
    if (questionText !== question.question_text)       payload.question_text = questionText;
    if (questionType !== question.question_type)       payload.question_type = questionType;
    if (correctAnswer !== question.correct_answer)     payload.correct_answer = correctAnswer;
    if (explanation !== (question.explanation ?? ""))  payload.explanation = explanation || null;
    if (isActive !== question.is_active)               payload.is_active = isActive;
    if (selectedSubtopicId)                            payload.subtopic_id = selectedSubtopicId;
    payload.difficulty_level = difficultyLevel !== "" ? parseFloat(difficultyLevel) : null;
    try {
      const response = await apiClient.patch(`/api/v1/question-bank/${question.id}`, payload);
      onSaveSuccess(response.data);
    } catch {
      setSaveError("Failed to save changes. Please try again.");
      setSaving(false);
    }
  };

  const currentContext = [question.curriculum_name, question.grade_name, question.subject_name, question.topic_name, question.subtopic_name].filter(Boolean).join(" → ") || "—";

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog" aria-modal="true" aria-label="Edit question">
      <div className="bg-white rounded-lg w-full max-w-[600px] shadow-xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#eaecf0]">
          <span className="text-[12px] font-semibold text-[#111827]">Edit Question</span>
          <button onClick={onClose} aria-label="Close modal"
            className="w-6 h-6 flex items-center justify-center rounded text-[#6b7280] hover:bg-[#f3f4f6] text-[14px]">✕</button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-5">

          {/* Curriculum context section */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">Curriculum Context</p>
            <p className="text-[10px] text-[#6b7280] mb-3">Current: {currentContext}</p>
            <div className="grid grid-cols-2 gap-3">
              <ModalSelect label="Curriculum" value={selectedCurriculumId} options={allCurriculums} placeholder="Unchanged"
                onChange={v => { setSelectedCurriculumId(v); setSelectedGradeId(""); setSelectedSubjectId(""); setSelectedTopicId(""); setSelectedSubtopicId(""); }} />
              <ModalSelect label="Grade" value={selectedGradeId} options={allGrades} placeholder="Unchanged"
                onChange={v => { setSelectedGradeId(v); setSelectedSubjectId(""); setSelectedTopicId(""); setSelectedSubtopicId(""); }} />
              <ModalSelect label="Subject" value={selectedSubjectId} options={allSubjects} placeholder="Unchanged"
                onChange={v => { setSelectedSubjectId(v); setSelectedTopicId(""); setSelectedSubtopicId(""); }} />
              <ModalSelect label="Topic" value={selectedTopicId} options={allTopics} placeholder="Unchanged"
                onChange={v => { setSelectedTopicId(v); setSelectedSubtopicId(""); }} />
              <ModalSelect label="Subtopic" value={selectedSubtopicId} options={subtopicOptions}
                placeholder={selectedTopicId ? "Select subtopic" : "Select topic first"}
                onChange={setSelectedSubtopicId} />
            </div>
          </div>

          {/* Content section */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">Content</p>
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">Question Text <span className="text-[#ef4444]">*</span></label>
                <textarea rows={4} value={questionText} onChange={e => setQuestionText(e.target.value)}
                  className="w-full border border-[#eaecf0] rounded-md text-[12px] text-[#374151] px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] resize-none" />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">Question Type <span className="text-[#ef4444]">*</span></label>
                <select value={questionType} onChange={e => setQuestionType(e.target.value)}
                  className="w-full border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]">
                  {["MCQ", "TRUE_FALSE", "SHORT_ANSWER"].map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">Correct Answer <span className="text-[#ef4444]">*</span></label>
                <textarea rows={2} value={correctAnswer} onChange={e => setCorrectAnswer(e.target.value)}
                  className="w-full border border-[#eaecf0] rounded-md text-[12px] text-[#374151] px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] resize-none" />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">Explanation</label>
                <textarea rows={3} value={explanation} onChange={e => setExplanation(e.target.value)}
                  placeholder="Optional — leave blank to clear"
                  className="w-full border border-[#eaecf0] rounded-md text-[12px] text-[#374151] px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] resize-none" />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">Difficulty (1.0 – 5.0)</label>
                <input type="number" min={1} max={5} step={0.1} value={difficultyLevel}
                  onChange={e => setDifficultyLevel(e.target.value)} placeholder="Leave blank to clear"
                  className="w-full border border-[#eaecf0] rounded-md text-[12px] text-[#374151] px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]" />
              </div>
              <div className="flex items-center justify-between">
                <label className="text-[10px] text-[#374151] font-medium">Active</label>
                <button type="button" role="switch" aria-checked={isActive} onClick={() => setIsActive(v => !v)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#1a5c38] focus:ring-offset-1 ${isActive ? "bg-[#1a5c38]" : "bg-[#e5e7eb]"}`}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${isActive ? "translate-x-4" : "translate-x-0.5"}`} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#eaecf0] px-5 py-4 flex flex-col gap-2">
          {saveError && <p className="text-[10px] text-[#ef4444] text-right" role="alert">{saveError}</p>}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} disabled={saving}
              className="border border-[#eaecf0] bg-white text-[#374151] text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#f3f4f6] disabled:opacity-40">
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving || !questionText.trim() || !correctAnswer.trim()}
              className="bg-[#1a5c38] text-white text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#155231] disabled:opacity-60 disabled:cursor-not-allowed">
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shared sub-components ──────────────────────────────────────────────────

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: FilterOption[];
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[8px] uppercase tracking-wide text-[#9ca3af] font-bold">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="border border-[#eaecf0] rounded text-[11px] text-[#374151] bg-white px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]">
        <option value="">All {label.toLowerCase()}s</option>
        {options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </div>
  );
}

function ModalSelect({ label, value, onChange, options, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; options: FilterOption[]; placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] text-[#374151] font-medium">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]">
        <option value="">{placeholder ?? `Select ${label.toLowerCase()}`}</option>
        {options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </div>
  );
}

function PageBtn({ label, onClick, disabled, active }: {
  label: string; onClick: () => void; disabled?: boolean; active?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={["w-7 h-7 rounded text-[10px] font-medium flex items-center justify-center transition-colors",
        active ? "bg-[#1a5c38] text-white" : "bg-white border border-[#eaecf0] text-[#374151] hover:bg-[#f3f4f6]",
        disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer",
      ].join(" ")}>
      {label}
    </button>
  );
}
```

### Edit: `frontend/apps/kaihle-admin/src/App.tsx`

Add import:
```typescript
import { AdminQuestionReview } from "./pages/AdminQuestionReview";
```

Add route inside `<Routes>`:
```typescript
<Route path="question-bank" element={<AdminQuestionReview />} />
```

### Edit: KaihleAdmin sidebar nav component

Find the sidebar component. Insert before the System section:

```tsx
{/* ── Content ── */}
<p className="px-3.5 pt-3 pb-1 text-[9px] font-bold uppercase tracking-widest text-[#9ca3af]">
  Content
</p>
<NavItem to="question-bank" icon="📝" label="Assessment Questions" />
```

Adapt `NavItem` props to match the existing component signature exactly.

---

## Test Specifications

### Backend — `backend/tests/api/test_question_bank.py` (CREATE)

`pytest-asyncio` + `httpx.AsyncClient`. Arrange → act → assert.

#### GET /api/v1/question-bank

```
test_list_questions_when_no_filters_then_returns_first_page
  Arrange: Seed 25 questions; auth as KAIHLE_ADMIN.
  Act:     GET /api/v1/question-bank
  Assert:  status==200, len(questions)==20, total==25, page==1, page_size==20

test_list_questions_when_curriculum_filter_then_returns_only_that_curriculum
  Arrange: Seed 10 under curriculum_A, 5 under curriculum_B.
  Act:     GET /api/v1/question-bank?curriculum_id=<curriculum_A.id>
  Assert:  status==200, total==10, all q.curriculum_name==curriculum_A.name

test_list_questions_when_grade_filter_then_returns_only_that_grade
  Arrange: Seed questions across grade_7 and grade_8.
  Act:     GET /api/v1/question-bank?grade_id=<grade_7.id>
  Assert:  status==200, all q.grade_name==grade_7.name

test_list_questions_when_curriculum_topic_filter_then_returns_matching_questions
  Arrange: Seed 3 under curriculum_topic_X, 7 under curriculum_topic_Y.
  Act:     GET /api/v1/question-bank?curriculum_topic_id=<curriculum_topic_X.id>
  Assert:  status==200, total==3

test_list_questions_when_text_search_then_case_insensitive_match
  Arrange: Seed one question containing "photosynthesis".
  Act:     GET /api/v1/question-bank?search=PHOTO
  Assert:  status==200, total>=1, all "photo" in q.question_text.lower()

test_list_questions_when_question_type_filtered_then_returns_only_that_type
  Arrange: Seed 5 MCQ, 3 TRUE_FALSE.
  Act:     GET /api/v1/question-bank?question_type=MCQ
  Assert:  status==200, total==5, all q.question_type=="MCQ"

test_list_questions_when_page_2_then_returns_correct_offset
  Arrange: Seed 25 questions.
  Act:     GET /api/v1/question-bank?page=2&page_size=20
  Assert:  status==200, len(questions)==5, page==2

test_list_questions_when_page_zero_then_returns_422
  Act:     GET /api/v1/question-bank?page=0
  Assert:  status==422

test_list_questions_when_page_size_over_max_then_returns_422
  Act:     GET /api/v1/question-bank?page_size=101
  Assert:  status==422

test_list_questions_when_teacher_role_then_returns_403
  Arrange: Auth as TEACHER role.
  Act:     GET /api/v1/question-bank
  Assert:  status==403

test_list_questions_when_unauthenticated_then_returns_401
  Act:     GET /api/v1/question-bank (no token)
  Assert:  status==401
```

#### PATCH /api/v1/question-bank/{question_id}

```
test_update_question_when_content_fields_changed_then_persists
  Arrange: Seed 1 question; auth as KAIHLE_ADMIN.
  Act:     PATCH /api/v1/question-bank/<id> { question_text: "Updated text" }
  Assert:  status==200, response.question_text=="Updated text", DB row updated

test_update_question_when_subtopic_id_changed_then_curriculum_context_updates
  Arrange: Seed question under subtopic_A (curriculum_A); seed subtopic_B (curriculum_B).
  Act:     PATCH /api/v1/question-bank/<id> { subtopic_id: <subtopic_B.id> }
  Assert:  status==200, response.curriculum_name==curriculum_B.name,
           DB QuestionBank.subtopic_id==subtopic_B.id

test_update_question_when_is_active_toggled_then_persists
  Arrange: Seed question with is_active=True.
  Act:     PATCH /api/v1/question-bank/<id> { is_active: false }
  Assert:  status==200, response.is_active==False

test_update_question_when_explanation_set_to_null_then_clears_field
  Arrange: Seed question with explanation="some text".
  Act:     PATCH /api/v1/question-bank/<id> { explanation: null }
  Assert:  status==200, response.explanation==None

test_update_question_when_difficulty_level_out_of_range_then_returns_422
  Act:     PATCH /api/v1/question-bank/<id> { difficulty_level: 1.5 }
  Assert:  status==422

test_update_question_when_subtopic_id_does_not_exist_then_returns_422
  Act:     PATCH /api/v1/question-bank/<id> { subtopic_id: <random_uuid> }
  Assert:  status==422, detail contains "subtopic_id does not exist"

test_update_question_when_question_not_found_then_returns_404
  Act:     PATCH /api/v1/question-bank/<random_uuid> { question_text: "x" }
  Assert:  status==404

test_update_question_when_omitted_fields_then_unchanged
  Arrange: Seed question; record original correct_answer.
  Act:     PATCH /api/v1/question-bank/<id> { question_text: "New text" }
  Assert:  status==200, response.correct_answer==original_correct_answer

test_update_question_when_teacher_role_then_returns_403
  Arrange: Auth as TEACHER.
  Act:     PATCH /api/v1/question-bank/<id> { is_active: false }
  Assert:  status==403
```

### Frontend — `frontend/apps/kaihle-admin/src/pages/__tests__/AdminQuestionReview.test.tsx` (CREATE)

`vitest` + `@testing-library/react` + `msw`. Wrap renders in `<MemoryRouter>`.

```
test_question_review_page_renders_all_filter_labels
  Arrange: Mock GET /api/v1/question-bank → empty list; mock all option endpoints.
  Act:     render <AdminQuestionReview />
  Assert:  Labels "Curriculum", "Grade", "Subject", "Topic", "Subtopic",
           "Curr. Topic", "Type", "Search", "Clear all" visible.

test_filter_selection_adds_correct_url_param_and_resets_page
  Arrange: Provide curriculum option {id:"c1", name:"Cambridge Lower"}.
  Act:     Select "Cambridge Lower" from Curriculum dropdown.
  Assert:  URL contains curriculum_id=c1; page param==1.

test_cascade_reset_clears_downstream_when_curriculum_changes
  Arrange: Render with initial params grade_id=g1&subject_id=s1&curriculum_id=c1.
  Act:     Change curriculum dropdown.
  Assert:  grade_id and subject_id removed from URL.

test_edit_button_opens_modal_with_question_data_prepopulated
  Arrange: Mock API returns 1 question row.
  Act:     Click ✏ edit button.
  Assert:  Modal visible; question_text textarea contains question's text;
           correct_answer textarea contains question's correct_answer.

test_modal_closes_on_escape_key
  Arrange: Open edit modal.
  Act:     Fire Escape keydown event.
  Assert:  Modal not in document.

test_modal_closes_on_backdrop_click
  Arrange: Open edit modal.
  Act:     Click the backdrop element.
  Assert:  Modal not in document.

test_save_changes_calls_patch_with_changed_fields_only
  Arrange: Mock PATCH → returns updated question. Open modal (is_active=true).
  Act:     Toggle Active to false; click "Save changes".
  Assert:  PATCH called once with body containing is_active==false;
           question_text NOT in body (unchanged).

test_save_changes_updates_table_row_on_success
  Arrange: Mock PATCH → returns question with question_text="Updated".
  Act:     Edit question_text; click "Save changes".
  Assert:  Modal closes; table row shows "Updated".

test_save_changes_shows_error_on_patch_failure
  Arrange: Mock PATCH → network error.
  Act:     Click "Save changes".
  Assert:  role="alert" text "Failed to save changes. Please try again." visible;
           modal remains open.

test_save_button_shows_saving_text_while_in_flight
  Arrange: Mock PATCH with delayed response.
  Act:     Click "Save changes"; check before response resolves.
  Assert:  Button text is "Saving…"; button disabled attribute present.

test_clear_all_resets_all_url_params
  Arrange: Render with params curriculum_id=c1&grade_id=g1&search=photo.
  Act:     Click "Clear all".
  Assert:  URL search params string is empty.

test_empty_state_shown_when_no_questions
  Arrange: Mock API returns { questions: [], total: 0 }.
  Act:     render <AdminQuestionReview />
  Assert:  "No questions match your filters." visible.

test_loading_skeleton_shown_before_api_resolves
  Arrange: Mock API with deferred response.
  Act:     render; check before promise resolves.
  Assert:  aria-label "Loading questions" visible; table not present.
```

---

## Definition of Done

- [ ] `backend/app/schemas/question_bank.py` created with all three schemas
- [ ] `backend/app/api/v1/routes/question_bank.py` created with `GET` and `PATCH` routes
- [ ] Router registered in `backend/app/main.py`
- [ ] Helper filter endpoints exist returning `{id, name}` lists (created if missing, confirmed if present)
- [ ] All 20 backend tests pass
- [ ] `frontend/apps/kaihle-admin/src/pages/AdminQuestionReview.tsx` created (page + modal in one file)
- [ ] Route `path="question-bank"` added in `App.tsx`
- [ ] **Content** sidebar section with "Assessment Questions" NavItem added
- [ ] All 13 frontend tests pass
- [ ] Cascade resets work correctly in both filter bar and edit modal
- [ ] Save only sends changed fields in PATCH body
- [ ] Modal closes on Escape, backdrop click, Cancel, and successful save
- [ ] "Save changes" disabled while request is in flight and when required fields empty
- [ ] Design matches KaihleAdmin system: Inter, `#1a5c38` actions, gray sidebar, green-dot active
- [ ] PR reviewed and approved
