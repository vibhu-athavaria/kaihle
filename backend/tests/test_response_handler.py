"""
Tests for the Diagnostic Response Handler.

This module tests:
- DiagnosticResponseHandler: Answer submission, evaluation, scoring
- AnswerResult: Result object for API responses
- check_all_subjects_complete: Completion detection and Celery dispatch
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4, UUID

from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    AssessmentType,
    QuestionBank,
)
from app.models.user import StudentProfile
from app.services.diagnostic import DiagnosticResponseHandler, DiagnosticSessionManager
from app.services.diagnostic.response_handler import AnswerResult


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
    return redis


@pytest.fixture
def sample_uuid():
    """Generate a sample UUID."""
    return uuid4()


@pytest.fixture
def sample_question():
    """Create a sample question."""
    question = MagicMock(spec=QuestionBank)
    question.id = uuid4()
    question.difficulty_level = 3
    question.correct_answer = "42"
    question.question_text = "What is 6 * 7?"
    return question


@pytest.fixture
def sample_assessment():
    """Create a sample assessment."""
    assessment = MagicMock(spec=Assessment)
    assessment.id = uuid4()
    assessment.student_id = uuid4()
    assessment.status = AssessmentStatus.IN_PROGRESS
    assessment.assessment_type = AssessmentType.DIAGNOSTIC
    return assessment


@pytest.fixture
def sample_assessment_question(sample_question):
    """Create a sample assessment question."""
    aq = MagicMock(spec=AssessmentQuestion)
    aq.id = uuid4()
    aq.assessment_id = uuid4()
    aq.question_bank_id = sample_question.id
    aq.is_correct = None  # Unanswered
    aq.student_answer = None
    aq.score = None
    aq.time_taken = None
    return aq


@pytest.fixture
def sample_student():
    """Create a sample student profile."""
    student = MagicMock(spec=StudentProfile)
    student.id = uuid4()
    student.has_completed_assessment = False
    return student


# =============================================================================
# AnswerResult Tests
# =============================================================================

class TestAnswerResult:
    """Tests for AnswerResult class."""

    def test_answer_result_creation(self):
        """Test creating an AnswerResult."""
        result = AnswerResult(
            is_correct=True,
            score=0.6,
            difficulty_level=3,
            next_difficulty=4,
            questions_answered=5,
            total_questions=25,
            subtopic_complete=False,
            assessment_status="in_progress",
            all_subjects_complete=False,
        )

        assert result.is_correct is True
        assert result.score == 0.6
        assert result.difficulty_level == 3
        assert result.next_difficulty == 4
        assert result.questions_answered == 5
        assert result.total_questions == 25
        assert result.subtopic_complete is False
        assert result.assessment_status == "in_progress"
        assert result.all_subjects_complete is False

    def test_answer_result_to_dict(self):
        """Test converting AnswerResult to dictionary."""
        result = AnswerResult(
            is_correct=False,
            score=0.0,
            difficulty_level=3,
            next_difficulty=2,
            questions_answered=10,
            total_questions=25,
            subtopic_complete=True,
            assessment_status="in_progress",
            all_subjects_complete=False,
        )

        result_dict = result.to_dict()

        assert result_dict["is_correct"] is False
        assert result_dict["score"] == 0.0
        assert result_dict["difficulty_level"] == 3
        assert result_dict["next_difficulty"] == 2
        assert result_dict["questions_answered"] == 10
        assert result_dict["total_questions"] == 25
        assert result_dict["subtopic_complete"] is True
        assert result_dict["assessment_status"] == "in_progress"
        assert result_dict["all_subjects_complete"] is False


# =============================================================================
# DiagnosticResponseHandler - evaluate_answer Tests
# =============================================================================

class TestEvaluateAnswer:
    """Tests for evaluate_answer method."""

    def test_evaluate_answer_correct(self, mock_db, sample_question):
        """Test correct answer evaluation."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "42"

        result = handler.evaluate_answer(sample_question, "42")

        assert result is True

    def test_evaluate_answer_correct_case_insensitive(self, mock_db, sample_question):
        """Test case-insensitive answer evaluation."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "Paris"

        result = handler.evaluate_answer(sample_question, "paris")

        assert result is True

    def test_evaluate_answer_correct_with_whitespace(self, mock_db, sample_question):
        """Test answer evaluation with whitespace."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "  42  "

        result = handler.evaluate_answer(sample_question, "42 ")

        assert result is True

    def test_evaluate_answer_incorrect(self, mock_db, sample_question):
        """Test incorrect answer evaluation."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "42"

        result = handler.evaluate_answer(sample_question, "41")

        assert result is False

    def test_evaluate_answer_empty_student_answer(self, mock_db, sample_question):
        """Test with empty student answer."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "42"

        result = handler.evaluate_answer(sample_question, "")

        assert result is False

    def test_evaluate_answer_none_student_answer(self, mock_db, sample_question):
        """Test with None student answer."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = "42"

        result = handler.evaluate_answer(sample_question, None)

        assert result is False

    def test_evaluate_answer_none_correct_answer(self, mock_db, sample_question):
        """Test with None correct answer."""
        handler = DiagnosticResponseHandler(mock_db)
        sample_question.correct_answer = None

        result = handler.evaluate_answer(sample_question, "42")

        assert result is False


# =============================================================================
# DiagnosticResponseHandler - calculate_score Tests
# =============================================================================

class TestCalculateScore:
    """Tests for calculate_score method."""

    def test_calculate_score_correct_difficulty_5(self, mock_db):
        """Test score for correct answer at difficulty 5."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=5)

        assert score == 1.0

    def test_calculate_score_correct_difficulty_4(self, mock_db):
        """Test score for correct answer at difficulty 4."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=4)

        assert score == 0.8

    def test_calculate_score_correct_difficulty_3(self, mock_db):
        """Test score for correct answer at difficulty 3."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=3)

        assert score == 0.6

    def test_calculate_score_correct_difficulty_2(self, mock_db):
        """Test score for correct answer at difficulty 2."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=2)

        assert score == 0.4

    def test_calculate_score_correct_difficulty_1(self, mock_db):
        """Test score for correct answer at difficulty 1."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=1)

        assert score == 0.2

    def test_calculate_score_incorrect(self, mock_db):
        """Test score for incorrect answer."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=False, difficulty_level=5)

        assert score == 0.0

    def test_calculate_score_incorrect_any_difficulty(self, mock_db):
        """Test score for incorrect answer at any difficulty."""
        handler = DiagnosticResponseHandler(mock_db)

        for difficulty in [1, 2, 3, 4, 5]:
            score = handler.calculate_score(is_correct=False, difficulty_level=difficulty)
            assert score == 0.0

    def test_calculate_score_clamps_difficulty_high(self, mock_db):
        """Test that difficulty is clamped to max 5."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=10)

        assert score == 1.0  # 5/5.0

    def test_calculate_score_clamps_difficulty_low(self, mock_db):
        """Test that difficulty is clamped to min 1."""
        handler = DiagnosticResponseHandler(mock_db)

        score = handler.calculate_score(is_correct=True, difficulty_level=0)

        assert score == 0.2  # 1/5.0


