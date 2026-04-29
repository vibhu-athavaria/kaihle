# Kaihle Admin — Curriculum Manager & User Edit
**Date:** 2026-04-28
**Status:** APPROVED — ready for implementation
**Features:** Curriculum CRUD, User Edit Drawer, Platform Users fix

---

## 1. Scope Summary

Two features, four tasks:

| Task | Layer | Description | Depends on |
|---|---|---|---|
| T1 | Backend | `curriculum_service.py` + write routes | — |
| T2 | Backend | Fix `platform/users` stub + `UserService.list_platform_users` | — |
| T3 | Frontend | `AdminCurriculum` page (tree + detail panel) | T1 |
| T4 | Frontend | `EditUserDrawer` + wire into `AdminUsers` | T2 |

---

## 7. API Contract — Full Request & Response Schemas

### 7.1 Extended Read Schemas (admin-specific variants needed)

Existing read schemas (`CurriculumResponse`, `SubjectResponse`, etc.) are too lean for the admin UI — they omit `is_active`, `description`, and other fields the edit forms need. We add admin-specific response schemas alongside the existing ones.

```python
# backend/app/schemas/curriculum.py — additions

class CurriculumAdminResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    country: str | None
    is_active: bool
    created_at: datetime

class GradeAdminResponse(BaseModel):
    id: UUID
    name: str
    level: int
    description: str | None
    is_active: bool

class SubjectAdminResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    icon: str | None
    color: str | None      # hex e.g. "#1a5c38"
    is_active: bool

class CurriculumSubjectResponse(BaseModel):
    curriculum_id: UUID
    subject_id: UUID
    subject_name: str      # joined from subjects.name
    subject_code: str
    is_core: bool
    sort_order: int | None

class TopicAdminResponse(BaseModel):
    # curriculum_topics row joined with topics row
    curriculum_topic_id: UUID
    topic_id: UUID
    name: str              # topics.name
    canonical_code: str | None
    standard_code: str | None          # curriculum_topics.standard_code
    sequence_order: int | None         # curriculum_topics.sequence_order
    learning_objectives: list[str]     # curriculum_topics.learning_objectives
    recommended_weeks: int | None
    is_required: bool
    is_active: bool                    # curriculum_topics.is_active
    subtopic_count: int                # COUNT of subtopics for this ct_id

class SubtopicAdminResponse(BaseModel):
    id: UUID
    curriculum_topic_id: UUID
    name: str
    canonical_code: str | None
    learning_objective: str
    description: str | None
    keywords: list[str]
    bloom_taxonomy_level: str | None
    difficulty_level: int | None
    estimated_minutes: int | None
    sequence_order: int | None
    is_active: bool
```

### 7.2 Write Request Schemas

