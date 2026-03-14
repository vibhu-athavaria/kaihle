"""Onboarding service for managing student learning profiles.

This module handles:
- Getting or creating learning profiles
- Processing questionnaire responses and calculating scores
- Tracking onboarding completion status
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.questionnaire_config import get_option_by_key
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment
from app.models.user import OnboardingStatus, StudentProfile

logger = structlog.get_logger()


class OnboardingService:
    """Service for onboarding-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the onboarding service.

        Args:
            db: Database session for persistence operations.
        """
        self.db = db

    async def get_or_create_learning_profile(self, student_id: UUID, school_id: UUID) -> StudentLearningProfile:
        """Get existing learning profile or create a new empty one.

        This is an upsert operation - returns existing row if present,
        creates empty row if not.

        Args:
            student_id: The student user ID.
            school_id: The school ID for multi-tenancy.

        Returns:
            Existing or newly created StudentLearningProfile.
        """
        result = await self.db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id == student_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(
                "learning_profile_found",
                student_id=str(student_id),
                profile_id=str(existing.id),
            )
            return existing

        # Create new empty profile
        new_profile = StudentLearningProfile(
            student_id=student_id,
            school_id=school_id,
            modality_scores={},
            work_style={},
            questionnaire_version="v1",
        )
        self.db.add(new_profile)
        await self.db.commit()
        await self.db.refresh(new_profile)

        logger.info(
            "learning_profile_created",
            student_id=str(student_id),
            profile_id=str(new_profile.id),
        )
        return new_profile

    async def save_questionnaire_response(
        self, student_id: UUID, responses: list[dict[str, Any]]
    ) -> StudentLearningProfile:
        """Process questionnaire responses and update learning profile.

        Calculates modality scores, work style preferences, and interests
        based on the submitted answers. Creates new profile or updates
        existing one (idempotent).

        Args:
            student_id: The student user ID.
            responses: List of answer dictionaries with question_id and answer data.

        Returns:
            Updated StudentLearningProfile.
        """
        # Get student's school_id from their profile
        result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
        student_profile = result.scalar_one_or_none()

        if not student_profile:
            raise ValueError(f"Student profile not found for user_id={student_id}")

        # Get or create learning profile
        result = await self.db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id == student_id)
        )
        learning_profile: StudentLearningProfile | None = cast(
            StudentLearningProfile | None, result.scalar_one_or_none()
        )

        if not learning_profile:
            # Need to get school_id from user record
            from app.models.user import User

            user_result = await self.db.execute(select(User).where(User.id == student_id))
            user = user_result.scalar_one_or_none()

            if user is None:
                raise ValueError(f"User not found for user_id={student_id}")

            learning_profile = StudentLearningProfile(
                student_id=student_id,
                school_id=user.school_id,
                modality_scores={},
                work_style={},
                questionnaire_version="v1",
            )
            self.db.add(learning_profile)

        # At this point, learning_profile is guaranteed to be StudentLearningProfile
        # Calculate scores from responses
        modality_scores = self._calculate_modality_scores(responses)
        work_style = self._calculate_work_style(responses)
        interests = self._extract_interests(responses)

        # Update profile
        assert learning_profile is not None
        learning_profile.modality_scores = modality_scores
        learning_profile.work_style = work_style
        learning_profile.interests = interests
        learning_profile.questionnaire_version = "v1"
        learning_profile.completed_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(learning_profile)

        # Update student_profiles.is_learning_profile_complete (v2.1)
        if student_profile and not student_profile.is_learning_profile_complete:
            student_profile.is_learning_profile_complete = True
            await self.db.commit()

        logger.info(
            "questionnaire_response_saved",
            student_id=str(student_id),
            profile_id=str(learning_profile.id),
            modality_scores=modality_scores,
            work_style=work_style,
            interests=interests,
        )

        return learning_profile

    def _calculate_modality_scores(self, responses: list[dict[str, Any]]) -> dict[str, float]:
        """Calculate modality scores from Q1 and Q2 responses.

        Each modality answer counts as 1 point, divided by 2 (max questions).

        Args:
            responses: List of response dictionaries.

        Returns:
            Dictionary with modality scores (0.0 to 1.0).
        """
        counts: dict[str, int] = {
            "visual": 0,
            "auditory": 0,
            "reading_writing": 0,
            "kinesthetic": 0,
        }

        # Process Q1 and Q2 for modality
        for response in responses:
            question_id = response.get("question_id")
            if question_id not in ("q1", "q2"):
                continue

            answer_key = response.get("answer_key")
            if not answer_key:
                continue

            option = get_option_by_key(question_id, answer_key)
            if option and "maps_to" in option:
                maps_to = option["maps_to"]
                if "modality" in maps_to:
                    modality = maps_to["modality"]
                    if modality in counts:
                        counts[modality] += 1

        # Normalize: count / 2 (max possible is 2, one per question)
        return {modality: count / 2 for modality, count in counts.items()}

    def _calculate_work_style(self, responses: list[dict[str, Any]]) -> dict[str, bool]:
        """Calculate work style preferences from Q3, Q4, Q5 responses.

        Args:
            responses: List of response dictionaries.

        Returns:
            Dictionary with work style boolean flags.
        """
        work_style: dict[str, bool] = {
            "prefers_solo": False,
            "short_sessions": False,
            "concept_first": False,
            "task_based": False,
        }

        for response in responses:
            question_id = response.get("question_id")
            if question_id not in ("q3", "q4", "q5"):
                continue

            answer_key = response.get("answer_key")
            if not answer_key:
                continue

            option = get_option_by_key(question_id, answer_key)
            if option and "maps_to" in option:
                maps_to = option["maps_to"]
                if "work_style" in maps_to and "value" in maps_to:
                    field_name = maps_to["work_style"]
                    field_value = maps_to["value"]
                    work_style[field_name] = field_value

        # Derive task_based from concept_first (opposite)
        work_style["task_based"] = not work_style["concept_first"]

        return work_style

    def _extract_interests(self, responses: list[dict[str, Any]]) -> list[str]:
        """Extract selected interests from Q6-Q10 (multi-select).

        Args:
            responses: List of response dictionaries.

        Returns:
            List of selected interest keys in lowercase.
        """
        for response in responses:
            question_id = response.get("question_id")
            if question_id != "q6_to_q10":
                continue

            answer_keys = response.get("answer_keys", [])
            if answer_keys:
                # Ensure all lowercase
                return [key.lower() for key in answer_keys]

        return []

    async def get_learning_profile_complete_status(self, student_id: UUID) -> dict[str, Any]:
        """Get the learning profile completion status for a student.

        Checks student_profiles.is_learning_profile_complete boolean.

        Args:
            student_id: The student user ID.

        Returns:
            Dictionary with completed (bool) and completed_at (datetime or None).
        """
        result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
        student_profile = result.scalar_one_or_none()

        if not student_profile:
            return {
                "completed": False,
                "completed_at": None,
            }

        # Get the learning profile to return completed_at
        learning_result = await self.db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id == student_id)
        )
        learning_profile = learning_result.scalar_one_or_none()

        return {
            "completed": student_profile.is_learning_profile_complete,
            "completed_at": learning_profile.completed_at if learning_profile else None,
        }

    async def get_onboarding_status(self, student_id: UUID) -> dict[str, Any]:
        """Get the overall onboarding status for a student.

        This is a simplified version that only returns learning profile completion status.

        Args:
            student_id: The student user ID.

        Returns:
            Dictionary with learning_profile_complete and overall status.
        """
        # Check learning profile completion via student_profiles
        result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
        student_profile = result.scalar_one_or_none()

        learning_profile_complete = student_profile.is_learning_profile_complete if student_profile else False

        return {
            "learning_profile_complete": learning_profile_complete,
            "overall": "COMPLETED" if learning_profile_complete else "PENDING",
        }

    async def get_learning_profile(self, student_id: UUID) -> StudentLearningProfile | None:
        """Get a student's learning profile.

        Args:
            student_id: The student user ID.

        Returns:
            StudentLearningProfile if found, None otherwise.
        """
        result = await self.db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id == student_id)
        )
        return result.scalar_one_or_none()

    async def verify_teacher_student_relationship(self, teacher_id: UUID, student_id: UUID) -> bool:
        """Verify that a student is enrolled in a class taught by the teacher.

        Args:
            teacher_id: The teacher user ID.
            student_id: The student user ID.

        Returns:
            True if the student is in one of the teacher's classes.
        """
        # Query to check if student is in any class taught by this teacher
        result = await self.db.execute(
            select(ClassEnrollment)
            .join(Class, ClassEnrollment.class_id == Class.id)
            .where(
                Class.teacher_id == teacher_id,
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
            )
        )

        enrollment = result.scalar_one_or_none()
        return enrollment is not None

    async def get_diagnostic_onboarding_status(
        self,
        student_id: UUID,
    ) -> str:
        """Get the aggregated diagnostic onboarding status from class_enrollments.

        A student is considered fully diagnostically onboarded when ALL active
        class_enrollments have onboarding_diagnostic_status = 'COMPLETED'.

        Args:
            student_id: The student user ID.

        Returns:
            One of 'PENDING', 'IN_PROGRESS', 'COMPLETED'.
        """
        result = await self.db.execute(
            select(ClassEnrollment.onboarding_diagnostic_status).where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
            )
        )
        statuses = result.scalars().all()

        if not statuses:
            return OnboardingStatus.PENDING
        if all(s == OnboardingStatus.COMPLETED for s in statuses):
            return OnboardingStatus.COMPLETED
        if any(s != OnboardingStatus.PENDING for s in statuses):
            return OnboardingStatus.IN_PROGRESS
        return OnboardingStatus.PENDING

    async def get_diagnostic_status_by_class(
        self,
        student_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get per-class diagnostic status breakdown.

        Args:
            student_id: The student user ID.

        Returns:
            List of dictionaries with class_id, class_name, and status.
        """
        result = await self.db.execute(
            select(ClassEnrollment, Class)
            .join(Class, ClassEnrollment.class_id == Class.id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
            )
        )
        rows = result.all()

        return [
            {
                "class_id": str(enrollment.class_id),
                "class_name": class_.name,
                "status": enrollment.onboarding_diagnostic_status,
            }
            for enrollment, class_ in rows
        ]

    async def get_class_diagnostic_status(
        self,
        student_id: UUID,
        class_id: UUID,
    ) -> dict[str, Any]:
        """Get diagnostic status for a specific class enrollment.

        Args:
            student_id: The student user ID.
            class_id: The class ID.

        Returns:
            Dictionary with class_id and onboarding_diagnostic_status.
        """
        result = await self.db.execute(
            select(ClassEnrollment, Class)
            .join(Class, ClassEnrollment.class_id == Class.id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.is_active.is_(True),
            )
        )
        row = result.one_or_none()

        if not row:
            return {
                "class_id": str(class_id),
                "onboarding_diagnostic_status": None,
            }

        enrollment, class_ = row
        return {
            "class_id": str(enrollment.class_id),
            "class_name": class_.name,
            "onboarding_diagnostic_status": enrollment.onboarding_diagnostic_status,
        }

    async def check_and_update_onboarding_complete(
        self,
        student_id: UUID,
        class_id: UUID,
    ) -> bool:
        """Check if the student completed the diagnostic for a specific class.

        Finds the Tier 1 diagnostic assessment for the class (is_system_generated = TRUE),
        checks if the student_attempt for that assessment is COMPLETED,
        and if so, updates the class_enrollment status to COMPLETED.

        Args:
            student_id: The student user ID.
            class_id: The class ID.

        Returns:
            True if the diagnostic was completed and the enrollment status was updated.
        """
        from app.models.assessment import Assessment, StudentAttempt

        # Find the Tier 1 diagnostic assessment for this class
        result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_id,
                Assessment.is_system_generated.is_(True),
            )
        )
        diagnostic = result.scalar_one_or_none()

        if not diagnostic:
            logger.warning(
                "no_diagnostic_found_for_class",
                student_id=str(student_id),
                class_id=str(class_id),
            )
            return False

        # Check if the student attempt for this diagnostic is COMPLETED
        attempt_result = await self.db.execute(
            select(StudentAttempt).where(
                StudentAttempt.assessment_id == diagnostic.id,
                StudentAttempt.student_id == student_id,
            )
        )
        attempt = attempt_result.scalar_one_or_none()

        if not attempt or attempt.status != "COMPLETED":
            return False

        # Update the class_enrollment status to COMPLETED
        from sqlalchemy import update

        await self.db.execute(
            update(ClassEnrollment)
            .where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.onboarding_diagnostic_status != OnboardingStatus.COMPLETED,
            )
            .values(onboarding_diagnostic_status=OnboardingStatus.COMPLETED)
        )

        logger.info(
            "onboarding_diagnostic_completed",
            student_id=str(student_id),
            class_id=str(class_id),
        )
        return True
