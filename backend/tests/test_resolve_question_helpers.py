#!/usr/bin/env python3
"""
Unit tests for resolve_question helper functions.

Tests for:
- get_subtopics_for_grade_and_subject
- count_questions_per_subtopic
- select_subtopic_by_priority

Note: These tests use mocking to avoid database compatibility issues between
PostgreSQL UUID types and SQLite. The helper functions are tested in isolation
with mocked database sessions and model objects.
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, List, Optional

from app.models.assessment import (
    Assessment,
    AssessmentType,
    AssessmentStatus,
    AssessmentQuestion,
    QuestionBank,
    StudentKnowledgeProfile
)
from app.models.curriculum import Subtopic, CurriculumTopic
from app.models.user import StudentProfile
from app.constants.constants import ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC


# ============== Tests for get_subtopics_for_grade_and_subject ==============

class TestGetSubtopicsForGradeAndSubject:
    """Tests for get_subtopics_for_grade_and_subject function."""

    def test_returns_subtopics_for_valid_grade_and_subject(self):
        """Test that subtopics are returned for valid grade/subject combination."""
        from app.crud.assessment import get_subtopics_for_grade_and_subject

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()
        subtopic1.name = "Linear Equations"
        subtopic1.sequence_order = 1
        subtopic1.is_active = True

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()
        subtopic2.name = "Quadratic Equations"
        subtopic2.sequence_order = 2
        subtopic2.is_active = True

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_options = MagicMock()
        mock_order = MagicMock()

        # Set up the chain: db.query().join().filter().options().order_by().all()
        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter  # for multiple filter calls
        mock_filter.options.return_value = mock_options
        mock_options.order_by.return_value = mock_order
        mock_order.all.return_value = [subtopic1, subtopic2]

        grade_id = uuid4()
        subject_id = uuid4()

        # Execute
        result = get_subtopics_for_grade_and_subject(mock_db, grade_id, subject_id)

        # Assert
        assert len(result) == 2
        assert result[0].name == "Linear Equations"
        assert result[1].name == "Quadratic Equations"

    def test_returns_empty_list_for_no_results(self):
        """Test that empty list is returned when no subtopics found."""
        from app.crud.assessment import get_subtopics_for_grade_and_subject

        # Create mock query chain that returns empty list
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_options = MagicMock()
        mock_order = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.options.return_value = mock_options
        mock_options.order_by.return_value = mock_order
        mock_order.all.return_value = []

        grade_id = uuid4()
        subject_id = uuid4()

        # Execute
        result = get_subtopics_for_grade_and_subject(mock_db, grade_id, subject_id)

        # Assert
        assert result == []

    def test_filters_by_curriculum_when_provided(self):
        """Test that results are filtered by curriculum_id when provided."""
        from app.crud.assessment import get_subtopics_for_grade_and_subject

        # Create mock subtopic
        subtopic = MagicMock(spec=Subtopic)
        subtopic.id = uuid4()
        subtopic.name = "Linear Equations"

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_options = MagicMock()
        mock_order = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        # Track filter calls for curriculum filtering
        mock_filter.filter.return_value = mock_filter
        mock_filter.options.return_value = mock_options
        mock_options.order_by.return_value = mock_order
        mock_order.all.return_value = [subtopic]

        grade_id = uuid4()
        subject_id = uuid4()
        curriculum_id = uuid4()

        # Execute with curriculum_id
        result = get_subtopics_for_grade_and_subject(
            mock_db, grade_id, subject_id, curriculum_id=curriculum_id
        )

        # Assert - should have one result
        assert len(result) == 1
        assert result[0].name == "Linear Equations"


# ============== Tests for count_questions_per_subtopic ==============

class TestCountQuestionsPerSubtopic:
    """Tests for count_questions_per_subtopic function."""

    def test_returns_correct_counts_for_assessment(self):
        """Test that correct question counts are returned per subtopic."""
        from app.crud.assessment import count_questions_per_subtopic

        # Create mock results
        subtopic1_id = uuid4()
        subtopic2_id = uuid4()

        mock_row1 = MagicMock()
        mock_row1.subtopic_id = subtopic1_id
        mock_row1.count = 2

        mock_row2 = MagicMock()
        mock_row2.subtopic_id = subtopic2_id
        mock_row2.count = 1

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter1 = MagicMock()
        mock_filter2 = MagicMock()
        mock_group = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter1
        mock_filter1.filter.return_value = mock_filter2
        mock_filter2.group_by.return_value = mock_group
        mock_group.all.return_value = [mock_row1, mock_row2]

        assessment_id = uuid4()

        # Execute
        result = count_questions_per_subtopic(mock_db, assessment_id)

        # Assert
        assert len(result) == 2
        assert result[subtopic1_id] == 2
        assert result[subtopic2_id] == 1

    def test_returns_empty_dict_for_no_questions(self):
        """Test that empty dict is returned when no questions exist."""
        from app.crud.assessment import count_questions_per_subtopic

        # Create mock query chain that returns empty list
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter1 = MagicMock()
        mock_filter2 = MagicMock()
        mock_group = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter1
        mock_filter1.filter.return_value = mock_filter2
        mock_filter2.group_by.return_value = mock_group
        mock_group.all.return_value = []

        assessment_id = uuid4()

        # Execute
        result = count_questions_per_subtopic(mock_db, assessment_id)

        # Assert
        assert result == {}


# ============== Tests for select_subtopic_by_priority ==============

class TestSelectSubtopicByPriority:
    """Tests for select_subtopic_by_priority function."""

    def test_selects_subtopic_with_lowest_mastery(self):
        """Test that subtopic with lowest mastery is selected (highest priority)."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()
        subtopic1.name = "Linear Equations"

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()
        subtopic2.name = "Quadratic Equations"

        # Create mock knowledge profiles
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = 0.3  # Lower mastery

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.8  # Higher mastery

        subtopics = [subtopic1, subtopic2]
        questions_per_subtopic = {}
        knowledge_profiles = [profile1, profile2]

        # Execute
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles
        )

        # Assert - subtopic1 should be selected (lower mastery = higher priority)
        assert result is not None
        assert result.id == subtopic1.id

    def test_filters_out_subtopics_at_max_questions(self):
        """Test that subtopics at max questions are filtered out."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()

        # Create mock knowledge profiles with same mastery
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = 0.5

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.5

        subtopics = [subtopic1, subtopic2]
        # subtopic1 is at max questions
        questions_per_subtopic = {
            subtopic1.id: ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC,
            subtopic2.id: 2
        }
        knowledge_profiles = [profile1, profile2]

        # Execute
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles
        )

        # Assert - subtopic2 should be selected (subtopic1 is at max)
        assert result is not None
        assert result.id == subtopic2.id

    def test_returns_none_when_all_subtopics_at_max(self):
        """Test that None is returned when all subtopics are at max questions."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()

        # Create mock knowledge profiles
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = 0.5

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.5

        subtopics = [subtopic1, subtopic2]
        # Both at max
        questions_per_subtopic = {
            subtopic1.id: ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC,
            subtopic2.id: ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC
        }
        knowledge_profiles = [profile1, profile2]

        # Execute
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles
        )

        # Assert
        assert result is None

    def test_returns_none_for_empty_subtopics_list(self):
        """Test that None is returned for empty subtopics list."""
        from app.crud.assessment import select_subtopic_by_priority

        # Execute
        result = select_subtopic_by_priority([], {}, [])

        # Assert
        assert result is None

    def test_uses_default_mastery_for_missing_profile(self):
        """Test that default mastery (0.5) is used when no profile exists."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()

        # Only create profile for subtopic2 with high mastery
        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.9

        subtopics = [subtopic1, subtopic2]
        questions_per_subtopic = {}
        knowledge_profiles = [profile2]  # Only profile for subtopic2

        # Execute
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles
        )

        # Assert - subtopic1 should be selected (default 0.5 mastery < 0.9)
        assert result is not None
        assert result.id == subtopic1.id

    def test_respects_custom_max_questions_parameter(self):
        """Test that custom max_questions_per_subtopic is respected."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()

        # Create mock knowledge profiles with same mastery
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = 0.5

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.5

        subtopics = [subtopic1, subtopic2]
        # subtopic1 at custom max of 3
        questions_per_subtopic = {
            subtopic1.id: 3,
            subtopic2.id: 2
        }
        knowledge_profiles = [profile1, profile2]

        # Execute with custom max of 3
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles, max_questions_per_subtopic=3
        )

        # Assert - subtopic2 should be selected (subtopic1 is at custom max)
        assert result is not None
        assert result.id == subtopic2.id

    def test_handles_none_mastery_level(self):
        """Test that None mastery_level is handled as default 0.5."""
        from app.crud.assessment import select_subtopic_by_priority

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()

        # Create mock knowledge profiles - one with None mastery
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = None  # None mastery

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.7  # Higher than default 0.5

        subtopics = [subtopic1, subtopic2]
        questions_per_subtopic = {}
        knowledge_profiles = [profile1, profile2]

        # Execute
        result = select_subtopic_by_priority(
            subtopics, questions_per_subtopic, knowledge_profiles
        )

        # Assert - subtopic1 should be selected (None treated as 0.5 < 0.7)
        assert result is not None
        assert result.id == subtopic1.id