# =============================================================================
# DiagnosticResponseHandler - submit_answer Tests
# =============================================================================

class TestSubmitAnswer:
    """Tests for submit_answer method."""

    def test_submit_answer_raises_if_assessment_completed(
        self, mock_db, mock_redis, sample_uuid
    ):
        """Test that submit_answer raises if assessment is already completed."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock session state as completed
        with patch.object(
            handler.session_manager,
            'get_session_state',
            return_value={'status': AssessmentStatus.COMPLETED.value}
        ):
            with pytest.raises(ValueError) as exc_info:
                handler.submit_answer(
                    assessment_id=sample_uuid,
                    question_bank_id=sample_uuid,
                    student_answer="42",
                )

            assert "already completed" in str(exc_info.value).lower()

    def test_submit_answer_raises_if_not_current_question(
        self, mock_db, mock_redis, sample_uuid
    ):
        """Test that submit_answer raises if question is not current."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock session state with different current question
        with patch.object(
            handler.session_manager,
            'get_session_state',
            return_value={
                'status': AssessmentStatus.IN_PROGRESS.value,
                'current_question_bank_id': uuid4(),
                'student_id': sample_uuid,
            }
        ):
            with pytest.raises(ValueError) as exc_info:
                handler.submit_answer(
                    assessment_id=sample_uuid,
                    question_bank_id=sample_uuid,  # Different from current
                    student_answer="42",
                )

            assert "not the current question" in str(exc_info.value).lower()

    def test_submit_answer_raises_if_already_answered(
        self, mock_db, mock_redis, sample_uuid, sample_question
    ):
        """Test that submit_answer raises if question already answered."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        current_question_id = sample_uuid

        # Mock session state
        with patch.object(
            handler.session_manager,
            'get_session_state',
            return_value={
                'status': AssessmentStatus.IN_PROGRESS.value,
                'current_question_bank_id': current_question_id,
                'student_id': sample_uuid,
                'subtopics': [{'current_difficulty': 3}],
                'current_subtopic_index': 0,
            }
        ):
            # Mock assessment question as already answered
            mock_aq = MagicMock()
            mock_aq.is_correct = True  # Already answered

            mock_db.query.return_value.filter.return_value.first.return_value = mock_aq

            with pytest.raises(ValueError) as exc_info:
                handler.submit_answer(
                    assessment_id=sample_uuid,
                    question_bank_id=current_question_id,
                    student_answer="42",
                )

            assert "already been answered" in str(exc_info.value).lower()

    def test_submit_answer_success_correct(
        self, mock_db, mock_redis, sample_uuid, sample_question, sample_assessment_question
    ):
        """Test successful answer submission with correct answer."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        assessment_id = sample_uuid
        question_id = sample_question.id

        # Mock session state
        with patch.object(
            handler.session_manager,
            'get_session_state',
            return_value={
                'status': AssessmentStatus.IN_PROGRESS.value,
                'current_question_bank_id': question_id,
                'student_id': sample_uuid,
                'subtopics': [{
                    'current_difficulty': 3,
                    'questions_answered': 0,
                    'questions_total': 5,
                }],
                'current_subtopic_index': 0,
                'answered_count': 0,
                'total_questions': 25,
            }
        ):
            # Mock record_answer_and_advance
            with patch.object(
                handler.session_manager,
                'record_answer_and_advance',
                return_value={
                    'status': AssessmentStatus.IN_PROGRESS.value,
                    'answered_count': 1,
                    'total_questions': 25,
                }
            ):
                # Mock database queries
                sample_assessment_question.is_correct = None
                sample_assessment_question.assessment_id = assessment_id
                sample_assessment_question.question_bank_id = question_id

                # Set up mock chain for database queries
                mock_db.query.return_value.filter.return_value.first.side_effect = [
                    sample_assessment_question,  # AssessmentQuestion query
                    sample_question,  # QuestionBank query
                ]

                result = handler.submit_answer(
                    assessment_id=assessment_id,
                    question_bank_id=question_id,
                    student_answer="42",
                    time_taken_seconds=30,
                )

                assert result.is_correct is True
                assert result.score == 0.6  # difficulty 3 / 5.0
                assert result.difficulty_level == 3
                assert result.next_difficulty == 4  # Correct answer increases difficulty


