from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.crud.billing import get_active_subscriptions, get_subscriptions_by_parent
from app.models.billing import Subscription


class AccessControlService:
    """Service for handling access control logic based on subscriptions and trials"""

    def __init__(self):
        pass

    def can_access_courses(self, db: Session, student_id: int) -> bool:
        """Check if student can access courses"""
        # Get active subscriptions for student
        subscriptions = get_active_subscriptions(db, student_id)

        now = datetime.now()

        for sub in subscriptions:
            # Check trial status
            if sub.status == "trial":
                if sub.trial_end_date and sub.trial_end_date > now:
                    return True
                continue

            # Check active subscription
            if sub.status == "active":
                if not sub.end_date or sub.end_date > now:
                    return True

        return False

    def can_create_courses(self, db: Session, student_id: int) -> bool:
        """Check if student can create new courses"""
        # Same logic as can_access_courses for now
        return self.can_access_courses(db, student_id)

    def get_access_restriction_notification(self, db: Session, student_id: int) -> Optional[str]:
        """Get notification message if access is restricted"""
        if self.can_access_courses(db, student_id):
            return None

        return "All new courses and assessments are paused. Please subscribe to a plan to continue."

    def can_access_subject(self, db: Session, student_id: int, subject_id: int) -> bool:
        """Check if student can access a specific subject"""
        subscriptions = get_active_subscriptions(db, student_id)

        now = datetime.now()

        for sub in subscriptions:
            # During trial, allow access to all subjects
            if sub.status == "trial" and sub.trial_end_date and sub.trial_end_date > now:
                return True

            # For active subscriptions, check subject access based on plan type
            if sub.status == "active" and (not sub.end_date or sub.end_date > now):
                if sub.plan and sub.plan.plan_type == "premium":
                    # Premium plan has access to all subjects
                    return True
                elif sub.subject_id == subject_id:
                    # Basic plan has access to the specific subject
                    return True

        return False

    def get_student_access_status(self, db: Session, student_id: int) -> Dict[str, Any]:
        """Get comprehensive access status for a student"""
        subscriptions = get_active_subscriptions(db, student_id)

        now = datetime.now()
        has_active_trial = False
        has_active_subscription = False
        trial_end_date = None
        subscription_end_date = None
        accessible_subjects = []

        for sub in subscriptions:
            if sub.status == "trial" and sub.trial_end_date and sub.trial_end_date > now:
                has_active_trial = True
                trial_end_date = sub.trial_end_date

            if sub.status == "active" and (not sub.end_date or sub.end_date > now):
                has_active_subscription = True
                if sub.end_date:
                    subscription_end_date = sub.end_date

                # Add accessible subjects based on plan
                if sub.plan:
                    if sub.plan.plan_type == "premium":
                        # Premium has access to all subjects
                        accessible_subjects = ["all"]
                    elif sub.subject_id:
                        accessible_subjects.append(sub.subject_id)

        return {
            "has_active_trial": has_active_trial,
            "has_active_subscription": has_active_subscription,
            "trial_end_date": trial_end_date,
            "subscription_end_date": subscription_end_date,
            "accessible_subjects": accessible_subjects,
            "can_access_courses": self.can_access_courses(db, student_id),
            "can_create_courses": self.can_create_courses(db, student_id),
            "restriction_notification": self.get_access_restriction_notification(db, student_id)
        }

    def get_parent_dashboard_status(self, db: Session, parent_id: int) -> Dict[str, Any]:
        """Get access status for all students of a parent"""
        subscriptions = get_subscriptions_by_parent(db, parent_id)

        now = datetime.now()
        student_statuses = {}

        for sub in subscriptions:
            student_id = sub.student_id
            if student_id not in student_statuses:
                student_statuses[student_id] = {
                    "student_id": student_id,
                    "has_active_trial": False,
                    "has_active_subscription": False,
                    "trial_end_date": None,
                    "subscription_end_date": None,
                    "show_subscribe_cta": False,
                    "trial_status": "none",
                    "subscription_status": "none"
                }

            status_info = student_statuses[student_id]

            if sub.status == "trial":
                status_info["has_active_trial"] = True
                status_info["trial_end_date"] = sub.trial_end_date
                if sub.trial_end_date and sub.trial_end_date > now:
                    status_info["trial_status"] = "active"
                else:
                    status_info["trial_status"] = "expired"
                    status_info["show_subscribe_cta"] = True

            elif sub.status == "active":
                status_info["has_active_subscription"] = True
                status_info["subscription_end_date"] = sub.end_date
                if not sub.end_date or sub.end_date > now:
                    status_info["subscription_status"] = "active"
                else:
                    status_info["subscription_status"] = "expired"
                    status_info["show_subscribe_cta"] = True

            # If no active trial or subscription, show CTA
            if not status_info["has_active_trial"] and not status_info["has_active_subscription"]:
                status_info["show_subscribe_cta"] = True

        return {"student_statuses": list(student_statuses.values())}


# Singleton instance for easy access
access_control_service = AccessControlService()