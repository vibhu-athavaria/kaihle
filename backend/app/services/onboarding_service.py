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
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.questionnaire_config import get_option_by_key
from app.models.assessment import Assessment, AssessmentType, StudentAttempt
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole

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
            questionnaire_version="v2",
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
            user_result = await self.db.execute(select(User).where(User.id == student_id))
            user = user_result.scalar_one_or_none()

            if user is None:
                raise ValueError(f"User not found for user_id={student_id}")

            learning_profile = StudentLearningProfile(
                student_id=student_id,
                school_id=user.school_id,
                modality_scores={},
                work_style={},
                questionnaire_version="v2",
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
        learning_profile.questionnaire_version = "v2"
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

    def _calculate_modality_scores(self, responses: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate modality scores from Q1, Q2, Q3 responses (v2 plurality vote).

        Tallies one vote per question (Q1–Q3) for each modality, then normalises
        the counts to fractions in [0.0, 1.0] so the result matches the CONSTITUTION
        §11 format: {"visual": float, "auditory": float, ...}.

        Args:
            responses: List of response dictionaries.

        Returns:
            Dictionary with one float score per modality (0.0–1.0).
        """
        counts: dict[str, int] = {
            "visual": 0,
            "auditory": 0,
            "reading_writing": 0,
            "kinesthetic": 0,
        }

        for response in responses:
            question_id = response.get("question_id")
            if question_id not in ("q1", "q2", "q3"):
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

        total = sum(counts.values()) or 1  # guard against division by zero
        return {modality: round(count / total, 4) for modality, count in counts.items()}

    def _calculate_work_style(self, responses: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate work style preferences from Q4, Q5, Q7 responses (v2).

        Q4 → short_sessions / prefers_solo
        Q5 → concept_first (True/False/None)
        Q7 → challenge_response (option key string)

        Args:
            responses: List of response dictionaries.

        Returns:
            Dictionary with work style fields including challenge_response.
        """
        work_style: dict[str, Any] = {
            "prefers_solo": False,
            "short_sessions": False,
            "concept_first": False,
            "task_based": False,
            "challenge_response": None,
        }

        for response in responses:
            question_id = response.get("question_id")

            if question_id in ("q4", "q5"):
                answer_key = response.get("answer_key")
                if not answer_key:
                    continue

                option = get_option_by_key(question_id, answer_key)
                if option and "maps_to" in option:
                    maps_to = option["maps_to"]
                    if "work_style" in maps_to and "value" in maps_to:
                        field_name = maps_to["work_style"]
                        field_value = maps_to["value"]
                        # concept_first can be None ("either_way") — store as-is
                        work_style[field_name] = field_value

            elif question_id == "q7":
                answer_key = response.get("answer_key")
                if answer_key:
                    work_style["challenge_response"] = answer_key

        # Derive task_based from concept_first (opposite; None → False)
        concept_first_val = work_style.get("concept_first")
        work_style["task_based"] = not concept_first_val if concept_first_val is not None else False

        return work_style

    def _extract_interests(self, responses: list[dict[str, Any]]) -> list[str]:
        """Extract selected interest category from Q6 (v2 single-select).

        Q6 maps_to "interest_category" — the selected option key is the
        canonical interest category (e.g. "sports_movement").

        Returns a single-item list to maintain list type for backward
        compatibility with existing profile readers.

        Args:
            responses: List of response dictionaries.

        Returns:
            Single-item list containing the selected interest category key,
            or empty list if Q6 was not answered.
        """
        for response in responses:
            question_id = response.get("question_id")
            if question_id != "q6":
                continue

            answer_key = response.get("answer_key")
            if answer_key:
                return [answer_key.lower()]

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
        """Get the learning profile complete status and each class enrolle class
         diagnostic completion status

        Args:
            student_id: The student user ID.

        Returns:
            Dictionary with learning_profile_complete
        """
        # Check learning profile completion via student_profiles
        result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
        student_profile = result.scalar_one_or_none()
        learning_profile_complete = student_profile.is_learning_profile_complete if student_profile else False

        return {"learning_profile_complete": learning_profile_complete}

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
            .limit(1)
        )

        enrollment = result.scalar_one_or_none()
        return enrollment is not None

    async def get_learning_profile_authorized(
        self,
        requester_id: UUID,
        requester_role: str,
        requester_school_id: UUID | None,
        target_student_id: UUID,
    ) -> StudentLearningProfile:
        """Get a student's learning profile with authorization checks.

        Args:
            requester_id: The user ID making the request.
            requester_role: The role of the requester.
            requester_school_id: The school_id of the requester (None for KAIHLE_ADMIN).
            target_student_id: The student ID whose profile to retrieve.

        Returns:
            The student's learning profile.

        Raises:
            PermissionError: If the requester doesn't have permission.
            ValueError: If the student is not found.
        """
        # Students can only view their own profile
        if requester_role == UserRole.STUDENT and target_student_id != requester_id:
            raise PermissionError("Students can only view their own learning profile")

        # Teachers must verify relationship
        if requester_role == UserRole.TEACHER:
            is_related = await self.verify_teacher_student_relationship(
                teacher_id=requester_id, student_id=target_student_id
            )
            if not is_related:
                raise PermissionError("You can only view profiles of students in your classes")

        # School admins must be in same school
        if requester_role == UserRole.SCHOOL_ADMIN:
            student = await self.db.get(User, target_student_id)
            if not student:
                raise ValueError("Invalid student id")
            if requester_school_id != student.school_id:
                raise PermissionError("You do not have permission to view this student")

        # Retrieve the profile
        profile = await self.get_learning_profile(target_student_id)
        if not profile:
            raise ValueError("Learning profile not found")

        return profile

    async def get_diagnostic_onboarding_status(
        self,
        student_id: UUID,
    ) -> str:
        """Get the diagnostic onboarding status from class_enrollments.

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

        Finds the Tier 1 diagnostic assessment for the class (assessment_type = DIAGNOSTIC),
        checks if the student_attempt for that assessment is COMPLETED,
        and if so, updates the class_enrollment status to COMPLETED.

        Args:
            student_id: The student user ID.
            class_id: The class ID.

        Returns:
            True if the diagnostic was completed and the enrollment status was updated.
        """

        # Subquery to check if diagnostic is completed for this student/class
        # Joins Assessment (via class_id) -> StudentAttempt (via student_id)
        diagnostic_completed_subquery = (
            select(StudentAttempt.id)
            .join(Assessment, Assessment.id == StudentAttempt.assessment_id)
            .where(
                Assessment.class_id == class_id,
                Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                StudentAttempt.student_id == student_id,
                StudentAttempt.status == "COMPLETED",
            )
            .exists()
        )

        # Single update query that checks all conditions atomically
        stmt = (
            update(ClassEnrollment)
            .where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.onboarding_diagnostic_status != OnboardingStatus.COMPLETED,
                diagnostic_completed_subquery,
            )
            .values(onboarding_diagnostic_status=OnboardingStatus.COMPLETED)
        )

        result = await self.db.execute(stmt)
        rows_updated = result.rowcount  # type: ignore[attr-defined]

        if rows_updated > 0:
            logger.info(
                "onboarding_diagnostic_completed",
                student_id=str(student_id),
                class_id=str(class_id),
                rows_updated=rows_updated,
            )
            return True

        # No diagnostic found - log warning
        logger.warning(
            "no_diagnostic_found_for_class",
            student_id=str(student_id),
            class_id=str(class_id),
        )
        return False
