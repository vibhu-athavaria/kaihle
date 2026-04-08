# M3-0-T2a — KaihleAdmin Video Review UI
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-0 — Content Infrastructure
**Task:** T2a
**Executor:** Coding agent
**Depends on:** M3-0-T1 (subtopic_content table seeded with pending videos),
               M0-8-T7 (Modal component), M0-8-T6 (Toast system)
**Blocks:** M3-1-T1 (content curator needs approved videos to serve)

> **App target:** `apps/kaihle-admin` ONLY.
> This UI is for Vibhu and the Kaihle team — not teachers, not school admins.
> Load `DESIGN_SYSTEM.md` §5.1 (Kaihle Admin) before writing any component.

---

## User Story

As Kaihle Admin, I want to review YouTube video candidates for each subtopic so I can
approve the ones that are curriculum-appropriate and reject unsuitable ones, building
a quality-controlled resource library that students and teachers can trust.

---

## Context

`M3-0-T1` seeded every subtopic with 2–3 YouTube video candidates, all with
`status = 'pending'`. This UI lets KaihleAdmin approve or reject each video, and
optionally replace a rejected video with a manual URL entry.

The review workflow:
1. KaihleAdmin sees a queue of subtopics with pending video reviews
2. Opens a subtopic → sees up to 3 video cards with YouTube embeds
3. Approves or rejects each video
4. Optionally adds a replacement URL if all were rejected
5. Subtopic marked complete when ≥1 video is approved

---

## Backend — API Endpoints

### New route file: `backend/app/api/v1/routes/subtopic_content.py`

Register in `main.py` with prefix `/api/v1`.

```python
# GET  /subtopic-content/review-queue
# Returns paginated list of subtopics with pending video reviews

# GET  /subtopic-content/{subtopic_id}
# Returns full subtopic_content row for one subtopic

# PATCH /subtopic-content/{subtopic_id}/videos/{video_index}
# Updates status of one video entry in the JSONB array
# Body: {"status": "approved" | "rejected"}

# POST /subtopic-content/{subtopic_id}/videos
# Adds a new manual video entry (KaihleAdmin provides URL)
# Body: {"url": "...", "title": "...", "channel": "manual"}
```

All endpoints: `KAIHLE_ADMIN` role only. Apply `_check_kaihle_admin()` guard.

### Schemas (`backend/app/schemas/subtopic_content.py`)

```python
class VideoEntry(BaseModel):
    url: str
    title: str
    channel: str
    view_count: int | None
    status: str   # 'pending' | 'approved' | 'rejected' | 'stale'
    last_checked_at: str | None

class SubtopicContentReviewResponse(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    subject_code: str
    grade_level: int
    curriculum_code: str
    learning_objective: str
    videos: list[VideoEntry]
    pending_count: int
    approved_count: int
    explanation_review_status: str

class ReviewQueueItem(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    subject_code: str
    grade_level: int
    pending_video_count: int
    approved_video_count: int

class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    pending_total: int   # total videos awaiting review across all subtopics

class VideoStatusUpdateRequest(BaseModel):
    status: str   # 'approved' | 'rejected'

class ManualVideoAddRequest(BaseModel):
    url: str
    title: str
    channel: str = "manual"
```

---

## Frontend — New Pages & Components

### Files to Create

```
frontend/apps/kaihle-admin/src/pages/content/
  VideoReviewQueue.tsx          ← list view — subtopics with pending reviews
  VideoReviewDetail.tsx         ← detail view — approve/reject videos for one subtopic

frontend/apps/kaihle-admin/src/components/content/
  VideoReviewCard.tsx           ← one video candidate card with embed + actions
  VideoStatusBadge.tsx          ← pending | approved | rejected | stale badge

frontend/apps/kaihle-admin/src/hooks/
  useSubtopicContent.ts         ← React Query hooks for all content endpoints
```

### Routing — `App.tsx` in `apps/kaihle-admin`

Add inside the authenticated admin routes:
```tsx
<Route path="content/videos" element={<VideoReviewQueue />} />
<Route path="content/videos/:subtopicId" element={<VideoReviewDetail />} />
```

### Sidebar — add Content section

In the KaihleAdmin sidebar nav, add a new section **CONTENT** between existing sections:

```tsx
{/* CONTENT section */}
<SidebarSection label="CONTENT">
  <SidebarNavItem
    to="/kaihle-admin/content/videos"
    icon={<PlaySquare className="w-4 h-4" aria-hidden="true" />}
    label="Video Library"
    badge={pendingVideoCount > 0 ? pendingVideoCount : undefined}
  />
</SidebarSection>
```

