"""Mini-course service.

Handles student mini-course delivery: interest-matched explanation,
approved video, check questions, and progress tracking.

All business logic lives here — route handlers are thin wrappers.
"""

import uuid
from typing import Literal

import structlog
from fastapi import HTTPException, status
from sqlalchemy import case, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.questionnaire_config import INTEREST_KEY_TO_CATEGORY
from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, Topic
from app.models.interest_category import InterestCategory
from app.models.mini_course import SubtopicContentFeedback, SubtopicCourseProgress
from app.models.onboarding import StudentLearningProfile
from app.models.subtopic_content import SubtopicContent
from app.schemas.mini_course import (
    CheckQuestion,
    CheckQuestionOption,
    CourseProgressItem,
    MarkProgressRequest,
    StudentCourseProgressResponse,
    SubtopicCourseResponse,
    SubtopicExplanationItem,
    SubtopicProgressItem,
    SubtopicVideoItem,
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
        # 1. Resolve subtopic + topic name
        subtopic_row = await self.db.execute(
            select(
                Subtopic.id,
                Subtopic.name.label("subtopic_name"),
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

        logger.debug(
            "mini_course_fetch_started",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
        )

        # 2. Load student's interest category id
        interest_category_id: uuid.UUID | None = await self._resolve_student_interest_category_id(student_id=student_id)

        # 3. Fetch best approved explanation
        explanation_content = await self._fetch_best_explanation(
            subtopic_id=subtopic_id,
            interest_category_id=interest_category_id,
        )

        # 4. Fetch best approved video
        video_content = await self._fetch_approved_video(subtopic_id=subtopic_id)

        # 5. Fetch check questions (random sample)
        check_questions = await self._fetch_check_questions(subtopic_id=subtopic_id)

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

        # 8. Assemble video schema
        video_item: SubtopicVideoItem | None = None
        if video_content is not None:
            video_item = SubtopicVideoItem(
                video_url=video_content.video_url or "",
                thumbnail_url=video_content.video_thumbnail_url,
                duration_seconds=video_content.video_duration_seconds,
            )

        content_status: Literal["ready", "unavailable"] = "ready" if explanation_item is not None else "unavailable"

        return SubtopicCourseResponse(
            subtopic_id=subtopic_id,
            subtopic_name=subtopic_name,
            topic_name=topic_name,
            explanation=explanation_item,
            content_status=content_status,
            video=video_item,
            check_questions=check_questions,
            progress=progress,
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
                func.count().filter(SubtopicContentFeedback.feedback_type == "thumbs_up").label("up_count"),
                func.count().filter(SubtopicContentFeedback.feedback_type == "thumbs_down").label("down_count"),
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

    async def _resolve_student_interest_category_id(self, student_id: uuid.UUID) -> uuid.UUID | None:
        """Return the interest_category_id for the student's first interest, or None."""
        profile_result = await self.db.execute(
            select(StudentLearningProfile.interests).where(StudentLearningProfile.student_id == student_id)
        )
        profile_row = profile_result.one_or_none()
        if profile_row is None or not profile_row.interests:
            return None

        first_interest: str = profile_row.interests[0]
        category_name = INTEREST_KEY_TO_CATEGORY.get(first_interest.lower())
        if category_name is None:
            return None

        cat_result = await self.db.execute(select(InterestCategory.id).where(InterestCategory.name == category_name))
        cat_row = cat_result.one_or_none()
        return cat_row.id if cat_row is not None else None

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

    async def _fetch_check_questions(self, subtopic_id: uuid.UUID) -> list[CheckQuestion]:
        """Return up to 3 random active questions from question_bank for subtopic."""
        result = await self.db.execute(
            select(QuestionBank)
            .where(
                QuestionBank.subtopic_id == subtopic_id,
                QuestionBank.is_active.is_(True),
            )
            .order_by(func.random())
            .limit(_CHECK_QUESTION_LIMIT)
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

    async def get_student_course_progress(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> StudentCourseProgressResponse:
        """Return all mini-course progress rows for a student, ordered by last_visited_at DESC.

        Validates that the student belongs to the given school before querying.
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
            .where(
                SubtopicCourseProgress.student_id == student_id,
                SubtopicCourseProgress.school_id == school_id,
            )
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
