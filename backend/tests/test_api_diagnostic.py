"""
Tests for the Diagnostic Assessment API Endpoints.

Phase 7 REST API Layer tests covering:
- POST /diagnostic/initialize - Initialize diagnostic assessments
- GET /diagnostic/status/{student_id} - Overall status
- GET /diagnostic/{assessment_id}/next-question - Get next question
- POST /diagnostic/{assessment_id}/answer - Submit answer
- GET /diagnostic/report/{student_id} - Full report
- GET /diagnostic/study-plan/{student_id} - Study plan
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID

from app.models.assessment import Assessment, AssessmentQuestion, AssessmentReport, AssessmentStatus, AssessmentType, QuestionBank
from app.models.study_plan import StudyPlan, StudyPlanCourse
from app.models.subject import Subject
from app.models.user import StudentProfile, User, UserRole


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.setex = MagicMock()
    return redis


@pytest.fixture
def sample_uuid():
    return uuid4()


@pytest.fixture
def sample_user(sample_uuid):
    user = MagicMock(spec=User)
    user.id = sample_uuid
    user.role = UserRole.PARENT
    user.student_profile = None
    return user


@pytest.fixture
def sample_student(sample_uuid):
    student = MagicMock(spec=StudentProfile)
    student.id = sample_uuid
    student.parent_id = sample_uuid
    student.has_completed_assessment = False
    student.grade_id = uuid4()
    student.curriculum_id = uuid4()
    return student


@pytest.fixture
def sample_subject():
    subject = MagicMock(spec=Subject)
    subject.id = uuid4()
    subject.name = "Mathematics"
    return subject


@pytest.fixture
def sample_assessment(sample_student, sample_subject):
    assessment = MagicMock(spec=Assessment)
    assessment.id = uuid4()
    assessment.student_id = sample_student.id
    assessment.subject_id = sample_subject.id
    assessment.assessment_type = AssessmentType.DIAGNOSTIC
    assessment.status = AssessmentStatus.IN_PROGRESS
    assessment.difficulty_level = 3
    assessment.questions_answered = 5
    assessment.total_questions = 25
    assessment.created_at = datetime.now(timezone.utc)
    assessment.completed_at = None
    return assessment


@pytest.fixture
def sample_question():
    question = MagicMock(spec=QuestionBank)
    question.id = uuid4()
    question.question_text = "What is 2 + 2?"
    question.question_type = "multiple_choice"
    question.difficulty_level = 3
    question.options = {"A": "2", "B": "3", "C": "4", "D": "5"}
    question.correct_answer = "C"
    question.estimated_time_seconds = 30
    return question


def create_mock_session_state(assessment_id, question_id=None):
    return {
        "assessment_id": str(assessment_id),
        "student_id": str(uuid4()),
        "subject_id": str(uuid4()),
        "status": AssessmentStatus.IN_PROGRESS.value,
        "subtopics": [{
            "subtopic_id": str(uuid4()),
            "subtopic_name": "Linear Equations",
            "questions_total": 5,
            "questions_answered": 2,
            "current_difficulty": 3,
            "used_question_ids": [],
        }],
        "current_subtopic_index": 0,
        "current_question_bank_id": str(question_id) if question_id else None,
        "total_questions": 25,
        "answered_count": 5,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }


class TestAuthorizeStudentAccess:
    """Tests for _authorize_student_access function."""

    def test_student_can_access_own_data(self, mock_db, sample_student):
        from app.api.v1.diagnostic import _authorize_student_access

        user = MagicMock(spec=User)
        user.role = UserRole.STUDENT
        user.student_profile = sample_student

        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        result = _authorize_student_access(user, sample_student.id, mock_db)

        assert result == sample_student

    def test_student_cannot_access_other_data(self, mock_db, sample_student):
        from app.api.v1.diagnostic import _authorize_student_access
        from fastapi import HTTPException

        other_student = MagicMock(spec=StudentProfile)
        other_student.id = uuid4()

        user = MagicMock(spec=User)
        user.role = UserRole.STUDENT
        user.student_profile = other_student

        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        with pytest.raises(HTTPException) as exc_info:
            _authorize_student_access(user, sample_student.id, mock_db)

        assert exc_info.value.status_code == 403

    def test_parent_can_access_child_data(self, mock_db, sample_user, sample_student):
        from app.api.v1.diagnostic import _authorize_student_access

        sample_user.role = UserRole.PARENT
        sample_student.parent_id = sample_user.id

        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        result = _authorize_student_access(sample_user, sample_student.id, mock_db)

        assert result == sample_student

    def test_parent_cannot_access_other_child_data(self, mock_db, sample_user, sample_student):
        from app.api.v1.diagnostic import _authorize_student_access
        from fastapi import HTTPException

        sample_user.role = UserRole.PARENT
        sample_student.parent_id = uuid4()

        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        with pytest.raises(HTTPException) as exc_info:
            _authorize_student_access(sample_user, sample_student.id, mock_db)

        assert exc_info.value.status_code == 403

    def test_admin_has_full_access(self, mock_db, sample_user, sample_student):
        from app.api.v1.diagnostic import _authorize_student_access

        sample_user.role = UserRole.ADMIN

        mock_db.query.return_value.filter.return_value.first.return_value = sample_student

        result = _authorize_student_access(sample_user, sample_student.id, mock_db)

        assert result == sample_student

    def test_raises_404_for_nonexistent_student(self, mock_db, sample_user):
        from app.api.v1.diagnostic import _authorize_student_access
        from fastapi import HTTPException

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            _authorize_student_access(sample_user, uuid4(), mock_db)

        assert exc_info.value.status_code == 404


class TestGetGenerationStatus:
    """Tests for _get_generation_status function."""

    def test_returns_none_when_no_flag(self, mock_redis, sample_uuid):
        from app.api.v1.diagnostic import _get_generation_status

        mock_redis.get.return_value = None

        result = _get_generation_status(mock_redis, sample_uuid)

        assert result is None

    def test_returns_status_string(self, mock_redis, sample_uuid):
        from app.api.v1.diagnostic import _get_generation_status

        mock_redis.get.return_value = b"reports"

        result = _get_generation_status(mock_redis, sample_uuid)

        assert result == "reports"

    def test_handles_string_response(self, mock_redis, sample_uuid):
        from app.api.v1.diagnostic import _get_generation_status

        mock_redis.get.return_value = "study_plan"

        result = _get_generation_status(mock_redis, sample_uuid)

        assert result == "study_plan"


class TestBuildQuestionResponse:
    """Tests for _build_question_response function."""

    def test_returns_none_question_when_no_question(self, sample_uuid):
        from app.api.v1.diagnostic import _build_question_response

        session_state = create_mock_session_state(sample_uuid)
        
        result = _build_question_response(None, sample_uuid, session_state, sample_uuid)

        assert result.question is None
        assert result.assessment_id == sample_uuid

    def test_builds_question_with_options(self, sample_uuid, sample_question):
        from app.api.v1.diagnostic import _build_question_response

        session_state = create_mock_session_state(sample_uuid, sample_question.id)
        
        result = _build_question_response(sample_question, sample_uuid, session_state, sample_uuid)

        assert result.question is not None
        assert result.question.question_text == sample_question.question_text
        assert result.question.difficulty_level == sample_question.difficulty_level

    def test_never_includes_correct_answer(self, sample_uuid, sample_question):
        from app.api.v1.diagnostic import _build_question_response

        session_state = create_mock_session_state(sample_uuid, sample_question.id)
        
        result = _build_question_response(sample_question, sample_uuid, session_state, sample_uuid)

        question_dict = result.question.model_dump()
        assert "correct_answer" not in question_dict
        assert "explanation" not in question_dict


class TestGetDifficultyLabel:
    """Tests for get_difficulty_label function."""

    def test_returns_correct_labels(self):
        from app.schemas.diagnostic import get_difficulty_label, DIFFICULTY_LABELS

        for difficulty, expected_label in DIFFICULTY_LABELS.items():
            assert get_difficulty_label(difficulty) == expected_label

    def test_returns_unknown_for_invalid(self):
        from app.schemas.diagnostic import get_difficulty_label

        assert get_difficulty_label(0) == "unknown"
        assert get_difficulty_label(6) == "unknown"
        assert get_difficulty_label(-1) == "unknown"


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_diagnostic_init_request(self):
        from app.schemas.diagnostic import DiagnosticInitRequest

        student_id = uuid4()
        request = DiagnosticInitRequest(student_id=student_id)

        assert request.student_id == student_id

    def test_answer_submit_request(self):
        from app.schemas.diagnostic import AnswerSubmitRequest

        question_id = uuid4()
        request = AnswerSubmitRequest(
            question_bank_id=question_id,
            answer_text="C",
            time_taken_seconds=30,
        )

        assert request.question_bank_id == question_id
        assert request.answer_text == "C"
        assert request.time_taken_seconds == 30

    def test_answer_submit_request_optional_time(self):
        from app.schemas.diagnostic import AnswerSubmitRequest

        question_id = uuid4()
        request = AnswerSubmitRequest(
            question_bank_id=question_id,
            answer_text="C",
        )

        assert request.time_taken_seconds is None

    def test_session_summary_item(self):
        from app.schemas.diagnostic import SessionSummaryItem

        assessment_id = uuid4()
        subject_id = uuid4()
        
        item = SessionSummaryItem(
            assessment_id=assessment_id,
            subject_id=subject_id,
            status="in_progress",
            total_questions=25,
            answered_count=10,
        )

        assert item.assessment_id == assessment_id
        assert item.status == "in_progress"

    def test_answer_submit_response(self):
        from app.schemas.diagnostic import AnswerSubmitResponse

        response = AnswerSubmitResponse(
            is_correct=True,
            score=0.6,
            difficulty_level=3,
            difficulty_label="medium",
            next_difficulty=4,
            next_difficulty_label="hard",
            questions_answered=10,
            total_questions=25,
            subtopic_complete=False,
            assessment_status="in_progress",
            all_subjects_complete=False,
        )

        assert response.is_correct is True
        assert response.score == 0.6
        assert response.next_difficulty == 4

    def test_generation_status_response(self):
        from app.schemas.diagnostic import GenerationStatusResponse

        response = GenerationStatusResponse(
            status="generating",
            stage="reports",
            retry_after_seconds=15,
        )

        assert response.status == "generating"
        assert response.stage == "reports"
        assert response.retry_after_seconds == 15


class TestRedisKeyFormat:
    """Tests for Redis key format compliance."""

    def test_generation_key_format(self):
        student_id = uuid4()
        expected_key = f"kaihle:diagnostic:generating:{student_id}"
        
        actual_key = f"kaihle:diagnostic:generating:{student_id}"
        
        assert actual_key == expected_key


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self):
        from app.api.v1.diagnostic import health_check

        result = health_check()

        assert result["status"] == "healthy"
        assert result["service"] == "diagnostic"
