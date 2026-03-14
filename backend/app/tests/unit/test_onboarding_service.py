"""Unit tests for the onboarding service.

Tests cover:
- Modality score calculations
- Work style extraction
- Interest extraction
- Profile creation and updates
- Onboarding status determination
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import StudentLearningProfile
from app.models.user import StudentProfile
from app.services.onboarding_service import OnboardingService


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def service(mock_db: MagicMock) -> OnboardingService:
    """Create an onboarding service with mock database."""
    return OnboardingService(mock_db)


@pytest.fixture
def student_id() -> uuid.UUID:
    """Create a sample student ID."""
    return uuid.uuid4()


@pytest.fixture
def school_id() -> uuid.UUID:
    """Create a sample school ID."""
    return uuid.uuid4()


class TestCalculateModalityScores:
    """Tests for modality score calculation."""

    def test_when_visual_answers_then_visual_score_1(self, service: OnboardingService) -> None:
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

    def test_when_kinesthetic_answers_then_kinesthetic_score_1(self, service: OnboardingService) -> None:
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

    def test_when_mixed_answers_then_scores_0_5(self, service: OnboardingService) -> None:
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

    def test_when_auditory_answers_then_auditory_score_1(self, service: OnboardingService) -> None:
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

    def test_when_reading_writing_answers_then_reading_writing_score_1(self, service: OnboardingService) -> None:
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

    def test_when_no_modality_responses_then_all_zero(self, service: OnboardingService) -> None:
        """Test that missing modality responses result in all zero scores."""
        responses: list[dict[str, Any]] = [
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

    def test_when_solo_selected_then_prefers_solo_true(self, service: OnboardingService) -> None:
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

    def test_when_group_selected_then_prefers_solo_false(self, service: OnboardingService) -> None:
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

    def test_when_short_sessions_selected_then_short_sessions_true(self, service: OnboardingService) -> None:
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

    def test_when_concept_first_selected_then_concept_first_true_and_task_based_false(
        self, service: OnboardingService
    ) -> None:
        """Test that selecting concept_first results in correct flags."""
        responses = [
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "concept_first"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_task_based_selected_then_concept_first_false_and_task_based_true(
        self, service: OnboardingService
    ) -> None:
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

    def test_when_interests_selected_then_interests_stored(self, service: OnboardingService) -> None:
        """Test that selected interests are stored as lowercase list."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": ["sports", "music"]},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["sports", "music"]

    def test_when_interests_mixed_case_then_lowered(self, service: OnboardingService) -> None:
        """Test that interests are converted to lowercase."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": ["SPORTS", "Music", "GAMING"]},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["sports", "music", "gaming"]

    def test_when_no_interests_selected_then_empty_list(self, service: OnboardingService) -> None:
        """Test that no interests results in empty list."""
        responses = [
            {"question_id": "q6_to_q10", "answer_keys": []},
        ]

        interests = service._extract_interests(responses)

        assert interests == []

    def test_when_no_q6_response_then_empty_list(self, service: OnboardingService) -> None:
        """Test that missing q6 response results in empty list."""
        responses = [
            {"question_id": "q1", "answer_key": "watch_video"},
        ]

        interests = service._extract_interests(responses)

        assert interests == []

    def test_when_all_interests_selected_then_all_stored(self, service: OnboardingService) -> None:
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

    async def test_when_existing_profile_then_returns_existing(
        self, service: OnboardingService, student_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
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
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.get_or_create_learning_profile(student_id, school_id)

        assert result == existing_profile
        assert result.student_id == student_id
        service.db.commit.assert_not_called()  # type: ignore[attr-defined]

    async def test_when_no_existing_profile_then_creates_new(
        self, service: OnboardingService, student_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Test that new profile is created if not found."""
        # Mock the query result (no existing profile)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        service.db.commit = AsyncMock()  # type: ignore[method-assign]
        service.db.refresh = AsyncMock()  # type: ignore[method-assign]

        result = await service.get_or_create_learning_profile(student_id, school_id)

        assert result.student_id == student_id
        assert result.school_id == school_id
        assert result.modality_scores == {}
        assert result.work_style == {}
        assert result.questionnaire_version == "v1"
        service.db.add.assert_called_once()  # type: ignore[attr-defined]
        service.db.commit.assert_called_once()


