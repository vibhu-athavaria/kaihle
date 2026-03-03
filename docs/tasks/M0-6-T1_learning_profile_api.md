# M0-6-T1 — Learning Profile Questionnaire API
**Milestone:** M0 · **Epic:** M0-6 (Student Onboarding) · **Task:** T1
**Depends on:** M0-2-T2 (ORM models — `StudentLearningProfile`), M0-3-T3 (auth middleware)

---

## User Story
As a student logging in for the first time, I want to complete a short learning style questionnaire so Kaihle can personalise my study plans and quizzes from day one.

---

## Files to Create / Modify

```
backend/app/services/onboarding_service.py       # new file
backend/app/api/v1/routes/onboarding.py          # new file
backend/app/schemas/onboarding.py                # new file
backend/app/core/questionnaire_config.py         # static questionnaire definition
backend/tests/unit/test_onboarding_service.py
backend/tests/integration/test_onboarding_api.py
```

---

## Questionnaire Definition (Static Config)

Store in `questionnaire_config.py` — this is the v1 questionnaire, version-tagged `"v1"`.

10 questions total (~5 minutes):

```python
QUESTIONNAIRE_V1 = {
    "version": "v1",
    "questions": [
        {
            "id": "q1",
            "text": "When learning something new, I prefer to...",
            "type": "single_select",
            "options": [
                {"key": "watch_video",    "text": "Watch a video explaining it",  "maps_to": {"modality": "visual"}},
                {"key": "read_about_it",  "text": "Read about it",                "maps_to": {"modality": "reading_writing"}},
                {"key": "try_it_out",     "text": "Try it out hands-on",          "maps_to": {"modality": "kinesthetic"}},
                {"key": "discuss_it",     "text": "Discuss it with someone",      "maps_to": {"modality": "auditory"}},
            ]
        },
        {
            "id": "q2",
            "text": "I remember things best when...",
            "type": "single_select",
            "options": [
                {"key": "see_diagrams",   "text": "I see diagrams or charts",     "maps_to": {"modality": "visual"}},
                {"key": "hear_explained", "text": "I hear them explained aloud",  "maps_to": {"modality": "auditory"}},
                {"key": "write_notes",    "text": "I write notes about them",     "maps_to": {"modality": "reading_writing"}},
                {"key": "do_exercise",    "text": "I do an exercise or activity", "maps_to": {"modality": "kinesthetic"}},
            ]
        },
        {
            "id": "q3",
            "text": "I prefer to study...",
            "type": "single_select",
            "options": [
                {"key": "solo",   "text": "Alone",           "maps_to": {"work_style": "prefers_solo", "value": True}},
                {"key": "group",  "text": "With friends",    "maps_to": {"work_style": "prefers_solo", "value": False}},
            ]
        },
        {
            "id": "q4",
            "text": "I prefer study sessions that are...",
            "type": "single_select",
            "options": [
                {"key": "short", "text": "Short and frequent (20–30 min)", "maps_to": {"work_style": "short_sessions", "value": True}},
                {"key": "long",  "text": "Long and deep (1+ hour)",        "maps_to": {"work_style": "short_sessions", "value": False}},
            ]
        },
        {
            "id": "q5",
            "text": "I learn better by...",
            "type": "single_select",
            "options": [
                {"key": "concept_first", "text": "Understanding the theory first",  "maps_to": {"work_style": "concept_first", "value": True}},
                {"key": "task_based",    "text": "Jumping straight into tasks",     "maps_to": {"work_style": "concept_first", "value": False}},
            ]
        },
        {
            "id": "q6_to_q10",
            "text": "Pick topics that interest you most (choose as many as you like)",
            "type": "multi_select",
            "maps_to": "interests",
            "options": [
                {"key": "sports",      "text": "Sports",       "emoji": "⚽"},
                {"key": "music",       "text": "Music",        "emoji": "🎵"},
                {"key": "gaming",      "text": "Gaming",       "emoji": "🎮"},
                {"key": "animals",     "text": "Animals",      "emoji": "🐾"},
                {"key": "cooking",     "text": "Cooking",      "emoji": "🍳"},
                {"key": "art",         "text": "Art & Design", "emoji": "🎨"},
                {"key": "technology",  "text": "Technology",   "emoji": "💻"},
                {"key": "nature",      "text": "Nature",       "emoji": "🌿"},
                {"key": "fashion",     "text": "Fashion",      "emoji": "👗"},
                {"key": "travel",      "text": "Travel",       "emoji": "✈️"},
            ]
        }
    ]
}
```