```python
# backend/app/schemas/curriculum.py — write schemas

class CurriculumCreate(BaseModel):
    name: str                          # max 200, unique
    code: str                          # max 50, unique, slug
    description: str | None = None
    country: str | None = None
    is_active: bool = True

class CurriculumUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    country: str | None = None
    is_active: bool | None = None

class GradeCreate(BaseModel):
    name: str                          # max 50
    level: int                         # 1–13, unique
    description: str | None = None
    is_active: bool = True

class GradeUpdate(BaseModel):
    name: str | None = None
    level: int | None = None           # 1–13
    description: str | None = None
    is_active: bool | None = None

class SubjectCreate(BaseModel):
    name: str                          # max 100, unique
    code: str                          # max 20, unique, uppercase slug
    description: str | None = None
    icon: str | None = None            # Lucide icon name
    color: str | None = None           # hex "#rrggbb"
    is_active: bool = True

class SubjectUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool | None = None

class LinkSubjectRequest(BaseModel):
    subject_id: UUID
    is_core: bool = True
    sort_order: int | None = None

class TopicIdentityCreate(BaseModel):
    # used when creating a NEW topic (step 1, "Create new" branch)
    name: str
    canonical_code: str | None = None
    description: str | None = None
    keywords: list[str] = []

class CurriculumTopicCreate(BaseModel):
    # Exactly one of topic_id or topic_data must be provided
    topic_id: UUID | None = None           # reuse existing topic
    topic_data: TopicIdentityCreate | None = None  # create new topic
    # placement fields (curriculum_id, grade_id, subject_id from URL path)
    standard_code: str | None = None
    sequence_order: int | None = None      # must be > 0 if set
    learning_objectives: list[str] = []
    recommended_weeks: int | None = None
    is_required: bool = True

class CurriculumTopicUpdate(BaseModel):
    standard_code: str | None = None
    sequence_order: int | None = None
    learning_objectives: list[str] | None = None
    recommended_weeks: int | None = None
    is_required: bool | None = None
    is_active: bool | None = None

class SubtopicCreate(BaseModel):
    name: str
    learning_objective: str            # NOT NULL — min 10 chars
    canonical_code: str | None = None
    description: str | None = None
    keywords: list[str] = []
    bloom_taxonomy_level: str | None = None  # Remember|Understand|Apply|Analyse|Evaluate|Create
    difficulty_level: int | None = None      # 1–5, DB CHECK enforced
    estimated_minutes: int | None = None
    sequence_order: int | None = None

class SubtopicUpdate(BaseModel):
    name: str | None = None
    learning_objective: str | None = None
    canonical_code: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    bloom_taxonomy_level: str | None = None
    difficulty_level: int | None = None
    estimated_minutes: int | None = None
    sequence_order: int | None = None
    is_active: bool | None = None
```

### 7.3 New Endpoints — Full Contract

All write endpoints require `require_role(UserRole.KAIHLE_ADMIN)`.

```
POST   /curricula
  Body:     CurriculumCreate
  Response: 201 CurriculumAdminResponse
  Errors:   409 { detail: "Curriculum name already exists" }
            409 { detail: "Curriculum code already exists" }

PATCH  /curricula/{curriculum_id}
  Body:     CurriculumUpdate
  Response: 200 CurriculumAdminResponse
  Errors:   404, 409

POST   /grades
  Body:     GradeCreate
  Response: 201 GradeAdminResponse
  Errors:   409 { detail: "Grade level {n} already exists" }
            422 if level not in 1–13

PATCH  /grades/{grade_id}
  Body:     GradeUpdate
  Response: 200 GradeAdminResponse
  Errors:   404, 409, 422

POST   /subjects
  Body:     SubjectCreate
  Response: 201 SubjectAdminResponse
  Errors:   409 { detail: "Subject name already exists" }
            409 { detail: "Subject code already exists" }

PATCH  /subjects/{subject_id}
  Body:     SubjectUpdate
  Response: 200 SubjectAdminResponse
  Errors:   404, 409

POST   /curricula/{curriculum_id}/subjects
  Body:     LinkSubjectRequest
  Response: 201 CurriculumSubjectResponse
  Errors:   404 if curriculum or subject not found
            409 { detail: "Subject already linked to this curriculum" }

DELETE /curricula/{curriculum_id}/subjects/{subject_id}
  Body:     (none)
  Response: 204
  Errors:   404

POST   /curricula/{curriculum_id}/grades/{grade_id}/subjects/{subject_id}/topics
  Body:     CurriculumTopicCreate
  Response: 201 TopicAdminResponse
  Errors:   400 { detail: "Provide exactly one of topic_id or topic_data" }
            404 if curriculum/grade/subject not found
            404 if topic_id provided but not found
            409 { detail: "Topic already placed in this curriculum/grade/subject" }

PATCH  /curriculum-topics/{ct_id}
  Body:     CurriculumTopicUpdate
  Response: 200 TopicAdminResponse
  Errors:   404

DELETE /curriculum-topics/{ct_id}
  Body:     (none)
  Response: 204  — removes placement, does NOT delete global topic
  Errors:   404

POST   /curriculum-topics/{ct_id}/subtopics
  Body:     SubtopicCreate
  Response: 201 SubtopicAdminResponse
  Errors:   400 { detail: "learning_objective is required" } if blank/empty
            422 if difficulty_level not in 1–5
            404 if ct_id not found

PATCH  /subtopics/{subtopic_id}
  Body:     SubtopicUpdate
  Response: 200 SubtopicAdminResponse
  Errors:   404
            422 if difficulty_level not in 1–5
```

