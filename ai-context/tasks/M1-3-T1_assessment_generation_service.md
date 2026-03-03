# M1-3-T1 — Assessment Generation Service (Tier 2)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T1
**Depends on:** M1-1-T1 (question bank populated), M0-2-T2 (ORM models)

---

## User Story
As a teacher, I want the system to select appropriate questions for the assessment I'm creating, so I don't have to manually find questions from the bank.

---

## Files to Create / Modify

```
backend/app/services/assessment_service.py       # new file
backend/app/schemas/assessment.py                # AssessmentConfig, AssessmentResponse schemas
backend/tests/unit/test_assessment_service.py
backend/tests/integration/test_assessment_generation.py
```

---

## Key Rule
All assessments created via this service are **Tier 2** (teacher-created). Always set `is_system_generated = FALSE`. Never set it to TRUE here — that is only done in `onboarding_tasks.py` (M0-6-T2).

---

## Schemas

```python
class AssessmentConfig(BaseModel):
    class_id: UUID
    assessment_type: AssessmentType          # DIAGNOSTIC | TOPIC_SPECIFIC | PROGRESS_CHECK | FINAL
    curriculum_topic_id: UUID | None = None  # None for DIAGNOSTIC (broad sweep)
    num_questions: int = Field(default=10, ge=5, le=30)
    question_types: list[QuestionType] = ["MCQ", "TRUE_FALSE"]
    difficulty_range: tuple[float, float] = (1.0, 5.0)
    deadline: datetime | None = None

class AssessmentResponse(BaseModel):
    id: UUID
    class_id: UUID
    assessment_type: AssessmentType
    status: AssessmentStatus
    is_system_generated: bool
    title: str
    num_questions: int
    deadline: datetime | None
    created_at: datetime
```

---

## Service Method: `create_assessment(config, teacher_id, school_id)`

```
1. Validate teacher owns the class (class.teacher_id == teacher_id)
2. Build question query:
   - Base filter: subject_id + grade_id (from class), is_active=TRUE
   - If curriculum_topic_id provided: filter by that topic
   - If DIAGNOSTIC (no topic): spread across all curriculum_topics for subject+grade
   - Filter by question_types
   - Filter difficulty_level BETWEEN difficulty_range[0] AND difficulty_range[1]
3. Sample num_questions from filtered pool:
   - Use weighted random: aim for even topic distribution
   - If insufficient questions in bank:
       → Call LLM fallback: generate_questions_via_llm(config)
       → Log warning: "Question bank insufficient, used LLM fallback"
4. Create assessments row:
   {
     school_id, class_id,
     created_by = teacher_id,
     assessment_type,
     is_system_generated = FALSE,   # ALWAYS FALSE here
     status = 'DRAFT',              # teacher must explicitly publish
     curriculum_topic_id,
     title = auto_generate_title(config),
     deadline,
   }
5. Insert assessment_selected_questions bridge rows
6. Return AssessmentResponse
```

### `auto_generate_title(config)` examples:
- DIAGNOSTIC → `"Diagnostic — Mathematics Grade 9"`
- TOPIC_SPECIFIC → `"Algebraic Fractions — Practice Check"`
- PROGRESS_CHECK → `"Progress Check — Week 3"`

### LLM fallback (`generate_questions_via_llm`):
Only called when bank has fewer than `num_questions` matching rows.
- Task: `"question_generation"` → Gemini 2.5 Flash
- Prompt: inject subtopic/topic name + grade + num needed + question types
- Parse + validate with Pydantic before inserting into `question_bank` with `source='LLM'`

---

## Acceptance Criteria

- [ ] Teacher creates 10-question Grade 9 Math assessment → 10 `assessment_selected_questions` rows
- [ ] Created assessment has `status='DRAFT'` and `is_system_generated=FALSE`
- [ ] DIAGNOSTIC type with no `curriculum_topic_id` → questions spread across multiple topics
- [ ] `difficulty_range=(1.0, 2.5)` → only questions with `difficulty_level ≤ 2.5` selected
- [ ] When bank has insufficient questions → LLM fallback called, warning logged
- [ ] Teacher not owning the class → 403
- [ ] `num_questions` outside 5–30 → 422

---

## Tests to Write

```python
test_create_assessment_when_valid_config_then_draft_assessment_created()
test_create_assessment_when_diagnostic_type_then_questions_span_multiple_topics()
test_create_assessment_when_difficulty_range_then_only_matching_questions()
test_create_assessment_when_insufficient_bank_then_llm_fallback_called()
test_create_assessment_always_sets_is_system_generated_false()
test_create_assessment_when_teacher_not_class_owner_then_403()
test_create_assessment_when_num_questions_too_high_then_422()
```
