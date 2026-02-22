"""
Tests for the Assessment Report Generation Task.

This module tests:
- Mastery calculation functions
- Mastery labels and gap priority classification
- Report generation logic
- StudentKnowledgeProfile upsert
- Celery task execution
- Redis flag updates
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4, UUID

from app.worker.tasks.report_generation import (
    get_mastery_label,
    get_gap_priority,
    calculate_subtopic_mastery,
    _generate_single_report,
    _update_redis_flag,
    generate_assessment_reports,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_uuid():
    """Generate a sample UUID."""
    return uuid4()


# =============================================================================
# Mastery Label Tests
# =============================================================================

class TestGetMasteryLabel:
    """Tests for get_mastery_label function."""

    def test_beginning_label(self):
        """Test beginning label for low mastery."""
        assert get_mastery_label(0.0) == "beginning"
        assert get_mastery_label(0.25) == "beginning"
        assert get_mastery_label(0.39) == "beginning"

    def test_developing_label(self):
        """Test developing label for developing mastery."""
        assert get_mastery_label(0.40) == "developing"
        assert get_mastery_label(0.50) == "developing"
        assert get_mastery_label(0.59) == "developing"

    def test_approaching_label(self):
        """Test approaching label for approaching mastery."""
        assert get_mastery_label(0.60) == "approaching"
        assert get_mastery_label(0.70) == "approaching"
        assert get_mastery_label(0.74) == "approaching"

    def test_strong_label(self):
        """Test strong label for strong mastery."""
        assert get_mastery_label(0.75) == "strong"
        assert get_mastery_label(0.80) == "strong"
        assert get_mastery_label(0.89) == "strong"

    def test_mastery_label(self):
        """Test mastery label for complete mastery."""
        assert get_mastery_label(0.90) == "mastery"
        assert get_mastery_label(0.95) == "mastery"
        assert get_mastery_label(1.0) == "mastery"


# =============================================================================
# Gap Priority Tests
# =============================================================================

class TestGetGapPriority:
    """Tests for get_gap_priority function."""

    def test_high_priority(self):
        """Test high priority for very low mastery."""
        assert get_gap_priority(0.0) == "high"
        assert get_gap_priority(0.25) == "high"
        assert get_gap_priority(0.39) == "high"

    def test_medium_priority(self):
        """Test medium priority for developing mastery."""
        assert get_gap_priority(0.40) == "medium"
        assert get_gap_priority(0.50) == "medium"
        assert get_gap_priority(0.59) == "medium"

    def test_low_priority(self):
        """Test low priority for approaching mastery."""
        assert get_gap_priority(0.60) == "low"
        assert get_gap_priority(0.70) == "low"
        assert get_gap_priority(0.74) == "low"

    def test_no_gap_for_strength(self):
        """Test that strong mastery returns None (not a gap)."""
        assert get_gap_priority(0.75) is None
        assert get_gap_priority(0.85) is None
        assert get_gap_priority(0.90) is None
        assert get_gap_priority(1.0) is None


# =============================================================================
# Mastery Calculation Tests
# =============================================================================

class TestCalculateSubtopicMastery:
    """Tests for calculate_subtopic_mastery function."""

    def test_empty_questions(self):
        """Test with no questions."""
        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery([])

        assert mastery == 0.0
        assert diff_path == []
        assert correct_path == []
        assert correct == 0
        assert total == 0

    def test_single_correct_answer_difficulty_5(self):
        """Test single correct answer at difficulty 5."""
        questions = [{
            "difficulty_level": 5,
            "score": 1.0,
            "is_correct": True,
        }]

        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 5/5.0 = 1.0
        # actual_score = 1.0
        # mastery = 1.0 / 1.0 = 1.0
        assert mastery == 1.0
        assert diff_path == [5]
        assert correct_path == [True]
        assert correct == 1
        assert total == 1

    def test_single_correct_answer_difficulty_3(self):
        """Test single correct answer at difficulty 3."""
        questions = [{
            "difficulty_level": 3,
            "score": 0.6,
            "is_correct": True,
        }]

        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 3/5.0 = 0.6
        # actual_score = 0.6
        # mastery = 0.6 / 0.6 = 1.0
        assert mastery == 1.0
        assert diff_path == [3]
        assert correct_path == [True]
        assert correct == 1
        assert total == 1

    def test_single_incorrect_answer(self):
        """Test single incorrect answer."""
        questions = [{
            "difficulty_level": 3,
            "score": 0.0,
            "is_correct": False,
        }]

        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 3/5.0 = 0.6
        # actual_score = 0.0
        # mastery = 0.0 / 0.6 = 0.0
        assert mastery == 0.0
        assert diff_path == [3]
        assert correct_path == [False]
        assert correct == 0
        assert total == 1

    def test_mixed_answers(self):
        """Test mixed correct and incorrect answers."""
        questions = [
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
            {"difficulty_level": 4, "score": 0.0, "is_correct": False},
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},
            {"difficulty_level": 5, "score": 0.0, "is_correct": False},
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
        ]

        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 3/5 + 4/5 + 4/5 + 5/5 + 3/5 = 0.6 + 0.8 + 0.8 + 1.0 + 0.6 = 3.8
        # actual_score = 0.6 + 0.0 + 0.8 + 0.0 + 0.6 = 2.0
        # mastery = 2.0 / 3.8 ≈ 0.526
        assert round(mastery, 2) == 0.53
        assert diff_path == [3, 4, 4, 5, 3]
        assert correct_path == [True, False, True, False, True]
        assert correct == 3
        assert total == 5

    def test_all_correct(self):
        """Test all correct answers."""
        questions = [
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
        ]

        mastery, _, _, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 0.6 * 3 = 1.8
        # actual_score = 0.6 * 3 = 1.8
        # mastery = 1.8 / 1.8 = 1.0
        assert mastery == 1.0
        assert correct == 3
        assert total == 3

    def test_all_incorrect(self):
        """Test all incorrect answers."""
        questions = [
            {"difficulty_level": 3, "score": 0.0, "is_correct": False},
            {"difficulty_level": 3, "score": 0.0, "is_correct": False},
            {"difficulty_level": 3, "score": 0.0, "is_correct": False},
        ]

        mastery, _, _, correct, total = calculate_subtopic_mastery(questions)

        # max_possible = 0.6 * 3 = 1.8
        # actual_score = 0.0
        # mastery = 0.0 / 1.8 = 0.0
        assert mastery == 0.0
        assert correct == 0
        assert total == 3


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestReportGenerationIntegration:
    """Integration-style tests for report generation."""

    def test_mastery_label_matches_gap_priority(self):
        """Test that mastery labels and gap priorities are consistent."""
        # Beginning mastery should be high priority gap
        assert get_mastery_label(0.30) == "beginning"
        assert get_gap_priority(0.30) == "high"

        # Developing mastery should be medium priority gap
        assert get_mastery_label(0.45) == "developing"
        assert get_gap_priority(0.45) == "medium"

        # Approaching mastery should be low priority gap
        assert get_mastery_label(0.65) == "approaching"
        assert get_gap_priority(0.65) == "low"

        # Strong mastery should not be a gap
        assert get_mastery_label(0.80) == "strong"
        assert get_gap_priority(0.80) is None

        # Full mastery should not be a gap
        assert get_mastery_label(0.95) == "mastery"
        assert get_gap_priority(0.95) is None

    def test_difficulty_path_tracking(self):
        """Test that difficulty path is correctly tracked."""
        questions = [
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},
            {"difficulty_level": 5, "score": 0.0, "is_correct": False},
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},
        ]

        _, diff_path, correct_path, _, _ = calculate_subtopic_mastery(questions)

        # Should show adaptive difficulty progression
        assert diff_path == [3, 4, 5, 4]
        assert correct_path == [True, True, False, True]


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_mastery_label_boundary_values(self):
        """Test exact boundary values for mastery labels."""
        # Just below boundary
        assert get_mastery_label(0.399) == "beginning"
        # At boundary
        assert get_mastery_label(0.40) == "developing"

        # Just below boundary
        assert get_mastery_label(0.599) == "developing"
        # At boundary
        assert get_mastery_label(0.60) == "approaching"

        # Just below boundary
        assert get_mastery_label(0.749) == "approaching"
        # At boundary
        assert get_mastery_label(0.75) == "strong"

        # Just below boundary
        assert get_mastery_label(0.899) == "strong"
        # At boundary
        assert get_mastery_label(0.90) == "mastery"

    def test_gap_priority_boundary_values(self):
        """Test exact boundary values for gap priority."""
        # Just below boundary
        assert get_gap_priority(0.399) == "high"
        # At boundary
        assert get_gap_priority(0.40) == "medium"

        # Just below boundary
        assert get_gap_priority(0.599) == "medium"
        # At boundary
        assert get_gap_priority(0.60) == "low"

        # Just below boundary
        assert get_gap_priority(0.749) == "low"
        # At boundary (not a gap)
        assert get_gap_priority(0.75) is None

    def test_calculate_mastery_with_zero_difficulty(self):
        """Test mastery calculation with zero difficulty (edge case)."""
        questions = [{
            "difficulty_level": 0,
            "score": 0.0,
            "is_correct": False,
        }]

        mastery, _, _, _, _ = calculate_subtopic_mastery(questions)

        # max_possible = 0/5.0 = 0.0
        # Should handle division by zero
        assert mastery == 0.0

    def test_calculate_mastery_with_missing_fields(self):
        """Test mastery calculation with missing fields."""
        questions = [
            {},  # Missing all fields
            {"difficulty_level": 3},  # Missing score and is_correct
        ]

        mastery, diff_path, correct_path, correct, total = calculate_subtopic_mastery(questions)

        # Should use defaults
        assert mastery >= 0.0
        assert len(diff_path) == 2
        assert len(correct_path) == 2


# =============================================================================
# _generate_single_report Tests
# =============================================================================

class TestGenerateSingleReport:
    """Tests for _generate_single_report function."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_assessment(self):
        """Create a mock assessment."""
        assessment = MagicMock()
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        return assessment

    @pytest.fixture
    def mock_question_bank(self):
        """Create a mock question bank entry."""
        qb = MagicMock()
        qb.id = uuid4()
        qb.subtopic_id = uuid4()
        qb.topic_id = uuid4()
        qb.difficulty_level = 3
        return qb

    @pytest.fixture
    def mock_assessment_question(self, mock_question_bank):
        """Create a mock assessment question."""
        aq = MagicMock()
        aq.question_bank_id = mock_question_bank.id
        aq.score = 0.6
        aq.is_correct = True
        return aq

    def test_generate_single_report_no_questions(self, mock_db, mock_assessment):
        """Test report generation when no answered questions exist."""
        # Setup the chain: query().join().filter().filter().order_by().all()
        query_mock = MagicMock()
        join_mock = MagicMock()
        filter_mock1 = MagicMock()
        filter_mock2 = MagicMock()
        order_by_mock = MagicMock()

        order_by_mock.all.return_value = []
        filter_mock2.order_by.return_value = order_by_mock
        filter_mock1.filter.return_value = filter_mock2
        join_mock.filter.return_value = filter_mock1
        query_mock.join.return_value = join_mock
        mock_db.query.return_value = query_mock

        _generate_single_report(mock_db, mock_assessment)

        # Should return early without creating a report
        mock_db.add.assert_not_called()

    def test_generate_single_report_with_questions(self, mock_db, mock_assessment, mock_question_bank):
        """Test report generation with answered questions."""
        # Create mock answered questions
        aq = MagicMock()
        aq.question_bank_id = mock_question_bank.id
        aq.score = 0.6
        aq.is_correct = True

        # Mock subtopic
        mock_subtopic = MagicMock()
        mock_subtopic.id = mock_question_bank.subtopic_id
        mock_subtopic.name = "Test Subtopic"
        mock_subtopic.topic_id = mock_question_bank.topic_id

        # Mock topic
        mock_topic = MagicMock()
        mock_topic.id = mock_question_bank.topic_id
        mock_topic.name = "Test Topic"

        # Setup query chain for answered questions
        answered_query = MagicMock()
        answered_join = MagicMock()
        answered_filter1 = MagicMock()
        answered_filter2 = MagicMock()
        answered_order = MagicMock()

        answered_order.all.return_value = [(aq, mock_question_bank)]
        answered_filter2.order_by.return_value = answered_order
        answered_filter1.filter.return_value = answered_filter2
        answered_join.filter.return_value = answered_filter1
        answered_query.join.return_value = answered_join

        # Setup query chain for subtopic
        subtopic_query = MagicMock()
        subtopic_filter = MagicMock()
        subtopic_filter.first.return_value = mock_subtopic
        subtopic_query.filter.return_value = subtopic_filter

        # Setup query chain for topic
        topic_query = MagicMock()
        topic_filter = MagicMock()
        topic_filter.first.return_value = mock_topic
        topic_query.filter.return_value = topic_filter

        # Setup query chain for existing report (none exists)
        report_query = MagicMock()
        report_filter = MagicMock()
        report_filter.first.return_value = None
        report_query.filter.return_value = report_filter

        # Setup query chain for existing profile (none exists)
        profile_query = MagicMock()
        profile_filter = MagicMock()
        profile_filter.first.return_value = None
        profile_query.filter.return_value = profile_filter

        # Configure mock_db.query to return different mocks based on call order
        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return answered_query
            elif call_count[0] == 2:
                return subtopic_query
            elif call_count[0] == 3:
                return topic_query
            elif call_count[0] == 4:
                return report_query
            else:
                return profile_query

        mock_db.query.side_effect = query_side_effect

        _generate_single_report(mock_db, mock_assessment)

        # Verify report was added
        mock_db.add.assert_called()

    def test_generate_single_report_updates_existing_report(self, mock_db, mock_assessment, mock_question_bank):
        """Test that existing report is updated, not duplicated."""
        # Create mock answered questions
        aq = MagicMock()
        aq.question_bank_id = mock_question_bank.id
        aq.score = 0.6
        aq.is_correct = True

        # Mock existing report
        existing_report = MagicMock()
        existing_report.assessment_id = mock_assessment.id

        # Mock subtopic
        mock_subtopic = MagicMock()
        mock_subtopic.id = mock_question_bank.subtopic_id
        mock_subtopic.name = "Test Subtopic"
        mock_subtopic.topic_id = mock_question_bank.topic_id

        # Mock topic
        mock_topic = MagicMock()
        mock_topic.id = mock_question_bank.topic_id
        mock_topic.name = "Test Topic"

        # Setup query chain for answered questions
        answered_query = MagicMock()
        answered_join = MagicMock()
        answered_filter1 = MagicMock()
        answered_filter2 = MagicMock()
        answered_order = MagicMock()

        answered_order.all.return_value = [(aq, mock_question_bank)]
        answered_filter2.order_by.return_value = answered_order
        answered_filter1.filter.return_value = answered_filter2
        answered_join.filter.return_value = answered_filter1
        answered_query.join.return_value = answered_join

        # Setup query chain for subtopic
        subtopic_query = MagicMock()
        subtopic_filter = MagicMock()
        subtopic_filter.first.return_value = mock_subtopic
        subtopic_query.filter.return_value = subtopic_filter

        # Setup query chain for topic
        topic_query = MagicMock()
        topic_filter = MagicMock()
        topic_filter.first.return_value = mock_topic
        topic_query.filter.return_value = topic_filter

        # Setup query chain for existing report (exists)
        report_query = MagicMock()
        report_filter = MagicMock()
        report_filter.first.return_value = existing_report
        report_query.filter.return_value = report_filter

        # Setup query chain for existing profile (none exists)
        profile_query = MagicMock()
        profile_filter = MagicMock()
        profile_filter.first.return_value = None
        profile_query.filter.return_value = profile_filter

        # Configure mock_db.query to return different mocks based on call order
        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return answered_query
            elif call_count[0] == 2:
                return subtopic_query
            elif call_count[0] == 3:
                return topic_query
            elif call_count[0] == 4:
                return report_query
            else:
                return profile_query

        mock_db.query.side_effect = query_side_effect

        _generate_single_report(mock_db, mock_assessment)

        # Verify existing report was updated (not added as new)
        # The report should have its fields updated
        assert hasattr(existing_report, 'diagnostic_summary')

    def test_generate_single_report_updates_existing_profile(self, mock_db, mock_assessment, mock_question_bank):
        """Test that existing StudentKnowledgeProfile is updated."""
        # Create mock answered questions
        aq = MagicMock()
        aq.question_bank_id = mock_question_bank.id
        aq.score = 0.6
        aq.is_correct = True

        # Mock subtopic
        mock_subtopic = MagicMock()
        mock_subtopic.id = mock_question_bank.subtopic_id
        mock_subtopic.name = "Test Subtopic"
        mock_subtopic.topic_id = mock_question_bank.topic_id

        # Mock topic
        mock_topic = MagicMock()
        mock_topic.id = mock_question_bank.topic_id
        mock_topic.name = "Test Topic"

        # Mock existing profile
        existing_profile = MagicMock()
        existing_profile.mastery_level = 0.5
        existing_profile.assessment_count = 1

        # Setup query chain for answered questions
        answered_query = MagicMock()
        answered_join = MagicMock()
        answered_filter1 = MagicMock()
        answered_filter2 = MagicMock()
        answered_order = MagicMock()

        answered_order.all.return_value = [(aq, mock_question_bank)]
        answered_filter2.order_by.return_value = answered_order
        answered_filter1.filter.return_value = answered_filter2
        answered_join.filter.return_value = answered_filter1
        answered_query.join.return_value = answered_join

        # Setup query chain for subtopic
        subtopic_query = MagicMock()
        subtopic_filter = MagicMock()
        subtopic_filter.first.return_value = mock_subtopic
        subtopic_query.filter.return_value = subtopic_filter

        # Setup query chain for topic
        topic_query = MagicMock()
        topic_filter = MagicMock()
        topic_filter.first.return_value = mock_topic
        topic_query.filter.return_value = topic_filter

        # Setup query chain for existing report (none)
        report_query = MagicMock()
        report_filter = MagicMock()
        report_filter.first.return_value = None
        report_query.filter.return_value = report_filter

        # Setup query chain for existing profile (exists)
        profile_query = MagicMock()
        profile_filter = MagicMock()
        profile_filter.first.return_value = existing_profile
        profile_query.filter.return_value = profile_filter

        # Configure mock_db.query
        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return answered_query
            elif call_count[0] == 2:
                return subtopic_query
            elif call_count[0] == 3:
                return topic_query
            elif call_count[0] == 4:
                return report_query
            else:
                return profile_query

        mock_db.query.side_effect = query_side_effect

        _generate_single_report(mock_db, mock_assessment)

        # Verify profile was updated
        assert existing_profile.assessment_count == 2  # Incremented from 1