### 7.4 Platform Users Fix

```
GET    /platform/users
  Query:    q (str, optional), role (str, optional), page (int ≥1), page_size (int 1–100)
  Response: 200 PlatformUsersResponse (already defined in platform.py)
  Change:   Inject AsyncSession; implement via UserService.list_platform_users()
  Errors:   403 if not KAIHLE_ADMIN
```

`PlatformUserSummary.last_active` maps to `users.last_login_at`.
`PlatformUserSummary.school_name` is a LEFT JOIN from `schools.name` (NULL for KAIHLE_ADMIN users who have no school).

### 7.5 Existing Read Endpoints Reused Without Change

The frontend reads use these as-is — no modifications needed:

```
GET /curricula                                    → list[CurriculumResponse]  (add admin variant)
GET /curricula/{id}                               → CurriculumResponse
GET /grades?curriculum_id=                        → list[GradeResponse]
GET /subjects?curriculum_id=                      → list[SubjectResponse]
GET /subjects/{id}/topics?curriculum_id=&grade_id= → list[TopicResponse]
GET /topics/{id}/subtopics?curriculum_id=&grade_id= → list[SubtopicResponse]
GET /topics                                       → list[TopicSimpleResponse]  (typeahead search)
GET /curriculum-topics                            → list[CurriculumTopicSimpleResponse]
```

Note: The admin frontend will call the same read endpoints but needs the richer `*AdminResponse` variants for edit forms. We add `GET /curricula` returning `list[CurriculumAdminResponse]` when called with an `admin=true` query param, **or** simply add the missing fields to the existing response schemas since they add no breaking changes (additive only).

---

## 2. Feature A — Curriculum Manager

### 2.1 New Route & Navigation

- **URL:** `/kaihle-admin/curriculum`
- **Page file:** `frontend/apps/kaihle-admin/src/pages/AdminCurriculum.tsx`
- **Nav:** Add "📚 Curriculum" item to `AdminLayout` sidebar under the **Content** section, between Schools and Question Bank
- **Active state:** `bg-gray-100 text-role-admin-ink` + green dot `w-1.5 h-1.5 rounded-full bg-brand-primary` (Kaihle Admin nav active pattern per DESIGN_SYSTEM.md §5.1)

### 2.2 Page Layout

Three columns inside `AdminLayout`:

```
[ App Sidebar (existing) ] [ Tree Panel 220px ] [ Detail Panel flex-1 ]
```

- Tree panel: `bg-[#f8f9fb] border-r border-[#eaecf0]`, full height
- Detail panel: `bg-white`, full height
- Both panels scroll independently

### 2.3 Tree Panel

**Header row** (h-[50px], border-b):
- Left: label "Curricula" (`font-['Inter'] text-sm font-bold text-role-admin-ink`)
- Right: `+ New` button (green rounded-full) → opens CreateCurriculumModal

**Tree nodes — three levels:**

```
▼ Cambridge Lower Secondary        [3 grades badge]     ← Curriculum node
    ▶ Grade 6                                           ← Grade node
    ▼ Grade 7                                           ← Grade node (expanded)
        Mathematics                                     ← Subject node
        ● Science                                       ← Subject node (selected)
        English
    ▶ Grade 8
▶ Cambridge IGCSE                  [2 grades badge]
```

**Node interactions:**
- Curriculum node: click chevron to expand/collapse. Right-click or `⋯` icon: Edit, Toggle active/inactive
- Grade node: click to expand/collapse. `⋯`: Edit, Toggle active/inactive
- Subject node: click to SELECT — loads Topics in detail panel. `⋯`: Edit, Toggle active/inactive
- Selected subject: `bg-[#e8f5e9] text-brand-primary font-semibold` + green left dot

