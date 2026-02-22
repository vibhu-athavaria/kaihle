"""
Diagnostic Response Handler Service.

This service handles answer submission, evaluation, scoring, and
triggers the Celery chain for report generation when all assessments complete.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    AssessmentType,
    QuestionBank,
)
from app.models.user import StudentProfile
from app.services.diagnostic.session_manager import DiagnosticSessionManager

logger = logging.getLogger(__name__)

# Redis key for generation status
REDIS_GENERATION_KEY_PREFIX = "kaihle:diagnostic:generating"
REDIS_GENERATION_TTL = 2 * 60 * 60  # 2 hours


class AnswerResult:
    """Result of an answer submission."""

    def __init__(
        self,
        is_correct: bool,
        score: float,
        difficulty_level: int,
        next_difficulty: int,
        questions_answered: int,
        total_questions: int,
        subtopic_complete: bool,
        assessment_status: str,
        all_subjects_complete: bool,
    ):
        self.is_correct = is_correct
        self.score = score
        self.difficulty_level = difficulty_level
        self.next_difficulty = next_difficulty
        self.questions_answered = questions_answered
        self.total_questions = total_questions
        self.subtopic_complete = subtopic_complete
        self.assessment_status = assessment_status
        self.all_subjects_complete = all_subjects_complete

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "is_correct": self.is_correct,
            "score": self.score,
            "difficulty_level": self.difficulty_level,
            "next_difficulty": self.next_difficulty,
            "questions_answered": self.questions_answered,
            "total_questions": self.total_questions,
            "subtopic_complete": self.subtopic_complete,
            "assessment_status": self.assessment_status,
            "all_subjects_complete": self.all_subjects_complete,
        }


class DiagnosticResponseHandler:
    """
    Handles answer submission for diagnostic assessments.

    Full pipeline:
    1. Load session state from Redis
    2. Validate: status not COMPLETED, question_bank_id == current_question_bank_id
    3. Load AssessmentQuestion row (must exist, must be unanswered)
    4. Evaluate correctness
    5. Calculate score = (difficulty_level / 5.0) if correct else 0.0
    6. Update AssessmentQuestion: student_answer, is_correct, score, time_taken, answered_at
    7. Call session_manager.record_answer_and_advance
    8. Update Assessment.questions_answered + status in DB
    9. Check all-subjects completion
    10. Return AnswerResult
    """

    def __init__(self, db: Session, redis_client=None):
        """
        Initialize the response handler.

        Args:
            db: SQLAlchemy database session
            redis_client: Optional Redis client for generation flags
        """
        self.db = db
        self.redis = redis_client
        self.session_manager = DiagnosticSessionManager(db, redis_client)

    def evaluate_answer(self, question: QuestionBank, student_answer: str) -> bool:
        """
        Evaluate if the student's answer is correct.

        Case-insensitive exact match on correct_answer field.

        Args:
            question: The QuestionBank object
            student_answer: The student's answer string

        Returns:
            True if correct, False otherwise
        """
        if not question.correct_answer or not student_answer:
            return False

        return (
            question.correct_answer.strip().lower()
            == student_answer.strip().lower()
        )

    def calculate_score(self, is_correct: bool, difficulty_level: int) -> float:
        """
        Calculate the score for an answer.

        Score = (difficulty_level / 5.0) if is_correct else 0.0
        difficulty_level is Integer 1-5.
        Range: 0.0 to 1.0

        Args:
            is_correct: Whether the answer was correct
            difficulty_level: The difficulty level of the question (1-5)

        Returns:
            Score as a float between 0.0 and 1.0
        """
        if not is_correct:
            return 0.0

        # Ensure difficulty is in valid range
        difficulty_level = max(1, min(5, difficulty_level))
        return difficulty_level / 5.0

    def submit_answer(
        self,
        assessment_id: UUID,
        question_bank_id: UUID,
        student_answer: str,
        time_taken_seconds: Optional[int] = None,
    ) -> AnswerResult:
        """
        Submit an answer for a diagnostic assessment question.

        Full pipeline:
        1. Load session state from Redis
        2. Validate: status not COMPLETED, question_bank_id == current_question_bank_id
        3. Load AssessmentQuestion row (must exist, must be unanswered)
        4. Evaluate correctness
        5. Calculate score
        6. Update AssessmentQuestion
        7. Call session_manager.record_answer_and_advance
        8. Check all-subjects completion
        9. Return AnswerResult

        Args:
            assessment_id: UUID of the assessment
            question_bank_id: UUID of the question being answered
            student_answer: The student's answer
            time_taken_seconds: Optional time taken to answer

        Returns:
            AnswerResult with submission details

        Raises:
            ValueError: If validation fails
        """
        # Get session state
        state = self.session_manager.get_session_state(assessment_id)

        # Validate: status not COMPLETED
        if state.get("status") == AssessmentStatus.COMPLETED.value:
            raise ValueError(
                f"Assessment {assessment_id} is already completed. "
                "Cannot submit more answers."
            )

        # Validate: question_bank_id == current_question_bank_id
        current_question_id = state.get("current_question_bank_id")
        if current_question_id != question_bank_id:
            raise ValueError(
                f"Question {question_bank_id} is not the current question. "
                f"Current question is {current_question_id}"
            )

        # Load AssessmentQuestion
        assessment_question = self.db.query(AssessmentQuestion).filter(
            AssessmentQuestion.assessment_id == assessment_id,
            AssessmentQuestion.question_bank_id == question_bank_id,
        ).first()

        if not assessment_question:
            raise ValueError(
                f"AssessmentQuestion not found for assessment {assessment_id}, "
                f"question {question_bank_id}"
            )

        # Validate: must be unanswered
        if assessment_question.is_correct is not None:
            raise ValueError(
                f"Question {question_bank_id} has already been answered."
            )

        # Load QuestionBank to get correct_answer and difficulty
        question = self.db.query(QuestionBank).filter(
            QuestionBank.id == question_bank_id
        ).first()

        if not question:
            raise ValueError(f"QuestionBank not found: {question_bank_id}")

        # Evaluate correctness
        is_correct = self.evaluate_answer(question, student_answer)

        # Calculate score
        score = self.calculate_score(is_correct, question.difficulty_level)

        # Get current difficulty from state for the answer result
        subtopics = state.get("subtopics", [])
        current_index = state.get("current_subtopic_index", 0)
        current_difficulty = (
            subtopics[current_index].get("current_difficulty", 3)
            if current_index < len(subtopics)
            else 3
        )

        # Record answer and advance session
        updated_state = self.session_manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_bank_id,
            is_correct=is_correct,
            student_answer=student_answer,
            time_taken=time_taken_seconds,
        )

        # Get next difficulty from updated state
        next_difficulty = current_difficulty
        if is_correct:
            next_difficulty = min(5, current_difficulty + 1)
        else:
            next_difficulty = max(1, current_difficulty - 1)

        # Check if subtopic is complete using updated state
        subtopic_complete = False
        updated_subtopics = updated_state.get("subtopics", [])
        if current_index < len(updated_subtopics):
            updated_subtopic = updated_subtopics[current_index]
            questions_answered = updated_subtopic.get("questions_answered", 0)
            questions_total = updated_subtopic.get("questions_total", 5)
            subtopic_complete = questions_answered >= questions_total

        # Check if all subjects are complete
        all_subjects_complete = False
        if updated_state.get("status") == AssessmentStatus.COMPLETED.value:
            all_subjects_complete = self.check_all_subjects_complete(
                state.get("student_id")
            )

        return AnswerResult(
            is_correct=is_correct,
            score=score,
            difficulty_level=current_difficulty,
            next_difficulty=next_difficulty,
            questions_answered=updated_state.get("answered_count", 0),
            total_questions=updated_state.get("total_questions", 0),
            subtopic_complete=subtopic_complete,
            assessment_status=updated_state.get("status", AssessmentStatus.IN_PROGRESS.value),
            all_subjects_complete=all_subjects_complete,
        )

    def check_all_subjects_complete(self, student_id: UUID) -> bool:
        """
        Check if all 4 subject assessments are COMPLETED.

        If True (and not already triggered):
        1. Set StudentProfile.has_completed_assessment = True
        2. Set Redis flag: kaihle:diagnostic:generating:{student_id} = "reports"
        3. Dispatch Celery chain: generate_reports.s() | generate_study_plan.s()

        Guard: check Redis flag before dispatching to prevent double-trigger.

        Args:
            student_id: UUID of the student

        Returns:
            True if all 4 assessments are complete, False otherwise
        """
        # Get all diagnostic assessments for this student
        assessments = self.db.query(Assessment).filter(
            Assessment.student_id == student_id,
            Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
        ).all()

        # Must have exactly 4 assessments (one per subject)
        if len(assessments) != 4:
            return False

        # All must be COMPLETED
        all_complete = all(
            a.status == AssessmentStatus.COMPLETED
            for a in assessments
        )

        if not all_complete:
            return False

        # Check Redis guard to prevent double-trigger
        if self.redis:
            generation_key = f"{REDIS_GENERATION_KEY_PREFIX}:{student_id}"
            existing_flag = self.redis.get(generation_key)
            if existing_flag:
                logger.info(
                    "Generation already in progress for student %s: %s",
                    student_id, existing_flag
                )
                return True

        # Update StudentProfile
        student = self.db.query(StudentProfile).filter(
            StudentProfile.id == student_id
        ).first()

        if student and not student.has_completed_assessment:
            student.has_completed_assessment = True
            self.db.commit()
            logger.info(
                "Set has_completed_assessment=True for student %s",
                student_id
            )

        # Set Redis flag and dispatch Celery chain
        if self.redis:
            generation_key = f"{REDIS_GENERATION_KEY_PREFIX}:{student_id}"
            self.redis.setex(
                generation_key,
                REDIS_GENERATION_TTL,
                "reports"
            )
            logger.info(
                "Set generation flag 'reports' for student %s",
                student_id
            )

            # Dispatch Celery chain for report and study plan generation
            # This will be implemented in Phase 5 & 6
            # For now, we just set the flag
            # from celery import chain as celery_chain
            # from app.worker.tasks.report_generation import generate_assessment_reports
            # from app.worker.tasks.study_plan import generate_study_plan
            # celery_chain(
            #     generate_assessment_reports.s(str(student_id)),
            #     generate_study_plan.s()
            # ).delay()

        return True