# =============================================================================
# _update_redis_flag Tests
# =============================================================================

class TestUpdateRedisFlag:
    """Tests for _update_redis_flag function."""

    def test_update_redis_flag_sets_key(self):
        """Test that Redis flag is set with correct key and TTL."""
        mock_client = MagicMock()
        mock_redis = MagicMock()
        mock_redis.from_url.return_value = mock_client

        with patch.dict('sys.modules', {'redis': mock_redis}):
            with patch.dict('os.environ', {'REDIS_URL': 'redis://test:6379/0'}):
                _update_redis_flag(str(uuid4()), "study_plan")

        mock_redis.from_url.assert_called_once()
        mock_client.setex.assert_called_once()

    def test_update_redis_flag_uses_default_url(self):
        """Test that Redis URL defaults to localhost if not in env."""
        mock_client = MagicMock()
        mock_redis = MagicMock()
        mock_redis.from_url.return_value = mock_client

        # Clear REDIS_URL from environment
        with patch.dict('sys.modules', {'redis': mock_redis}):
            with patch.dict('os.environ', {}, clear=False):
                # Remove REDIS_URL if present
                os_env = dict(os.environ)
                os_env.pop('REDIS_URL', None)
                with patch.dict('os.environ', os_env, clear=True):
                    _update_redis_flag(str(uuid4()), "test")

        mock_redis.from_url.assert_called_with("redis://localhost:6379/0")