**Add Grade under a Curriculum:**
- Each curriculum node has `+ Grade` inline action on hover
- Opens CreateGradeModal

**Add Subject under a Grade:**
- Each grade node has `+ Subject` inline action on hover
- Opens LinkSubjectModal (search existing OR create new)

**Inactive nodes:** `opacity-50`, strikethrough on name, `[Inactive]` badge

**Empty state:** when no curricula exist → "No curricula yet. Click + New to create your first."

**Loading state:** skeleton rows (`animate-pulse`) while fetching

### 2.4 Detail Panel States

#### State 1 — Nothing selected
```
Empty state centred:
  Icon: BookOpen (Lucide, w-12 h-12 text-role-admin-muted)
  Title: "Select a subject"
  Body: "Choose a curriculum → grade → subject from the tree to view its topics."
```

#### State 2 — Subject selected (Topics list)

**Header (h-[50px], border-b):**
- Breadcrumb: `Cambridge Lower › Grade 7 › Science` (each crumb is a link, clicking navigates tree + clears detail drill)
- Right buttons: `+ Add subject` (secondary), `+ Add topic` (primary green rounded-full)

**Topics table columns:**

| Column | Source | Notes |
|---|---|---|
| # | `curriculum_topics.sequence_order` | Editable via drag handle |
| Topic name | `topics.name` | Click row → drills to Subtopics |
| Subtopics | count of `subtopics` rows | |
| Std. code | `curriculum_topics.standard_code` | |
| Req. weeks | `curriculum_topics.recommended_weeks` | |
| Required | `curriculum_topics.is_required` | Badge: Core / Elective |
| Status | `curriculum_topics.is_active` | Badge: Active / Inactive |
| Actions | — | Edit (opens EditTopicModal), ↕ drag handle |

**Loading state:** skeleton rows
**Empty state:** "No topics yet. Click + Add topic to get started."

#### State 3 — Topic selected (drill-down to Subtopics)

**Breadcrumb deepens:** `Cambridge Lower › Grade 7 › Science › Cell Biology`
- Clicking any crumb segment navigates back to that level

**Header right buttons:** `+ Add subtopic` (primary green rounded-full)

**Subtopics table columns:**

| Column | Source | Notes |
|---|---|---|
| # | `subtopics.sequence_order` | Drag to reorder |
| Name | `subtopics.name` | |
| Learning objective | `subtopics.learning_objective` | Truncated to 60 chars, tooltip on hover |
| Bloom level | `subtopics.bloom_taxonomy_level` | Badge |
| Difficulty | `subtopics.difficulty_level` | 1–5 dots or — |
| Est. mins | `subtopics.estimated_minutes` | |
| Status | `subtopics.is_active` | Badge |
| Actions | — | Edit (opens EditSubtopicModal) |

**Loading state:** skeleton rows
**Empty state:** "No subtopics yet. Click + Add subtopic."

### 2.5 Forms (all use `Modal` from `@kaihle/ui`)

#### CreateCurriculumModal / EditCurriculumModal

| Field | Input | Required | Validation |
|---|---|---|---|
| Name | text | ★ | max 200 chars, unique (409 on conflict) |
| Code | text | ★ | max 50 chars, lowercase-slug hint, unique (409 on conflict) |
| Description | textarea | — | |
| Country | text | — | Leave blank for international boards |
| Is active | toggle | — | Default: true |

#### CreateGradeModal / EditGradeModal

| Field | Input | Required | Validation |
|---|---|---|---|
| Name | text | ★ | max 50 chars (e.g. "Grade 7", "Year 9", "Form 3") |
| Level | number | ★ | Integer 1–13 (DB CHECK — show inline error if out of range) |
| Description | textarea | — | |
| Is active | toggle | — | Default: true |

Note: Level must be unique across all grades. Show error "Level 7 is already taken by Grade 7" on 409.