# =============================================================================
# DiagnosticResponseHandler - check_all_subjects_complete Tests
# =============================================================================

class TestCheckAllSubjectsComplete:
    """Tests for check_all_subjects_complete method."""

    def test_returns_false_if_not_four_assessments(self, mock_db, mock_redis, sample_uuid):
        """Test returns False if student doesn't have 4 assessments."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock 3 assessments
        mock_db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
        ]

        result = handler.check_all_subjects_complete(sample_uuid)

        assert result is False

    def test_returns_false_if_not_all_completed(self, mock_db, mock_redis, sample_uuid):
        """Test returns False if not all assessments are completed."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock 4 assessments, one not completed
        mock_db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.IN_PROGRESS),
        ]

        result = handler.check_all_subjects_complete(sample_uuid)

        assert result is False

    def test_returns_true_and_sets_flag_when_all_complete(
        self, mock_db, mock_redis, sample_uuid, sample_student
    ):
        """Test returns True and sets has_completed_assessment when all complete."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock 4 completed assessments
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [  # First call for assessments
                MagicMock(status=AssessmentStatus.COMPLETED),
                MagicMock(status=AssessmentStatus.COMPLETED),
                MagicMock(status=AssessmentStatus.COMPLETED),
                MagicMock(status=AssessmentStatus.COMPLETED),
            ],
        ]

        # Mock student query
        sample_student.has_completed_assessment = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        result = handler.check_all_subjects_complete(sample_uuid)

        assert result is True
        assert sample_student.has_completed_assessment is True
        mock_redis.setex.assert_called_once()

    def test_prevents_double_trigger_with_redis_flag(
        self, mock_db, mock_redis, sample_uuid
    ):
        """Test that Redis flag prevents double-trigger of Celery chain."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        # Mock Redis flag already set
        mock_redis.get.return_value = b"reports"

        # Mock 4 completed assessments
        mock_db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
        ]

        result = handler.check_all_subjects_complete(sample_uuid)

        assert result is True
        # Should NOT call setex since flag already exists
        mock_redis.setex.assert_not_called()

    def test_works_without_redis(self, mock_db, sample_uuid, sample_student):
        """Test that check_all_subjects_complete works without Redis client."""
        handler = DiagnosticResponseHandler(mock_db, redis_client=None)

        # Mock 4 completed assessments
        mock_db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
            MagicMock(status=AssessmentStatus.COMPLETED),
        ]

        # Mock student query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        result = handler.check_all_subjects_complete(sample_uuid)

        assert result is True


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestResponseHandlerIntegration:
    """Integration-style tests for ResponseHandler with SessionManager."""

    def test_full_answer_submission_flow(
        self, mock_db, mock_redis, sample_uuid, sample_question, sample_assessment_question
    ):
        """Test the full flow of answer submission."""
        handler = DiagnosticResponseHandler(mock_db, mock_redis)

        assessment_id = sample_uuid
        question_id = sample_question.id
        student_id = sample_uuid

        # Mock session state
        session_state = {
            'status': AssessmentStatus.IN_PROGRESS.value,
            'current_question_bank_id': question_id,
            'student_id': student_id,
            'subtopics': [{
                'subtopic_id': sample_uuid,
                'current_difficulty': 3,
                'questions_answered': 0,
                'questions_total': 5,
                'used_question_ids': [],
            }],
            'current_subtopic_index': 0,
            'answered_count': 0,
            'total_questions': 25,
        }

        updated_state = {
            'status': AssessmentStatus.IN_PROGRESS.value,
            'answered_count': 1,
            'total_questions': 25,
            'subtopics': [{
                'questions_answered': 1,
                'questions_total': 5,
            }],
            'current_subtopic_index': 0,
        }

        with patch.object(
            handler.session_manager,
            'get_session_state',
            return_value=session_state
        ):
            with patch.object(
                handler.session_manager,
                'record_answer_and_advance',
                return_value=updated_state
            ):
                with patch.object(
                    handler,
                    'check_all_subjects_complete',
                    return_value=False
                ):
                    sample_assessment_question.is_correct = None
                    sample_assessment_question.assessment_id = assessment_id
                    sample_assessment_question.question_bank_id = question_id

                    mock_db.query.return_value.filter.return_value.first.side_effect = [
                        sample_assessment_question,
                        sample_question,
                    ]

                    result = handler.submit_answer(
                        assessment_id=assessment_id,
                        question_bank_id=question_id,
                        student_answer="42",
                        time_taken_seconds=30,
                    )

                    assert isinstance(result, AnswerResult)
                    assert result.is_correct is True
                    assert result.score == 0.6
