# M4-2-T1 — Student Pack On-Demand Generation
**Milestone:** M4 — Teacher Copilot
**Epic:** M4-2 — Student Pack
**Task:** T1
**Executor:** Coding agent
**Depends on:**
  - M4-1-T2 (lesson plan schema + `lesson_plans` table must exist)
  - M4-1-T3 (lesson plan routes — `/classes/{id}/lesson-plans` must return real data)
  - M3-0-T1 (subtopic_content table with approved explanations + videos)
  - M3-0-T2b (teacher explanation review — approved_explanation should exist for subtopics)
  - M1-1-T1 (question bank populated — pre/post quiz questions drawn from here)
**Blocks:** M4-2-T2 (student lesson pack UI — needs this endpoint)

---

## User Story

As a student, when I open a lesson plan assigned by my teacher, I want to see a
personalised lesson pack built around my learning style and interests — with a
clear real-life introduction, a short explanation, a video, and a pre-lesson quiz —
so I can engage with the topic before class.

---

## Context

The Monday Celery beat task (M4-1-T1) generates the **teacher plan** and stores it
in `lesson_plans`. The **student pack** is different: it is personalised per student
based on their learning style and interests, and is generated **on first access** then
cached in `student_lesson_packs`.

The same lesson plan can produce many different student packs — one per
`(student_id, learning_style, interest_category)` combination. Students with the
same learning style and interest category share the same cached pack.

The generation is synchronous on first access (the student waits ~5–8 seconds for
Gemini to generate), then instant on subsequent access (cache hit). A loading state
in the UI covers the first-time latency.

---

## Files to Create / Modify

```
CREATE  backend/app/services/student_pack_service.py
CREATE  backend/app/schemas/student_pack.py
CREATE  backend/app/models/student_lesson_pack.py
CREATE  backend/app/api/v1/routes/student_packs.py
CREATE  backend/app/ai/prompts/student_pack_system.jinja2
CREATE  backend/app/ai/prompts/student_pack_user.jinja2
CREATE  backend/tests/unit/test_student_pack_service.py
CREATE  backend/tests/integration/test_student_pack_routes.py

MODIFY  backend/app/main.py   ← register student_packs router
MODIFY  backend/app/api/v1/routes/lesson_plans.py  ← add student pack endpoint
```

---

## Part 1 — ORM Model

**`backend/app/models/student_lesson_pack.py`**

```python
from __future__ import annotations
from uuid import uuid4
from sqlalchemy import (
    Column, String, Text, Float, ForeignKey,
    DateTime, ARRAY, UniqueConstraint, func, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class StudentLessonPack(Base):
    __tablename__ = "student_lesson_packs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id       = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    # CONSTITUTION Rule 2: every non-curriculum table requires school_id.
    # student_lesson_packs is student data — school_id mandatory for tenant isolation.
    lesson_plan_id  = Column(UUID(as_uuid=True), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False)
    subtopic_id     = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False)
    learning_style  = Column(String(30), nullable=False)
    interest_category = Column(String(50), nullable=True)

    # Generated pack content
    what_you_will_learn = Column(Text, nullable=False)
    real_life_intro     = Column(Text, nullable=False)
    explanation         = Column(Text, nullable=False)
    content_sequence    = Column(String(20), nullable=False, default="video_first")
    video_url           = Column(Text, nullable=True)
    video_title         = Column(Text, nullable=True)

    # Quiz questions (UUIDs reference question_bank)
    pre_quiz_question_ids   = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    post_quiz_question_ids  = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    post_quiz_score         = Column(Float, nullable=True)
    post_quiz_completed_at  = Column(DateTime(timezone=True), nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ai_model     = Column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "student_id", "lesson_plan_id", "learning_style", "interest_category",
            name="uq_student_pack_lookup",
        ),
        CheckConstraint(
            "content_sequence IN ('video_first', 'text_first')",
            name="chk_content_sequence",
        ),
        CheckConstraint(
            "post_quiz_score IS NULL OR (post_quiz_score >= 0.0 AND post_quiz_score <= 1.0)",
            name="chk_post_quiz_score",
        ),
    )
```

---

## Part 2 — Pydantic Schemas

**`backend/app/schemas/student_pack.py`**