#### CreateSubjectModal / EditSubjectModal

| Field | Input | Required | Validation |
|---|---|---|---|
| Name | text | ★ | max 100 chars, unique |
| Code | text | ★ | max 20 chars, uppercase hint (e.g. GLOB_PERSP, HUM), unique |
| Description | textarea | — | |
| Icon | text | — | Lucide icon name (e.g. "book", "flask") — show preview |
| Color | color picker | — | Hex #rrggbb — drives subject dot color in teacher/student UI |
| Is active | toggle | — | Default: true |

#### LinkSubjectModal (Add Subject to Curriculum+Grade)

Two modes toggled by radio at top:
- **Use existing subject** — typeahead search of all subjects (`GET /subjects`)
- **Create new subject** — shows CreateSubjectModal fields inline

Common fields (shown in both modes after subject is picked/created):

| Field | Input | Required | Notes |
|---|---|---|---|
| Is core | toggle | — | Default: true. FALSE = elective |
| Sort order | number | — | Display order within curriculum |

#### AddTopicModal (two steps)

**Step 1 — Topic identity**

| Field | Input | Required | Notes |
|---|---|---|---|
| Topic | typeahead search | ★ | Searches `topics.name`. Shows "Create new topic: [query]" option |
| (if new) Name | text | ★ | max 255 chars |
| (if new) Canonical code | text | — | e.g. `MATH-ALG` — stable across grades |
| (if new) Description | textarea | — | |
| (if new) Keywords | tag input | — | Comma-separated, stored as TEXT[] |

**Step 2 — Curriculum placement** (context: curriculum_id, grade_id, subject_id from tree — pre-filled, read-only display)

| Field | Input | Required | Notes |
|---|---|---|---|
| Standard code | text | — | e.g. `8Ma1` |
| Sequence order | number | — | Teaching order; auto-appended to end if blank |
| Learning objectives | multi-line tag textarea | — | TEXT[] — one LO per line |
| Recommended weeks | number | — | |
| Is required | toggle | — | Default: true. FALSE = elective |

#### EditTopicModal

Same as AddTopicModal Step 2 (placement fields only — topic identity is locked once placed).
Plus: **is_active toggle** for the curriculum_topic row.
Plus: **Danger zone** — "Remove topic from this curriculum" (DELETE curriculum_topic row, with confirmation).

#### AddSubtopicModal / EditSubtopicModal

| Field | Input | Required | Validation |
|---|---|---|---|
| Name | text | ★ | |
| Learning objective | textarea | ★ NOT NULL | Fed directly to LLM prompts. Min 10 chars. Cannot submit blank. |
| Canonical code | text | — | e.g. `8Ma1.2` |
| Description | textarea | — | |
| Keywords | tag input | — | TEXT[] |
| Bloom taxonomy level | select | — | Remember / Understand / Apply / Analyse / Evaluate / Create |
| Difficulty level | radio 1–5 | — | DB CHECK 1–5 enforced. Show as 5 buttons. |
| Estimated minutes | number | — | |
| Sequence order | number | — | Auto-appended to end if blank |
| Is active | toggle | — | Default: true (edit mode only) |

`embedding` field: **never shown in UI**. Populated by backend ingest script after save.

### 2.6 Hooks & API calls (frontend)

New file: `frontend/apps/kaihle-admin/src/hooks/useCurriculum.ts`

