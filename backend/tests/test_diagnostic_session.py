"""
Tests for the Adaptive Diagnostic Session Engine.

This module tests:
- AdaptiveDiagnosticSelector: Question selection with fallback chain
- DiagnosticSessionManager: Session state machine and Redis caching

Note: These tests use mocking to avoid database compatibility issues with SQLite.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, call
from uuid import uuid4, UUID
import json

from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    AssessmentType,
    QuestionBank,
)
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    CurriculumSubject,
    Grade,
    Subtopic,
    Topic,
)
from app.models.subject import Subject
from app.models.user import StudentProfile, User, UserRole
from app.services.diagnostic import AdaptiveDiagnosticSelector, DiagnosticSessionManager
from app.services.diagnostic.question_selector import AdaptiveDiagnosticSelector as Selector


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get.return_value = None
    redis.setex = MagicMock()
    redis.delete = MagicMock()
    return redis


@pytest.fixture
def sample_uuid():
    """Generate a sample UUID."""
    return uuid4()


@pytest.fixture
def sample_grade():
    """Create a sample grade model."""
    grade = MagicMock(spec=Grade)
    grade.id = uuid4()
    grade.name = "Grade 5"
    grade.level = 5
    grade.is_active = True
    return grade


@pytest.fixture
def sample_curriculum():
    """Create a sample curriculum model."""
    curriculum = MagicMock(spec=Curriculum)
    curriculum.id = uuid4()
    curriculum.name = "Cambridge Primary"
    curriculum.code = "CAM-PRI"
    curriculum.is_active = True
    return curriculum


@pytest.fixture
def sample_subject():
    """Create a sample subject model."""
    subject = MagicMock(spec=Subject)
    subject.id = uuid4()
    subject.name = "Mathematics"
    subject.is_active = True
    return subject


@pytest.fixture
def sample_subtopic():
    """Create a sample subtopic model."""
    subtopic = MagicMock(spec=Subtopic)
    subtopic.id = uuid4()
    subtopic.name = "Linear Equations"
    subtopic.sequence_order = 1
    subtopic.is_active = True
    subtopic.curriculum_topic_id = uuid4()
    return subtopic


@pytest.fixture
def sample_question(sample_subtopic, sample_subject, sample_grade):
    """Create a sample question model."""
    question = MagicMock(spec=QuestionBank)
    question.id = uuid4()
    question.subtopic_id = sample_subtopic.id
    question.subject_id = sample_subject.id
    question.grade_id = sample_grade.id
    question.question_text = "What is 2 + 2?"
    question.question_type = "multiple_choice"
    question.difficulty_level = 3
    question.is_active = True
    return question


@pytest.fixture
def sample_student(sample_grade, sample_curriculum):
    """Create a sample student profile."""
    student = MagicMock(spec=StudentProfile)
    student.id = uuid4()
    student.user_id = uuid4()
    student.parent_id = uuid4()
    student.grade_id = sample_grade.id
    student.curriculum_id = sample_curriculum.id
    student.age = 10
    student.has_completed_assessment = False
    return student


@pytest.fixture
def sample_assessment(sample_student, sample_subject):
    """Create a sample assessment model."""
    assessment = MagicMock(spec=Assessment)
    assessment.id = uuid4()
    assessment.student_id = sample_student.id
    assessment.subject_id = sample_subject.id
    assessment.assessment_type = AssessmentType.DIAGNOSTIC
    assessment.status = AssessmentStatus.STARTED
    assessment.difficulty_level = 3
    assessment.questions_answered = 0
    assessment.total_questions = 15
    assessment.created_at = datetime.now(timezone.utc)
    assessment.student = sample_student
    return assessment


# =============================================================================
# AdaptiveDiagnosticSelector Tests
# =============================================================================

class TestAdaptiveDiagnosticSelector:
    """Tests for the AdaptiveDiagnosticSelector class."""

    def test_get_next_question_returns_difficulty_3_first(self, mock_db, sample_subtopic, sample_question):
        """Test that the selector returns difficulty 3 (starting difficulty) first."""
        # Setup mock query chain
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        sample_question.difficulty_level = 3
        mock_order.first.return_value = sample_question

        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        selector = AdaptiveDiagnosticSelector(mock_db)

        question = selector.get_next_question(
            subtopic_id=sample_subtopic.id,
            grade_id=uuid4(),
            subject_id=uuid4(),
            target_difficulty=3,
            used_question_ids=[],
        )

        assert question is not None
        assert question.difficulty_level == 3

    def test_fallback_difficulty_selection(self, mock_db, sample_subtopic):
        """Test that the selector falls back to adjacent difficulties."""
        # Create questions at different difficulties
        q4 = MagicMock(spec=QuestionBank)
        q4.id = uuid4()
        q4.difficulty_level = 4

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        # First call for difficulty 3 returns None
        # Second call for difficulty 4 returns question
        call_count = [0]
        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # No difficulty 3 question
            return q4  # Return difficulty 4 question

        mock_order.first = mock_first
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        selector = AdaptiveDiagnosticSelector(mock_db)

        question = selector.get_next_question(
            subtopic_id=sample_subtopic.id,
            grade_id=uuid4(),
            subject_id=uuid4(),
            target_difficulty=3,
            used_question_ids=[],
        )

        assert question is not None
        assert question.difficulty_level == 4

    def test_used_question_ids_prevents_repetition(self, mock_db, sample_subtopic):
        """Test that used questions are not selected again."""
        used_id = uuid4()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        new_question = MagicMock(spec=QuestionBank)
        new_question.id = uuid4()
        new_question.difficulty_level = 3

        mock_order.first.return_value = new_question
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        selector = AdaptiveDiagnosticSelector(mock_db)

        question = selector.get_next_question(
            subtopic_id=sample_subtopic.id,
            grade_id=uuid4(),
            subject_id=uuid4(),
            target_difficulty=3,
            used_question_ids=[used_id],
        )

        assert question is not None
        assert question.id != used_id

    def test_get_next_question_returns_none_when_exhausted(self, mock_db, sample_subtopic):
        """Test that None is returned when all questions are exhausted."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        mock_order.first.return_value = None
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        selector = AdaptiveDiagnosticSelector(mock_db)

        question = selector.get_next_question(
            subtopic_id=sample_subtopic.id,
            grade_id=uuid4(),
            subject_id=uuid4(),
            target_difficulty=3,
            used_question_ids=[uuid4(), uuid4(), uuid4()],
        )

        assert question is None

    def test_difficulty_invalid_raises_error(self, mock_db, sample_subtopic):
        """Test that invalid difficulty values raise ValueError."""
        selector = AdaptiveDiagnosticSelector(mock_db)

        with pytest.raises(ValueError):
            selector.get_next_question(
                subtopic_id=sample_subtopic.id,
                grade_id=uuid4(),
                subject_id=uuid4(),
                target_difficulty=6,  # Invalid
                used_question_ids=[],
            )

        with pytest.raises(ValueError):
            selector.get_next_question(
                subtopic_id=sample_subtopic.id,
                grade_id=uuid4(),
                subject_id=uuid4(),
                target_difficulty=0,  # Invalid
                used_question_ids=[],
            )

    def test_get_subtopics_returns_ordered_by_sequence(self, mock_db, sample_curriculum, sample_grade, sample_subject):
        """Test that subtopics are returned in sequence order."""
        # Create mock subtopics
        subtopics = []
        for i, name in enumerate(["Linear Equations", "Quadratic Equations", "Polynomials"]):
            st = MagicMock(spec=Subtopic)
            st.id = uuid4()
            st.name = name
            st.sequence_order = i + 1
            st.is_active = True
            subtopics.append(st)

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_options = MagicMock()
        mock_order = MagicMock()

        mock_order.all.return_value = subtopics
        mock_options.options.return_value = mock_options
        mock_options.order_by.return_value = mock_order
        mock_filter.filter.return_value = mock_options
        mock_query.join.return_value = mock_filter
        mock_db.query.return_value = mock_query

        selector = AdaptiveDiagnosticSelector(mock_db)

        result = selector.get_subtopics_for_session(
            curriculum_id=sample_curriculum.id,
            grade_id=sample_grade.id,
            subject_id=sample_subject.id,
        )

        assert len(result) == 3
        # Verify order
        for i in range(len(result) - 1):
            assert result[i].sequence_order <= result[i + 1].sequence_order

    def test_build_difficulty_fallback_order(self, mock_db):
        """Test the difficulty fallback order generation."""
        selector = AdaptiveDiagnosticSelector(mock_db)

        # Test middle difficulty
        order = selector._build_difficulty_fallback_order(3)
        assert order == [3, 4, 2]  # target, +1, -1

        # Test minimum difficulty
        order = selector._build_difficulty_fallback_order(1)
        assert order == [1, 2]  # target, +1 (no -1 possible)

        # Test maximum difficulty
        order = selector._build_difficulty_fallback_order(5)
        assert order == [5, 4]  # target, -1 (no +1 possible)