@pytest.mark.asyncio
class TestSaveQuestionnaireResponse:
    """Tests for save_questionnaire_response method."""

    async def test_when_resubmitted_then_no_duplicate_row(
        self, service: OnboardingService, student_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Test that re-submitting updates existing row instead of creating duplicate."""
        existing_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=school_id,
            modality_scores={},
            work_style={},
            questionnaire_version="v1",
        )

        # StudentProfile no longer has onboarding_diagnostic_status (moved to class_enrollments in v2.1)
        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
        )

        responses: list[dict[str, Any]] = [
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
        service.db.execute = AsyncMock(side_effect=mock_results)  # type: ignore[method-assign]
        service.db.commit = AsyncMock()  # type: ignore[method-assign]
        service.db.refresh = AsyncMock()  # type: ignore[method-assign]

        result = await service.save_questionnaire_response(student_id, responses)

        assert result == existing_profile
        assert result.completed_at is not None
        assert result.modality_scores["visual"] == 1.0
        service.db.add.assert_not_called()  # type: ignore[attr-defined]  # Should not create new row
        assert service.db.commit.call_count == 2  # type: ignore[attr-defined]  # Once for profile, once for is_learning_profile_complete

    async def test_when_completed_at_is_set_on_submit(
        self, service: OnboardingService, student_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Test that completed_at timestamp is set when submitting."""
        # StudentProfile no longer has onboarding_diagnostic_status (moved to class_enrollments in v2.1)
        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
        )

        responses: list[dict[str, Any]] = [
            {"question_id": "q1", "answer_key": "watch_video"},
            {"question_id": "q2", "answer_key": "see_diagrams"},
            {"question_id": "q3", "answer_key": "solo"},
            {"question_id": "q4", "answer_key": "short"},
            {"question_id": "q5", "answer_key": "concept_first"},
            {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
        ]

        # Create existing profile for the second call
        existing_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=school_id,
            modality_scores={},
            work_style={},
            questionnaire_version="v1",
        )

        # Mock the database queries
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),  # First call: student profile
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing_profile)),  # Second call: learning profile
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)  # type: ignore[method-assign]
        service.db.commit = AsyncMock()  # type: ignore[method-assign]
        service.db.refresh = AsyncMock()  # type: ignore[method-assign]

        result = await service.save_questionnaire_response(student_id, responses)

        assert result == existing_profile
        assert result.completed_at is not None
        assert result.modality_scores["visual"] == 1.0
        service.db.add.assert_not_called()  # type: ignore[attr-defined]  # Should not create new row
        assert service.db.commit.call_count == 2  # type: ignore[attr-defined]  # Once for profile, once for is_learning_profile_complete

    async def test_when_student_profile_not_found_then_raises_value_error(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that ValueError is raised when student profile not found."""
        responses = [{"question_id": "q1", "answer_key": "watch_video"}]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Student profile not found"):
            await service.save_questionnaire_response(student_id, responses)


@pytest.mark.asyncio
class TestGetOnboardingStatus:
    """Tests for get_onboarding_status method (v2.1 - uses student_profiles.is_learning_profile_complete)."""

    async def test_when_learning_profile_complete_then_overall_completed(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that overall=COMPLETED when learning profile is complete."""
        # Create student profile with is_learning_profile_complete = True
        student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student_id,
            is_learning_profile_complete=True,
        )

        # Mock the database queries:
        # 1. First call: StudentProfile query
        # 2. Second call: ClassEnrollment diagnostic status query (returns empty list = no enrollments)
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=student_profile)),  # StudentProfile query
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            ),  # ClassEnrollment query
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)  # type: ignore[method-assign]

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is True
        assert len(status["diagnostics_by_class"]) == 0

    async def test_when_no_student_profile_then_false(self, service: OnboardingService, student_id: uuid.UUID) -> None:
        """Test that learning_profile_complete return false when student profile doesn't exist."""
        # Mock the database queries:
        # 1. First call: StudentProfile query (returns None = no profile)
        # 2. Second call: ClassEnrollment diagnostic status query (returns empty list)
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # StudentProfile query - returns None
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            ),  # ClassEnrollment query
        ]
        service.db.execute = AsyncMock(side_effect=mock_results)  # type: ignore[method-assign]

        status = await service.get_onboarding_status(student_id)

        assert status["learning_profile_complete"] is False
        assert len(status["diagnostics_by_class"]) == 0