```typescript
// Reads (existing endpoints, no changes needed)
useCurricula()                          // GET /curricula
useGrades(curriculumId?)                // GET /grades
useSubjects(curriculumId?)              // GET /subjects
useTopics(subjectId, curriculumId, gradeId)  // GET /subjects/{id}/topics
useSubtopics(topicId, curriculumId, gradeId) // GET /topics/{id}/subtopics

// Writes (new endpoints)
useCreateCurriculum()                   // POST /curricula
useUpdateCurriculum()                   // PATCH /curricula/{id}
useCreateGrade()                        // POST /grades
useUpdateGrade()                        // PATCH /grades/{id}
useCreateSubject()                      // POST /subjects
useUpdateSubject()                      // PATCH /subjects/{id}
useLinkSubject()                        // POST /curricula/{id}/subjects
useUnlinkSubject()                      // DELETE /curricula/{id}/subjects/{subjectId}
useAddTopic()                           // POST /curricula/{cid}/grades/{gid}/subjects/{sid}/topics
useUpdateCurriculumTopic()              // PATCH /curriculum-topics/{ctId}
useCreateSubtopic()                     // POST /curriculum-topics/{ctId}/subtopics
useUpdateSubtopic()                     // PATCH /subtopics/{id}
```

Cache invalidation: each mutation invalidates the relevant query key tier.

---

## 3. Feature B — User Management

### 3.1 Fix Platform Users Stub

**File:** `backend/app/api/v1/routes/platform.py`

Current problem: `get_platform_users` returns `PlatformUsersResponse(users=[], total=0, ...)` hardcoded. `AsyncSession` is not injected.

**New UserService method:** `list_platform_users(db, q, role, page, page_size)`

```
- Query: SELECT users.*, schools.name AS school_name
         FROM users
         LEFT JOIN schools ON users.school_id = schools.id
         WHERE is_active = TRUE (or ALL — see below)
         AND (q is None OR users.email ILIKE %q% OR first_name ILIKE %q% OR last_name ILIKE %q%)
         AND (role is None OR users.role = role)
         ORDER BY users.created_at DESC
         LIMIT page_size OFFSET (page-1)*page_size
- No school_id filter — KAIHLE_ADMIN bypass (explicit per Rule 12)
- Returns: (list[User + school_name], total_count)
```

**Fix `platform.py` route:**
- Add `db: AsyncSession = Depends(get_db)` parameter
- Call `UserService(db).list_platform_users(q, role, page, page_size)`
- Map result to `PlatformUserSummary` (field `last_active` = `user.last_login_at`)

### 3.2 EditUserDrawer Component

**File:** `frontend/apps/kaihle-admin/src/components/users/EditUserDrawer.tsx`

**Implementation:** Radix Dialog (`@radix-ui/react-dialog`) with custom positioning — `DialogContent` styled as right-side drawer:
```
position: fixed; right: 0; top: 0; bottom: 0; width: 320px;
animation: slide-in from right; border-left: 1px solid #eaecf0;
```
Radix Dialog guarantees: Tab cycles within drawer, Escape closes, focus returns to trigger. (Constitution Rule 21 satisfied)

**Drawer sections:**

1. **Header** (border-b): "Edit user" title + close button (X icon)

2. **User identity** (read-only display): full name, email, school name, role badge, last active

3. **Editable fields form:**

| Field | Input | Required | Notes |
|---|---|---|---|
| First name | text | ★ | |
| Last name | text | ★ | |
| Role | select | ★ | Options: TEACHER, SCHOOL_ADMIN, PARENT, STUDENT — cannot set KAIHLE_ADMIN via UI |
| New password | password | — | Leave blank to keep current. Min 8 chars if provided. |

4. **Save button:** primary green rounded-full, `loading={true}` spinner while pending (Constitution Rule 22)

5. **Danger zone** (border-t, mt-auto at bottom): "Deactivate user" button (danger style: `border border-red-300 text-red-600 hover:bg-red-50 rounded-full`). Opens inline confirmation: "This will prevent [name] from logging in. Confirm?" with Deactivate / Cancel buttons.

**Mutation:** `PATCH /api/v1/schools/{schoolId}/users/{userId}` with `{ first_name, last_name, role, password? }`

### 3.3 AdminUsers.tsx Changes

- Remove standalone `DeactivateUserModal` usage (deactivate is now inside the drawer)
- Add `editingUser: PlatformUser | null` state
- Clicking any table row → `setEditingUser(user)` → opens drawer
- Table row action column: replace deactivate button with "Edit →" link
- Add `school_name` column to `PlatformUserTable` (now available from fixed backend)