# =============================================================================
# DiagnosticSessionManager Tests
# =============================================================================

class TestDiagnosticSessionManager:
    """Tests for the DiagnosticSessionManager class."""

    def test_initialize_diagnostic_creates_assessments(
        self, mock_db, mock_redis, sample_student, sample_subject
    ):
        """Test that initialization creates assessments for subjects."""
        # Mock student query
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value.first.return_value = sample_student

        # Mock existing assessments query (empty list)
        mock_existing_query = MagicMock()
        mock_existing_query.filter.return_value.all.return_value = []

        # Mock subtopics query (for selector)
        mock_subtopics_query = MagicMock()
        mock_subtopics_query.join.return_value.filter.return_value.options.return_value.order_by.return_value.all.return_value = []

        mock_db.query.side_effect = [
            mock_student_query,  # Student lookup
            mock_existing_query,  # Existing assessments lookup
            mock_subtopics_query,  # Subtopics lookup (via selector)
        ]

        # Mock subjects query
        with patch.object(
            DiagnosticSessionManager,
            '_get_subjects_for_curriculum',
            return_value=[sample_subject]
        ):
            manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

            result = manager.initialize_diagnostic(sample_student.id)

            assert result["existing"] is False
            assert len(result["sessions"]) == 1

    def test_initialize_diagnostic_requires_grade(self, mock_db, mock_redis):
        """Test that initialization fails without grade_id."""
        # Create student without grade
        student = MagicMock(spec=StudentProfile)
        student.id = uuid4()
        student.grade_id = None  # Missing
        student.curriculum_id = uuid4()

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student
        mock_db.query.return_value = mock_query

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        with pytest.raises(ValueError, match="missing grade_id"):
            manager.initialize_diagnostic(student.id)

    def test_initialize_diagnostic_requires_curriculum(self, mock_db, mock_redis, sample_grade):
        """Test that initialization fails without curriculum_id."""
        # Create student without curriculum
        student = MagicMock(spec=StudentProfile)
        student.id = uuid4()
        student.grade_id = sample_grade.id
        student.curriculum_id = None  # Missing

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student
        mock_db.query.return_value = mock_query

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        with pytest.raises(ValueError, match="missing curriculum_id"):
            manager.initialize_diagnostic(student.id)

    def test_record_answer_adjusts_difficulty_up_on_correct(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that correct answer increases difficulty."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 3,
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        # Mock assessment query
        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        # Mock assessment question query
        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None  # Not yet answered
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,  # Assessment lookup
            mock_aq_query,  # AssessmentQuestion lookup
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,
        )

        assert new_state["subtopics"][0]["current_difficulty"] == 4  # Increased

    def test_record_answer_adjusts_difficulty_down_on_incorrect(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that incorrect answer decreases difficulty."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 3,
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        # Mock assessment query
        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        # Mock assessment question query
        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=False,
        )

        assert new_state["subtopics"][0]["current_difficulty"] == 2  # Decreased

    def test_difficulty_clamped_at_minimum(self, mock_db, mock_redis, sample_assessment, sample_question, sample_student):
        """Test that difficulty stays at minimum 1."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state with difficulty at 1
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 1,  # At minimum
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=False,  # Wrong answer
        )

        assert new_state["subtopics"][0]["current_difficulty"] == 1  # Stays at minimum

    def test_difficulty_clamped_at_maximum(self, mock_db, mock_redis, sample_assessment, sample_question, sample_student):
        """Test that difficulty stays at maximum 5."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state with difficulty at 5
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 5,  # At maximum
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,  # Correct answer
        )

        assert new_state["subtopics"][0]["current_difficulty"] == 5  # Stays at maximum

    def test_session_advances_subtopic_when_complete(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that session advances to next subtopic when current is complete."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state with 4 questions answered (1 more to complete)
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [
                {
                    "subtopic_id": str(sample_question.subtopic_id),
                    "subtopic_name": "Subtopic 1",
                    "questions_total": 5,
                    "questions_answered": 4,  # One more to complete
                    "current_difficulty": 3,
                    "used_question_ids": [],
                },
                {
                    "subtopic_id": str(uuid4()),
                    "subtopic_name": "Subtopic 2",
                    "questions_total": 5,
                    "questions_answered": 0,
                    "current_difficulty": 3,
                    "used_question_ids": [],
                }
            ],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 10,
            "answered_count": 4,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,
        )

        # Should have advanced to next subtopic
        assert new_state["current_subtopic_index"] == 1

    def test_session_marks_completed_when_all_done(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that session is marked completed when all subtopics are done."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state with last question of last subtopic
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Last Subtopic",
                "questions_total": 5,
                "questions_answered": 4,  # One more to complete
                "current_difficulty": 3,
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 4,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
            mock_assessment_query,  # For status update
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,
        )

        assert new_state["status"] == "completed"

    def test_cannot_answer_same_question_twice(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that answering the same question twice raises an error."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "in_progress",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 1,
                "current_difficulty": 3,
                "used_question_ids": [str(question_id)],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": None,  # No current question
            "total_questions": 5,
            "answered_count": 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_db.query.return_value = mock_assessment_query

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        with pytest.raises(ValueError, match="not the current question"):
            manager.record_answer_and_advance(
                assessment_id=assessment_id,
                question_bank_id=question_id,
                is_correct=True,
            )

    def test_status_transitions_to_in_progress_on_first_answer(
        self, mock_db, mock_redis, sample_assessment, sample_question, sample_student
    ):
        """Test that status transitions from STARTED to IN_PROGRESS."""
        assessment_id = sample_assessment.id
        question_id = sample_question.id

        # Mock Redis to return state with STARTED status
        mock_redis.get.return_value = json.dumps({
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_assessment.subject_id),
            "status": "started",  # Initial status
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 3,
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).encode('utf-8')

        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        mock_aq = MagicMock(spec=AssessmentQuestion)
        mock_aq.is_correct = None
        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = mock_aq

        # Need three queries: assessment lookup, aq lookup, and status update
        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
            mock_assessment_query,  # For status update
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,
        )

        assert new_state["status"] == "in_progress"

    def test_get_session_state_reconstructs_from_db_on_cache_miss(
        self, mock_db, mock_redis, sample_assessment, sample_student
    ):
        """Test that session state is reconstructed from DB when Redis is empty."""
        assessment_id = sample_assessment.id

        # Mock Redis to return None (cache miss)
        mock_redis.get.return_value = None

        # Setup proper datetime mocks
        now = datetime.now(timezone.utc)

        # Mock assessment with proper datetime
        sample_assessment.created_at = now
        sample_assessment.updated_at = now

        # Mock assessment query
        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = sample_assessment

        # Mock student query
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value.first.return_value = sample_student

        # Mock answered questions query (empty)
        mock_questions_query = MagicMock()
        mock_questions_query.filter.return_value.order_by.return_value.all.return_value = []

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_student_query,
            mock_questions_query,
        ]

        # Mock the selector
        with patch.object(
            AdaptiveDiagnosticSelector,
            'get_subtopics_for_session',
            return_value=[]
        ):
            manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

            state = manager.get_session_state(assessment_id)

            assert state is not None
            assert state["assessment_id"] == assessment_id


