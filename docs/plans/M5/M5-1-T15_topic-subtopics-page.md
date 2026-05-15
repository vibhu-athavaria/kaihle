# M5-1-T15 — Topic Subtopics Page (Mini-Course Entry Point)

**Executor:** Coding agent
**Branch:** `M5-1-T15_feature/topic-subtopics-page`
**Parent branch:** `M5-1-T12_feature/explain-this-drawer` (all M5 backend is there)
**Milestone:** M5

---

## Context

`MiniCoursePage` (`/student/subtopics/:subtopicId/course`) is fully built and working.
`TopicDetailPage` (`/student/classes/:classId/topics/:topicId`) is a placeholder with "coming soon" toasts. It is the missing link — it must list the subtopics inside a topic and let students tap into each mini-course.

The route `GET /api/v1/topics/{topic_id}/subtopics` exists (curriculum router) but uses
an admin schema. A student-accessible subtopics listing must be added.

---

## What to build

### Backend — 1 new endpoint

`GET /api/v1/classes/{class_id}/topics/{class_topic_id}/subtopics`

- Auth: STUDENT (must be enrolled in class), TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN
- Logic: look up the `ClassTopic` row by `class_topic_id` to get `topic_id` (curriculum topic UUID), then query `subtopics` by `topic_id`, ordered by `sequence_order`
- Response: `list[SubtopicStudentResponse]`

```python
class SubtopicStudentResponse(BaseModel):
    id: UUID          # subtopic primary key (used for /subtopics/:subtopicId/course)
    name: str
    order: int
```

Route lives in `student_content.py` (already has the class/topic prefix pattern).

**TDD — unit tests** (`app/tests/unit/test_student_content_service.py`):

```
test_list_subtopics_for_class_topic_when_valid_then_returns_ordered_list
test_list_subtopics_for_class_topic_when_class_topic_not_found_then_raises_404
test_list_subtopics_for_class_topic_when_student_not_enrolled_then_raises_403
```

---

### Frontend — rebuild TopicDetailPage

Replace the placeholder with a real subtopics listing page.

**Hook:** `useTopicSubtopics(classId, topicId)` → `GET /api/v1/classes/{classId}/topics/{topicId}/subtopics`

```typescript
interface SubtopicItem {
  id: string;
  name: string;
  order: number;
}
```

**Page layout** (`TopicDetailPage.tsx`):

1. **Breadcrumb:** Dashboard / Class name / Topic name
2. **Topic header card:** topic name + subtopic count chip (e.g. "6 subtopics")
3. **Subtopics grid:** `grid-cols-1 sm:grid-cols-2 gap-4` — same pattern as TopicsTab
4. **Each subtopic card:**
   - Name (font-display font-bold text-base)
   - Status chip: "Not started" (gray) — no progress data needed at this stage
   - "Learn →" CTA navigating to `/student/subtopics/${subtopic.id}/course`
   - Full card is clickable (hover:border-brand-primary)

**Skeleton loading:** 4-cell 2-column grid skeleton (matches TopicsTab pattern)

**Empty state:** "No subtopics yet — your teacher will add content soon."

---

## Acceptance criteria

- [ ] `GET /api/v1/classes/{classId}/topics/{topicId}/subtopics` returns ordered subtopic list for enrolled student
- [ ] 403 returned when student is not enrolled; 404 when class_topic not found
- [ ] `TopicDetailPage` renders the subtopics grid (not the placeholder)
- [ ] Clicking a subtopic card navigates to `/student/subtopics/:subtopicId/course`
- [ ] `MiniCoursePage` loads and the breadcrumb shows correct topic/subtopic names
- [ ] Skeleton loading during fetch; empty state when no subtopics
- [ ] 3 unit tests pass for the new service method

---

## Files touched

**Backend:**
- `app/api/v1/routes/student_content.py` — new endpoint
- `app/schemas/student_content.py` (or `curriculum.py`) — `SubtopicStudentResponse`
- `app/services/student_content_service.py` (or inline) — query logic
- `app/tests/unit/test_student_content_service.py` — 3 new tests

**Frontend:**
- `frontend/apps/student/src/hooks/useTopicSubtopics.ts` — new hook
- `frontend/apps/student/src/pages/topics/TopicDetailPage.tsx` — full rewrite

---

## Notes for the agent

- The `topicId` URL param in `TopicDetailPage` is the `class_topic.id` (not `curriculum_topic.id`). The backend must look up `ClassTopic` first to get the `topic_id`, then query `subtopics`.
- Do NOT modify `MiniCoursePage` — it is complete.
- Do NOT add progress status indicators on the subtopic cards in this task — that is a future enhancement. "Not started" is acceptable for now.
- No migrations needed.
- Branch from `M5-1-T12_feature/explain-this-drawer`, not from main — all M5 backend changes are there.