---

## 4. Backend — New Schemas Required

New Pydantic schemas in `backend/app/schemas/curriculum.py`:

```python
# Write schemas
CurriculumCreate(name, code, description?, country?, is_active)
CurriculumUpdate(name?, code?, description?, country?, is_active?)
GradeCreate(name, level, description?, is_active)
GradeUpdate(name?, level?, description?, is_active?)
SubjectCreate(name, code, description?, icon?, color?, is_active)
SubjectUpdate(name?, code?, description?, icon?, color?, is_active?)
LinkSubjectRequest(subject_id, is_core, sort_order?)
TopicCreate(name, canonical_code?, description?, keywords?)
CurriculumTopicCreate(topic_id?, topic_data: TopicCreate?, standard_code?, sequence_order?, learning_objectives?, recommended_weeks?, is_required)
CurriculumTopicUpdate(standard_code?, sequence_order?, learning_objectives?, recommended_weeks?, is_required?, is_active?)
SubtopicCreate(name, learning_objective, canonical_code?, description?, keywords?, bloom_taxonomy_level?, difficulty_level?, estimated_minutes?, sequence_order?)
SubtopicUpdate(name?, learning_objective?, canonical_code?, description?, keywords?, bloom_taxonomy_level?, difficulty_level?, estimated_minutes?, sequence_order?, is_active?)
```

Existing `UserUpdate` schema in `backend/app/schemas/user.py` already supports `first_name`, `last_name`, `role`, `password` — no changes needed.

---

## 5. Completeness Checklist

### Schema fields
- [x] All `curricula` columns mapped (name★, code★, description, country, is_active)
- [x] All `grades` columns mapped (name★, level★ 1-13, description, is_active)
- [x] All `subjects` columns mapped (name★, code★, description, icon, color, is_active)
- [x] All `curriculum_subjects` columns mapped (curriculum_id★, subject_id★, is_core, sort_order)
- [x] All `curriculum_topics` columns mapped (all 4 FKs★, standard_code, sequence_order, learning_objectives, recommended_weeks, is_required, is_active)
- [x] All `topics` columns mapped (name★, canonical_code, description, keywords, is_active)
- [x] All `subtopics` columns mapped (curriculum_topic_id★, name★, learning_objective★, canonical_code, description, keywords, bloom_taxonomy_level, difficulty_level, estimated_minutes, sequence_order, is_active)
- [x] `embedding` explicitly excluded from UI (system-generated)

### Interaction states
- [x] Loading skeleton on tree panel initial load
- [x] Loading skeleton on detail panel topic/subtopic list
- [x] Empty state: no curricula
- [x] Empty state: no topics for subject
- [x] Empty state: no subtopics for topic
- [x] Empty state: nothing selected in detail panel
- [x] Button loading spinner on all form submit buttons
- [x] Error state on API failure (toast or inline message)

### Validation rules
- [x] `grades.level` must be 1–13 (frontend + backend enforce, DB CHECK)
- [x] `subtopics.difficulty_level` must be 1–5 (frontend + backend enforce, DB CHECK)
- [x] `subtopics.learning_objective` NOT NULL — form blocks submit if blank
- [x] `curricula.name`, `curricula.code` UNIQUE — show 409 conflict as inline field error
- [x] `subjects.name`, `subjects.code` UNIQUE — show 409 conflict as inline field error
- [x] `grades.level` UNIQUE — show "Level X already taken by [Grade name]" on 409
- [x] `curriculum_topics` composite UNIQUE (curriculum_id, subject_id, grade_id, topic_id) — show "This topic is already placed in this curriculum/grade/subject" on 409