```python
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, field_validator


class StudentPackLLMOutput(BaseModel):
    """
    Validated JSON structure returned by Gemini for a student pack.
    Interest injection and learning style adaptation happen via the prompt.
    The LLM returns this shape. Validation failure triggers a retry.
    """
    what_you_will_learn: str    # 1 plain-language sentence — no Cambridge LO codes
    real_life_intro: str        # max 100 words — interest-matched real-world connection
    explanation: str            # max 200 words — learning-style adapted, no jargon

    @field_validator("what_you_will_learn")
    @classmethod
    def single_sentence(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("what_you_will_learn cannot be empty")
        return v

    @field_validator("real_life_intro")
    @classmethod
    def intro_word_limit(cls, v: str) -> str:
        v = v.strip()
        word_count = len(v.split())
        if word_count > 120:   # 20-word buffer over 100-word target
            raise ValueError(f"real_life_intro too long: {word_count} words (max 120)")
        return v

    @field_validator("explanation")
    @classmethod
    def explanation_word_limit(cls, v: str) -> str:
        v = v.strip()
        word_count = len(v.split())
        if word_count > 230:   # 30-word buffer over 200-word target
            raise ValueError(f"explanation too long: {word_count} words (max 230)")
        return v


class QuizQuestionResponse(BaseModel):
    """One question from question_bank for pre/post quiz display."""
    id: UUID
    question_text: str
    options: list[dict]         # [{"key": "A", "text": "..."}]
    correct_answer: str | None  # None in pre_quiz (revealed after post_quiz)
    explanation: str | None


class StudentPackResponse(BaseModel):
    """Returned by GET /lesson-plans/{id}/student-pack"""
    id: UUID
    lesson_plan_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    learning_style: str
    interest_category: str | None

    # Content
    what_you_will_learn: str
    real_life_intro: str
    explanation: str
    content_sequence: str       # 'video_first' | 'text_first'
    video_url: str | None
    video_title: str | None

    # Quizzes
    pre_quiz: list[QuizQuestionResponse]    # 3 questions — correct_answer is None
    post_quiz: list[QuizQuestionResponse]   # 3 questions — correct_answer revealed after score
    post_quiz_score: float | None
    post_quiz_completed_at: str | None

    generated_at: str
    ai_model: str | None


class PostQuizSubmitRequest(BaseModel):
    """Student submits post-quiz answers."""
    answers: dict[str, str]   # {question_id: selected_key}
```

---

## Part 3 — Service

**`backend/app/services/student_pack_service.py`**