# =============================================================================
# Integration Tests
# =============================================================================

class TestDiagnosticSessionIntegration:
    """Integration tests for the diagnostic session engine."""

    def test_full_diagnostic_flow(self, mock_db, mock_redis, sample_student, sample_subject, sample_question):
        """Test a complete diagnostic assessment flow."""
        assessment_id = uuid4()
        question_id = sample_question.id

        # Initial state
        initial_state = {
            "assessment_id": str(assessment_id),
            "student_id": str(sample_student.id),
            "subject_id": str(sample_subject.id),
            "status": "started",
            "subtopics": [{
                "subtopic_id": str(sample_question.subtopic_id),
                "subtopic_name": "Test Subtopic",
                "questions_total": 5,
                "questions_answered": 0,
                "current_difficulty": 3,
                "used_question_ids": [],
            }],
            "current_subtopic_index": 0,
            "current_question_bank_id": str(question_id),
            "total_questions": 5,
            "answered_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }

        # Mock Redis to return initial state
        mock_redis.get.return_value = json.dumps(initial_state).encode('utf-8')

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = assessment_id
        assessment.student_id = sample_student.id
        assessment.subject_id = sample_subject.id
        assessment.status = AssessmentStatus.STARTED
        assessment.questions_answered = 0
        assessment.student = sample_student

        # Create mock assessment question
        aq = MagicMock(spec=AssessmentQuestion)
        aq.is_correct = None
        aq.question_bank_id = question_id

        # Setup mock queries
        mock_assessment_query = MagicMock()
        mock_assessment_query.filter.return_value.first.return_value = assessment

        mock_aq_query = MagicMock()
        mock_aq_query.filter.return_value.first.return_value = aq

        mock_db.query.side_effect = [
            mock_assessment_query,
            mock_aq_query,
            mock_assessment_query,  # For status update
        ]

        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        # Answer first question
        new_state = manager.record_answer_and_advance(
            assessment_id=assessment_id,
            question_bank_id=question_id,
            is_correct=True,
        )

        # Verify state changed
        assert new_state["status"] == "in_progress"
        assert new_state["answered_count"] == 1
        assert new_state["subtopics"][0]["current_difficulty"] == 4  # Increased


# =============================================================================
# Redis Key Format Tests
# =============================================================================

class TestRedisKeyFormat:
    """Tests for Redis key format compliance."""

    def test_redis_key_format(self, mock_db, mock_redis):
        """Test that Redis keys follow the required format."""
        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        assessment_id = uuid4()
        expected_key = f"kaihle:diagnostic:session:{assessment_id}"

        actual_key = manager._get_redis_key(assessment_id)

        assert actual_key == expected_key

    def test_redis_ttl_is_24_hours(self, mock_db, mock_redis):
        """Test that Redis TTL is set to 24 hours."""
        manager = DiagnosticSessionManager(mock_db, redis_client=mock_redis)

        assessment_id = uuid4()
        state = {"test": "data"}

        manager._save_session_state(assessment_id, state)

        # Verify setex was called with 24 hour TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 86400  # 24 hours in seconds
