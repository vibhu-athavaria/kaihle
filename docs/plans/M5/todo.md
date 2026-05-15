# M5 — Student Mini-Course: Task List
**Updated:** 2026-05-14

## Dependency Order
```
main → T1 [MIGRATION] → T2 → T3, T4, T6, T9 (parallel)
                              T4 → T5
                              T6 → T7 → T8
                              T9 → T10
main → T11 (independent) → T12
main → T13 (independent)
main → T14 (independent)
```

---

## Phase 1 — Foundation

- [ ] **T1** `M5-1-T1_migration/mini-course-schema`
  - New tables: `subtopic_course_progress`, `subtopic_content_feedback`
  - Add columns to `subtopic_content`: `thumbs_up_count`, `thumbs_down_count`, `rejection_teacher_note`
  - New ORM models in `backend/app/models/mini_course.py`
  - **⚠ MIGRATION — must be deployed before T2–T10 begin**

- [ ] **✅ CHECKPOINT 1** — alembic up/down pass, model tests pass — human review required

---

## Phase 2 — Core Backend

- [ ] **T2** `M5-1-T2_feature/mini-course-service-and-route` *(branches from T1)*
  - `mini_course_service.py`: `get_course_for_student` + `mark_progress`
  - `schemas/mini_course.py`: SubtopicCourseResponse + nested types
  - Routes: `GET /students/me/subtopics/{id}/course`, `POST /students/me/subtopics/{id}/course/progress`

- [ ] **T4** `M5-1-T4_feature/teacher-generate-course-task` *(branches from T2)*
  - Celery task `generate_topic_mini_course` in `mini_course_tasks.py`
  - Jinja2 prompt `mini_course_explanation.jinja2`
  - `LLM_MINI_COURSE_MODEL` env var + router.py entry
  - Route: `POST /topics/{topicId}/generate-course`

- [ ] **T6** `M5-1-T6_feature/content-feedback-service-and-route` *(branches from T2)*
  - `mini_course_service.py`: `submit_feedback` with atomic counter update
  - Route: `POST /students/me/subtopic-content/{id}/feedback`
  - Extend PATCH reject endpoint with `teacher_note`

- [ ] **T9** `M5-1-T9_feature/teacher-student-course-progress-route` *(branches from T2)*
  - `mini_course_service.py`: `get_student_course_progress`
  - Route: `GET /students/{studentId}/subtopics/course-progress`

- [ ] **T11** `M5-1-T11_feature/explain-this-sse-route` *(branches from main — independent)*
  - `concept_guide_service.py`: `explain_subtopic_question` async generator
  - Jinja2 prompt `explain_this.jinja2`
  - `LLM_EXPLAIN_THIS_MODEL` env var + router.py entry
  - Route: `POST /students/me/subtopics/{id}/explain` (SSE)

- [ ] **✅ CHECKPOINT 2** — all backend tests pass, services ≥90% coverage, mypy clean — human review required

---

## Phase 3 — Frontend

- [ ] **T3** `M5-1-T3_feature/student-mini-course-page` *(branches from T2)*
  - `useSubtopicCourse.ts`, `useMarkCourseProgress.ts` hooks
  - `SubtopicCoursePage.tsx`: explanation + video + check questions
  - Wire subtopic cards in `ClassTopicsPage.tsx` to new page
  - Add route to student app router

- [ ] **T5** `M5-1-T5_feature/teacher-generate-button` *(branches from T4)*
  - `useGenerateMiniCourse.ts` hook
  - Generate button per topic row in `ClassDetailPage.tsx`
  - Pulsing "Generating..." badge state

- [ ] **T7** `M5-1-T7_feature/student-feedback-thumbs` *(branches from T6)*
  - `useContentFeedback.ts` hook
  - 👍👎 buttons + optional comment in `SubtopicCoursePage.tsx`

- [ ] **T8** `M5-1-T8_feature/teacher-content-quality-signals` *(branches from T7)*
  - Quality badge column in `ContentReviewPage.tsx`
  - Student feedback list in row detail
  - `teacher_note` field in reject modal

- [ ] **T10** `M5-1-T10_feature/teacher-student-mini-courses-tab` *(branches from T9)*
  - `useStudentCourseProgress.ts` hook
  - `MiniCoursesTab.tsx` component
  - Add "Mini-Courses" tab to `StudentProfilePage.tsx`

- [ ] **T12** `M5-1-T12_feature/explain-this-drawer` *(branches from T11)*
  - `ExplainThisDrawer.tsx`: SSE streaming chat, focus trap
  - Wire to `SubtopicCoursePage.tsx`

---

## Phase 4 — Standalone

- [ ] **T13** `M5-1-T13_feature/questionnaire-v2` *(branches from main)*
  - 7-question v2 config in `questionnaire_config.py`
  - New scoring logic in `onboarding_service.py`
  - Unit tests for plurality-vote modality + single-select interests

- [ ] **T14** `M5-1-T14_chore/mvp-ui-cleanup` *(branches from main)*
  - Hide "My Progress" + "Study Plans" from `StudentLayout.tsx`
  - Remove My Progress + Study Plan tabs from `ClassPage.tsx`

---

## Final Checklist

- [ ] All 14 PRs open, CI green (non-E2E)
- [ ] `.env.example` updated: `LLM_MINI_COURSE_MODEL`, `LLM_EXPLAIN_THIS_MODEL`
- [ ] Human confirms merge order before any merge
- [ ] T1 deployed + `alembic upgrade head` run before any other PR merged
