"""Mini-course service.

Handles student mini-course delivery: interest-matched explanation,
approved video, check questions, progress tracking, chat history,
AI-graded transfer questions, teacher course-detail view, and teacher
interest-category overrides per student.

All business logic lives here — route handlers are thin wrappers.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Literal, cast

import structlog
from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import case, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import router as llm_router
from app.core.questionnaire_config import INTEREST_KEY_TO_CATEGORY
from app.models.class_topic import ClassTopic
from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, Topic
from app.models.interest_category import InterestCategory
from app.models.mini_course import (
    MiniCourseChatMessage,
    MiniCourseQuizResponse,
    MiniCourseStudentOverride,
    SubtopicContentFeedback,
    SubtopicCourseProgress,
)
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class
from app.models.subtopic_content import SubtopicContent
from app.schemas.mini_course import (
    ChatHistoryResponse,
    ChatMessageItem,
    CheckQuestion,
    CheckQuestionOption,
    CourseProgressItem,
    GradeAnswerResponse,
    LatestOpenAnswerItem,
    LearningProfileItem,
    MarkProgressRequest,
    NextSubtopicItem,
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudentCourseProgressResponse,
    SubtopicCourseResponse,
    SubtopicExplanationItem,
    SubtopicProgressItem,
    SubtopicVideoItem,
    TransferQuestionResponse,
)
from app.services.question_selection import questions_for_subtopic

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

# Human-readable labels for learning profile fields surfaced in the UI
_MODALITY_LABELS: dict[str, str] = {
    "visual": "Visual learner",
    "auditory": "Auditory learner",
    "reading_writing": "Reading/writing",
    "kinesthetic": "Hands-on learner",
}
_WORK_STYLE_LABELS: dict[str, str] = {
    "prefers_solo": "Solo learner",
    "short_sessions": "Quick sessions",
    "task_based": "Task-based",
    "group_learning": "Group learner",
    "concept_first": "Concept-first",
}

# Fallback question when LLM generation fails
_TRANSFER_QUESTION_FALLBACK = (
    "Can you explain this concept in your own words and give one real-life example of where you might see it?"
)

logger = structlog.get_logger()

# Maximum check questions served per mini-course page
_CHECK_QUESTION_LIMIT = 3


class MiniCourseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_course_for_student(
        self,
        subtopic_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> SubtopicCourseResponse:
        """Return the full mini-course payload for a subtopic and student.

        Steps:
        1. Resolve subtopic + topic name (404 if not found).
        2. Load student's first interest key → resolve to interest_category_id.
        3. Fetch best approved explanation (interest-matched first, fallback generic).
        4. Fetch best approved video.
        5. Fetch up to 3 random check questions from question_bank.
        6. Upsert SubtopicCourseProgress (update last_visited_at).
        7. Return assembled SubtopicCourseResponse.
        """
        # 1. Resolve subtopic + topic name + sequence_order + curriculum_topic_id
        subtopic_row = await self.db.execute(
            select(
                Subtopic.id,
                Subtopic.name.label("subtopic_name"),
                Subtopic.sequence_order,
                Subtopic.curriculum_topic_id,
                Topic.name.label("topic_name"),
            )
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .where(Subtopic.id == subtopic_id)
        )
        subtopic_data = subtopic_row.one_or_none()
        if subtopic_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subtopic {subtopic_id} not found",
            )

        subtopic_name: str = subtopic_data.subtopic_name
        topic_name: str = subtopic_data.topic_name
        current_order: int | None = subtopic_data.sequence_order
        curriculum_topic_id: uuid.UUID = subtopic_data.curriculum_topic_id

        logger.debug(
            "mini_course_fetch_started",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
        )

        # 2. Load full learning profile (interest category + profile labels)
        interest_category_id, learning_profile_item = await self._resolve_learning_profile(student_id=student_id)

        # 3. Fetch best approved explanation
        explanation_content = await self._fetch_best_explanation(
            subtopic_id=subtopic_id,
            interest_category_id=interest_category_id,
        )

        # 4. Fetch best approved video
        video_content = await self._fetch_approved_video(subtopic_id=subtopic_id)

        # 5. Fetch check questions (random sample)
        check_questions = await self._fetch_check_questions(subtopic_id=subtopic_id)

        # 5b. Fetch latest open-ended answer for re-entry display
        latest_open_answer = await self._fetch_latest_open_answer(student_id=student_id, subtopic_id=subtopic_id)

        # 6. Upsert progress row (last_visited_at = now)
        progress = await self._upsert_visit(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
        )

        # 7. Assemble explanation schema
        explanation_item: SubtopicExplanationItem | None = None
        if explanation_content is not None:
            display_text = explanation_content.teacher_explanation or explanation_content.explanation_text or ""
            interest_matched = (
                interest_category_id is not None and explanation_content.interest_category_id == interest_category_id
            )
            explanation_item = SubtopicExplanationItem(
                content_id=explanation_content.id,
                explanation_text=display_text,
                interest_matched=interest_matched,
            )

        # 8. Assemble video schema — read from JSONB array, not legacy flat columns
        video_item: SubtopicVideoItem | None = None
        if video_content is not None:
            approved_entries = [v for v in (video_content.videos or []) if v.get("status") == "approved"]
            if approved_entries:
                first = approved_entries[0]
                video_item = SubtopicVideoItem(
                    video_url=first.get("url", ""),
                    thumbnail_url=first.get("thumbnail_url"),
                    duration_seconds=first.get("duration_seconds"),
                )

        content_status: Literal["ready", "unavailable"] = "ready" if explanation_item is not None else "unavailable"

        # 9. Resolve next subtopic in sequence (skip inactive)
        next_subtopic_item: NextSubtopicItem | None = None
        if current_order is not None:
            next_row = await self.db.execute(
                select(Subtopic.id, Subtopic.name)
                .where(
                    Subtopic.curriculum_topic_id == curriculum_topic_id,
                    Subtopic.sequence_order > current_order,
                    Subtopic.is_active.is_(True),
                )
                .order_by(Subtopic.sequence_order)
                .limit(1)
            )
            next_subtopic_data = next_row.one_or_none()
            if next_subtopic_data is not None:
                next_subtopic_item = NextSubtopicItem(
                    id=next_subtopic_data.id,
                    name=next_subtopic_data.name,
                )

        return SubtopicCourseResponse(
            subtopic_id=subtopic_id,
            subtopic_name=subtopic_name,
            topic_name=topic_name,
            explanation=explanation_item,
            content_status=content_status,
            video=video_item,
            check_questions=check_questions,
            progress=progress,
            next_subtopic=next_subtopic_item,
            learning_profile=learning_profile_item,
            latest_open_answer=latest_open_answer,
        )

    async def mark_progress(
        self,
        subtopic_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        request: MarkProgressRequest,
    ) -> None:
        """Idempotent upsert of explanation_accessed / video_accessed flags.

        Uses INSERT ... ON CONFLICT DO UPDATE with GREATEST() to only ever
        advance flags from False → True, never backwards.
        """
        await self.db.execute(
            text(
                """
                INSERT INTO subtopic_course_progress
                    (student_id, subtopic_id, school_id,
                     explanation_accessed, video_accessed, last_visited_at)
                VALUES
                    (:student_id, :subtopic_id, :school_id,
                     :explanation_accessed, :video_accessed, now())
                ON CONFLICT (student_id, subtopic_id) DO UPDATE SET
                    explanation_accessed = GREATEST(
                        subtopic_course_progress.explanation_accessed,
                        EXCLUDED.explanation_accessed
                    ),
                    video_accessed = GREATEST(
                        subtopic_course_progress.video_accessed,
                        EXCLUDED.video_accessed
                    ),
                    last_visited_at = now()
                """
            ),
            {
                "student_id": student_id,
                "subtopic_id": subtopic_id,
                "school_id": school_id,
                "explanation_accessed": request.explanation_accessed,
                "video_accessed": request.video_accessed,
            },
        )
        await self.db.commit()

        logger.info(
            "mini_course_progress_marked",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
            explanation_accessed=request.explanation_accessed,
            video_accessed=request.video_accessed,
        )

    async def submit_quiz(
        self,
        subtopic_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        request: QuizSubmitRequest,
    ) -> QuizSubmitResponse:
        """Score the student's MCQ answers, persist per-response rows, update aggregate score.

        Writes one MiniCourseQuizResponse row per answer, then recomputes
        check_questions_score as AVG(score) across all MCQ responses for this
        student+subtopic. GREATEST() ensures the recorded score never regresses.
        """
        # Fetch correct answers for submitted question IDs
        question_ids = [a.question_id for a in request.answers]
        bank_rows = await self.db.execute(
            select(QuestionBank.id, QuestionBank.question_text, QuestionBank.correct_answer).where(
                QuestionBank.id.in_(question_ids)
            )
        )
        bank_map: dict[str, tuple[str, str]] = {
            str(row.id): (row.question_text, row.correct_answer) for row in bank_rows
        }

        answer_map: dict[str, str] = {str(a.question_id): a.selected_key for a in request.answers}
        total = len(bank_map)
        correct_count = 0

        # Write one response row per submitted answer
        for qid, selected_key in answer_map.items():
            question_text, correct_answer = bank_map.get(qid, ("", ""))
            is_correct = selected_key == correct_answer
            if is_correct:
                correct_count += 1
            self.db.add(
                MiniCourseQuizResponse(
                    student_id=student_id,
                    subtopic_id=subtopic_id,
                    school_id=school_id,
                    question_type="mcq",
                    question_text=question_text,
                    student_answer=selected_key,
                    ai_grade="correct" if is_correct else "incorrect",
                    ai_feedback=None,
                    score=1.0 if is_correct else 0.0,
                )
            )

        score = correct_count / total if total > 0 else 0.0

        # Upsert progress — GREATEST() ensures score never regresses on re-submission
        await self.db.execute(
            text(
                """
                INSERT INTO subtopic_course_progress
                    (student_id, subtopic_id, school_id,
                     explanation_accessed, video_accessed,
                     check_questions_score, last_visited_at)
                VALUES
                    (:student_id, :subtopic_id, :school_id,
                     false, false, :score, now())
                ON CONFLICT (student_id, subtopic_id) DO UPDATE SET
                    check_questions_score = GREATEST(
                        subtopic_course_progress.check_questions_score,
                        EXCLUDED.check_questions_score
                    ),
                    last_visited_at = now()
                """
            ),
            {
                "student_id": student_id,
                "subtopic_id": subtopic_id,
                "school_id": school_id,
                "score": score,
            },
        )
        await self.db.commit()

        logger.info(
            "mini_course_quiz_submitted",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
            score=score,
            correct=correct_count,
            total=total,
        )

        return QuizSubmitResponse(
            score=score,
            correct=correct_count,
            total=total,
            status="completed",
        )

    async def submit_content_feedback(
        self,
        content_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        feedback_type: str,
        comment: str | None,
    ) -> SubtopicContentFeedback:
        """Upsert student feedback (thumbs_up / thumbs_down) for a subtopic content row.

        Steps:
        1. Verify the SubtopicContent row exists (404 if not).
        2. Upsert SubtopicContentFeedback (unique on student_id + subtopic_content_id).
           On conflict, update feedback_type and comment.
        3. Recalculate and update thumbs_up_count / thumbs_down_count on subtopic_content.
        4. Return the feedback row.
        """
        # 1. Verify content exists
        content_result = await self.db.execute(select(SubtopicContent).where(SubtopicContent.id == content_id))
        content_row = content_result.scalar_one_or_none()
        if content_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SubtopicContent {content_id} not found",
            )

        # 2. Upsert feedback row
        await self.db.execute(
            text(
                """
                INSERT INTO subtopic_content_feedback
                    (id, student_id, subtopic_content_id, school_id,
                     feedback_type, comment, created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :student_id, :content_id, :school_id,
                     :feedback_type, :comment, now(), now())
                ON CONFLICT (student_id, subtopic_content_id) DO UPDATE SET
                    feedback_type = EXCLUDED.feedback_type,
                    comment       = EXCLUDED.comment,
                    updated_at    = now()
                """
            ),
            {
                "student_id": student_id,
                "content_id": content_id,
                "school_id": school_id,
                "feedback_type": feedback_type,
                "comment": comment,
            },
        )

        # 3. Recalculate aggregate counts
        counts_result = await self.db.execute(
            select(
                func.count(case((SubtopicContentFeedback.feedback_type == "thumbs_up", 1))).label("up_count"),
                func.count(case((SubtopicContentFeedback.feedback_type == "thumbs_down", 1))).label("down_count"),
            ).where(SubtopicContentFeedback.subtopic_content_id == content_id)
        )
        counts = counts_result.one()

        await self.db.execute(
            update(SubtopicContent)
            .where(SubtopicContent.id == content_id)
            .values(
                thumbs_up_count=counts.up_count,
                thumbs_down_count=counts.down_count,
            )
        )
        await self.db.commit()

        # 4. Return the feedback row
        feedback_result = await self.db.execute(
            select(SubtopicContentFeedback).where(
                SubtopicContentFeedback.student_id == student_id,
                SubtopicContentFeedback.subtopic_content_id == content_id,
            )
        )
        feedback_row = feedback_result.scalar_one()

        logger.info(
            "content_feedback_submitted",
            student_id=str(student_id),
            content_id=str(content_id),
            feedback_type=feedback_type,
        )

        return feedback_row

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_learning_profile(
        self, student_id: uuid.UUID
    ) -> tuple[uuid.UUID | None, LearningProfileItem | None]:
        """Return (interest_category_id, LearningProfileItem) for the student.

        interest_category_id is used for content matching.
        LearningProfileItem carries human-readable labels for the UI header.
        Both are None if the student has no completed learning profile.
        """
        profile_result = await self.db.execute(
            select(StudentLearningProfile).where(
                StudentLearningProfile.student_id == student_id,
                StudentLearningProfile.completed_at.is_not(None),
            )
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            return None, None

        # Dominant modality — handle both schema versions:
        #   v2 (current): {"visual": 0.7, "auditory": 0.5, ...}  — float scores per modality
        #   v1 (legacy):  {"dominant": "reading_writing", ...}    — string modality names as values
        raw_modality = profile.modality_scores
        dominant_key: str | None = None
        if isinstance(raw_modality, dict):
            first_val = next(iter(raw_modality.values()), None)
            if isinstance(first_val, str):
                # v1 legacy format — "dominant" key holds the modality name directly
                dominant_key = raw_modality.get("dominant")
            else:
                try:
                    modality_scores: dict[str, float] = {
                        k: float(v) for k, v in raw_modality.items() if v is not None and isinstance(k, str)
                    }
                    dominant_key = max(modality_scores, key=lambda k: modality_scores[k]) if modality_scores else None
                except (ValueError, TypeError):
                    dominant_key = None
        dominant_label = _MODALITY_LABELS.get(dominant_key, None) if dominant_key else None

        # Top interest
        interests: list[str] = profile.interests or []
        first_interest = interests[0] if interests else None

        # Top work style flag
        work_style: dict[str, object] = profile.work_style or {}
        work_style_label: str | None = None
        for key, label in _WORK_STYLE_LABELS.items():
            if work_style.get(key):
                work_style_label = label
                break

        profile_item = LearningProfileItem(
            dominant_modality=dominant_label,
            interest=first_interest,
            work_style_label=work_style_label,
        )

        # Resolve interest category ID
        interest_category_id: uuid.UUID | None = None
        if first_interest:
            category_name = INTEREST_KEY_TO_CATEGORY.get(first_interest.lower())
            if category_name:
                cat_result = await self.db.execute(
                    select(InterestCategory.id).where(InterestCategory.name == category_name)
                )
                cat_row = cat_result.one_or_none()
                interest_category_id = cat_row.id if cat_row else None

        return interest_category_id, profile_item

    async def _fetch_best_explanation(
        self,
        subtopic_id: uuid.UUID,
        interest_category_id: uuid.UUID | None,
    ) -> SubtopicContent | None:
        """Return best approved explanation for subtopic.

        Ordering: interest-matched row first (CASE score 0), generic fallback (score 1).
        """
        priority_expr = case(
            (SubtopicContent.interest_category_id == interest_category_id, 0),
            else_=1,
        )
        result = await self.db.execute(
            select(SubtopicContent)
            .where(
                SubtopicContent.subtopic_id == subtopic_id,
                SubtopicContent.content_type == "explanation",
                SubtopicContent.review_status == "approved",
                SubtopicContent.is_active.is_(True),
                SubtopicContent.is_archived.is_(False),
            )
            .order_by(priority_expr, SubtopicContent.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _fetch_approved_video(self, subtopic_id: uuid.UUID) -> SubtopicContent | None:
        """Return first approved active video for subtopic."""
        result = await self.db.execute(
            select(SubtopicContent)
            .where(
                SubtopicContent.subtopic_id == subtopic_id,
                SubtopicContent.content_type == "video",
                SubtopicContent.review_status == "approved",
                SubtopicContent.is_active.is_(True),
                SubtopicContent.is_archived.is_(False),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _fetch_latest_open_answer(
        self, student_id: uuid.UUID, subtopic_id: uuid.UUID
    ) -> LatestOpenAnswerItem | None:
        """Return the most recent open_ended response for this student+subtopic, or None."""
        result = await self.db.execute(
            select(MiniCourseQuizResponse)
            .where(
                MiniCourseQuizResponse.student_id == student_id,
                MiniCourseQuizResponse.subtopic_id == subtopic_id,
                MiniCourseQuizResponse.question_type == "open_ended",
            )
            .order_by(MiniCourseQuizResponse.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return LatestOpenAnswerItem(
            question_text=row.question_text,
            student_answer=row.student_answer,
            ai_grade=row.ai_grade,
            ai_feedback=row.ai_feedback,
            score=row.score,
        )

    async def _fetch_check_questions(self, subtopic_id: uuid.UUID) -> list[CheckQuestion]:
        """Return up to 3 random active questions from question_bank for subtopic.

        Resolves through the subtopic's learning objectives, not question_bank.subtopic_id.
        That column is NULL for every remapped question, so keying on it returned an
        empty list for any remapped subtopic and the check step silently had no
        questions at all.
        """
        result = await self.db.execute(
            questions_for_subtopic(subtopic_id).order_by(func.random()).limit(_CHECK_QUESTION_LIMIT)
        )
        rows = result.scalars().all()

        questions: list[CheckQuestion] = []
        for row in rows:
            # MCQ options JSONB: [{"key": "A", "text": "..."}, ...]
            options: list[CheckQuestionOption] = []
            if row.options and isinstance(row.options, list):
                for opt in row.options:
                    if isinstance(opt, dict) and "key" in opt and "text" in opt:
                        options.append(CheckQuestionOption(key=opt["key"], text=opt["text"]))
            questions.append(
                CheckQuestion(
                    question_id=row.id,
                    question_text=row.question_text,
                    options=options,
                    correct_answer=row.correct_answer or "",
                )
            )
        return questions

    async def _upsert_visit(
        self,
        student_id: uuid.UUID,
        subtopic_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> CourseProgressItem:
        """Upsert SubtopicCourseProgress, updating last_visited_at to now.

        Returns the current progress state for the response.
        """
        await self.db.execute(
            text(
                """
                INSERT INTO subtopic_course_progress
                    (student_id, subtopic_id, school_id,
                     explanation_accessed, video_accessed, last_visited_at)
                VALUES
                    (:student_id, :subtopic_id, :school_id,
                     false, false, now())
                ON CONFLICT (student_id, subtopic_id) DO UPDATE SET
                    last_visited_at = now()
                """
            ),
            {
                "student_id": student_id,
                "subtopic_id": subtopic_id,
                "school_id": school_id,
            },
        )
        await self.db.commit()

        # Reload to get current state
        result = await self.db.execute(
            select(SubtopicCourseProgress).where(
                SubtopicCourseProgress.student_id == student_id,
                SubtopicCourseProgress.subtopic_id == subtopic_id,
            )
        )
        row = result.scalar_one()
        return CourseProgressItem(
            explanation_accessed=row.explanation_accessed,
            video_accessed=row.video_accessed,
            check_questions_score=row.check_questions_score,
            last_visited_at=row.last_visited_at,
        )

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------

    async def get_chat_history(
        self,
        student_id: uuid.UUID,
        subtopic_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> ChatHistoryResponse:
        """Return up to 50 chat messages for this student+subtopic, oldest first."""
        result = await self.db.execute(
            select(MiniCourseChatMessage)
            .where(
                MiniCourseChatMessage.student_id == student_id,
                MiniCourseChatMessage.subtopic_id == subtopic_id,
                MiniCourseChatMessage.school_id == school_id,
            )
            .order_by(MiniCourseChatMessage.created_at.asc())
            .limit(50)
        )
        rows = result.scalars().all()
        return ChatHistoryResponse(
            messages=[ChatMessageItem(role=row.role, content=row.content, created_at=row.created_at) for row in rows]
        )

    async def save_chat_message(
        self,
        student_id: uuid.UUID,
        subtopic_id: uuid.UUID,
        school_id: uuid.UUID,
        role: Literal["student", "ai"],
        content: str,
    ) -> MiniCourseChatMessage:
        """Persist one chat message and return the saved row."""
        msg = MiniCourseChatMessage(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            role=role,
            content=content,
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    # ------------------------------------------------------------------
    # Transfer question generation + AI grading
    # ------------------------------------------------------------------

    async def generate_transfer_question(
        self,
        subtopic_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> TransferQuestionResponse:
        """Generate a personalised open-ended transfer question via LLM.

        Uses the subtopic's learning_objective + keywords and the student's
        dominant modality + top interests. Falls back to a generic question
        if the LLM call fails or returns unparseable output.
        """
        # Load subtopic fields
        subtopic_result = await self.db.execute(
            select(
                Subtopic.name,
                Subtopic.learning_objective,
                Subtopic.keywords,
            ).where(Subtopic.id == subtopic_id, Subtopic.is_active.is_(True))
        )
        subtopic_row = subtopic_result.one_or_none()
        if subtopic_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtopic {subtopic_id} not found")

        # Load student profile for personalisation
        profile_result = await self.db.execute(
            select(StudentLearningProfile).where(
                StudentLearningProfile.student_id == student_id,
                StudentLearningProfile.completed_at.is_not(None),
            )
        )
        profile = profile_result.scalar_one_or_none()

        interests: list[str] = ((profile.interests or []) if profile else [])[:2]

        raw_modality = (profile.modality_scores if profile else None) or {}
        dominant_key: str = "visual"
        if isinstance(raw_modality, dict) and raw_modality:
            first_val = next(iter(raw_modality.values()), None)
            if isinstance(first_val, str):
                dominant_key = raw_modality.get("dominant", "visual")
            else:
                try:
                    scores = {k: float(v) for k, v in raw_modality.items() if v is not None and isinstance(k, str)}
                    dominant_key = max(scores, key=lambda k: scores.get(k, 0.0)) if scores else "visual"
                except (ValueError, TypeError):
                    pass
        dominant_modality = _MODALITY_LABELS.get(dominant_key, dominant_key)

        keywords: list[str] = subtopic_row.keywords or [] if subtopic_row.keywords else []

        template = _jinja_env.get_template("transfer_question.jinja2")
        prompt = template.render(
            subtopic_name=subtopic_row.name,
            learning_objective=subtopic_row.learning_objective,
            keywords=keywords,
            dominant_modality=dominant_modality,
            interests=interests,
        )

        try:
            raw = await llm_router.complete(
                task="transfer_question",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150,
            )
            question_text = raw.strip().strip('"').strip()
            if not question_text or len(question_text) < 10:
                question_text = _TRANSFER_QUESTION_FALLBACK
        except Exception:
            logger.warning(
                "transfer_question_generation_failed",
                subtopic_id=str(subtopic_id),
                student_id=str(student_id),
            )
            question_text = _TRANSFER_QUESTION_FALLBACK

        logger.info(
            "transfer_question_generated",
            subtopic_id=str(subtopic_id),
            student_id=str(student_id),
        )
        return TransferQuestionResponse(question_text=question_text)

    async def grade_open_answer(
        self,
        subtopic_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        question_text: str,
        student_answer: str,
    ) -> GradeAnswerResponse:
        """Grade a student's open-ended answer via LLM, persist the result, update course score.

        Returns grade ('correct'|'partial'|'incorrect'), feedback, score, and the
        updated check_questions_score aggregate for the course progress row.
        """
        # Load subtopic for context
        subtopic_result = await self.db.execute(
            select(Subtopic.name, Subtopic.learning_objective).where(
                Subtopic.id == subtopic_id, Subtopic.is_active.is_(True)
            )
        )
        subtopic_row = subtopic_result.one_or_none()
        if subtopic_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtopic {subtopic_id} not found")

        template = _jinja_env.get_template("grade_open_answer.jinja2")
        prompt = template.render(
            subtopic_name=subtopic_row.name,
            learning_objective=subtopic_row.learning_objective,
            question_text=question_text,
            student_answer=student_answer,
        )

        grade: Literal["correct", "partial", "incorrect"] = "incorrect"
        feedback = "We couldn't evaluate your answer. Please try again."

        try:
            raw = await llm_router.complete(
                task="grade_open_answer",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            parsed = json.loads(raw.strip())
            raw_grade = str(parsed.get("grade", "incorrect")).lower()
            if raw_grade in ("correct", "partial", "incorrect"):
                grade = cast(Literal["correct", "partial", "incorrect"], raw_grade)
            feedback = str(parsed.get("feedback", feedback))
        except Exception:
            logger.warning(
                "grade_open_answer_parse_failed",
                subtopic_id=str(subtopic_id),
                student_id=str(student_id),
            )

        score_map = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
        score = score_map[grade]

        # Persist the response row
        self.db.add(
            MiniCourseQuizResponse(
                student_id=student_id,
                subtopic_id=subtopic_id,
                school_id=school_id,
                question_type="open_ended",
                question_text=question_text,
                student_answer=student_answer,
                ai_grade=grade,
                ai_feedback=feedback,
                score=score,
            )
        )

        # Recompute aggregate course score (MCQ + open_ended combined)
        await self.db.flush()
        agg_result = await self.db.execute(
            select(func.avg(MiniCourseQuizResponse.score)).where(
                MiniCourseQuizResponse.student_id == student_id,
                MiniCourseQuizResponse.subtopic_id == subtopic_id,
            )
        )
        agg_score: float | None = agg_result.scalar_one_or_none()

        # Always upsert progress to record engagement. When agg_score is None
        # (edge case: flush didn't persist yet), GREATEST(existing, NULL) in
        # Postgres returns the existing value, so the score never regresses.
        await self.db.execute(
            text(
                """
                INSERT INTO subtopic_course_progress
                    (student_id, subtopic_id, school_id,
                     explanation_accessed, video_accessed,
                     check_questions_score, last_visited_at)
                VALUES
                    (:student_id, :subtopic_id, :school_id,
                     false, false, :score, now())
                ON CONFLICT (student_id, subtopic_id) DO UPDATE SET
                    check_questions_score = GREATEST(
                        subtopic_course_progress.check_questions_score,
                        EXCLUDED.check_questions_score
                    ),
                    last_visited_at = now()
                """
            ),
            {
                "student_id": student_id,
                "subtopic_id": subtopic_id,
                "school_id": school_id,
                "score": agg_score,
            },
        )

        await self.db.commit()

        logger.info(
            "open_answer_graded",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
            grade=grade,
            score=score,
        )

        return GradeAnswerResponse(
            grade=grade,
            feedback=feedback,
            score=score,
            updated_course_score=agg_score,
        )

    async def get_student_course_progress(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> StudentCourseProgressResponse:
        """Return mini-course progress for a student, scoped to the teacher's classes.

        Validates the student belongs to the school and only returns subtopics
        whose curriculum topic is assigned to one of this teacher's classes.
        Cross-school access raises HTTP 403.
        """
        from app.models.user import User, UserRole

        # Validate student exists in the caller's school
        student_result = await self.db.execute(
            select(User).where(
                User.id == student_id,
                User.role == UserRole.STUDENT,
                User.school_id == school_id,
            )
        )
        student = student_result.scalar_one_or_none()
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found in your school",
            )

        rows_result = await self.db.execute(
            select(
                SubtopicCourseProgress.subtopic_id,
                Subtopic.name.label("subtopic_name"),
                Topic.name.label("topic_name"),
                SubtopicCourseProgress.last_visited_at,
                SubtopicCourseProgress.explanation_accessed,
                SubtopicCourseProgress.video_accessed,
                SubtopicCourseProgress.check_questions_score,
            )
            .join(Subtopic, Subtopic.id == SubtopicCourseProgress.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .join(ClassTopic, ClassTopic.curriculum_topic_id == CurriculumTopic.id)
            .join(Class, Class.id == ClassTopic.class_id)
            .where(
                SubtopicCourseProgress.student_id == student_id,
                SubtopicCourseProgress.school_id == school_id,
                Class.teacher_id == teacher_id,
                Class.school_id == school_id,
            )
            .distinct()
            .order_by(SubtopicCourseProgress.last_visited_at.desc())
        )
        rows = rows_result.all()

        progress_items = [
            SubtopicProgressItem(
                subtopic_id=row.subtopic_id,
                subtopic_name=row.subtopic_name,
                topic_name=row.topic_name,
                last_visited_at=row.last_visited_at,
                explanation_accessed=row.explanation_accessed,
                video_accessed=row.video_accessed,
                check_questions_score=row.check_questions_score,
            )
            for row in rows
        ]

        logger.info(
            "teacher_student_course_progress_fetched",
            student_id=str(student_id),
            school_id=str(school_id),
            count=len(progress_items),
        )

        return StudentCourseProgressResponse(
            student_id=student_id,
            progress=progress_items,
        )

    # ------------------------------------------------------------------
    # Teacher: course-detail view (4-variant grid + student assignments)
    # ------------------------------------------------------------------

    async def get_course_detail_for_teacher(
        self,
        topic_id: uuid.UUID,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return full course detail for the teacher Course Detail page.

        Returns:
          {
            topic_name: str,
            subtopics: [
              {
                subtopic_id, subtopic_name, sequence_order,
                variants: {
                  <interest_category_name>: {
                    content_id, explanation_text, review_status, interest_label
                  } | null
                }
              }
            ],
            students: [
              {
                student_id, student_name, email,
                auto_interest_category: str | null,   -- from learning profile
                override_interest_category: str | null,  -- teacher-set
                effective_interest_category: str | null  -- override if set, else auto
              }
            ],
            interest_categories: [{id, name}]
          }
        """
        from app.models.school import Class, ClassEnrollment
        from app.models.user import User

        # Validate class belongs to this school
        class_result = await self.db.execute(select(Class).where(Class.id == class_id, Class.school_id == school_id))
        cls = class_result.scalar_one_or_none()
        if cls is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

        # Topic name
        topic_result = await self.db.execute(select(Topic.name).where(Topic.id == topic_id))
        topic_row = topic_result.first()
        if topic_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
        topic_name: str = topic_row.name

        # All interest categories
        cats_result = await self.db.execute(select(InterestCategory))
        all_categories = list(cats_result.scalars().all())
        cat_by_id = {cat.id: cat.name for cat in all_categories}
        cat_by_name = {cat.name: cat.id for cat in all_categories}

        # Human-readable labels per interest category name
        interest_labels: dict[str, str] = {
            "sports_movement": "Sports & Fitness",
            "tech_gaming": "Technology & Innovation",
            "nature_animals": "Nature & Science",
            "arts_culture": "Music & Arts",
        }

        # Subtopics for this topic
        subtopics_result = await self.db.execute(
            select(Subtopic)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(CurriculumTopic.topic_id == topic_id, Subtopic.is_active.is_(True))
            .order_by(Subtopic.sequence_order)
        )
        subtopics = list(subtopics_result.scalars().all())
        subtopic_ids = [s.id for s in subtopics]

        # All SubtopicContent for these subtopics (any review status, not archived)
        content_result = await self.db.execute(
            select(SubtopicContent).where(
                SubtopicContent.subtopic_id.in_(subtopic_ids),
                SubtopicContent.content_type == "explanation",
                SubtopicContent.is_archived.is_(False),
            )
        )
        all_content = list(content_result.scalars().all())

        # Index: subtopic_id → {category_name → SubtopicContent}
        content_index: dict[uuid.UUID, dict[str, SubtopicContent]] = {}
        for row in all_content:
            cat_name = cat_by_id.get(row.interest_category_id, "unknown") if row.interest_category_id else "unknown"
            content_index.setdefault(row.subtopic_id, {})[cat_name] = row

        subtopics_out = []
        for sub in subtopics:
            variants: dict[str, dict[str, str] | None] = {}
            for cat in all_categories:
                sc = content_index.get(sub.id, {}).get(cat.name)
                if sc is not None:
                    variants[cat.name] = {
                        "content_id": str(sc.id),
                        "explanation_text": sc.teacher_explanation or sc.explanation_text or "",
                        "review_status": sc.review_status,
                        "interest_label": interest_labels.get(cat.name, cat.name),
                    }
                else:
                    variants[cat.name] = None
            subtopics_out.append(
                {
                    "subtopic_id": str(sub.id),
                    "subtopic_name": sub.name,
                    "sequence_order": sub.sequence_order,
                    "variants": variants,
                }
            )

        # Enrolled students
        enrolled_result = await self.db.execute(
            select(ClassEnrollment.student_id).where(ClassEnrollment.class_id == class_id)
        )
        student_ids = [row[0] for row in enrolled_result.all()]

        students_out: list[dict[str, Any]] = []
        if student_ids:
            users_result = await self.db.execute(select(User).where(User.id.in_(student_ids)))
            users = {u.id: u for u in users_result.scalars().all()}

            profiles_result = await self.db.execute(
                select(StudentLearningProfile).where(StudentLearningProfile.student_id.in_(student_ids))
            )
            profiles = {p.student_id: p for p in profiles_result.scalars().all()}

            overrides_result = await self.db.execute(
                select(MiniCourseStudentOverride).where(
                    MiniCourseStudentOverride.topic_id == topic_id,
                    MiniCourseStudentOverride.school_id == school_id,
                    MiniCourseStudentOverride.student_id.in_(student_ids),
                )
            )
            overrides = {o.student_id: o for o in overrides_result.scalars().all()}

            for sid in student_ids:
                user = users.get(sid)
                if user is None:
                    continue

                # Auto interest from learning profile
                auto_category: str | None = None
                profile = profiles.get(sid)
                if profile and profile.interests:
                    cat_name_from_interest = INTEREST_KEY_TO_CATEGORY.get(profile.interests[0].lower())
                    if cat_name_from_interest and cat_name_from_interest in cat_by_name:
                        auto_category = cat_name_from_interest

                # Teacher override
                override_category: str | None = None
                override = overrides.get(sid)
                if override:
                    override_category = cat_by_id.get(override.interest_category_id)

                effective = override_category if override_category else auto_category

                students_out.append(
                    {
                        "student_id": str(sid),
                        "student_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
                        or user.username
                        or user.email
                        or "Unknown",
                        "email": user.email or "",
                        "auto_interest_category": auto_category,
                        "override_interest_category": override_category,
                        "effective_interest_category": effective,
                        "override_id": str(override.id) if override else None,
                    }
                )

        logger.info(
            "teacher_course_detail_fetched",
            topic_id=str(topic_id),
            class_id=str(class_id),
            subtopic_count=len(subtopics),
            student_count=len(students_out),
        )

        return {
            "topic_id": str(topic_id),
            "topic_name": topic_name,
            "subtopics": subtopics_out,
            "students": students_out,
            "interest_categories": [
                {"id": str(cat.id), "name": cat.name, "label": interest_labels.get(cat.name, cat.name)}
                for cat in all_categories
            ],
        }

    # ------------------------------------------------------------------
    # Teacher: set / clear student interest override
    # ------------------------------------------------------------------

    async def set_student_override(
        self,
        topic_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        interest_category_id: uuid.UUID | None,
    ) -> None:
        """Upsert or delete a teacher interest-category override for a student on a topic.

        If interest_category_id is None, deletes any existing override (clears back to auto).
        """
        existing_result = await self.db.execute(
            select(MiniCourseStudentOverride).where(
                MiniCourseStudentOverride.school_id == school_id,
                MiniCourseStudentOverride.topic_id == topic_id,
                MiniCourseStudentOverride.student_id == student_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if interest_category_id is None:
            # Clear override
            if existing is not None:
                await self.db.delete(existing)
                await self.db.commit()
                logger.info(
                    "mini_course_student_override_cleared",
                    topic_id=str(topic_id),
                    student_id=str(student_id),
                )
            return

        if existing is not None:
            existing.interest_category_id = interest_category_id
            existing.set_by_teacher_id = teacher_id
        else:
            override = MiniCourseStudentOverride(
                school_id=school_id,
                topic_id=topic_id,
                student_id=student_id,
                interest_category_id=interest_category_id,
                set_by_teacher_id=teacher_id,
            )
            self.db.add(override)

        await self.db.commit()
        logger.info(
            "mini_course_student_override_set",
            topic_id=str(topic_id),
            student_id=str(student_id),
            interest_category_id=str(interest_category_id),
        )
