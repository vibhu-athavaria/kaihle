"""Unit tests for the onboarding service.

Tests cover:
- Modality score calculations
- Work style extraction
- Interest extraction
- Profile creation and updates
- Onboarding status determination
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import StudentLearningProfile
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole
from app.services.onboarding_service import OnboardingService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def service(mock_db):
    """Create an onboarding service with mock database."""
    return OnboardingService(mock_db)


@pytest.fixture
def student_id():
    """Create a sample student ID."""
    return uuid.uuid4()


@pytest.fixture
def school_id():
    """Create a sample school ID."""
    return uuid.uuid4()


class TestCalculateModalityScores:
    """Tests for modality score calculation."""

    def test_when_visual_answers_then_visual_score_1(self, service):
        """Test that visual answers result in visual=1.0 score."""
        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
            {"question_id": "q2", "answer_key": "see_diagrams"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["visual"] == 1.0
        assert scores["auditory"] == 0.0
        assert scores["reading_writing"] == 0.0
        assert scores["kinesthetic"] == 0.0

    def test_when_kinesthetic_answers_then_kinesthetic_score_1(self, service):
        """Test that kinesthetic answers result in kinesthetic=1.0 score."""
        responses = [
            {"question_id": "q1", "answer_key": "try_it_out"},
            {"question_id": "q2", "answer_key": "do_exercise"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["kinesthetic"] == 1.0
        assert scores["visual"] == 0.0
        assert scores["auditory"] == 0.0
        assert scores["reading_writing"] == 0.0

    def test_when_mixed_answers_then_scores_0_5(self, service):
        """Test that mixed answers result in 0.5 scores for each modality."""
        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
            {"question_id": "q2", "answer_key": "do_exercise"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["visual"] == 0.5
        assert scores["kinesthetic"] == 0.5
        assert scores["auditory"] == 0.0
        assert scores["reading_writing"] == 0.0

    def test_when_auditory_answers_then_auditory_score_1(self, service):
        """Test that auditory answers result in auditory=1.0 score."""
        responses = [
            {"question_id": "q1", "answer_key": "discuss_it"},
            {"question_id": "q2", "answer_key": "hear_explained"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["auditory"] == 1.0
        assert scores["visual"] == 0.0
        assert scores["reading_writing"] == 0.0
        assert scores["kinesthetic"] == 0.0

    def test_when_reading_writing_answers_then_reading_writing_score_1(self, service):
        """Test that reading/writing answers result in reading_writing=1.0 score."""
        responses = [
            {"question_id": "q1", "answer_key": "read_about_it"},
            {"question_id": "q2", "answer_key": "write_notes"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["reading_writing"] == 1.0
        assert scores["visual"] == 0.0
        assert scores["auditory"] == 0.0
        assert scores["kinesthetic"] == 0.0

    def test_when_no_modality_responses_then_all_zero(self, service):
        """Test that missing modality responses result in all zero scores."""
        responses = [
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["visual"] == 0.0
        assert scores["auditory"] == 0.0
        assert scores["reading_writing"] == 0.0
        assert scores["kinesthetic"] == 0.0


class TestCalculateWorkStyle:
    """Tests for work style calculation."""

    def test_when_solo_selected_then_prefers_solo_true(self, service):
        """Test that selecting solo results in prefers_solo=True."""
        responses = [
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "long"},
            {"question_id": "q5", "answer_key": "concept_first"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["prefers_solo"] is True
        assert work_style["short_sessions"] is False
        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_group_selected_then_prefers_solo_false(self, service):
        """Test that selecting group results in prefers_solo=False."""
        responses = [
            {"question_id": "q3", "answer_key": "group"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "task_based"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["prefers_solo"] is False
        assert work_style["short_sessions"] is True
        assert work_style["concept_first"] is False
        assert work_style["task_based"] is True

    def test_when_short_sessions_selected_then_short_sessions_true(self, service):
        """Test that selecting short sessions results in short_sessions=True."""
        responses = [
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "concept_first"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["short_sessions"] is True
        assert work_style["prefers_solo"] is True
        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_concept_first_selected_then_concept_first_true_and_task_based_false(self, service):
        """Test that selecting concept_first results in correct flags."""
        responses = [
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "concept_first"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_task_based_selected_then_concept_first_false_and_task_based_true(self, service):
        """Test that selecting task_based results in correct flags."""
        responses = [
            {"question_id": "q3", "answer_key": "group"},
            {"question_id": "q4", "answer_key": "long"},
            {"question_id": "q5", "answer_key": "task_based"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["concept_first"] is False
        assert work_style["task_based"] is True


class TestExtractInterests:
    """Tests for interest extraction."""

    def test_when_interests_selected_then_interests_stored(self, service):
        """Test that selected interests are stored as lowercase list."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": ["sports", "music"]},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["sports", "music"]

    def test_when_interests_mixed_case_then_lowered(self, service):
        """Test that interests are converted to lowercase."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": ["SPORTS", "Music", "GAMING"]},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["sports", "music", "gaming"]

    def test_when_no_interests_selected_then_empty_list(self, service):
        """Test that no interests results in empty list."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": []},
        ]

        interests = service._extract_interests(responses)

        assert interests == []

    def test_when_no_q6_response_then_empty_list(self, service):
        """Test that missing q6 response results in empty list."""
        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
        ]

        interests = service._extract_interests(responses)

        assert interests == []

    def test_when_all_interests_selected_then_all_stored(self, service):
        """Test that all 10 interests can be selected."""
        all_interests = [
            "sports",
            "music",
            "gaming",
            "animals",
            "cooking",
            "art",
            "technology",
            "nature",
            "fashion",
            "travel",
        ]
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": all_interests},
        ]

        interests = service._extract_interests(responses)

        assert interests == all_interests
        assert len(interests) == 10


