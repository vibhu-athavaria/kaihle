"""
Tests for the Diagnostic REST API Layer.

This module tests the endpoints:
1. POST /diagnostic/initialize - Initialize diagnostic assessments
2. GET /diagnostic/status/{student_id} - Get overall status
3. GET /diagnostic/{assessment_id}/next-question - Get next question
4. POST /diagnostic/{assessment_id}/answer - Submit answer
5. GET /diagnostic/report/{student_id} - Get diagnostic report
6. GET /diagnostic/study-plan/{student_id} - Get study plan
7. POST /diagnostic/{assessment_id}/abandon - Abandon assessment
8. GET /diagnostic/health - Health check

Uses mocking to test endpoint logic without TestClient.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1 import diagnostic
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType, QuestionBank
from app.models.user import StudentProfile, User, UserRole
from app.schemas.diagnostic import (
    AnswerSubmitRequest,
    DiagnosticInitRequest,
    get_difficulty_label,
    DIFFICULTY_LABELS,
)
from app.services.diagnostic.session_manager import DiagnosticSessionManager
from app.services.diagnostic.response_handler import DiagnosticResponseHandler, AnswerResult


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.setex = MagicMock()
    redis.delete = MagicMock()
    return redis


@pytest.fixture
def sample_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "parent@test.com"
    user.full_name = "Test Parent"
    user.role = UserRole.PARENT
    user.is_active = True
    return user


@pytest.fixture
def sample_admin_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "admin@test.com"
    user.full_name = "Test Admin"
    user.role = UserRole.ADMIN
    user.is_active = True
    return user


@pytest.fixture
def sample_student(sample_user):
    student = MagicMock(spec=StudentProfile)
    student.id = uuid4()
    student.user_id = uuid4()
    student.parent_id = sample_user.id
    student.grade_id = uuid4()
    student.curriculum_id = uuid4()
    student.has_completed_assessment = False
    return student


@pytest.fixture
def sample_assessment(sample_student):
    assessment = MagicMock(spec=Assessment)
    assessment.id = uuid4()
    assessment.student_id = sample_student.id
    assessment.subject_id = uuid4()
    assessment.assessment_type = AssessmentType.DIAGNOSTIC
    assessment.status = AssessmentStatus.IN_PROGRESS
    assessment.questions_answered = 2
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
    question.correct_answer = "4"
    question.options = {"A": "3", "B": "4", "C": "5", "D": "6"}
    question.estimated_time_seconds = 60
    return question


@pytest.fixture
def sample_subject():
    from app.models.subject import Subject
    subject = MagicMock(spec=Subject)
    subject.id = uuid4()
    subject.name = "Mathematics"
    return subject


@pytest.fixture
def sample_session_state(sample_assessment, sample_question):
    return {
        "assessment_id": str(sample_assessment.id),
        "student_id": str(sample_assessment.student_id),
        "subject_id": str(sample_assessment.subject_id),
        "status": AssessmentStatus.IN_PROGRESS.value,
        "subtopics": [{
            "subtopic_id": str(uuid4()),
            "subtopic_name": "Test Subtopic",
            "questions_total": 5,
            "questions_answered": 2,
            "current_difficulty": 3,
            "used_question_ids": [],
        }],
        "current_subtopic_index": 0,
        "current_question_bank_id": str(sample_question.id),
        "total_questions": 15,
        "answered_count": 2,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }


class TestHealthEndpoint:
    """Tests for GET /diagnostic/health"""

    def test_health_check_returns_healthy(self):
        result = diagnostic.health_check()
        assert result == {"status": "healthy", "service": "diagnostic"}


class TestAuthorizeStudentAccess:
    """Tests for _authorize_student_access helper"""

    def test_authorize_parent_access_success(self, mock_db, sample_user, sample_student):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_student
        mock_db.query.return_value = mock_query

        result = diagnostic._authorize_student_access(sample_user, sample_student.id, mock_db)

        assert result == sample_student

    def test_authorize_admin_access_success(self, mock_db, sample_admin_user, sample_student):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_student
        mock_db.query.return_value = mock_query

        result = diagnostic._authorize_student_access(sample_admin_user, sample_student.id, mock_db)

        assert result == sample_student

    def test_authorize_student_not_found(self, mock_db, sample_user):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            diagnostic._authorize_student_access(sample_user, uuid4(), mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_authorize_unauthorized_parent(self, mock_db, sample_user, sample_student):
        sample_student.parent_id = uuid4()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_student
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            diagnostic._authorize_student_access(sample_user, sample_student.id, mock_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestGetGenerationStatus:
    """Tests for _get_generation_status helper"""

    def test_get_generation_status_none(self, mock_redis, sample_student):
        mock_redis.get.return_value = None
        result = diagnostic._get_generation_status(mock_redis, sample_student.id)
        assert result is None

    def test_get_generation_status_reports(self, mock_redis, sample_student):
        mock_redis.get.return_value = b"reports"
        result = diagnostic._get_generation_status(mock_redis, sample_student.id)
        assert result == "reports"

    def test_get_generation_status_string(self, mock_redis, sample_student):
        mock_redis.get.return_value = "complete"
        result = diagnostic._get_generation_status(mock_redis, sample_student.id)
        assert result == "complete"


class TestBuildQuestionResponse:
    """Tests for _build_question_response helper"""

    def test_build_question_response_with_question(self, sample_question, sample_session_state, sample_assessment):
        result = diagnostic._build_question_response(sample_question, sample_assessment.id, sample_session_state, sample_assessment.subject_id)

        assert result.assessment_id == sample_assessment.id
        assert result.question is not None
        assert result.question.question_id == sample_question.id
        assert result.question.question_text == sample_question.question_text
        assert result.question.difficulty_level == sample_question.difficulty_level
        assert result.question.difficulty_label == get_difficulty_label(sample_question.difficulty_level)
        assert result.question.options is not None
        assert len(result.question.options) == 4

    def test_build_question_response_without_question(self, sample_session_state, sample_assessment):
        result = diagnostic._build_question_response(None, sample_assessment.id, sample_session_state, sample_assessment.subject_id)

        assert result.assessment_id == sample_assessment.id
        assert result.question is None
        assert result.status == AssessmentStatus.IN_PROGRESS.value

    def test_build_question_response_completed_session(self, sample_question, sample_session_state, sample_assessment):
        sample_session_state["status"] = AssessmentStatus.COMPLETED.value
        result = diagnostic._build_question_response(None, sample_assessment.id, sample_session_state, sample_assessment.subject_id)

        assert result.question is None
        assert result.status == AssessmentStatus.COMPLETED.value

    def test_build_question_response_includes_subtopics(self, sample_question, sample_session_state, sample_assessment):
        result = diagnostic._build_question_response(sample_question, sample_assessment.id, sample_session_state, sample_assessment.subject_id)

        assert len(result.subtopics) == 1
        assert result.subtopics[0].subtopic_name == "Test Subtopic"
        assert result.subtopics[0].current_difficulty == 3
        assert result.subtopics[0].difficulty_label == "medium"


class TestInitializeDiagnostic:
    """Tests for POST /diagnostic/initialize"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "initialize_diagnostic")
    def test_initialize_diagnostic_success(
        self, mock_init, mock_get_redis, mock_db, sample_user, sample_student, sample_subject, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        subject_id = uuid4()

        mock_init.return_value = {
            "sessions": [{
                "assessment_id": uuid4(),
                "subject_id": subject_id,
                "status": "started",
                "total_questions": 15,
                "answered_count": 0,
                "current_subtopic_index": 0,
                "subtopics_count": 3,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }],
            "student_id": sample_student.id,
            "grade_id": sample_student.grade_id,
            "curriculum_id": sample_student.curriculum_id,
            "existing": False,
        }

        sample_subject.id = subject_id

        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if model.__name__ == "Subject":
                mock_query.filter.return_value.first.return_value = sample_subject
            return mock_query

        mock_db.query.side_effect = mock_query_side_effect

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = DiagnosticInitRequest(student_id=sample_student.id)
            result = diagnostic.initialize_diagnostic(payload, mock_db, sample_user)

        assert result.student_id == sample_student.id
        assert result.existing is False
        assert len(result.sessions) == 1

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "initialize_diagnostic")
    def test_initialize_diagnostic_missing_grade(
        self, mock_init, mock_get_redis, mock_db, sample_user, sample_student, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        mock_init.side_effect = ValueError("Student profile missing grade_id")

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = DiagnosticInitRequest(student_id=sample_student.id)
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.initialize_diagnostic(payload, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestGetNextQuestion:
    """Tests for GET /diagnostic/{assessment_id}/next-question"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_current_question")
    def test_get_next_question_success(
        self, mock_get_q, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_question, sample_session_state, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        mock_get_q.return_value = (sample_question, sample_session_state)

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert result.assessment_id == sample_assessment.id
        assert result.question is not None
        assert result.question.question_id == sample_question.id

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_get_next_question_assessment_not_found(
        self, mock_get_redis, mock_db, sample_user, mock_redis
    ):
        mock_get_redis.return_value = mock_redis

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            diagnostic.get_next_question(uuid4(), mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_get_next_question_wrong_assessment_type(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.assessment_type = AssessmentType.PROGRESS
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "only for diagnostic assessments" in exc_info.value.detail

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_get_next_question_completed_assessment(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.status = AssessmentStatus.COMPLETED
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert result.status_code == status.HTTP_204_NO_CONTENT

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_get_next_question_abandoned_assessment(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.status = AssessmentStatus.ABANDONED
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "abandoned" in exc_info.value.detail

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_current_question")
    def test_get_next_question_returns_none_when_complete(
        self, mock_get_q, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_get_q.return_value = (None, sample_session_state)

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert result.status_code == status.HTTP_204_NO_CONTENT


class TestSubmitAnswer:
    """Tests for POST /diagnostic/{assessment_id}/answer"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    @patch.object(DiagnosticResponseHandler, "submit_answer")
    def test_submit_answer_correct(
        self, mock_submit, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_get_state.return_value = sample_session_state

        answer_result = AnswerResult(
            is_correct=True,
            score=0.6,
            difficulty_level=3,
            next_difficulty=4,
            questions_answered=3,
            total_questions=15,
            subtopic_complete=False,
            assessment_status=AssessmentStatus.IN_PROGRESS.value,
            all_subjects_complete=False,
        )
        mock_submit.return_value = answer_result

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="4", time_taken_seconds=30)
            result = diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert result.is_correct is True
        assert result.score == 0.6
        assert result.next_difficulty == 4

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    @patch.object(DiagnosticResponseHandler, "submit_answer")
    def test_submit_answer_incorrect(
        self, mock_submit, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_get_state.return_value = sample_session_state

        answer_result = AnswerResult(
            is_correct=False,
            score=0.0,
            difficulty_level=3,
            next_difficulty=2,
            questions_answered=3,
            total_questions=15,
            subtopic_complete=False,
            assessment_status=AssessmentStatus.IN_PROGRESS.value,
            all_subjects_complete=False,
        )
        mock_submit.return_value = answer_result

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="5", time_taken_seconds=None)
            result = diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert result.is_correct is False
        assert result.score == 0.0
        assert result.next_difficulty == 2

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    @patch.object(DiagnosticResponseHandler, "submit_answer")
    def test_submit_answer_already_answered(
        self, mock_submit, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_get_state.return_value = sample_session_state
        mock_submit.side_effect = ValueError("Question has already been answered")

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="4", time_taken_seconds=None)
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    def test_submit_answer_no_current_question(
        self, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        sample_session_state["current_question_bank_id"] = None
        mock_get_state.return_value = sample_session_state

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="4", time_taken_seconds=None)
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "No current question" in exc_info.value.detail

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_submit_answer_completed_assessment(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.status = AssessmentStatus.COMPLETED
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="4", time_taken_seconds=None)
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already completed" in exc_info.value.detail


class TestGetDiagnosticStatus:
    """Tests for GET /diagnostic/status/{student_id}"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    def test_get_status_success(
        self, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, sample_subject, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        mock_get_state.return_value = sample_session_state
        sample_subject.id = sample_assessment.subject_id

        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if model.__name__ == "StudentProfile":
                mock_query.filter.return_value.first.return_value = sample_student
            elif model.__name__ == "Assessment":
                mock_query.filter.return_value.all.return_value = [sample_assessment]
            elif model.__name__ == "Subject":
                mock_query.filter.return_value.first.return_value = sample_subject
            return mock_query

        mock_db.query.side_effect = mock_query_side_effect

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_diagnostic_status(sample_student.id, mock_db, sample_user)

        assert result.student_id == sample_student.id
        assert result.has_completed_assessment is False
        assert len(result.subjects) == 1

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    def test_get_status_with_generation_in_progress(
        self, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, sample_subject, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = b"reports"
        mock_get_state.return_value = sample_session_state
        sample_subject.id = sample_assessment.subject_id

        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if model.__name__ == "StudentProfile":
                mock_query.filter.return_value.first.return_value = sample_student
            elif model.__name__ == "Assessment":
                mock_query.filter.return_value.all.return_value = [sample_assessment]
            elif model.__name__ == "Subject":
                mock_query.filter.return_value.first.return_value = sample_subject
            return mock_query

        mock_db.query.side_effect = mock_query_side_effect

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_diagnostic_status(sample_student.id, mock_db, sample_user)

        assert result.generation_status == "reports"
        assert result.generation_status_label == "Generating reports"

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_get_status_student_not_found(
        self, mock_get_redis, mock_db, sample_user, mock_redis
    ):
        mock_get_redis.return_value = mock_redis

        with patch("app.api.v1.diagnostic._authorize_student_access") as mock_check:
            mock_check.side_effect = HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.get_diagnostic_status(uuid4(), mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    def test_get_status_no_assessments(
        self, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, mock_redis
    ):
        mock_get_redis.return_value = mock_redis

        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if model.__name__ == "StudentProfile":
                mock_query.filter.return_value.first.return_value = sample_student
            elif model.__name__ == "Assessment":
                mock_query.filter.return_value.all.return_value = []
            return mock_query

        mock_db.query.side_effect = mock_query_side_effect

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_diagnostic_status(sample_student.id, mock_db, sample_user)

        assert len(result.subjects) == 0
        assert result.overall_status == "not_started"


class TestAbandonAssessment:
    """Tests for POST /diagnostic/{assessment_id}/abandon"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "abandon_session")
    def test_abandon_success(
        self, mock_abandon, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_abandon.return_value = {"status": AssessmentStatus.ABANDONED.value}

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.abandon_assessment(sample_assessment.id, mock_db, sample_user)

        assert result.status == "abandoned"
        assert "abandoned successfully" in result.message

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_abandon_assessment_not_found(
        self, mock_get_redis, mock_db, sample_user, mock_redis
    ):
        mock_get_redis.return_value = mock_redis

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            diagnostic.abandon_assessment(uuid4(), mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_abandon_already_completed(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.status = AssessmentStatus.COMPLETED
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.abandon_assessment(sample_assessment.id, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot abandon a completed" in exc_info.value.detail

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_abandon_already_abandoned(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.status = AssessmentStatus.ABANDONED
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.abandon_assessment(sample_assessment.id, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already abandoned" in exc_info.value.detail

    @patch("app.api.v1.diagnostic.get_redis_client")
    def test_abandon_non_diagnostic_assessment(
        self, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.assessment_type = AssessmentType.PROGRESS
        sample_assessment.student = sample_student

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            with pytest.raises(HTTPException) as exc_info:
                diagnostic.abandon_assessment(sample_assessment.id, mock_db, sample_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "only for diagnostic" in exc_info.value.detail


class TestDifficultyLabels:
    """Tests for difficulty label mapping"""

    def test_difficulty_label_mapping(self):
        assert DIFFICULTY_LABELS[1] == "beginner"
        assert DIFFICULTY_LABELS[2] == "easy"
        assert DIFFICULTY_LABELS[3] == "medium"
        assert DIFFICULTY_LABELS[4] == "hard"
        assert DIFFICULTY_LABELS[5] == "expert"

    def test_get_difficulty_label(self):
        assert get_difficulty_label(1) == "beginner"
        assert get_difficulty_label(3) == "medium"
        assert get_difficulty_label(5) == "expert"
        assert get_difficulty_label(0) == "unknown"
        assert get_difficulty_label(6) == "unknown"

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_current_question")
    def test_difficulty_labels_in_response(
        self, mock_get_q, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_question, sample_session_state, mock_redis
    ):
        mock_get_redis.return_value = mock_redis
        sample_question.difficulty_level = 1
        sample_assessment.student = sample_student
        sample_session_state["subtopics"][0]["current_difficulty"] = 1
        mock_get_q.return_value = (sample_question, sample_session_state)

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            result = diagnostic.get_next_question(sample_assessment.id, mock_db, sample_user)

        assert result.question is not None
        assert result.question.difficulty_label == "beginner"
        assert result.subtopics[0].difficulty_label == "beginner"


class TestAllSubjectsComplete:
    """Tests for all_subjects_complete flag in answer response"""

    @patch("app.api.v1.diagnostic.get_redis_client")
    @patch.object(DiagnosticSessionManager, "get_session_state")
    @patch.object(DiagnosticResponseHandler, "submit_answer")
    def test_all_subjects_complete_flag(
        self, mock_submit, mock_get_state, mock_get_redis, mock_db, sample_user, sample_student, sample_assessment, sample_session_state, mock_redis, sample_question
    ):
        mock_get_redis.return_value = mock_redis
        sample_assessment.student = sample_student
        mock_get_state.return_value = sample_session_state

        answer_result = AnswerResult(
            is_correct=True,
            score=0.6,
            difficulty_level=3,
            next_difficulty=4,
            questions_answered=15,
            total_questions=15,
            subtopic_complete=True,
            assessment_status=AssessmentStatus.COMPLETED.value,
            all_subjects_complete=True,
        )
        mock_submit.return_value = answer_result

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_assessment
        mock_db.query.return_value = mock_query

        with patch("app.api.v1.diagnostic._authorize_student_access", return_value=sample_student):
            payload = AnswerSubmitRequest(question_bank_id=sample_question.id, answer_text="4", time_taken_seconds=None)
            result = diagnostic.submit_answer(sample_assessment.id, payload, mock_db, sample_user)

        assert result.all_subjects_complete is True
        assert result.assessment_status == AssessmentStatus.COMPLETED.value