The badge shows the total pending video count. Use `brand-gold` for the badge background
when count > 0 — this matches the "needs attention" pattern.

---

## Component Specifications

### `VideoReviewQueue.tsx`

**Route:** `/kaihle-admin/content/videos`

```
Page layout:
─────────────────────────────────────────────────────
  Page title:  "Video Library Review"  (Inter, text-sm, font-bold)
  Sub-label:   "X videos pending review across Y subtopics"  (text-role-admin-muted)

  Filter bar:  [Subject dropdown] [Grade dropdown] [Status: All | Pending | Complete]

  Table:
  ┌──────────────────────────┬────────────┬───────┬────────┬──────────┐
  │ SUBTOPIC                 │ SUBJECT    │ GRADE │ VIDEOS │ STATUS   │
  ├──────────────────────────┼────────────┼───────┼────────┼──────────┤
  │ Algebraic Fractions      │ MATH       │ Gr.8  │ 0/3 ✓  │ ● Pending│
  │ Forces and Motion        │ SCI        │ Gr.7  │ 2/3 ✓  │ ● Partial│
  │ Cell Structure           │ BIO        │ Gr.9  │ 3/3 ✓  │ ✓ Done   │
  └──────────────────────────┴────────────┴───────┴────────┴──────────┘

  Row click → navigate to /kaihle-admin/content/videos/:subtopicId
─────────────────────────────────────────────────────
```

Status indicators:
- `● Pending` — `text-brand-amber` (no approved videos yet)
- `● Partial` — `text-brand-gold` (some approved, some pending)
- `✓ Done` — `text-brand-primary` (≥1 approved, none pending)

Use skeleton rows while loading. Use `EmptyState` if no subtopics found.

### `VideoReviewDetail.tsx`

**Route:** `/kaihle-admin/content/videos/:subtopicId`

```
Page layout:
─────────────────────────────────────────────────────
  Back link:  ← Video Library

  Header card:
  ┌─────────────────────────────────────────────────┐
  │  Forces and Motion  ·  SCI · Grade 7            │
  │  Learning objective: Describe balanced and...   │
  └─────────────────────────────────────────────────┘

  Video cards (1–3 cards in a responsive grid):
  [VideoReviewCard] [VideoReviewCard] [VideoReviewCard]

  Add video button:
  [+ Add manual video URL]  (opens Modal)
─────────────────────────────────────────────────────
```

### `VideoReviewCard.tsx`

```
┌──────────────────────────────────────────────┐
│  [VideoStatusBadge: PENDING]                 │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  YouTube embed (iframe, 16:9 ratio)    │  │
│  │  src: youtube.com/embed/{videoId}      │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  Forces and Newton's Laws — Science Sauce    │
│  Channel: Science Sauce  · 847K views        │
│                                              │
│  [✓ Approve]    [✗ Reject]                   │
└──────────────────────────────────────────────┘
```

**Full iframe implementation — security and accessibility required:**