```python
import asyncio
import json
import os
from datetime import datetime
from uuid import UUID
import random

import litellm
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.student_lesson_pack import StudentLessonPack
from app.models.student_learning_profile import StudentLearningProfile
from app.models.subtopic_content import SubtopicContent
from app.models.lesson_plan import LessonPlan
from app.models.question_bank import QuestionBank
from app.schemas.student_pack import StudentPackLLMOutput
from pydantic import ValidationError

logger = structlog.get_logger()

MODEL      = os.getenv("LLM_STUDENT_PACK_MODEL", "gemini/gemini-2.5-pro")
TIMEOUT_S  = float(os.getenv("LLM_STUDENT_PACK_TIMEOUT_S", "30"))
MAX_TOKENS = int(os.getenv("LLM_STUDENT_PACK_MAX_TOKENS", "1000"))
API_KEY    = os.getenv("OPENROUTER_API_KEY", "")

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../ai/prompts")
_jinja_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR))

# Interest category → plain-language example domains for the prompt
INTEREST_EXAMPLES = {
    "sports_movement": "sports, athletics, movement, physical activity",
    "tech_gaming":     "technology, gaming, apps, computers, robotics",
    "nature_animals":  "nature, animals, the environment, wildlife",
    "arts_culture":    "music, art, design, stories, films, culture",
}

# Learning style → content sequence preference
CONTENT_SEQUENCE = {
    "visual":          "video_first",
    "auditory":        "video_first",
    "kinesthetic":     "video_first",
    "reading_writing": "text_first",
    "mixed":           "video_first",
}


class StudentPackService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Public entry point ────────────────────────────────────────────────────

    async def get_or_generate(
        self,
        lesson_plan_id: UUID,
        student_id: UUID,
        school_id: UUID,
    ) -> StudentLessonPack:
        """
        Returns cached pack if available, otherwise generates and stores one.
        Cache key: (student_id, lesson_plan_id, learning_style, interest_category)
        """
        profile = await self._load_profile(student_id)
        learning_style = self._dominant_style(profile)
        interest_category = self._top_interest_category(profile)

        # Cache check
        existing = await self._load_cached(
            lesson_plan_id, student_id, learning_style, interest_category
        )
        if existing:
            logger.info(
                "student_pack_cache_hit",
                student_id=str(student_id),
                lesson_plan_id=str(lesson_plan_id),
            )
            return existing

        # Generate
        pack = await self._generate(
            lesson_plan_id=lesson_plan_id,
            student_id=student_id,
            school_id=school_id,
            profile=profile,
            learning_style=learning_style,
            interest_category=interest_category,
        )
        return pack

    # ── Post-quiz submission ──────────────────────────────────────────────────

    async def submit_post_quiz(
        self,
        pack_id: UUID,
        student_id: UUID,
        answers: dict[str, str],
    ) -> float:
        """
        Score the post-quiz, update mastery, return score 0.0–1.0.
        """
        pack = await self.session.get(StudentLessonPack, pack_id)
        if not pack or pack.student_id != student_id:
            raise ValueError("Pack not found or access denied")

        if pack.post_quiz_completed_at:
            return pack.post_quiz_score  # Already submitted — idempotent

        # Score MCQ answers
        correct = 0
        total = len(pack.post_quiz_question_ids)
        for q_id in pack.post_quiz_question_ids:
            question = await self.session.get(QuestionBank, q_id)
            if not question:
                continue
            selected = answers.get(str(q_id), "")
            if selected.strip().lower() == question.correct_answer.strip().lower():
                correct += 1

        score = correct / total if total > 0 else 0.0
        pack.post_quiz_score = score
        pack.post_quiz_completed_at = datetime.utcnow()
        await self.session.commit()

        # Update gap_states — reuse the mastery update logic from M1-4-T3
        from app.tasks.gap_state_tasks import update_mastery_from_pack_quiz
        await update_mastery_from_pack_quiz(
            student_id=student_id,
            subtopic_id=pack.subtopic_id,
            class_id=None,   # pack quiz does not require class context
            score=score,
            session=self.session,
        )

        logger.info(
            "student_pack_post_quiz_submitted",
            pack_id=str(pack_id),
            score=score,
            correct=correct,
            total=total,
        )
        return score

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _generate(
        self,
        lesson_plan_id: UUID,
        student_id: UUID,
        school_id: UUID,
        profile: StudentLearningProfile | None,
        learning_style: str,
        interest_category: str | None,
    ) -> StudentLessonPack:
        """Generate a new student pack via LLM and store it."""
        plan = await self.session.get(LessonPlan, lesson_plan_id)
        if not plan:
            raise ValueError(f"Lesson plan {lesson_plan_id} not found")

        # Get primary focus subtopic from lesson plan
        focus_subtopic_ids = plan.generated_plan.get("focus_subtopic_ids", [])
        if not focus_subtopic_ids:
            raise ValueError("Lesson plan has no focus subtopics")
        subtopic_id = UUID(focus_subtopic_ids[0])

        # Load subtopic content
        content = await self.session.get(SubtopicContent, subtopic_id)
        subtopic = await self.session.get(Subtopic, subtopic_id)

        base_explanation = (
            content.approved_explanation
            if content and content.approved_explanation
            else (subtopic.learning_objective if subtopic else "")
        )

        # Select video
        video_url, video_title = None, None
        if content:
            approved = content.get_approved_videos()
            if approved:
                # Pick the first approved video — already ranked by view_count in seed
                video_url = approved[0]["url"]
                video_title = approved[0]["title"]

        # Select pre/post quiz questions from question_bank (mastery-calibrated)
        # Load current mastery for this subtopic to calibrate post-quiz difficulty
        from app.services.gap_map_service import GapMapService
        gap_service = GapMapService(self.session)
        student_mastery = await gap_service.get_subtopic_mastery(
            student_id=student_id, subtopic_id=subtopic_id
        ) or 0.0   # default to 0.0 if no prior assessment data
        pre_ids, post_ids = await self._select_quiz_questions(
            subtopic_id, student_mastery=student_mastery
        )

        # Call LLM
        llm_output = await self._call_llm(
            subtopic=subtopic,
            base_explanation=base_explanation,
            learning_style=learning_style,
            interest_category=interest_category,
        )

        # Determine content sequence
        content_sequence = CONTENT_SEQUENCE.get(learning_style, "video_first")

        # Store
        pack = StudentLessonPack(
            student_id=student_id,
            lesson_plan_id=lesson_plan_id,
            subtopic_id=subtopic_id,
            learning_style=learning_style,
            interest_category=interest_category,
            what_you_will_learn=llm_output.what_you_will_learn,
            real_life_intro=llm_output.real_life_intro,
            explanation=llm_output.explanation,
            content_sequence=content_sequence,
            video_url=video_url,
            video_title=video_title,
            pre_quiz_question_ids=pre_ids,
            post_quiz_question_ids=post_ids,
            ai_model=MODEL,
        )
        self.session.add(pack)
        await self.session.commit()
        await self.session.refresh(pack)

        logger.info(
            "student_pack_generated",
            pack_id=str(pack.id),
            student_id=str(student_id),
            learning_style=learning_style,
            interest_category=interest_category,
            has_video=video_url is not None,
        )
        return pack

    async def _call_llm(
        self,
        subtopic,
        base_explanation: str,
        learning_style: str,
        interest_category: str | None,
    ) -> StudentPackLLMOutput:
        """Call LLM with retry. Returns validated StudentPackLLMOutput."""
        system_tmpl = _jinja_env.get_template("student_pack_system.jinja2")
        user_tmpl   = _jinja_env.get_template("student_pack_user.jinja2")

        system_prompt = system_tmpl.render()
        user_prompt = user_tmpl.render(
            subtopic_name=subtopic.name if subtopic else "this topic",
            learning_objective=subtopic.learning_objective if subtopic else "",
            base_explanation=base_explanation,
            learning_style=learning_style,
            interest_examples=INTEREST_EXAMPLES.get(interest_category, ""),
            has_interest=interest_category is not None,
        )

        is_openrouter = MODEL.startswith("openrouter/") or MODEL.startswith("gemini/")
        kwargs: dict = dict(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.4,
        )
        if API_KEY and is_openrouter:
            kwargs["api_key"] = API_KEY

        for attempt in range(2):
            try:
                response = await asyncio.wait_for(
                    litellm.acompletion(**kwargs),
                    timeout=TIMEOUT_S,
                )
                raw = response.choices[0].message.content or ""
                validated = self._parse_and_validate(raw)
                if validated:
                    return validated
                logger.warning("student_pack_validation_retry", attempt=attempt + 1)
            except asyncio.TimeoutError:
                logger.warning("student_pack_timeout", attempt=attempt + 1)
            except Exception as exc:
                logger.warning("student_pack_llm_error", attempt=attempt + 1, error=str(exc))

        # Both attempts failed — return a minimal degraded pack
        logger.error("student_pack_generation_failed_degraded", subtopic=subtopic.name if subtopic else "")
        return StudentPackLLMOutput(
            what_you_will_learn=f"You will learn about {subtopic.name if subtopic else 'this topic'}.",
            real_life_intro=base_explanation[:200] if base_explanation else "See your teacher for context.",
            explanation=base_explanation[:500] if base_explanation else subtopic.learning_objective if subtopic else "",
        )

    @staticmethod
    def _parse_and_validate(raw: str) -> StudentPackLLMOutput | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.strip().startswith("```"))
        try:
            data = json.loads(cleaned)
            return StudentPackLLMOutput(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("student_pack_parse_failed", error=str(exc))
            return None

    async def _select_quiz_questions(
        self, subtopic_id: UUID, student_mastery: float, count: int = 3
    ) -> tuple[list[UUID], list[UUID]]:
        """
        Select pre-quiz and post-quiz questions from question_bank for this subtopic.

        Pre-quiz: easier questions (difficulty_level 1–2) — diagnostic baseline.
        Post-quiz: calibrated to student mastery level — harder if mastery is high.
        Pre and post never overlap.

        Mastery → post-quiz difficulty range:
          < 0.4  → difficulty 1–2 (foundational)
          0.4–0.7 → difficulty 2–3 (developing)
          > 0.7  → difficulty 3–5 (extension)

        Falls back to any available questions if difficulty-filtered set is too small.
        """
        # Determine difficulty ranges
        pre_difficulty_max = 2.0   # pre-quiz always tests foundational recall
        if student_mastery < 0.4:
            post_difficulty_min, post_difficulty_max = 1.0, 2.5
        elif student_mastery < 0.7:
            post_difficulty_min, post_difficulty_max = 2.0, 3.5
        else:
            post_difficulty_min, post_difficulty_max = 3.0, 5.0

        base_query = (
            select(QuestionBank)
            .where(QuestionBank.subtopic_id == subtopic_id)
            .where(QuestionBank.is_active == True)
            .where(QuestionBank.question_type == "MCQ")
        )

        # Pre-quiz: easy questions
        pre_result = await self.session.scalars(
            base_query
            .where(QuestionBank.difficulty_level <= pre_difficulty_max)
            .limit(count + 3)
        )
        pre_pool = list(pre_result.all())
        random.shuffle(pre_pool)
        pre_questions = pre_pool[:count]
        pre_ids_set = {q.id for q in pre_questions}

        # Post-quiz: mastery-calibrated, exclude pre-quiz questions
        post_result = await self.session.scalars(
            base_query
            .where(QuestionBank.difficulty_level >= post_difficulty_min)
            .where(QuestionBank.difficulty_level <= post_difficulty_max)
            .where(QuestionBank.id.notin_(pre_ids_set))
            .limit(count + 3)
        )
        post_pool = list(post_result.all())

        # Fallback: if not enough calibrated questions, use any remaining
        if len(post_pool) < count:
            fallback_result = await self.session.scalars(
                base_query
                .where(QuestionBank.id.notin_(pre_ids_set))
                .limit(count + 3)
            )
            post_pool = list(fallback_result.all())
            logger.info(
                "student_pack_quiz_difficulty_fallback",
                subtopic_id=str(subtopic_id),
                student_mastery=student_mastery,
                post_difficulty_min=post_difficulty_min,
            )

        random.shuffle(post_pool)
        post_questions = post_pool[:count]

        return [q.id for q in pre_questions], [q.id for q in post_questions]

    async def _load_cached(
        self,
        lesson_plan_id: UUID,
        student_id: UUID,
        learning_style: str,
        interest_category: str | None,
    ) -> StudentLessonPack | None:
        result = await self.session.scalars(
            select(StudentLessonPack).where(
                StudentLessonPack.student_id == student_id,
                StudentLessonPack.lesson_plan_id == lesson_plan_id,
                StudentLessonPack.learning_style == learning_style,
                StudentLessonPack.interest_category == interest_category,
            )
        )
        return result.first()

    async def _load_profile(self, student_id: UUID) -> StudentLearningProfile | None:
        return await self.session.get(StudentLearningProfile, student_id)

    @staticmethod
    def _dominant_style(profile: StudentLearningProfile | None) -> str:
        if not profile or not profile.modality_scores:
            return "mixed"
        scores = profile.modality_scores
        dominant = max(scores, key=scores.get)
        return dominant if scores[dominant] > 0.5 else "mixed"

    @staticmethod
    def _top_interest_category(profile: StudentLearningProfile | None) -> str | None:
        """
        Maps raw student interests to one of the 4 canonical interest categories.
        Uses questionnaire_config.py — do NOT duplicate the mapping here.
        """
        if not profile or not profile.interests:
            return None
        from app.core.questionnaire_config import get_interest_category
        # get_interest_category(interests: list[str]) -> str | None
        # Returns: 'sports_movement' | 'tech_gaming' | 'nature_animals' | 'arts_culture' | None
        # Iterates student interests in order and returns the first category match.
        # Returns None if no interest maps to a known category.
        return get_interest_category(profile.interests)
```

---

## Part 4 — Prompt Templates

### `student_pack_system.jinja2`

```jinja2
You are an educational content writer creating personalised lesson packs for
secondary school students (aged 11–18).

Your job is to take a curriculum topic and write three things:
1. A single motivating sentence telling the student what they will learn
2. A short real-world introduction (max 100 words) connecting the topic to their life
3. A clear explanation of the topic (max 200 words) adapted to how they learn best

Rules:
- Write directly TO the student ("you will learn", "imagine you are", "think about")
- Never mention Cambridge, IGCSE, learning objectives, or assessment
- No bullet points, no headers in the explanation — flowing prose only
- Use simple language suitable for the student's grade level
- Academic accuracy is non-negotiable — do not sacrifice correctness for simplicity
- Return ONLY valid JSON with keys: what_you_will_learn, real_life_intro, explanation
- No preamble, no markdown fences, no explanation outside the JSON
```

### `student_pack_user.jinja2`

```jinja2
Topic: {{ subtopic_name }}
What students should understand: {{ learning_objective }}

Background explanation (use this as your source of truth — rewrite for the student):
{{ base_explanation }}

How this student learns best: {{ learning_style }}
{% if learning_style == "visual" %}
Use concrete imagery and comparisons. Help them picture the concept.
{% elif learning_style == "auditory" %}
Write as if you are speaking to them. Use rhythm and flow in your sentences.
{% elif learning_style == "kinesthetic" %}
Frame the explanation around doing and experiencing. Use action verbs.
{% elif learning_style == "reading_writing" %}
Be precise and structured. Define key terms clearly in the prose.
{% else %}
Use a clear, direct style that balances explanation and example.
{% endif %}

{% if has_interest %}
Real-world connection: Frame the real_life_intro using examples from:
{{ interest_examples }}
Make it genuine — if the connection is forced, use a different real-world context.
{% endif %}

Return this exact JSON structure:
{
  "what_you_will_learn": "By the end of this lesson, you will be able to [one sentence].",
  "real_life_intro": "[max 100 words — real-world hook matched to student interests]",
  "explanation": "[max 200 words — curriculum-accurate, written for this student]"
}
```

---

## Part 5 — API Endpoint

**Add to `backend/app/api/v1/routes/lesson_plans.py`:**

```python
@router.get(
    "/lesson-plans/{plan_id}/student-pack",
    response_model=StudentPackResponse,
    summary="Get or generate student pack for a lesson plan",
)
async def get_student_pack(
    plan_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentPackResponse:
    """
    Returns the student pack for this lesson plan.
    On first access: generates pack synchronously (~5-8s) then caches.
    On subsequent access: returns cached pack instantly.

    Auth: STUDENT role only. Student must be enrolled in the class this
    plan belongs to — enforced in service layer.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students only")

    service = StudentPackService(db)
    pack = await service.get_or_generate(
        lesson_plan_id=plan_id,
        student_id=current_user.id,
        school_id=current_user.school_id,
    )
    return await _build_response(pack, db)


@router.post(
    "/lesson-plans/{plan_id}/student-pack/quiz/submit",
    response_model=dict,
    summary="Submit post-lesson quiz answers",
)
async def submit_post_quiz(
    plan_id: UUID,
    body: PostQuizSubmitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit post-quiz answers. Updates mastery score for the subtopic.
    Returns: {"score": 0.0-1.0, "correct": N, "total": N}
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students only")

    service = StudentPackService(db)
    score = await service.submit_post_quiz(
        pack_id=plan_id,   # pack resolved from plan via student context
        student_id=current_user.id,
        answers=body.answers,
    )
    return {"score": score}


async def _build_response(pack: StudentLessonPack, db: AsyncSession) -> StudentPackResponse:
    """Load question details and build response schema."""
    pre_questions = await _load_questions(pack.pre_quiz_question_ids, db, reveal_answers=False)
    post_questions = await _load_questions(
        pack.post_quiz_question_ids, db,
        reveal_answers=pack.post_quiz_completed_at is not None,
    )
    subtopic = await db.get(Subtopic, pack.subtopic_id)
    return StudentPackResponse(
        id=pack.id,
        lesson_plan_id=pack.lesson_plan_id,
        subtopic_id=pack.subtopic_id,
        subtopic_name=subtopic.name if subtopic else "",
        learning_style=pack.learning_style,
        interest_category=pack.interest_category,
        what_you_will_learn=pack.what_you_will_learn,
        real_life_intro=pack.real_life_intro,
        explanation=pack.explanation,
        content_sequence=pack.content_sequence,
        video_url=pack.video_url,
        video_title=pack.video_title,
        pre_quiz=pre_questions,
        post_quiz=post_questions,
        post_quiz_score=pack.post_quiz_score,
        post_quiz_completed_at=pack.post_quiz_completed_at.isoformat() if pack.post_quiz_completed_at else None,
        generated_at=pack.generated_at.isoformat(),
        ai_model=pack.ai_model,
    )
```

---

## Part 6 — Acceptance Criteria

### Service
- [ ] `get_or_generate` returns cached pack on second call — no LLM called
- [ ] Cache key is `(student_id, lesson_plan_id, learning_style, interest_category)`
- [ ] Two students with same learning_style + interest_category share the same pack
- [ ] Two students with different learning_styles get different packs
- [ ] Student with `reading_writing` dominant style → `content_sequence = "text_first"`
- [ ] Student with `visual` dominant style → `content_sequence = "video_first"`
- [ ] Student with no profile → `learning_style = "mixed"`, `interest_category = None`
- [ ] Pack with approved video → `video_url` is populated
- [ ] Pack with no approved videos → `video_url = None` (no error)
- [ ] Pre and post quiz question IDs do not overlap
- [ ] LLM timeout on both attempts → degraded pack stored, no error raised to caller
- [ ] Post-quiz submit scores correctly (5 MCQ, deterministic)
- [ ] Post-quiz submit is idempotent — second submit returns same score
- [ ] Post-quiz submit triggers mastery update

### API
- [ ] `GET /lesson-plans/{id}/student-pack` — STUDENT role returns 200
- [ ] `GET /lesson-plans/{id}/student-pack` — TEACHER role returns 403
- [ ] `GET /lesson-plans/{id}/student-pack` — first call takes ≤ 30s (LLM timeout)
- [ ] `GET /lesson-plans/{id}/student-pack` — second call returns instantly (cached)
- [ ] `POST /lesson-plans/{id}/student-pack/quiz/submit` — returns score
- [ ] Pre-quiz questions have `correct_answer = null` in response
- [ ] Post-quiz questions reveal `correct_answer` only after submission

---

## Part 7 — Tests

```python
# backend/tests/unit/test_student_pack_service.py

def test_get_or_generate_when_cached_then_no_llm_call()
def test_get_or_generate_when_not_cached_then_llm_called_and_stored()
def test_dominant_style_when_visual_above_0_5_then_visual()
def test_dominant_style_when_all_equal_then_mixed()
def test_dominant_style_when_no_profile_then_mixed()
def test_content_sequence_when_reading_writing_then_text_first()
def test_content_sequence_when_visual_then_video_first()
def test_top_interest_when_interests_include_football_then_sports_movement()
def test_top_interest_when_no_interests_then_none()
def test_select_quiz_questions_when_enough_questions_then_no_overlap()
def test_select_quiz_questions_when_few_questions_then_degrades_gracefully()
def test_submit_post_quiz_when_all_correct_then_score_1_0()
def test_submit_post_quiz_when_already_submitted_then_idempotent()
def test_parse_and_validate_when_valid_json_then_returns_output()
def test_parse_and_validate_when_markdown_fences_then_stripped()
def test_parse_and_validate_when_explanation_too_long_then_none()
def test_llm_timeout_both_attempts_then_degraded_pack_returned()

# backend/tests/integration/test_student_pack_routes.py

def test_get_student_pack_when_student_role_then_200()
def test_get_student_pack_when_teacher_role_then_403()
def test_get_student_pack_when_first_call_then_pack_stored_in_db()
def test_get_student_pack_when_second_call_then_same_pack_returned()
def test_submit_post_quiz_when_valid_answers_then_score_returned()
def test_submit_post_quiz_when_second_submission_then_same_score()
```

---

## Environment Variables

Add to `.env.example`:

```bash
# Student pack generation
LLM_STUDENT_PACK_MODEL=gemini/gemini-2.5-pro
LLM_STUDENT_PACK_TIMEOUT_S=30
LLM_STUDENT_PACK_MAX_TOKENS=1000
```

---

## Do NOT Touch

- `lesson_plans` table — student pack is stored in `student_lesson_packs` only
- `M4-1-T1` Celery beat task — student packs are NOT generated on the Monday schedule
- `curriculum_chunks` — never read or write
- `subtopics.embedding` — not used
- `apps/teacher` — no student pack UI goes there (student pack UI is M4-2-T2 in `apps/student`)

---

*Task M4-2-T1 · Kramer (Technical Lead) · April 2026*