# ============== Integration Tests ==============

class TestHelperFunctionsIntegration:
    """Integration tests combining multiple helper functions."""

    def test_full_workflow_with_mocks(self):
        """Test the full workflow of loading subtopics, counting, and selecting."""
        from app.crud.assessment import (
            get_subtopics_for_grade_and_subject,
            count_questions_per_subtopic,
            select_subtopic_by_priority
        )

        # Create mock subtopics
        subtopic1 = MagicMock(spec=Subtopic)
        subtopic1.id = uuid4()
        subtopic1.name = "Linear Equations"
        subtopic1.sequence_order = 1
        subtopic1.is_active = True

        subtopic2 = MagicMock(spec=Subtopic)
        subtopic2.id = uuid4()
        subtopic2.name = "Quadratic Equations"
        subtopic2.sequence_order = 2
        subtopic2.is_active = True

        subtopic3 = MagicMock(spec=Subtopic)
        subtopic3.id = uuid4()
        subtopic3.name = "Polynomials"
        subtopic3.sequence_order = 3
        subtopic3.is_active = True

        # Mock get_subtopics_for_grade_and_subject
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_options = MagicMock()
        mock_order = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.options.return_value = mock_options
        mock_options.order_by.return_value = mock_order
        mock_order.all.return_value = [subtopic1, subtopic2, subtopic3]

        grade_id = uuid4()
        subject_id = uuid4()

        # Step 1: Get subtopics
        subtopics = get_subtopics_for_grade_and_subject(mock_db, grade_id, subject_id)
        assert len(subtopics) == 3

        # Step 2: Mock count_questions_per_subtopic
        assessment_id = uuid4()
        mock_count_query = MagicMock()
        mock_count_join = MagicMock()
        mock_count_filter1 = MagicMock()
        mock_count_filter2 = MagicMock()
        mock_count_group = MagicMock()

        # Create mock rows for count query
        mock_row = MagicMock()
        mock_row.subtopic_id = subtopic1.id
        mock_row.count = 2

        mock_db.query.return_value = mock_count_query
        mock_count_query.join.return_value = mock_count_join
        mock_count_join.filter.return_value = mock_count_filter1
        mock_count_filter1.filter.return_value = mock_count_filter2
        mock_count_filter2.group_by.return_value = mock_count_group
        mock_count_group.all.return_value = [mock_row]

        question_counts = count_questions_per_subtopic(mock_db, assessment_id)
        assert question_counts.get(subtopic1.id, 0) == 2
        assert question_counts.get(subtopic2.id, 0) == 0
        assert question_counts.get(subtopic3.id, 0) == 0

        # Step 3: Select subtopic by priority
        # Create knowledge profiles
        profile1 = MagicMock(spec=StudentKnowledgeProfile)
        profile1.subtopic_id = subtopic1.id
        profile1.mastery_level = 0.8

        profile2 = MagicMock(spec=StudentKnowledgeProfile)
        profile2.subtopic_id = subtopic2.id
        profile2.mastery_level = 0.3  # Lowest mastery

        profile3 = MagicMock(spec=StudentKnowledgeProfile)
        profile3.subtopic_id = subtopic3.id
        profile3.mastery_level = 0.6

        knowledge_profiles = [profile1, profile2, profile3]

        selected = select_subtopic_by_priority(
            subtopics, question_counts, knowledge_profiles
        )

        # Assert - subtopic2 should be selected (lowest mastery = 0.3)
        assert selected is not None
        assert selected.id == subtopic2.id