```tsx
// Extract videoId from URL (handles both youtu.be and youtube.com/watch formats)
function extractYouTubeId(url: string): string | null {
  const patterns = [
    /youtube\.com\/watch\?v=([^&]+)/,
    /youtu\.be\/([^?]+)/,
    /youtube\.com\/embed\/([^?]+)/,
  ]
  for (const pattern of patterns) {
    const match = url.match(pattern)
    if (match) return match[1]
  }
  return null
}

// In VideoReviewCard render:
const videoId = extractYouTubeId(video.url)

{videoId ? (
  <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
    {/* 16:9 aspect ratio wrapper */}
    <iframe
      className="absolute inset-0 w-full h-full rounded-lg"
      src={`https://www.youtube.com/embed/${videoId}`}
      title={`${video.title} — preview for ${subtopicName}`}
      // aria-label required: title alone insufficient for all screen readers
      aria-label={`Video preview: ${video.title}`}
      // sandbox: minimum permissions for YouTube embed to function
      // allow-scripts: YouTube player JS
      // allow-same-origin: YouTube session cookies (required for player)
      // allow-presentation: fullscreen via JS
      // NO allow-forms, allow-popups, allow-top-navigation — reduces attack surface
      sandbox="allow-scripts allow-same-origin allow-presentation"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowFullScreen
      loading="lazy"
    />
  </div>
) : (
  // URL is not a valid YouTube URL — show fallback
  <div className="w-full h-32 bg-gray-100 rounded-lg flex items-center justify-center">
    <span className="text-sm text-brand-muted">Preview unavailable</span>
  </div>
)}
```

> ⚠️ **Security:** Never omit `sandbox`. An iframe without `sandbox` grants the
> embedded page full access to the parent origin. `allow-same-origin` is included
> only because YouTube requires it for the player — this is an accepted tradeoff
> for authenticated embeds. Do not add `allow-top-navigation` or `allow-popups`.
>
> ⚠️ **Accessibility:** The `title` attribute on `<iframe>` is mandatory for
> WCAG 2.1 Success Criterion 4.1.2. Without it, screen readers announce "iframe"
> with no context. The value must describe the content, not the mechanism.

Props:
```tsx
interface VideoReviewCardProps {
  subtopicId: string
  videoIndex: number
  video: VideoEntry
  onStatusChange: (index: number, status: 'approved' | 'rejected') => void
}
```

After approve/reject:
- Button enters loading state (spinner)
- On success: badge updates, buttons dim if action confirmed
- On error: toast error message

Approved state: card border changes to `border-brand-primary`, badge shows green "APPROVED"
Rejected state: card opacity `opacity-50`, badge shows red "REJECTED", "Undo" link appears

### `VideoStatusBadge.tsx`

```tsx
const STATUS_CONFIG = {
  pending:  { label: 'Pending',  className: 'bg-brand-amber-light text-brand-amber' },
  approved: { label: 'Approved', className: 'bg-brand-green-light text-brand-green' },
  rejected: { label: 'Rejected', className: 'bg-brand-red-light text-brand-red' },
  stale:    { label: 'Stale',    className: 'bg-gray-100 text-brand-muted' },
}
```

### Add Manual Video Modal

When KaihleAdmin clicks "+ Add manual video URL":

```
Modal title: "Add Video Manually"

Fields:
  YouTube URL  [text input — validated as youtube.com URL]
  Title        [text input]
  Channel      [text input, optional]

[Cancel]  [Add Video]
```

On submit: `POST /subtopic-content/{subtopicId}/videos`. New entry added with
`status = 'pending'` — KaihleAdmin must then approve it separately.

---

## React Query Hooks (`useSubtopicContent.ts`)

```typescript
// Paginated queue
useVideoReviewQueue(filters: { subject?: string; grade?: number; status?: string })

// Single subtopic detail
useSubtopicContentDetail(subtopicId: string)

// Mutations
useUpdateVideoStatus()    // PATCH /subtopic-content/{id}/videos/{index}
useAddManualVideo()       // POST /subtopic-content/{id}/videos

// Invalidate queue + detail on mutation success
```

---

## Acceptance Criteria

### Backend
- [ ] `GET /subtopic-content/review-queue` returns paginated list, `KAIHLE_ADMIN` only
- [ ] `GET /subtopic-content/{id}` returns full content row with videos array
- [ ] `PATCH /subtopic-content/{id}/videos/{index}` updates correct JSONB entry
- [ ] `PATCH` with invalid index returns 404
- [ ] `PATCH` with invalid status returns 422
- [ ] `POST` adds new entry to videos JSONB array
- [ ] Non-KaihleAdmin role returns 403 on all endpoints
- [ ] `pending_total` in queue response reflects correct count

### Frontend
- [ ] Queue page loads with skeleton while fetching
- [ ] Queue shows correct pending count badge per subtopic
- [ ] Sidebar badge updates when pending count changes
- [ ] Filtering by subject and grade narrows results correctly
- [ ] Approve action → video card shows green APPROVED badge
- [ ] Reject action → video card shows reduced opacity + REJECTED badge
- [ ] Undo reject → video returns to pending
- [ ] Add manual video modal → validates YouTube URL format
- [ ] Empty state shown when all videos are reviewed
- [ ] Toast shown on API error

---

## Tests to Write

```python
# backend/tests/unit/test_subtopic_content_routes.py
def test_review_queue_when_kaihle_admin_then_returns_queue()
def test_review_queue_when_teacher_role_then_403()
def test_update_video_status_when_valid_index_then_status_updated()
def test_update_video_status_when_invalid_index_then_404()
def test_add_manual_video_when_valid_then_appended_to_array()
def test_pending_total_when_all_pending_then_correct_count()
def test_pending_total_when_some_approved_then_excludes_approved()
```

---

## Do NOT Touch

- `apps/teacher` — video review is KaihleAdmin only
- `apps/school-admin` — no content review access
- `subtopic_content.approved_explanation` or `explanation_review_status` — those are
  for the teacher explanation review (M3-0-T2b), not this task
- `curriculum_chunks` — never read or write

---

*Task M3-0-T2a · Pixel (UX/UI Lead) + Kramer (Technical Lead) · April 2026*