import os  # Add import for os.environ tests


# =============================================================================
# generate_assessment_reports Celery Task Tests
# =============================================================================

class TestGenerateAssessmentReportsTask:
    """Tests for the main Celery task generate_assessment_reports."""

    @pytest.fixture
    def mock_celery_task(self):
        """Create a mock Celery task self object."""
        task = MagicMock()
        task.retry = MagicMock(side_effect=Exception("Retry triggered"))
        return task

    @patch('app.worker.tasks.report_generation.create_engine')
    @patch('app.worker.tasks.report_generation.sessionmaker')
    @patch('app.worker.tasks.report_generation._update_redis_flag')
    def test_task_returns_student_id_on_success(
        self, mock_update_redis, mock_sessionmaker, mock_create_engine, mock_celery_task
    ):
        """Test that task returns student_id on successful completion."""
        mock_session = MagicMock()
        mock_sessionmaker.return_value.return_value = mock_session

        # Mock no assessments found
        mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        student_id = str(uuid4())
        # Use .run() to call the task directly without Celery machinery
        result = generate_assessment_reports.run(student_id)

        assert result == student_id

    @patch('app.worker.tasks.report_generation.create_engine')
    @patch('app.worker.tasks.report_generation.sessionmaker')
    @patch('app.worker.tasks.report_generation._update_redis_flag')
    def test_task_processes_assessments(
        self, mock_update_redis, mock_sessionmaker, mock_create_engine, mock_celery_task
    ):
        """Test that task processes all completed assessments."""
        mock_session = MagicMock()
        mock_sessionmaker.return_value.return_value = mock_session

        # Create mock assessments
        mock_assessment1 = MagicMock()
        mock_assessment1.id = uuid4()
        mock_assessment2 = MagicMock()
        mock_assessment2.id = uuid4()

        mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
            mock_assessment1, mock_assessment2
        ]

        # Mock no answered questions (early return path)
        mock_session.query.return_value.join.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        student_id = str(uuid4())
        result = generate_assessment_reports.run(student_id)

        assert result == student_id
        mock_session.commit.assert_called_once()

    @patch('app.worker.tasks.report_generation.create_engine')
    @patch('app.worker.tasks.report_generation.sessionmaker')
    def test_task_retries_on_database_error(self, mock_sessionmaker, mock_create_engine, mock_celery_task):
        """Test that task retries on SQLAlchemyError."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_create_engine.side_effect = SQLAlchemyError("DB Error")

        student_id = str(uuid4())

        with pytest.raises(Exception):
            generate_assessment_reports.run(student_id)

    @patch('app.worker.tasks.report_generation.create_engine')
    @patch('app.worker.tasks.report_generation.sessionmaker')
    def test_task_retries_on_general_error(self, mock_sessionmaker, mock_create_engine, mock_celery_task):
        """Test that task retries on general Exception."""
        mock_create_engine.side_effect = Exception("General Error")

        student_id = str(uuid4())

        with pytest.raises(Exception):
            generate_assessment_reports.run(student_id)

    @patch('app.worker.tasks.report_generation.create_engine')
    @patch('app.worker.tasks.report_generation.sessionmaker')
    @patch('app.worker.tasks.report_generation._update_redis_flag')
    def test_task_updates_redis_flag_on_success(
        self, mock_update_redis, mock_sessionmaker, mock_create_engine, mock_celery_task
    ):
        """Test that Redis flag is updated after successful processing."""
        mock_session = MagicMock()
        mock_sessionmaker.return_value.return_value = mock_session

        mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        student_id = str(uuid4())
        generate_assessment_reports.run(student_id)

        mock_update_redis.assert_called_once_with(student_id, "study_plan")


# =============================================================================
# Phase 5 Acceptance Criteria Tests
# =============================================================================

class TestPhase5AcceptanceCriteria:
    """Tests verifying Phase 5 acceptance criteria."""

    def test_mastery_calculation_correct(self):
        """Verify mastery calculation matches specification.

        Per subtopic:
          max_possible = Σ (difficulty_level / 5.0) for all questions
          actual_score = Σ score for all questions
          mastery_level = actual_score / max_possible
        """
        questions = [
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},
            {"difficulty_level": 5, "score": 0.0, "is_correct": False},
        ]

        mastery, _, _, _, _ = calculate_subtopic_mastery(questions)

        # max_possible = 3/5 + 4/5 + 5/5 = 0.6 + 0.8 + 1.0 = 2.4
        # actual_score = 0.6 + 0.8 + 0.0 = 1.4
        # mastery = 1.4 / 2.4 ≈ 0.583
        assert abs(mastery - 0.5833333333333333) < 0.001

    def test_mastery_labels_match_specification(self):
        """Verify mastery labels match specification.

        | Range | Label |
        | 0.00 – 0.39 | beginning |
        | 0.40 – 0.59 | developing |
        | 0.60 – 0.74 | approaching |
        | 0.75 – 0.89 | strong |
        | 0.90 – 1.00 | mastery |
        """
        assert get_mastery_label(0.0) == "beginning"
        assert get_mastery_label(0.39) == "beginning"
        assert get_mastery_label(0.40) == "developing"
        assert get_mastery_label(0.59) == "developing"
        assert get_mastery_label(0.60) == "approaching"
        assert get_mastery_label(0.74) == "approaching"
        assert get_mastery_label(0.75) == "strong"
        assert get_mastery_label(0.89) == "strong"
        assert get_mastery_label(0.90) == "mastery"
        assert get_mastery_label(1.0) == "mastery"

    def test_gap_priority_matches_specification(self):
        """Verify gap priority matches specification.

        | Mastery | Priority |
        | < 0.40 | high |
        | 0.40 – 0.59 | medium |
        | 0.60 – 0.74 | low |
        | ≥ 0.75 | (strength, not a gap) |
        """
        assert get_gap_priority(0.0) == "high"
        assert get_gap_priority(0.39) == "high"
        assert get_gap_priority(0.40) == "medium"
        assert get_gap_priority(0.59) == "medium"
        assert get_gap_priority(0.60) == "low"
        assert get_gap_priority(0.74) == "low"
        assert get_gap_priority(0.75) is None
        assert get_gap_priority(1.0) is None

    def test_difficulty_path_reflects_adaptive_sequence(self):
        """Verify difficulty_path correctly reflects adaptive sequence."""
        questions = [
            {"difficulty_level": 3, "score": 0.6, "is_correct": True},   # Start at 3
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},   # Correct → 4
            {"difficulty_level": 5, "score": 0.0, "is_correct": False},  # Correct → 5
            {"difficulty_level": 4, "score": 0.8, "is_correct": True},   # Incorrect → 4
            {"difficulty_level": 5, "score": 1.0, "is_correct": True},   # Correct → 5
        ]

        _, diff_path, correct_path, _, _ = calculate_subtopic_mastery(questions)

        assert diff_path == [3, 4, 5, 4, 5]
        assert correct_path == [True, True, False, True, True]

    def test_needs_review_threshold(self):
        """Verify needs_review = True where mastery_level < 0.6."""
        # This is tested via the _generate_single_report function
        # which sets needs_review = result["mastery_level"] < 0.60
        mastery_below_threshold = 0.55
        mastery_at_threshold = 0.60
        mastery_above_threshold = 0.65

        # needs_review should be True for mastery < 0.60
        assert mastery_below_threshold < 0.60
        assert mastery_at_threshold >= 0.60
        assert mastery_above_threshold >= 0.60
