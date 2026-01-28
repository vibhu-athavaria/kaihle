from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.crud.billing import get_subscription_plan, get_subscription
from app.crud.user import get_user, get_student_profile
from app.models.billing import Subscription
from app.models.user import User


class ValidationService:
    """Service for validating subscription-related operations"""

    def __init__(self):
        pass

    def validate_subscription_creation(
        self, db: Session, parent_id: int, student_id: int,
        plan_id: int, subject_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate subscription creation parameters"""
        errors = []

        # Check if parent exists
        parent = get_user(db, parent_id)
        if not parent or parent.role != "parent":
            errors.append("Invalid parent")

        # Check if student exists and belongs to parent
        student_profile = get_student_profile(db, student_id)
        if not student_profile:
            errors.append("Invalid student")
        elif student_profile.parent_id != parent_id:
            errors.append("Student doesn't belong to parent")

        # Check if plan exists
        plan = get_subscription_plan(db, plan_id)
        if not plan or not plan.is_active:
            errors.append("Invalid or inactive plan")

        # For Basic plan, subject is required
        if plan and plan.plan_type == "basic" and not subject_id:
            errors.append("Subject is required for Basic plan")

        # For Premium plan, subject should be None
        if plan and plan.plan_type == "premium" and subject_id:
            errors.append("Subject should not be specified for Premium plan")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True, "plan_type": plan.plan_type if plan else None}

    def validate_trial_extension(
        self, db: Session, subscription_id: int, admin_id: int
    ) -> Dict[str, Any]:
        """Validate trial extension request"""
        errors = []

        # Check if admin exists
        admin = get_user(db, admin_id)
        if not admin or admin.role != "admin":
            errors.append("Invalid admin")

        # Check if subscription exists
        subscription = get_subscription(db, subscription_id)
        if not subscription:
            errors.append("Subscription not found")
        elif subscription.status != "trial":
            errors.append("Cannot extend non-trial subscription")
        elif not subscription.trial_end_date:
            errors.append("Subscription has no trial end date")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True, "subscription": subscription}

    def validate_subject_access(
        self, db: Session, student_id: int, subject_id: int
    ) -> Dict[str, Any]:
        """Validate if student can access a specific subject"""
        from app.services.access_control_service import access_control_service

        can_access = access_control_service.can_access_subject(db, student_id, subject_id)

        if not can_access:
            return {
                "valid": False,
                "error": "Student does not have access to this subject"
            }

        return {"valid": True}

    def validate_trial_start(
        self, db: Session, parent_id: int, student_id: int
    ) -> Dict[str, Any]:
        """Validate if a trial can be started for a student"""
        errors = []

        # Check if parent exists
        parent = get_user(db, parent_id)
        if not parent or parent.role != "parent":
            errors.append("Invalid parent")

        # Check if student exists and belongs to parent
        student_profile = get_student_profile(db, student_id)
        if not student_profile:
            errors.append("Invalid student")
        elif student_profile.parent_id != parent_id:
            errors.append("Student doesn't belong to parent")

        # Check if student already has an active trial
        from app.crud.billing import get_active_subscriptions
        subscriptions = get_active_subscriptions(db, student_id)
        active_trials = [sub for sub in subscriptions if sub.status == "trial"]

        if active_trials:
            now = datetime.now()
            for trial in active_trials:
                if trial.trial_end_date and trial.trial_end_date > now:
                    errors.append("Student already has an active trial")
                    break

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}

    def validate_subscription_cancellation(
        self, db: Session, subscription_id: int, user_id: int, user_role: str
    ) -> Dict[str, Any]:
        """Validate subscription cancellation"""
        errors = []

        subscription = get_subscription(db, subscription_id)
        if not subscription:
            errors.append("Subscription not found")
        elif user_role != "admin" and subscription.parent_id != user_id:
            errors.append("Not authorized to cancel this subscription")
        elif subscription.status == "canceled":
            errors.append("Subscription is already canceled")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True, "subscription": subscription}


# Singleton instance for easy access
validation_service = ValidationService()