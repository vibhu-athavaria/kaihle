"""
Adaptive Diagnostic Question Selector Service.

This service handles question selection for diagnostic assessments,
implementing the fallback chain for difficulty selection and
subtopic retrieval for sessions.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.models.assessment import QuestionBank
from app.models.curriculum import CurriculumTopic, Subtopic
from app.core.config import settings

logger = logging.getLogger(__name__)


class AdaptiveDiagnosticSelector:
    """
    Handles adaptive question selection for diagnostic assessments.

    Implements the fallback chain for difficulty selection:
    1. Exact target_difficulty, not in used_question_ids, RANDOM()
    2. target_difficulty + 1 (if < 5)
    3. target_difficulty - 1 (if > 1)
    4. Any difficulty, not in used_question_ids
    5. Return None (subtopic exhausted)
    """

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.questions_per_subtopic = settings.DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC
        self.starting_difficulty = settings.DIAGNOSTIC_STARTING_DIFFICULTY

    def get_next_question(
        self,
        subtopic_id: UUID,
        grade_id: UUID,
        subject_id: UUID,
        target_difficulty: int,
        used_question_ids: List[UUID],
    ) -> Optional[QuestionBank]:
        """
        Select the next question for a diagnostic assessment.

        Uses a fallback chain to find an appropriate question:
        1. Exact target_difficulty, not in used_question_ids, RANDOM()
        2. target_difficulty + 1 (if < 5)
        3. target_difficulty - 1 (if > 1)
        4. Any difficulty, not in used_question_ids
        5. Return None (subtopic exhausted)

        Args:
            subtopic_id: UUID of the subtopic to select questions from
            grade_id: UUID of the grade level
            subject_id: UUID of the subject
            target_difficulty: Integer 1-5 for target difficulty level
            used_question_ids: List of question IDs already used in this session

        Returns:
            QuestionBank object if found, None if subtopic is exhausted

        Raises:
            ValueError: If target_difficulty is not in valid range 1-5
        """
        # Validate difficulty is in range 1-5
        if not 1 <= target_difficulty <= 5:
            raise ValueError(f"target_difficulty must be between 1 and 5, got {target_difficulty}")

        # Clamp difficulty to valid range (defensive)
        target_difficulty = max(1, min(5, target_difficulty))

        # Build base query conditions
        base_conditions = [
            QuestionBank.subtopic_id == subtopic_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.is_active == True,
        ]

        # Add grade filter if provided
        if grade_id is not None:
            base_conditions.append(QuestionBank.grade_id == grade_id)

        # Exclude used questions
        if used_question_ids:
            base_conditions.append(QuestionBank.id.notin_(used_question_ids))

        # Fallback chain: try each difficulty level in order
        difficulty_order = self._build_difficulty_fallback_order(target_difficulty)

        for difficulty in difficulty_order:
            question = self._try_select_question(base_conditions, difficulty)
            if question:
                logger.info(
                    "Selected question for subtopic %s at difficulty %d (target was %d)",
                    subtopic_id, difficulty, target_difficulty
                )
                return question

        # Final fallback: any difficulty (already filtered by used_question_ids)
        question = self._try_select_question(base_conditions, None)
        if question:
            logger.info(
                "Selected question for subtopic %s at any difficulty (fallback)",
                subtopic_id
            )
            return question

        logger.warning("No more questions available for subtopic %s", subtopic_id)
        return None

    def _build_difficulty_fallback_order(self, target: int) -> List[int]:
        """
        Build the fallback order for difficulty selection.

        Order: target, target+1 (if valid), target-1 (if valid)

        Args:
            target: Target difficulty (1-5)

        Returns:
            List of difficulty levels to try in order
        """
        order = [target]

        # Try higher difficulty first (if not at max)
        if target < 5:
            order.append(target + 1)

        # Then try lower difficulty (if not at min)
        if target > 1:
            order.append(target - 1)

        return order

    def _try_select_question(
        self,
        base_conditions: List,
        difficulty: Optional[int]
    ) -> Optional[QuestionBank]:
        """
        Attempt to select a question with the given conditions.

        Args:
            base_conditions: List of SQLAlchemy filter conditions
            difficulty: Specific difficulty to filter for, or None for any

        Returns:
            QuestionBank object if found, None otherwise
        """
        try:
            query = self.db.query(QuestionBank).filter(and_(*base_conditions))

            if difficulty is not None:
                query = query.filter(QuestionBank.difficulty_level == difficulty)

            # Order by random and limit to 1
            question = query.order_by(func.random()).first()

            return question

        except SQLAlchemyError as e:
            logger.error("Database error selecting question: %s", str(e))
            return None

    def get_subtopics_for_session(
        self,
        curriculum_id: UUID,
        grade_id: UUID,
        subject_id: UUID,
    ) -> List[Subtopic]:
        """
        Get active subtopics for a diagnostic session.

        Returns subtopics ordered by CurriculumTopic.sequence_order
        via: CurriculumTopic → Subtopic join.

        Args:
            curriculum_id: UUID of the curriculum
            grade_id: UUID of the grade level
            subject_id: UUID of the subject

        Returns:
            List of Subtopic objects ordered by sequence_order
        """
        try:
            subtopics = (
                self.db.query(Subtopic)
                .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
                .filter(
                    CurriculumTopic.curriculum_id == curriculum_id,
                    CurriculumTopic.grade_id == grade_id,
                    CurriculumTopic.subject_id == subject_id,
                    CurriculumTopic.is_active == True,
                    Subtopic.is_active == True,
                )
                .options(joinedload(Subtopic.curriculum_topic))
                .order_by(CurriculumTopic.sequence_order, Subtopic.sequence_order)
                .all()
            )

            logger.info(
                "Found %d subtopics for curriculum %s, grade %s, subject %s",
                len(subtopics), curriculum_id, grade_id, subject_id
            )

            return list(subtopics)

        except SQLAlchemyError as e:
            logger.error("Database error fetching subtopics: %s", str(e))
            return []

    def count_available_questions(
        self,
        subtopic_id: UUID,
        grade_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
    ) -> int:
        """
        Count available questions for a subtopic.

        Args:
            subtopic_id: UUID of the subtopic
            grade_id: Optional UUID of the grade level
            subject_id: Optional UUID of the subject

        Returns:
            Count of active questions matching the criteria
        """
        try:
            query = self.db.query(func.count(QuestionBank.id)).filter(
                QuestionBank.subtopic_id == subtopic_id,
                QuestionBank.is_active == True,
            )

            if grade_id:
                query = query.filter(QuestionBank.grade_id == grade_id)

            if subject_id:
                query = query.filter(QuestionBank.subject_id == subject_id)

            count = query.scalar() or 0
            return count

        except SQLAlchemyError as e:
            logger.error("Database error counting questions: %s", str(e))
            return 0