---

## Service Methods (`onboarding_service.py`)

### `get_or_create_learning_profile(student_id, school_id) → StudentLearningProfile`
- Upsert — returns existing row if present, creates empty row if not

### `save_questionnaire_response(student_id, responses) → StudentLearningProfile`

**Scoring logic:**

```
modality_scores:
  For q1 + q2 answers that map to a modality:
    count[modality] += 1
  Final score = count[modality] / 2   (max 1.0 since 2 questions)

work_style:
  For q3, q4, q5: map answer_key → work_style field + boolean value
  Result: { prefers_solo: bool, short_sessions: bool, concept_first: bool }
  Derive: task_based = NOT concept_first

interests:
  From multi_select: collect selected option keys as list[str], lowercase
```

Set `completed_at = now()`, `questionnaire_version = "v1"`, `updated_at = now()`

### `get_onboarding_status(student_id) → dict`
```python
{
    "learning_profile_complete": bool,   # completed_at IS NOT NULL
    "diagnostics_complete": bool,        # onboarding_diagnostic_status == 'COMPLETED'
    "overall": "PENDING" | "IN_PROGRESS" | "COMPLETED"
    # overall = COMPLETED only if both True
    # overall = IN_PROGRESS if either True
    # overall = PENDING if both False
}
```

---

## API Endpoints

### `GET /api/v1/onboarding/status`
Auth: Student (own only)
Returns: `OnboardingStatus` dict from `get_onboarding_status()`

### `GET /api/v1/onboarding/questionnaire`
Auth: Student
Returns: full questionnaire definition from `QUESTIONNAIRE_V1` config (no DB call)

### `POST /api/v1/onboarding/questionnaire/submit`
Auth: Student
```
Body: {
  "responses": [
    { "question_id": "q1", "answer_key": "watch_video" },
    { "question_id": "q2", "answer_key": "see_diagrams" },
    { "question_id": "q3", "answer_key": "solo" },
    { "question_id": "q4", "answer_key": "short" },
    { "question_id": "q5", "answer_key": "task_based" },
    { "question_id": "q6_to_q10", "answer_keys": ["sports", "music"] }
  ]
}
```
Returns: completed `StudentLearningProfile` (all fields)
Behaviour: idempotent — re-submitting updates scores, does not create duplicate row

### `GET /api/v1/onboarding/learning-profile`
Auth: Student (own) | Teacher (for students in own class) | KaihleAdmin
Query param: `student_id` (required for Teacher/KaihleAdmin, ignored for Student)
Returns: `StudentLearningProfile`

---

## Acceptance Criteria

- [ ] `GET /api/v1/onboarding/questionnaire` returns full 10-question definition
- [ ] Submit with q1=watch_video, q2=see_diagrams → `modality_scores.visual = 1.0`
- [ ] Submit with q1=try_it_out, q2=do_exercise → `modality_scores.kinesthetic = 1.0`
- [ ] Submit with q1=watch_video, q2=do_exercise → `visual = 0.5, kinesthetic = 0.5`
- [ ] Submit with q3=solo → `work_style.prefers_solo = true`
- [ ] Submit with interests=["sports","music"] → `interests = ["sports", "music"]`
- [ ] Re-submit updates existing row — no duplicate `student_learning_profiles` rows
- [ ] `completed_at` is set on submit
- [ ] `get_onboarding_status` returns `overall: COMPLETED` only when both profile and diagnostics done
- [ ] Teacher can read a student's learning profile (in own class)
- [ ] Student cannot read another student's profile → 403

---

## Tests to Write

```python
test_save_questionnaire_when_visual_answers_then_visual_score_1()
test_save_questionnaire_when_mixed_answers_then_scores_0_5()
test_save_questionnaire_when_kinesthetic_answers_then_kinesthetic_score_1()
test_save_questionnaire_when_interests_selected_then_interests_stored()
test_save_questionnaire_when_resubmitted_then_no_duplicate_row()
test_get_onboarding_status_when_both_complete_then_overall_completed()
test_get_onboarding_status_when_only_profile_done_then_in_progress()
test_submit_api_when_valid_body_then_profile_stored()
test_learning_profile_api_when_teacher_requests_student_then_200()
test_learning_profile_api_when_student_requests_other_student_then_403()
```