### Constitution rules
- [x] Rule 1: All logic in `curriculum_service.py`, routes thin
- [x] Rule 4: No direct DB queries in routes
- [x] Rule 9: Migrations not needed (no new tables — only write routes for existing tables)
- [x] Rule 14: No new UI kits — using existing `Modal` from `@kaihle/ui`, Radix Dialog for drawer
- [x] Rule 20: TDD — each service method must have named unit + integration test
- [x] Rule 21: Focus trap — all modals via `Modal` from `@kaihle/ui`; EditUserDrawer via Radix Dialog
- [x] Rule 22: Loading states — skeletons on lists, button spinners on actions, no full-page spinners
- [x] KAIHLE_ADMIN role guard on ALL write routes

### Junction table operations
- [x] `curriculum_subjects` link (POST) and unlink (DELETE) both have explicit endpoints
- [x] `curriculum_topics` two-step creation (topic identity + placement) reflected in modal UX and service method
- [x] Topic reuse: `add_topic_to_curriculum` accepts either `topic_id` (existing) OR `topic_data` (create new) — service branches accordingly

### Backend wiring
- [x] `AsyncSession` dependency injected into platform.py `get_platform_users` (currently missing)
- [x] `require_role(UserRole.KAIHLE_ADMIN)` on all new curriculum write routes
- [x] `require_role(UserRole.KAIHLE_ADMIN)` already on platform routes
- [x] No `school_id` filter in `list_platform_users` (KAIHLE_ADMIN bypass, Rule 12 explicit comment)

---

## 6. TDD Spec (Rule 20)

### `test_curriculum_service.py` — unit tests

```
test_create_curriculum_when_valid_data_then_returns_curriculum
test_create_curriculum_when_duplicate_name_then_raises_value_error
test_create_curriculum_when_duplicate_code_then_raises_value_error
test_create_grade_when_level_out_of_range_then_raises_value_error
test_create_grade_when_duplicate_level_then_raises_value_error
test_create_subject_when_duplicate_code_then_raises_value_error
test_link_subject_to_curriculum_when_already_linked_then_raises_value_error
test_add_topic_to_curriculum_when_existing_topic_id_then_creates_curriculum_topic
test_add_topic_to_curriculum_when_new_topic_data_then_creates_topic_and_curriculum_topic
test_add_topic_to_curriculum_when_duplicate_placement_then_raises_value_error
test_create_subtopic_when_learning_objective_blank_then_raises_value_error
test_create_subtopic_when_difficulty_level_out_of_range_then_raises_value_error
test_create_subtopic_when_valid_data_then_embedding_field_is_none
```

### `test_curriculum_routes.py` — integration tests

```
test_post_curricula_when_kaihle_admin_then_201
test_post_curricula_when_school_admin_then_403
test_post_curricula_when_duplicate_code_then_409
test_patch_curriculum_when_valid_then_200
test_post_grades_when_level_13_then_201
test_post_grades_when_level_14_then_422
test_post_subjects_when_valid_then_201
test_post_curriculum_subjects_when_valid_then_201
test_delete_curriculum_subjects_when_valid_then_204
test_post_curriculum_topics_when_new_topic_data_then_201_and_topic_created
test_post_curriculum_topics_when_existing_topic_id_then_201
test_post_curriculum_topics_when_duplicate_placement_then_409
test_patch_curriculum_topics_when_valid_then_200
test_post_subtopics_when_missing_learning_objective_then_422
test_post_subtopics_when_valid_then_201
test_patch_subtopics_when_valid_then_200
```

### `test_platform_users.py` — unit + integration

```
test_list_platform_users_when_no_filter_then_returns_all_users
test_list_platform_users_when_role_filter_then_returns_only_that_role
test_list_platform_users_when_q_filter_then_searches_name_and_email
test_list_platform_users_when_paginated_then_correct_page_returned
test_get_platform_users_route_when_kaihle_admin_then_200_with_real_data
test_get_platform_users_route_when_teacher_then_403
```

### Frontend — `EditUserDrawer.test.tsx`

```
test_renders_user_fields_when_open
test_closes_on_escape_key
test_returns_focus_to_trigger_on_close
test_submit_calls_patch_with_correct_payload
test_submit_button_shows_spinner_while_pending
test_deactivate_shows_confirmation_before_calling_delete
```
