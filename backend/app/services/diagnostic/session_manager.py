"""
Diagnostic Session Manager Service.

This service manages the state machine for diagnostic assessments,
including session initialization, question delivery, answer recording,
and session state management via Redis.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

import redis
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    AssessmentType,
    QuestionBank,
)
from app.models.curriculum import CurriculumTopic, Subtopic
from app.models.user import StudentProfile
from app.models.subject import Subject
from app.core.config import settings
from .question_selector import AdaptiveDiagnosticSelector

logger = logging.getLogger(__name__)


# Redis key format: kaihle:diagnostic:session:{assessment_id}
REDIS_KEY_PREFIX = "kaihle:diagnostic:session"
REDIS_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def get_redis_client() -> redis.Redis:
    """Get Redis client from environment configuration."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


class DiagnosticSessionManager:
    """
    Manages diagnostic assessment sessions.

    This class implements the state machine for diagnostic assessments:
    - STARTED → IN_PROGRESS (first answer received)
    - IN_PROGRESS → COMPLETED (final question answered)
    - IN_PROGRESS → ABANDONED (explicit abandon or future timeout)

    Session state is cached in Redis with 24-hour TTL.
    """

    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the session manager.

        Args:
            db: SQLAlchemy database session
            redis_client: Optional Redis client (will create one if not provided)
        """
        self.db = db
        self.redis = redis_client or get_redis_client()
        self.selector = AdaptiveDiagnosticSelector(db)
        self.questions_per_subtopic = settings.DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC
        self.starting_difficulty = settings.DIAGNOSTIC_STARTING_DIFFICULTY

    def _get_redis_key(self, assessment_id: UUID) -> str:
        """Generate Redis key for an assessment session."""
        return f"{REDIS_KEY_PREFIX}:{assessment_id}"

    def _serialize_session_state(self, state: Dict) -> str:
        """Serialize session state to JSON string for Redis."""
        # Convert UUIDs to strings for JSON serialization
        serializable_state = self._convert_uuids_to_strings(state)
        return json.dumps(serializable_state)

    def _deserialize_session_state(self, data: str) -> Dict:
        """Deserialize session state from Redis JSON string."""
        state = json.loads(data)
        return self._convert_strings_to_uuids(state)

    def _convert_uuids_to_strings(self, obj: Any) -> Any:
        """Recursively convert UUIDs to strings in a data structure."""
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_uuids_to_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_uuids_to_strings(item) for item in obj]
        return obj

    def _convert_strings_to_uuids(self, obj: Any) -> Any:
        """Recursively convert UUID strings back to UUIDs in a data structure."""
        if isinstance(obj, str):
            # Try to parse as UUID
            try:
                return UUID(obj)
            except ValueError:
                return obj
        elif isinstance(obj, dict):
            return {k: self._convert_strings_to_uuids(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_strings_to_uuids(item) for item in obj]
        return obj

    def _save_session_state(self, assessment_id: UUID, state: Dict) -> None:
        """Save session state to Redis with TTL."""
        key = self._get_redis_key(assessment_id)
        data = self._serialize_session_state(state)
        self.redis.setex(key, REDIS_TTL_SECONDS, data)
        logger.debug("Saved session state for assessment %s to Redis", assessment_id)

    def _get_session_state_from_redis(self, assessment_id: UUID) -> Optional[Dict]:
        """Get session state from Redis."""
        key = self._get_redis_key(assessment_id)
        data = self.redis.get(key)
        if data:
            return self._deserialize_session_state(data.decode('utf-8'))
        return None

    def _delete_session_state(self, assessment_id: UUID) -> None:
        """Delete session state from Redis."""
        key = self._get_redis_key(assessment_id)
        self.redis.delete(key)
        logger.debug("Deleted session state for assessment %s from Redis", assessment_id)

    def initialize_diagnostic(
        self,
        student_id: UUID
    ) -> Dict[str, Any]:
        """
        Initialize diagnostic assessments for a student.

        Idempotent: If diagnostics already exist, returns existing sessions.

        Steps:
        1. Verify student profile has grade_id and curriculum_id
        2. For each subject: create Assessment(type=DIAGNOSTIC, status=STARTED)
        3. Load subtopics for each subject
        4. Cache session state in Redis (no questions selected yet)
        5. Return session summaries

        Args:
            student_id: UUID of the student

        Returns:
            Dict containing:
            - sessions: List of session summaries (one per subject)
            - student_id: UUID of the student
            - grade_id: UUID of the student's grade
            - curriculum_id: UUID of the student's curriculum

        Raises:
            ValueError: If student profile is incomplete
        """
        # Get student profile
        student = self.db.query(StudentProfile).filter(
            StudentProfile.id == student_id
        ).first()

        if not student:
            raise ValueError(f"Student profile not found: {student_id}")

        if not student.grade_id:
            raise ValueError(f"Student profile missing grade_id: {student_id}")

        if not student.curriculum_id:
            raise ValueError(f"Student profile missing curriculum_id: {student_id}")

        # Check for existing diagnostic assessments
        existing_assessments = self.db.query(Assessment).filter(
            Assessment.student_id == student_id,
            Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
            Assessment.status.in_([
                AssessmentStatus.STARTED,
                AssessmentStatus.IN_PROGRESS
            ])
        ).all()

        if existing_assessments:
            # Return existing sessions
            logger.info(
                "Found %d existing diagnostic sessions for student %s",
                len(existing_assessments), student_id
            )
            sessions = []
            for assessment in existing_assessments:
                state = self.get_session_state(assessment.id)
                sessions.append(self._build_session_summary(assessment, state))

            return {
                "sessions": sessions,
                "student_id": student_id,
                "grade_id": student.grade_id,
                "curriculum_id": student.curriculum_id,
                "existing": True
            }

        # Get all subjects for the curriculum
        subjects = self._get_subjects_for_curriculum(student.curriculum_id)

        if not subjects:
            raise ValueError(
                f"No subjects found for curriculum {student.curriculum_id}"
            )

        # Create assessments for each subject
        created_sessions = []

        for subject in subjects:
            # Create assessment
            assessment = Assessment(
                student_id=student_id,
                subject_id=subject.id,
                assessment_type=AssessmentType.DIAGNOSTIC,
                status=AssessmentStatus.STARTED,
                difficulty_level=self.starting_difficulty,
            )
            self.db.add(assessment)
            self.db.flush()  # Get the ID

            # Get subtopics for this subject
            subtopics = self.selector.get_subtopics_for_session(
                curriculum_id=student.curriculum_id,
                grade_id=student.grade_id,
                subject_id=subject.id,
            )

            # Build initial session state
            state = self._build_initial_session_state(
                assessment=assessment,
                student_id=student_id,
                subject_id=subject.id,
                subtopics=subtopics,
            )

            # Save to Redis
            self._save_session_state(assessment.id, state)

            created_sessions.append(self._build_session_summary(assessment, state))

            logger.info(
                "Created diagnostic assessment %s for student %s, subject %s",
                assessment.id, student_id, subject.id
            )

        self.db.commit()

        return {
            "sessions": created_sessions,
            "student_id": student_id,
            "grade_id": student.grade_id,
            "curriculum_id": student.curriculum_id,
            "existing": False
        }

    def _get_subjects_for_curriculum(self, curriculum_id: UUID) -> List[Subject]:
        """Get all subjects for a curriculum."""
        from app.models.curriculum import CurriculumSubject

        subjects = (
            self.db.query(Subject)
            .join(CurriculumSubject, Subject.id == CurriculumSubject.subject_id)
            .filter(CurriculumSubject.curriculum_id == curriculum_id)
            .order_by(CurriculumSubject.sort_order)
            .all()
        )
        return list(subjects)

    def _build_initial_session_state(
        self,
        assessment: Assessment,
        student_id: UUID,
        subject_id: UUID,
        subtopics: List[Subtopic],
    ) -> Dict:
        """
        Build the initial session state for a new diagnostic assessment.

        Args:
            assessment: The Assessment model instance
            student_id: UUID of the student
            subject_id: UUID of the subject
            subtopics: List of Subtopic objects for this subject

        Returns:
            Dict containing the initial session state
        """
        now = datetime.now(timezone.utc).isoformat()

        subtopic_states = []
        total_questions = 0

        for subtopic in subtopics:
            subtopic_state = {
                "subtopic_id": subtopic.id,
                "subtopic_name": subtopic.name,
                "questions_total": self.questions_per_subtopic,
                "questions_answered": 0,
                "current_difficulty": self.starting_difficulty,
                "used_question_ids": [],
            }
            subtopic_states.append(subtopic_state)
            total_questions += self.questions_per_subtopic

        return {
            "assessment_id": assessment.id,
            "student_id": student_id,
            "subject_id": subject_id,
            "status": AssessmentStatus.STARTED.value,
            "subtopics": subtopic_states,
            "current_subtopic_index": 0,
            "current_question_bank_id": None,
            "total_questions": total_questions,
            "answered_count": 0,
            "started_at": now,
            "last_activity": now,
        }

    def _build_session_summary(
        self,
        assessment: Assessment,
        state: Dict
    ) -> Dict:
        """Build a session summary for API responses."""
        return {
            "assessment_id": assessment.id,
            "subject_id": assessment.subject_id,
            "status": state.get("status", assessment.status.value),
            "total_questions": state.get("total_questions", 0),
            "answered_count": state.get("answered_count", 0),
            "current_subtopic_index": state.get("current_subtopic_index", 0),
            "subtopics_count": len(state.get("subtopics", [])),
            "started_at": state.get("started_at"),
            "last_activity": state.get("last_activity"),
        }

    def get_current_question(
        self,
        assessment_id: UUID
    ) -> Tuple[Optional[QuestionBank], Dict]:
        """
        Get the current question for an assessment.

        If no current_question_bank_id in state:
        - Selects first question for current subtopic at starting difficulty
        - Creates AssessmentQuestion row (unanswered)
        - Updates session state current_question_bank_id in Redis

        Args:
            assessment_id: UUID of the assessment

        Returns:
            Tuple of (QuestionBank or None, session_state)
            Returns (None, state) if session is complete.

        Raises:
            ValueError: If assessment not found or invalid state
        """
        # Get assessment with student relationship eagerly loaded
        assessment = self.db.query(Assessment).options(
            joinedload(Assessment.student)
        ).filter(
            Assessment.id == assessment_id
        ).first()

        if not assessment:
            raise ValueError(f"Assessment not found: {assessment_id}")

        if not assessment.student:
            raise ValueError(
                f"Assessment {assessment_id} has no associated student. "
                "Data integrity error."
            )

        # Get session state
        state = self.get_session_state(assessment_id)

        # Check if already complete
        if state.get("status") == AssessmentStatus.COMPLETED.value:
            return None, state

        # Check if we already have a current question
        current_question_id = state.get("current_question_bank_id")

        if current_question_id:
            # Return the existing current question
            question = self.db.query(QuestionBank).filter(
                QuestionBank.id == current_question_id
            ).first()
            return question, state

        # Need to select a new question
        subtopics = state.get("subtopics", [])
        current_index = state.get("current_subtopic_index", 0)

        if current_index >= len(subtopics):
            # All subtopics complete
            state["status"] = AssessmentStatus.COMPLETED.value
            self._save_session_state(assessment_id, state)
            self._update_assessment_status(assessment_id, AssessmentStatus.COMPLETED)
            return None, state

        current_subtopic = subtopics[current_index]

        # Select next question
        question = self.selector.get_next_question(
            subtopic_id=current_subtopic["subtopic_id"],
            grade_id=assessment.student.grade_id,
            subject_id=state["subject_id"],
            target_difficulty=current_subtopic["current_difficulty"],
            used_question_ids=current_subtopic["used_question_ids"],
        )

        if not question:
            # No more questions for this subtopic, advance to next
            state["current_subtopic_index"] = current_index + 1
            self._save_session_state(assessment_id, state)
            return self.get_current_question(assessment_id)

        # Create AssessmentQuestion row
        question_number = state.get("answered_count", 0) + 1
        assessment_question = AssessmentQuestion(
            assessment_id=assessment_id,
            question_bank_id=question.id,
            question_number=question_number,
        )
        self.db.add(assessment_question)
        self.db.commit()

        # Update state with current question
        state["current_question_bank_id"] = question.id
        state["last_activity"] = datetime.now(timezone.utc).isoformat()
        self._save_session_state(assessment_id, state)

        return question, state

    def record_answer_and_advance(
        self,
        assessment_id: UUID,
        question_bank_id: UUID,
        is_correct: bool,
        student_answer: Optional[str] = None,
        time_taken: Optional[int] = None,
    ) -> Dict:
        """
        Record an answer and advance the session state.

        Steps:
        1. Add question_bank_id to subtopic.used_question_ids
        2. Increment subtopic.questions_answered
        3. Adjust subtopic.current_difficulty (±1, clamped 1-5)
        4. Clear current_question_bank_id
        5. If subtopic complete → increment current_subtopic_index
        6. If all subtopics complete → set status = completed
        7. Save to Redis + DB (Assessment.questions_answered, Assessment.status)
        8. Return updated state

        Args:
            assessment_id: UUID of the assessment
            question_bank_id: UUID of the question that was answered
            is_correct: Whether the answer was correct
            student_answer: Optional student's answer text
            time_taken: Optional time taken in seconds

        Returns:
            Updated session state dict

        Raises:
            ValueError: If assessment, question, or state is invalid
        """
        # Get assessment
        assessment = self.db.query(Assessment).filter(
            Assessment.id == assessment_id
        ).first()

        if not assessment:
            raise ValueError(f"Assessment not found: {assessment_id}")

        # Get session state
        state = self.get_session_state(assessment_id)

        # Verify this is the current question
        current_question_id = state.get("current_question_bank_id")
        if current_question_id != question_bank_id:
            raise ValueError(
                f"Question {question_bank_id} is not the current question. "
                f"Current question is {current_question_id}"
            )

        # Get current subtopic
        subtopics = state.get("subtopics", [])
        current_index = state.get("current_subtopic_index", 0)

        if current_index >= len(subtopics):
            raise ValueError("No more subtopics to answer")

        current_subtopic = subtopics[current_index]

        # Update AssessmentQuestion
        assessment_question = self.db.query(AssessmentQuestion).filter(
            AssessmentQuestion.assessment_id == assessment_id,
            AssessmentQuestion.question_bank_id == question_bank_id,
        ).first()

        if not assessment_question:
            raise ValueError(
                f"AssessmentQuestion not found for assessment {assessment_id}, "
                f"question {question_bank_id}"
            )

        if assessment_question.is_correct is not None:
            raise ValueError(
                f"Question {question_bank_id} has already been answered"
            )

        # Update the answer
        assessment_question.is_correct = is_correct
        assessment_question.student_answer = student_answer
        assessment_question.time_taken = time_taken
        assessment_question.answered_at = datetime.now(timezone.utc)

        # Update subtopic state
        current_subtopic["used_question_ids"].append(question_bank_id)
        current_subtopic["questions_answered"] += 1

        # Adjust difficulty (±1, clamped 1-5)
        current_difficulty = current_subtopic["current_difficulty"]
        if is_correct:
            new_difficulty = min(5, current_difficulty + 1)
        else:
            new_difficulty = max(1, current_difficulty - 1)
        current_subtopic["current_difficulty"] = new_difficulty

        # Update overall state
        state["answered_count"] = state.get("answered_count", 0) + 1
        state["current_question_bank_id"] = None  # Clear for next question
        state["last_activity"] = datetime.now(timezone.utc).isoformat()

        # Update status to IN_PROGRESS if this was the first answer
        if state["status"] == AssessmentStatus.STARTED.value:
            state["status"] = AssessmentStatus.IN_PROGRESS.value
            self._update_assessment_status(assessment_id, AssessmentStatus.IN_PROGRESS)

        # Check if subtopic is complete
        if current_subtopic["questions_answered"] >= current_subtopic["questions_total"]:
            # Advance to next subtopic
            state["current_subtopic_index"] = current_index + 1

            # Check if all subtopics are complete
            if state["current_subtopic_index"] >= len(subtopics):
                state["status"] = AssessmentStatus.COMPLETED.value
                self._update_assessment_status(
                    assessment_id,
                    AssessmentStatus.COMPLETED,
                    state["answered_count"]
                )

        # Update assessment questions_answered count
        assessment.questions_answered = state["answered_count"]

        # Save to Redis and DB
        self._save_session_state(assessment_id, state)
        self.db.commit()

        logger.info(
            "Recorded answer for assessment %s, question %s, correct=%s, "
            "difficulty %d→%d",
            assessment_id, question_bank_id, is_correct,
            current_difficulty, new_difficulty
        )

        return state

    def get_session_state(self, assessment_id: UUID) -> Dict:
        """
        Get session state from Redis, with DB fallback.

        Falls back to DB reconstruction if cache is cold.

        Args:
            assessment_id: UUID of the assessment

        Returns:
            Session state dict

        Raises:
            ValueError: If assessment not found
        """
        # Try Redis first
        state = self._get_session_state_from_redis(assessment_id)
        if state:
            return state

        # Fallback: reconstruct from DB
        logger.warning(
            "Redis cache miss for assessment %s, reconstructing from DB",
            assessment_id
        )

        return self._reconstruct_session_state(assessment_id)

    def _reconstruct_session_state(self, assessment_id: UUID) -> Dict:
        """
        Reconstruct session state from database.

        This is used when Redis cache is cold (e.g., after restart).

        Args:
            assessment_id: UUID of the assessment

        Returns:
            Reconstructed session state dict

        Raises:
            ValueError: If assessment not found
        """
        assessment = self.db.query(Assessment).filter(
            Assessment.id == assessment_id
        ).first()

        if not assessment:
            raise ValueError(f"Assessment not found: {assessment_id}")

        # Get all answered questions
        answered_questions = (
            self.db.query(AssessmentQuestion, QuestionBank)
            .join(QuestionBank, AssessmentQuestion.question_bank_id == QuestionBank.id)
            .filter(AssessmentQuestion.assessment_id == assessment_id)
            .filter(AssessmentQuestion.is_correct.isnot(None))
            .order_by(AssessmentQuestion.question_number)
            .all()
        )

        # Get subtopics for this subject
        student = self.db.query(StudentProfile).filter(
            StudentProfile.id == assessment.student_id
        ).first()

        subtopics = []
        if student and student.grade_id and student.curriculum_id:
            subtopics = self.selector.get_subtopics_for_session(
                curriculum_id=student.curriculum_id,
                grade_id=student.grade_id,
                subject_id=assessment.subject_id,
            )

        # Build subtopic states
        subtopic_states = []
        used_by_subtopic: Dict[UUID, List[UUID]] = {}
        answered_by_subtopic: Dict[UUID, int] = {}
        difficulty_by_subtopic: Dict[UUID, int] = {}

        # Initialize
        for subtopic in subtopics:
            used_by_subtopic[subtopic.id] = []
            answered_by_subtopic[subtopic.id] = 0
            difficulty_by_subtopic[subtopic.id] = self.starting_difficulty

        # Process answered questions
        for aq, qb in answered_questions:
            if qb.subtopic_id:
                used_by_subtopic[qb.subtopic_id].append(qb.id)
                answered_by_subtopic[qb.subtopic_id] += 1
                # Adjust difficulty based on answer
                if aq.is_correct:
                    difficulty_by_subtopic[qb.subtopic_id] = min(
                        5, difficulty_by_subtopic[qb.subtopic_id] + 1
                    )
                else:
                    difficulty_by_subtopic[qb.subtopic_id] = max(
                        1, difficulty_by_subtopic[qb.subtopic_id] - 1
                    )

        # Build state
        for subtopic in subtopics:
            subtopic_state = {
                "subtopic_id": subtopic.id,
                "subtopic_name": subtopic.name,
                "questions_total": self.questions_per_subtopic,
                "questions_answered": answered_by_subtopic.get(subtopic.id, 0),
                "current_difficulty": difficulty_by_subtopic.get(subtopic.id, self.starting_difficulty),
                "used_question_ids": used_by_subtopic.get(subtopic.id, []),
            }
            subtopic_states.append(subtopic_state)

        # Determine current subtopic index
        current_index = 0
        for i, st in enumerate(subtopic_states):
            if st["questions_answered"] < st["questions_total"]:
                current_index = i
                break
            current_index = i + 1

        # Build full state
        state = {
            "assessment_id": assessment_id,
            "student_id": assessment.student_id,
            "subject_id": assessment.subject_id,
            "status": assessment.status.value,
            "subtopics": subtopic_states,
            "current_subtopic_index": current_index,
            "current_question_bank_id": None,
            "total_questions": len(subtopics) * self.questions_per_subtopic,
            "answered_count": len(answered_questions),
            "started_at": assessment.created_at.isoformat() if assessment.created_at else None,
            "last_activity": assessment.updated_at.isoformat() if assessment.updated_at else None,
        }

        # Save to Redis for future use
        self._save_session_state(assessment_id, state)

        return state

    def _update_assessment_status(
        self,
        assessment_id: UUID,
        status: AssessmentStatus,
        questions_answered: Optional[int] = None
    ) -> None:
        """Update assessment status in database."""
        assessment = self.db.query(Assessment).filter(
            Assessment.id == assessment_id
        ).first()

        if assessment:
            assessment.status = status
            if questions_answered is not None:
                assessment.questions_answered = questions_answered
            if status == AssessmentStatus.COMPLETED:
                assessment.completed_at = datetime.now(timezone.utc)
            self.db.commit()

    def abandon_session(self, assessment_id: UUID) -> Dict:
        """
        Mark a session as abandoned.

        Args:
            assessment_id: UUID of the assessment

        Returns:
            Updated session state

        Raises:
            ValueError: If assessment not found
        """
        state = self.get_session_state(assessment_id)

        state["status"] = AssessmentStatus.ABANDONED.value
        state["last_activity"] = datetime.now(timezone.utc).isoformat()

        self._save_session_state(assessment_id, state)
        self._update_assessment_status(assessment_id, AssessmentStatus.ABANDONED)

        logger.info("Abandoned assessment %s", assessment_id)

        return state