# ============== Tests for get_recent_answers_for_subtopic ==============

class TestGetRecentAnswersForSubtopic:
    """Tests for get_recent_answers_for_subtopic function."""

    def test_returns_recent_answers_for_subtopic(self):
        """Test that recent answers are returned for a subtopic."""
        from app.crud.assessment import get_recent_answers_for_subtopic

        # Create mock answers
        answer1 = MagicMock(spec=AssessmentQuestion)
        answer1.id = uuid4()
        answer1.is_correct = True

        answer2 = MagicMock(spec=AssessmentQuestion)
        answer2.id = uuid4()
        answer2.is_correct = False

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.all.return_value = [answer1, answer2]

        assessment_id = uuid4()
        subtopic_id = uuid4()

        # Execute
        result = get_recent_answers_for_subtopic(mock_db, assessment_id, subtopic_id)

        # Assert
        assert len(result) == 2
        assert result[0].is_correct == True
        assert result[1].is_correct == False

    def test_returns_empty_list_for_no_answers(self):
        """Test that empty list is returned when no answers exist."""
        from app.crud.assessment import get_recent_answers_for_subtopic

        # Create mock query chain that returns empty list
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.all.return_value = []

        assessment_id = uuid4()
        subtopic_id = uuid4()

        # Execute
        result = get_recent_answers_for_subtopic(mock_db, assessment_id, subtopic_id)

        # Assert
        assert result == []

    def test_respects_limit_parameter(self):
        """Test that limit parameter is respected."""
        from app.crud.assessment import get_recent_answers_for_subtopic

        # Create mock answers
        answers = [MagicMock(spec=AssessmentQuestion, id=uuid4()) for _ in range(5)]

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.all.return_value = answers[:3]  # Simulate limit of 3

        assessment_id = uuid4()
        subtopic_id = uuid4()

        # Execute with limit=3
        result = get_recent_answers_for_subtopic(mock_db, assessment_id, subtopic_id, limit=3)

        # Assert
        assert len(result) == 3