@pytest.mark.asyncio
class TestGetOrCreateLearningProfile:
    """Tests for get_or_create_learning_profile method."""

    async def test_when_existing_profile_then_returns_existing(self, service, student_id, school_id):
        """Test that existing profile is returned if found."""
        existing_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=school_id,
            modality_scores={"visual": 0.8},
            work_style={"prefers_solo": True},
            questionnaire_version="v1",
        )

        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_profile
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_or_create_learning_profile(student_id, school_id)

        assert result == existing_profile
        assert result.student_id == student_id
        service.db.commit.assert_not_called()

    async def test_when_no_existing_profile_then_creates_new(self, service, student_id, school_id):
        """Test that new profile is created if not found."""
        # Mock the query result (no existing profile)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)

        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        result = await service.get_or_create_learning_profile(student_id, school_id)

        assert result.student_id == student_id
        assert result.school_id == school_id
        assert result.modality_scores == {}
        assert result.work_style == {}
        assert result.questionnaire_version == "v1"
        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()


@pytest.mark.asyncio
class TestSaveQuestionnaireResponse:
    """Tests for save_questionnaire_response method."""

    async def test_when_resubmitted_then_no_duplicate_row(self, service, student_id, school_id):
        """Test that re-submitting updates existing row instead of creating duplicate."""
        existing_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=school_id,
            modality_scores={},
            work_style={},
            questionnaire_version="v1",
        )

        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
            {"question_id": "q2", "answer_key": "see_diagrams"},
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "concept_first"},
            {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
        ]

        # Mock the database queries
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),  # First call: student profile
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing_profile)),  # Second call: learning profile
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        result = await service.save_questionnaire_response(student_id, responses)

        assert result == existing_profile
        assert result.completed_at is not None
        assert result.modality_scores["visual"] == 1.0
        service.db.add.assert_not_called()  # Should not create new row
        service.db.commit.assert_called_once()

    async def test_when_completed_at_is_set_on_submit(self, service, student_id, school_id):
        """Test that completed_at timestamp is set when submitting."""
        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        user = User(
            id=student_id,
            school_id=school_id,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role=UserRole.STUDENT,
        )

        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
        ]

        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # No existing profile
            MagicMock(scalar_one=MagicMock(return_value=user)),  # User lookup
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        result = await service.save_questionnaire_response(student_id, responses)

        assert result.completed_at is not None
        assert isinstance(result.completed_at, datetime)

    async def test_when_student_profile_not_found_then_raises_value_error(self, service, student_id):
        """Test that ValueError is raised when student profile not found."""
        responses = [{"question_id": "q1", "answer_key": "watch_video"}]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Student profile not found"):
            await service.save_questionnaire_response(student_id, responses)


@pytest.mark.asyncio
class TestGetOnboardingStatus:
    """Tests for get_onboarding_status method."""

    async def test_when_both_complete_then_overall_completed(self, service, student_id):
        """Test that overall=COMPLETED when both profile and diagnostics are done."""
        learning_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=uuid.uuid4(),
            modality_scores={"visual": 1.0},
            completed_at=datetime.now(UTC),
        )

        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=learning_profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is True
        assert status["diagnostics_complete"] is True
        assert status["overall"] == "COMPLETED"

    async def test_when_only_profile_done_then_in_progress(self, service, student_id):
        """Test that overall=IN_PROGRESS when only profile is done."""
        learning_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=uuid.uuid4(),
            modality_scores={"visual": 1.0},
            completed_at=datetime.now(UTC),
        )

        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=learning_profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is True
        assert status["diagnostics_complete"] is False
        assert status["overall"] == "IN_PROGRESS"

    async def test_when_only_diagnostics_done_then_in_progress(self, service, student_id):
        """Test that overall=IN_PROGRESS when only diagnostics are done."""
        learning_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=uuid.uuid4(),
            modality_scores={},
            completed_at=None,
        )

        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.COMPLETED,
        )

        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=learning_profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is False
        assert status["diagnostics_complete"] is True
        assert status["overall"] == "IN_PROGRESS"

    async def test_when_nothing_done_then_pending(self, service, student_id):
        """Test that overall=PENDING when neither is done."""
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # No learning profile
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # No student profile
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is False
        assert status["diagnostics_complete"] is False
        assert status["overall"] == "PENDING"

    async def test_when_learning_profile_no_completed_at_then_not_complete(self, service, student_id):
        """Test that learning profile without completed_at is not considered complete."""
        learning_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=uuid.uuid4(),
            modality_scores={},
            completed_at=None,
        )

        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )

        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=learning_profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is False


@pytest.mark.asyncio
class TestVerifyTeacherStudentRelationship:
    """Tests for verify_teacher_student_relationship method."""

    async def test_when_student_in_teacher_class_then_returns_true(self, service):
        """Test that relationship is verified when student is in teacher's class."""
        teacher_id = uuid.uuid4()
        student_id = uuid.uuid4()

        # Mock enrollment found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Enrollment exists
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.verify_teacher_student_relationship(teacher_id, student_id)

        assert result is True

    async def test_when_student_not_in_teacher_class_then_returns_false(self, service):
        """Test that relationship is not verified when student is not in teacher's class."""
        teacher_id = uuid.uuid4()
        student_id = uuid.uuid4()

        # Mock no enrollment found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.verify_teacher_student_relationship(teacher_id, student_id)

        assert result is False
