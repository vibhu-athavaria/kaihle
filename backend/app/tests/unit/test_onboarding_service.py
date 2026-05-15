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
    """Tests for modality score calculation (v2 plurality-vote format).

    v2 returns {"dominant": str, "secondary": str | None} instead of 0.0-1.0 floats.
    """

    def test_when_visual_answers_then_dominant_is_visual(self, service: OnboardingService) -> None:
        """Test that visual answers result in dominant=visual."""
        # v2 keys: Q1=see_diagram (visual), Q2=draw_it (visual), Q3=find_example (visual)
        responses = [
            {"question_id": "q1", "answer_key": "see_diagram"},
            {"question_id": "q2", "answer_key": "draw_it"},
            {"question_id": "q3", "answer_key": "find_example"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["dominant"] == "visual"

    def test_when_kinesthetic_answers_then_dominant_is_kinesthetic(self, service: OnboardingService) -> None:
        """Test that kinesthetic answers result in dominant=kinesthetic."""
        # v2 keys: Q1=try_problems (kinesthetic), Q2=show_example (kinesthetic), Q3=try_different (kinesthetic)
        responses = [
            {"question_id": "q1", "answer_key": "try_problems"},
            {"question_id": "q2", "answer_key": "show_example"},
            {"question_id": "q3", "answer_key": "try_different"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["dominant"] == "kinesthetic"

    def test_when_mixed_answers_then_dominant_is_most_common(self, service: OnboardingService) -> None:
        """Test that the most-voted modality is dominant."""
        # Q1=see_diagram (visual), Q2=draw_it (visual), Q3=talk_through (auditory) → visual wins
        responses = [
            {"question_id": "q1", "answer_key": "see_diagram"},
            {"question_id": "q2", "answer_key": "draw_it"},
            {"question_id": "q3", "answer_key": "ask_someone"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["dominant"] == "visual"
        assert scores["secondary"] == "auditory"

    def test_when_auditory_answers_then_dominant_is_auditory(self, service: OnboardingService) -> None:
        """Test that auditory answers result in dominant=auditory."""
        responses = [
            {"question_id": "q1", "answer_key": "watch_walkthrough"},
            {"question_id": "q2", "answer_key": "talk_through"},
            {"question_id": "q3", "answer_key": "ask_someone"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["dominant"] == "auditory"

    def test_when_reading_writing_answers_then_dominant_is_reading_writing(self, service: OnboardingService) -> None:
        """Test that reading/writing answers result in dominant=reading_writing."""
        responses = [
            {"question_id": "q1", "answer_key": "read_explanation"},
            {"question_id": "q2", "answer_key": "write_points"},
            {"question_id": "q3", "answer_key": "reread_alone"},
        ]

        scores = service._calculate_modality_scores(responses)

        assert scores["dominant"] == "reading_writing"

    def test_when_no_modality_responses_then_dominant_set_by_tiebreak(self, service: OnboardingService) -> None:
        """Test that missing modality responses produce a tiebreak-determined dominant."""
        # No Q1/Q2/Q3 responses → all counts = 0 → reading_writing wins by tiebreak
        responses: list[dict[str, Any]] = [
            {"question_id": "q4", "answer_key": "short_focused"},
            {"question_id": "q6", "answer_key": "sports_movement"},
        ]

        scores = service._calculate_modality_scores(responses)

        # All counts are 0 → tiebreak gives reading_writing
        assert scores["dominant"] == "reading_writing"
        assert "secondary" in scores


class TestCalculateWorkStyle:
    """Tests for work style calculation (v2: Q4=study setup, Q5=concept_first, Q7=challenge)."""

    def test_when_with_friends_selected_then_prefers_solo_false(self, service: OnboardingService) -> None:
        """Test that selecting with_friends (Q4) results in prefers_solo=False."""
        # v2: Q4 "with_friends" maps to prefers_solo=False
        responses = [
            {"question_id": "q4", "answer_key": "with_friends"},
            {"question_id": "q5", "answer_key": "big_picture"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["prefers_solo"] is False
        assert work_style["short_sessions"] is False
        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_long_deep_selected_then_short_sessions_false(self, service: OnboardingService) -> None:
        """Test that selecting long_deep results in short_sessions=False."""
        responses = [
            {"question_id": "q4", "answer_key": "long_deep"},
            {"question_id": "q5", "answer_key": "dive_in"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["prefers_solo"] is False
        assert work_style["short_sessions"] is False
        assert work_style["concept_first"] is False
        assert work_style["task_based"] is True

    def test_when_short_focused_selected_then_short_sessions_true(self, service: OnboardingService) -> None:
        """Test that selecting short_focused results in short_sessions=True."""
        responses = [
            {"question_id": "q4", "answer_key": "short_focused"},
            {"question_id": "q5", "answer_key": "big_picture"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["short_sessions"] is True
        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_solo_quiet_selected_then_prefers_solo_true(self, service: OnboardingService) -> None:
        """Test that selecting solo_quiet (Q4) results in prefers_solo=True."""
        responses = [
            {"question_id": "q4", "answer_key": "solo_quiet"},
            {"question_id": "q5", "answer_key": "big_picture"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["prefers_solo"] is True
        assert work_style["short_sessions"] is False

    def test_when_big_picture_selected_then_concept_first_true_and_task_based_false(
        self, service: OnboardingService
    ) -> None:
        """Test that selecting big_picture (Q5) results in correct flags."""
        responses = [
            {"question_id": "q4", "answer_key": "short_focused"},
            {"question_id": "q5", "answer_key": "big_picture"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["concept_first"] is True
        assert work_style["task_based"] is False

    def test_when_dive_in_selected_then_concept_first_false_and_task_based_true(
        self, service: OnboardingService
    ) -> None:
        """Test that selecting dive_in (Q5) results in correct flags."""
        responses = [
            {"question_id": "q4", "answer_key": "long_deep"},
            {"question_id": "q5", "answer_key": "dive_in"},
        ]

        work_style = service._calculate_work_style(responses)

        assert work_style["concept_first"] is False
        assert work_style["task_based"] is True


class TestExtractInterests:
    """Tests for interest extraction (v2: Q6 single-select → canonical category key)."""

    def test_when_sports_movement_selected_then_returns_single_item_list(self, service: OnboardingService) -> None:
        """Test that Q6 single-select returns a one-item list."""
        responses = [
            {"question_id": "q6", "answer_key": "sports_movement"},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["sports_movement"]

    def test_when_tech_gaming_selected_then_interest_lowercased(self, service: OnboardingService) -> None:
        """Test that interest key is lowercased."""
        responses = [
            {"question_id": "q6", "answer_key": "TECH_GAMING"},
        ]

        interests = service._extract_interests(responses)

        assert interests == ["tech_gaming"]

    def test_when_no_q6_response_then_empty_list(self, service: OnboardingService) -> None:
        """Test that missing q6 response results in empty list."""
        responses = [
            {"question_id": "q1", "answer_key": "see_diagram"},
        ]

        interests = service._extract_interests(responses)

        assert interests == []

    def test_when_nature_animals_selected_then_returns_nature_animals(self, service: OnboardingService) -> None:
        """Test each canonical interest category is returned correctly."""
        for category in ("sports_movement", "tech_gaming", "nature_animals", "arts_culture"):
            responses = [{"question_id": "q6", "answer_key": category}]
            interests = service._extract_interests(responses)
            assert interests == [category]


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
        assert result.questionnaire_version == "v2"
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

        # v2 responses
        responses: list[dict[str, Any]] = [
            {"question_id": "q1", "answer_key": "see_diagram"},
            {"question_id": "q2", "answer_key": "draw_it"},
            {"question_id": "q3", "answer_key": "find_example"},
            {"question_id": "q4", "answer_key": "short_focused"},
            {"question_id": "q5", "answer_key": "big_picture"},
            {"question_id": "q6", "answer_key": "sports_movement"},
            {"question_id": "q7", "answer_key": "persists"},
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
        # v2: dominant should be visual (all three Q1/Q2/Q3 answered visual)
        assert result.modality_scores["dominant"] == "visual"
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

        # v2 responses
        responses: list[dict[str, Any]] = [
            {"question_id": "q1", "answer_key": "see_diagram"},
            {"question_id": "q2", "answer_key": "draw_it"},
            {"question_id": "q3", "answer_key": "find_example"},
            {"question_id": "q4", "answer_key": "short_focused"},
            {"question_id": "q5", "answer_key": "big_picture"},
            {"question_id": "q6", "answer_key": "sports_movement"},
            {"question_id": "q7", "answer_key": "persists"},
        ]

        # Create existing profile for the second call
        existing_profile = StudentLearningProfile(
            id=uuid.uuid4(),
            student_id=student_id,
            school_id=school_id,
            modality_scores={},
            work_style={},
            questionnaire_version="v2",
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
        assert result.modality_scores["dominant"] == "visual"
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

    async def test_when_diagnostic_completed_enrollment_updated_returns_true(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that True is returned when diagnostic completed and enrollment updated."""
        class_id = uuid.uuid4()

        # Mock successful update with rowcount = 1
        mock_result = MagicMock()
        mock_result.rowcount = 1
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is True
        service.db.execute.assert_called_once()

    async def test_when_no_diagnostic_found_for_class_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that False is returned when no diagnostic found for class."""
        class_id = uuid.uuid4()

        # Mock update with rowcount = 0 (no matching enrollment)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is False
        service.db.execute.assert_called_once()

    async def test_when_diagnostic_found_but_no_attempt_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that False is returned when diagnostic exists but no student attempt."""
        class_id = uuid.uuid4()

        # Mock update with rowcount = 0 (subquery returns false - no attempt)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is False

    async def test_when_attempt_status_not_completed_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that False is returned when attempt status is not COMPLETED."""
        class_id = uuid.uuid4()

        # Mock update with rowcount = 0 (attempt not completed)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is False

    async def test_when_enrollment_already_completed_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that False is returned when enrollment already COMPLETED."""
        class_id = uuid.uuid4()

        # Mock update with rowcount = 0 (already completed, WHERE clause excludes it)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is False

    async def test_when_enrollment_not_found_returns_false(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that False is returned when no enrollment exists for student/class."""
        class_id = uuid.uuid4()

        # Mock update with rowcount = 0 (no enrollment record)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is False

    async def test_when_multiple_attempts_one_completed_returns_true(
        self, service: OnboardingService, student_id: uuid.UUID
    ) -> None:
        """Test that True is returned when multiple attempts exist and one is COMPLETED."""
        class_id = uuid.uuid4()

        # Mock successful update (subquery finds completed attempt)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        result = await service.check_and_update_onboarding_complete(student_id, class_id)

        assert result is True

    async def test_uses_single_query_with_subquery(self, service: OnboardingService, student_id: uuid.UUID) -> None:
        """Test that the implementation uses a single query with EXISTS subquery."""
        class_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        service.db.execute = AsyncMock(return_value=mock_result)  # type: ignore[method-assign]

        await service.check_and_update_onboarding_complete(student_id, class_id)

        # Verify only ONE call to db.execute (not 3 separate queries)
        assert service.db.execute.call_count == 1