@pytest.mark.asyncio
class TestVerifyTeacherStudentRelationship:
    """Tests for verify_teacher_student_relationship method."""

    async def test_when_student_in_teacher_class_then_returns_true(self, service: OnboardingService) -> None:
        """Test that relationship is verified when student is in teacher's class."""
        teacher_id = uuid.uuid4()
        student_id = uuid.uuid4()

        # Mock enrollment found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Enrollment exists
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.verify_teacher_student_relationship(teacher_id, student_id)

        assert result is True

    async def test_when_student_not_in_teacher_class_then_returns_false(self, service: OnboardingService) -> None:
        """Test that relationship is not verified when student is not in teacher's class."""
        teacher_id = uuid.uuid4()
        student_id = uuid.uuid4()

        # Mock no enrollment found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.verify_teacher_student_relationship(teacher_id, student_id)

        assert result is False


@pytest.mark.asyncio
class TestCheckAndUpdateOnboardingComplete:
    """Tests for check_and_update_onboarding_complete method."""

    async def test_when_2_of_3_complete_then_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that when 2 of 3 Tier 1 diagnostics are complete, returns False."""
        from app.models.assessment import Assessment, AttemptStatus, StudentAttempt

        # Create mock Tier 1 assessments and attempts
        assessment1 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)
        assessment2 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)
        assessment3 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)

        # 2 completed, 1 in progress
        attempt1 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)
        attempt2 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)
        attempt3 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.IN_PROGRESS)

        # First query returns tier1_rows (empty or with data)
        # Second query returns attempts
        mock_result_assessments = MagicMock()
        mock_result_assessments.all.return_value = [assessment1, assessment2, assessment3]

        mock_result_attempts = MagicMock()
        mock_result_attempts.scalars.return_value.all.return_value = [attempt1, attempt2, attempt3]

        service.db.execute = AsyncMock(side_effect=[mock_result_assessments, mock_result_attempts])  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id)

        assert result is False

    async def test_when_all_3_complete_then_returns_true_and_status_updated(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that when all 3 Tier 1 diagnostics are complete, returns True and updates status."""
        from app.models.assessment import Assessment, AttemptStatus, StudentAttempt
        from app.models.user import OnboardingStatus, StudentProfile

        # Create mock Tier 1 assessments
        assessment1 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)
        assessment2 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)
        assessment3 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)

        # All 3 completed
        attempt1 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)
        attempt2 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)
        attempt3 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)

        # Student profile in IN_PROGRESS status
        student_profile = MagicMock(spec=StudentProfile)
        student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS

        # Mock results
        mock_result_assessments = MagicMock()
        mock_result_assessments.all.return_value = [assessment1, assessment2, assessment3]

        mock_result_attempts = MagicMock()
        mock_result_attempts.scalars.return_value.all.return_value = [attempt1, attempt2, attempt3]

        mock_result_profile = MagicMock()
        mock_result_profile.scalar_one_or_none.return_value = student_profile

        service.db.execute = AsyncMock(side_effect=[mock_result_assessments, mock_result_attempts, mock_result_profile])  # type: ignore[method-assign]
        service.db.commit = AsyncMock()  # type: ignore[method-assign]
        service.db.refresh = AsyncMock()  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id)

        assert result is True
        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    async def test_when_already_completed_then_idempotent(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that calling when already COMPLETED returns True without updating."""
        from app.models.assessment import Assessment, AttemptStatus, StudentAttempt
        from app.models.user import OnboardingStatus, StudentProfile

        # Create mock Tier 1 assessments
        assessment1 = MagicMock(spec=Assessment, id=uuid.uuid4(), is_system_generated=True)

        # All completed
        attempt1 = MagicMock(spec=StudentAttempt, id=uuid.uuid4(), status=AttemptStatus.COMPLETED)

        # Student profile already COMPLETED
        student_profile = MagicMock(spec=StudentProfile)
        student_profile.onboarding_diagnostic_status = OnboardingStatus.COMPLETED

        # Mock results
        mock_result_assessments = MagicMock()
        mock_result_assessments.all.return_value = [assessment1]

        mock_result_attempts = MagicMock()
        mock_result_attempts.scalars.return_value.all.return_value = [attempt1]

        mock_result_profile = MagicMock()
        mock_result_profile.scalar_one_or_none.return_value = student_profile

        service.db.execute = AsyncMock(side_effect=[mock_result_assessments, mock_result_attempts, mock_result_profile])  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id)

        # Should return True but NOT update (idempotent)
        assert result is True
        # Status should remain COMPLETED (not changed)
        assert student_profile.onboarding_diagnostic_status == OnboardingStatus.COMPLETED

    async def test_when_no_tier1_assessments_then_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that when no Tier 1 assessments exist, returns False (no crash)."""
        # First query returns empty
        mock_result = MagicMock()
        mock_result.all.return_value = []

        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id)

        assert result is False
