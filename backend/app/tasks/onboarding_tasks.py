"""Onboarding Celery tasks."""

import logging

logger = logging.getLogger(__name__)


def trigger_onboarding_diagnostics(student_id: str, class_id: str) -> None:
    """Trigger onboarding diagnostics for a student.

    This is a placeholder for M0-6-T2 (Tier 1 diagnostic trigger).
    When a student with onboarding_diagnostic_status='PENDING' is enrolled,
    this task should be fired to create Tier 1 diagnostic assessments.

    Args:
        student_id: The student UUID
        class_id: The class UUID

    Note:
        This is a stub implementation. The full implementation will:
        1. Load class to get curriculum_id, grade_id
        2. Load subjects for this curriculum
        3. Create one DIAGNOSTIC assessment per subject
        4. Select questions from question bank
        5. Create student_attempts rows
        6. Update student_profiles.onboarding_diagnostic_status to 'IN_PROGRESS'
    """
    logger.info(
        "trigger_onboarding_diagnostics called",
        extra={"student_id": student_id, "class_id": class_id},
    )
    # TODO: Implement full M0-6-T2 logic here
    # For now, this is a placeholder that gets called when a student
    # with onboarding_diagnostic_status='PENDING' is enrolled
    pass