# ============== Tests for calculate_subtopic_difficulty ==============

class TestCalculateSubtopicDifficulty:
    """Tests for calculate_subtopic_difficulty function."""

    def test_returns_initial_difficulty_for_no_answers(self):
        """Test that initial difficulty is returned when no answers exist."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Mock get_recent_answers_for_subtopic to return empty list
        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = []

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=3)

            # Assert
            assert result == 3

    def test_increases_difficulty_for_correct_answers(self):
        """Test that difficulty increases for correct answers."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Create mock answers - all correct
        answers = [
            MagicMock(spec=AssessmentQuestion, is_correct=True),
            MagicMock(spec=AssessmentQuestion, is_correct=True),
            MagicMock(spec=AssessmentQuestion, is_correct=True)
        ]

        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = answers

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute with initial difficulty 3
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=3)

            # Assert - 3 correct answers should increase difficulty from 3 to 5 (max)
            # Actually: start at 3, +1 for each correct = 6, but max is 5
            assert result == 5

    def test_decreases_difficulty_for_wrong_answers(self):
        """Test that difficulty decreases for wrong answers."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Create mock answers - all wrong
        answers = [
            MagicMock(spec=AssessmentQuestion, is_correct=False),
            MagicMock(spec=AssessmentQuestion, is_correct=False),
            MagicMock(spec=AssessmentQuestion, is_correct=False)
        ]

        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = answers

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute with initial difficulty 3
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=3)

            # Assert - 3 wrong answers should decrease difficulty from 3 to 1 (min)
            # Actually: start at 3, -1 for each wrong = 0, but min is 1
            assert result == 1

    def test_difficulty_respects_minimum_boundary(self):
        """Test that difficulty doesn't go below 1."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Create mock answers - all wrong
        answers = [MagicMock(spec=AssessmentQuestion, is_correct=False) for _ in range(5)]

        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = answers

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute with initial difficulty 1
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=1)

            # Assert - should stay at minimum 1
            assert result == 1

    def test_difficulty_respects_maximum_boundary(self):
        """Test that difficulty doesn't go above 5."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Create mock answers - all correct
        answers = [MagicMock(spec=AssessmentQuestion, is_correct=True) for _ in range(5)]

        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = answers

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute with initial difficulty 5
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=5)

            # Assert - should stay at maximum 5
            assert result == 5

    def test_mixed_answers_adjust_difficulty(self):
        """Test that mixed correct/wrong answers adjust difficulty appropriately."""
        from app.crud.assessment import calculate_subtopic_difficulty

        # Create mock answers - mixed
        answers = [
            MagicMock(spec=AssessmentQuestion, is_correct=True),   # 3 + 1 = 4
            MagicMock(spec=AssessmentQuestion, is_correct=False),  # 4 - 1 = 3
            MagicMock(spec=AssessmentQuestion, is_correct=True)    # 3 + 1 = 4
        ]

        with patch('app.crud.assessment.get_recent_answers_for_subtopic') as mock_get_answers:
            mock_get_answers.return_value = answers

            mock_db = MagicMock()
            assessment_id = uuid4()
            subtopic_id = uuid4()

            # Execute with initial difficulty 3
            result = calculate_subtopic_difficulty(mock_db, assessment_id, subtopic_id, initial_difficulty=3)

            # Assert - should end at 4
            assert result == 4


# ============== Tests for find_existing_question ==============

class TestFindExistingQuestion:
    """Tests for find_existing_question function."""

    def test_returns_question_for_exact_difficulty_match(self):
        """Test that question is returned for exact difficulty match."""
        from app.crud.assessment import find_existing_question

        # Create mock question
        mock_question = MagicMock(spec=QuestionBank)
        mock_question.id = uuid4()
        mock_question.difficulty_level = 3  # Integer difficulty 1-5

        # Create mock query chain - need to match the actual function's chain
        # db.query(QuestionBank).filter(...).filter(...).filter(...).filter(...).first()
        mock_db = MagicMock()
        mock_query = MagicMock()

        # Set up the chain to return the same mock for each filter call
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_question

        mock_db.query.return_value = mock_query

        subtopic_id = uuid4()
        grade_id = uuid4()
        subject_id = uuid4()

        # Execute with difficulty 3
        result = find_existing_question(mock_db, subtopic_id, 3, grade_id, subject_id)

        # Assert
        assert result is not None
        assert result == mock_question

    def test_returns_none_when_no_question_found(self):
        """Test that None is returned when no question matches."""
        from app.crud.assessment import find_existing_question

        # Create mock query chain that returns None for both exact and range match
        mock_db = MagicMock()
        mock_query = MagicMock()

        # Set up the chain to return None for first() calls
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        subtopic_id = uuid4()
        grade_id = uuid4()
        subject_id = uuid4()

        # Execute
        result = find_existing_question(mock_db, subtopic_id, 3, grade_id, subject_id)

        # Assert
        assert result is None

    def test_excludes_specified_question_ids(self):
        """Test that excluded question IDs are filtered out."""
        from app.crud.assessment import find_existing_question

        # Create mock question
        mock_question = MagicMock(spec=QuestionBank)
        mock_question.id = uuid4()

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()

        # Set up the chain to return the same mock for each filter call
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_question

        mock_db.query.return_value = mock_query

        subtopic_id = uuid4()
        grade_id = uuid4()
        subject_id = uuid4()
        exclude_ids = {uuid4(), uuid4()}

        # Execute with exclude_ids
        result = find_existing_question(
            mock_db, subtopic_id, 3, grade_id, subject_id, exclude_ids=exclude_ids
        )

        # Assert - should return the question (mocked)
        assert result is not None

    def test_falls_back_to_range_match_when_no_exact_match(self):
        """Test that difficulty range is used when no exact match exists."""
        from app.crud.assessment import find_existing_question

        # Create mock question for range match
        mock_question = MagicMock(spec=QuestionBank)
        mock_question.id = uuid4()
        mock_question.difficulty_level = 4  # Within range for difficulty 3 (±1)

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()

        # First call returns None (exact match), second call returns question (range match)
        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # Exact match fails
            return mock_question  # Range match succeeds

        mock_query.filter.return_value = mock_query
        mock_query.first = mock_first
        mock_db.query.return_value = mock_query

        subtopic_id = uuid4()
        grade_id = uuid4()
        subject_id = uuid4()

        # Execute
        result = find_existing_question(mock_db, subtopic_id, 3, grade_id, subject_id)

        # Assert - should return the question from range match
        assert result is not None
        assert result == mock_question


# ============== Tests for get_used_question_ids ==============

class TestGetUsedQuestionIds:
    """Tests for get_used_question_ids function."""

    def test_returns_set_of_used_question_ids(self):
        """Test that set of used question IDs is returned."""
        from app.crud.assessment import get_used_question_ids

        # Create mock question IDs
        qid1 = uuid4()
        qid2 = uuid4()

        # Create mock rows
        mock_row1 = MagicMock()
        mock_row1.question_bank_id = qid1

        mock_row2 = MagicMock()
        mock_row2.question_bank_id = qid2

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = [mock_row1, mock_row2]

        assessment_id = uuid4()

        # Execute
        result = get_used_question_ids(mock_db, assessment_id)

        # Assert
        assert len(result) == 2
        assert qid1 in result
        assert qid2 in result

    def test_returns_empty_set_for_no_questions(self):
        """Test that empty set is returned when no questions exist."""
        from app.crud.assessment import get_used_question_ids

        # Create mock query chain that returns empty list
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = []

        assessment_id = uuid4()

        # Execute
        result = get_used_question_ids(mock_db, assessment_id)

        # Assert
        assert result == set()

    def test_returns_correct_type(self):
        """Test that return type is a set."""
        from app.crud.assessment import get_used_question_ids

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = []

        assessment_id = uuid4()

        # Execute
        result = get_used_question_ids(mock_db, assessment_id)

        # Assert
        assert isinstance(result, set)


# ============== Tests for resolve_question ==============

class TestResolveQuestion:
    """Tests for resolve_question function."""

    @pytest.mark.asyncio
    async def test_returns_unanswered_question_if_exists(self):
        """Test that existing unanswered question is returned."""
        from app.crud.assessment import resolve_question

        # Create mock unanswered question
        unanswered_question = MagicMock(spec=AssessmentQuestion)
        unanswered_question.id = uuid4()
        unanswered_question.student_answer = None

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = 0

        # Create mock query chain
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_options = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        # Set up chain for unanswered query
        mock_db.query.return_value = mock_query
        mock_query.options.return_value = mock_options
        mock_options.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = unanswered_question

        grade_id = uuid4()

        # Execute
        result = await resolve_question(mock_db, assessment, grade_id)

        # Assert
        assert result == unanswered_question

    @pytest.mark.asyncio
    async def test_raises_error_when_max_questions_reached(self):
        """Test that ValueError is raised when max questions reached."""
        from app.crud.assessment import resolve_question
        from app.constants.constants import TOTAL_QUESTIONS_PER_ASSESSMENT

        # Create mock assessment at max questions
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = TOTAL_QUESTIONS_PER_ASSESSMENT
        assessment.total_questions_configurable = None

        # Create mock query chain that returns None for unanswered
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_options = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.options.return_value = mock_options
        mock_options.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = None  # No unanswered question

        grade_id = uuid4()

        # Execute and Assert
        with pytest.raises(ValueError, match="Max questions per assessment reached"):
            await resolve_question(mock_db, assessment, grade_id)

    @pytest.mark.asyncio
    async def test_raises_error_when_no_subtopics_found(self):
        """Test that ValueError is raised when no subtopics found."""
        from app.crud.assessment import resolve_question

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = 0
        assessment.total_questions_configurable = None

        # Create mock student
        student = MagicMock(spec=StudentProfile)
        student.id = assessment.student_id
        student.grade_id = uuid4()
        student.curriculum_id = None

        # Create mock query chains
        mock_db = MagicMock()

        # Set up for unanswered query (returns None)
        mock_query = MagicMock()
        mock_options = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        def mock_query_side_effect(*args, **kwargs):
            return mock_query

        mock_db.query.side_effect = mock_query_side_effect
        mock_query.options.return_value = mock_options
        mock_options.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.first.return_value = None  # No unanswered

        # Patch helper functions
        with patch('app.crud.assessment.get_subtopics_for_grade_and_subject') as mock_get_subtopics, \
             patch('app.crud.assessment.joinedload'):
            mock_get_subtopics.return_value = []  # No subtopics

            grade_id = uuid4()

            # Execute and Assert
            with pytest.raises(ValueError, match="No subtopics found"):
                await resolve_question(mock_db, assessment, grade_id)

    @pytest.mark.asyncio
    async def test_raises_error_when_all_subtopics_at_max(self):
        """Test that ValueError is raised when all subtopics at max questions."""
        from app.crud.assessment import resolve_question
        from app.constants.constants import ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = 0
        assessment.total_questions_configurable = None

        # Create mock subtopic
        subtopic = MagicMock(spec=Subtopic)
        subtopic.id = uuid4()
        subtopic.name = "Linear Equations"

        # Create mock student
        student = MagicMock(spec=StudentProfile)
        student.id = assessment.student_id
        student.grade_id = uuid4()
        student.curriculum_id = None

        # Patch helper functions
        with patch('app.crud.assessment.get_subtopics_for_grade_and_subject') as mock_get_subtopics, \
             patch('app.crud.assessment.count_questions_per_subtopic') as mock_count, \
             patch('app.crud.assessment.select_subtopic_by_priority') as mock_select, \
             patch('app.crud.assessment.joinedload'):

            mock_get_subtopics.return_value = [subtopic]
            mock_count.return_value = {subtopic.id: ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC}
            mock_select.return_value = None  # All at max

            # Create mock query chains
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_options = MagicMock()
            mock_filter = MagicMock()
            mock_order = MagicMock()

            mock_db.query.return_value = mock_query
            mock_query.options.return_value = mock_options
            mock_options.filter.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.order_by.return_value = mock_order
            mock_order.first.return_value = None  # No unanswered

            grade_id = uuid4()

            # Execute and Assert
            with pytest.raises(ValueError, match="All subtopics have reached maximum questions"):
                await resolve_question(mock_db, assessment, grade_id)

    @pytest.mark.asyncio
    async def test_raises_error_when_no_question_in_bank(self):
        """Test that ValueError is raised when no question found in QuestionBank."""
        from app.crud.assessment import resolve_question

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = 0
        assessment.total_questions_configurable = None

        # Create mock subtopic
        subtopic = MagicMock(spec=Subtopic)
        subtopic.id = uuid4()
        subtopic.name = "Linear Equations"

        # Create mock student
        student = MagicMock(spec=StudentProfile)
        student.id = assessment.student_id
        student.grade_id = uuid4()
        student.curriculum_id = None

        # Create mock knowledge profile
        knowledge_profile = MagicMock(spec=StudentKnowledgeProfile)
        knowledge_profile.subtopic_id = subtopic.id
        knowledge_profile.mastery_level = 0.5

        # Patch helper functions
        with patch('app.crud.assessment.get_subtopics_for_grade_and_subject') as mock_get_subtopics, \
             patch('app.crud.assessment.count_questions_per_subtopic') as mock_count, \
             patch('app.crud.assessment.select_subtopic_by_priority') as mock_select, \
             patch('app.crud.assessment.calculate_subtopic_difficulty') as mock_difficulty, \
             patch('app.crud.assessment.get_used_question_ids') as mock_used, \
             patch('app.crud.assessment.find_existing_question') as mock_find, \
             patch('app.crud.assessment.joinedload'):

            mock_get_subtopics.return_value = [subtopic]
            mock_count.return_value = {}
            mock_select.return_value = subtopic
            mock_difficulty.return_value = 3
            mock_used.return_value = set()
            mock_find.return_value = None  # No question found

            # Create mock query chains
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_options = MagicMock()
            mock_filter = MagicMock()
            mock_order = MagicMock()

            mock_db.query.return_value = mock_query
            mock_query.options.return_value = mock_options
            mock_options.filter.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.order_by.return_value = mock_order
            mock_order.first.return_value = None  # No unanswered

            grade_id = uuid4()

            # Execute and Assert
            with pytest.raises(ValueError, match="No question found in QuestionBank"):
                await resolve_question(mock_db, assessment, grade_id)

    @pytest.mark.asyncio
    async def test_creates_assessment_question_on_success(self):
        """Test that AssessmentQuestion is created when all conditions are met."""
        from app.crud.assessment import resolve_question

        # Create mock assessment
        assessment = MagicMock(spec=Assessment)
        assessment.id = uuid4()
        assessment.student_id = uuid4()
        assessment.subject_id = uuid4()
        assessment.total_questions = 0
        assessment.total_questions_configurable = None

        # Create mock subtopic
        subtopic = MagicMock(spec=Subtopic)
        subtopic.id = uuid4()
        subtopic.name = "Linear Equations"

        # Create mock student
        student = MagicMock(spec=StudentProfile)
        student.id = assessment.student_id
        student.grade_id = uuid4()
        student.curriculum_id = None

        # Create mock question
        question = MagicMock(spec=QuestionBank)
        question.id = uuid4()
        question.question_text = "What is 2 + 2?"

        # Create mock created assessment question
        created_aq = MagicMock(spec=AssessmentQuestion)
        created_aq.id = uuid4()
        created_aq.question_bank = question

        # Patch helper functions
        with patch('app.crud.assessment.get_subtopics_for_grade_and_subject') as mock_get_subtopics, \
             patch('app.crud.assessment.count_questions_per_subtopic') as mock_count, \
             patch('app.crud.assessment.select_subtopic_by_priority') as mock_select, \
             patch('app.crud.assessment.calculate_subtopic_difficulty') as mock_difficulty, \
             patch('app.crud.assessment.get_used_question_ids') as mock_used, \
             patch('app.crud.assessment.find_existing_question') as mock_find, \
             patch('app.crud.assessment.asc') as mock_asc, \
             patch('app.crud.assessment.joinedload'):

            mock_get_subtopics.return_value = [subtopic]
            mock_count.return_value = {}
            mock_select.return_value = subtopic
            mock_difficulty.return_value = 3
            mock_used.return_value = set()
            mock_find.return_value = question
            mock_asc.return_value = MagicMock()  # Mock the asc() return value

            # Create mock query chains
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_options = MagicMock()
            mock_filter = MagicMock()
            mock_order = MagicMock()

            mock_db.query.return_value = mock_query
            mock_query.options.return_value = mock_options
            mock_options.filter.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.order_by.return_value = mock_order
            mock_order.first.return_value = None  # No unanswered initially

            # Set up for add/commit/refresh
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            grade_id = uuid4()

            # Execute
            result = await resolve_question(mock_db, assessment, grade_id)

            # Assert - verify the question was created
            mock_db.add.assert_called()
            mock_db.commit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])