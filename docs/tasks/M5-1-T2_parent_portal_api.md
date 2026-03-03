# M5-1-T2 — Parent Portal API Routes

**Milestone:** M5 — Parent Portal
**Epic:** M5-1 — Parent Narratives
**Task ID:** M5-1-T2
**Depends on:** M5-1-T1 (narratives stored in DB), M0-3-T1/T2 (auth — Parent role must work)
**Blocks:** M5-1-T3 (UI needs these endpoints)

---

## User Story

As a parent, I want to securely access my child's progress data — including weekly reports and a simplified gap map — without seeing raw scores or confusing educational terminology.

---

## What To Build

Four API endpoints under `/api/v1/parent/`. All are strictly scoped to the Parent role. A parent can only see data for children linked to them via the `parent_student` table. Responses use plain-language labels — never raw mastery scores.

---

## Files To Create / Modify

```
/backend/app/api/v1/routes/
  parent.py                     ← NEW

/backend/app/services/
  parent_service.py             ← NEW

/backend/app/schemas/
  parent.py                     ← NEW — response schemas

/backend/app/api/v1/
  router.py                     ← MODIFY — mount parent router
```

---

## Endpoints

### `GET /api/v1/parent/children`
List all children linked to the current parent.

**Auth:** Parent role only

**Response:**
```json
[
  {
    "student_id": "uuid",
    "first_name": "Emma",
    "last_name": "Wilson",
    "grade_name": "Grade 9",
    "school_name": "Bali International School",
    "subjects": ["Mathematics", "Science", "English Language"]
  }
]
```

**Service logic:**
```python
async def get_children(self, parent_user_id: UUID) -> list[ChildSummary]:
    # JOIN parent_student → users → student_profiles → classes → subjects
    # Return one row per child — never expose school_id or internal UUIDs except student_id
```

---

### `GET /api/v1/parent/children/{student_id}/reports`
List all weekly reports for one child. Parent must be linked to this student.

**Auth:** Parent role. Verify `parent_student` link before returning data — return 403 if not linked.

**Query params:** `?limit=10&offset=0` (default: last 10 weeks)

**Response:**
```json
[
  {
    "report_id": "uuid",
    "week_start": "2026-03-02",
    "subject_name": "Mathematics",
    "narrative": "Emma had a productive week in Mathematics...",
    "highlights": ["Improved understanding of fractions", "Started work on ratios"],
    "created_at": "2026-03-02T18:05:00Z"
  }
]
```

**Notes:**
- `highlights` is derived from `gap_summary.improvements` — list of topic names where improvement was detected
- Narratives are stored verbatim from LLM — no post-processing needed
- Sort by `week_start DESC`

---

### `GET /api/v1/parent/children/{student_id}/gap-map`
Simplified gap map — plain language only, no numeric scores.

**Auth:** Parent role. Verify `parent_student` link.

**Response:**
```json
{
  "student_name": "Emma Wilson",
  "grade_name": "Grade 9",
  "subjects": [
    {
      "subject_name": "Mathematics",
      "topics": [
        {
          "topic_name": "Algebra",
          "status": "Developing",
          "status_label": "amber",
          "subtopics_count": 8,
          "subtopics_done_count": 3
        },
        {
          "topic_name": "Geometry",
          "status": "Strong",
          "status_label": "green"
        }
      ]
    }
  ]
}
```

**CRITICAL — What NOT to include in the parent gap map response:**
- ❌ `mastery_score` (e.g. 0.62) — never expose raw scores to parents
- ❌ `confidence` scores
- ❌ `attempt_count`
- ❌ subtopic-level breakdown (too granular for parents)

**Status mapping** (topic-level average):
```python
def mastery_to_status(avg_mastery: float) -> tuple[str, str]:
    if avg_mastery < 0.4:
        return "Needs Work", "red"
    elif avg_mastery <= 0.7:
        return "Developing", "amber"
    else:
        return "Strong", "green"
```

---

### `GET /api/v1/parent/children/{student_id}/reports/{report_id}`
Fetch a single weekly report in full.

**Auth:** Parent role. Verify both parent→student link AND that this report belongs to this student.

**Response:** Single report object (same shape as list item above, but can include full narrative without truncation)

---

## Schemas (`parent.py`)

```python
class ChildSummary(BaseModel):
    student_id: UUID
    first_name: str
    last_name: str
    grade_name: str
    school_name: str
    subjects: list[str]

class TopicStatus(BaseModel):
    topic_name: str
    status: str          # "Strong" | "Developing" | "Needs Work"
    status_label: str    # "green" | "amber" | "red"

class SubjectGapSummary(BaseModel):
    subject_name: str
    topics: list[TopicStatus]

class ParentGapMap(BaseModel):
    student_name: str
    grade_name: str
    subjects: list[SubjectGapSummary]

class WeeklyReport(BaseModel):
    report_id: UUID
    week_start: date
    subject_name: str
    narrative: str
    highlights: list[str]
    created_at: datetime
```

---

## `parent_service.py` — Key Methods

```python
class ParentService:

    async def verify_parent_child_link(
        self, parent_user_id: UUID, student_id: UUID
    ) -> None:
        """Raises HTTP 403 if no parent_student link exists."""
        link = await self.session.execute(
            select(ParentStudent)
            .where(ParentStudent.parent_id == parent_user_id)
            .where(ParentStudent.student_id == student_id)
        )
        if not link.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    async def get_simplified_gap_map(
        self, student_id: UUID
    ) -> ParentGapMap:
        """
        Load gap_states, aggregate to topic level, apply plain-language labels.
        No subtopic detail. No numeric scores in output.
        """
        # Load gap states joined to subtopics → curriculum_topics → topics → subjects
        # Group by (subject, topic) → compute average mastery per topic
        # Map to TopicStatus using mastery_to_status()
        ...
```

---

## Acceptance Criteria

- [ ] Integration test: parent fetches `/parent/children` → sees only their own children
- [ ] Integration test: parent fetches report for child not linked to them → 403
- [ ] Integration test: gap map response contains NO `mastery_score` fields anywhere
- [ ] Integration test: gap map topic with avg mastery 0.35 → `status: "Needs Work"`, `status_label: "red"`
- [ ] Integration test: gap map topic with avg mastery 0.62 → `status: "Developing"`, `status_label: "amber"`
- [ ] Integration test: gap map topic with avg mastery 0.81 → `status: "Strong"`, `status_label: "green"`
- [ ] Integration test: student with no weekly reports → returns empty list `[]`, not 404
- [ ] Integration test: Teacher role calling parent endpoints → 403
- [ ] Unit test: `verify_parent_child_link` raises 403 when link does not exist
- [ ] Unit test: `mastery_to_status(0.4)` → "Developing" (boundary — 0.4 is amber, not red)

---

## Output (what M5-1-T3 needs)

All four endpoints operational and tested:
- `GET /api/v1/parent/children`
- `GET /api/v1/parent/children/{student_id}/reports`
- `GET /api/v1/parent/children/{student_id}/gap-map`
- `GET /api/v1/parent/children/{student_id}/reports/{report_id}`
