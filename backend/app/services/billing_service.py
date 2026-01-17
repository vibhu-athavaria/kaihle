from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.crud.billing import (
    create_subscription, get_subscriptions_by_parent, is_in_free_trial,
    start_free_trial, create_payment, mark_payment_as_paid,
    get_billing_info_by_user, get_default_billing_info
)
from app.crud.user import get_user
from app.models.user import User
from app.schemas.billing import SubscriptionCreate, PaymentCreate
from app.core.config import settings

class BillingService:
    """Service for handling billing and subscription logic"""

    def __init__(self):
        self.PRICE_PER_STUDENT_PER_SUBJECT = 25.00  # $25 per student per subject per month
        self.FREE_TRIAL_DAYS = 15

    def start_free_trial_for_new_parent(
        self, db: Session, parent_id: int, student_id: int, subject_id: Optional[int] = None
    ) -> Any:
        """Start a free trial when a new parent signs up"""

        # Check if parent already has a trial
        if is_in_free_trial(db, parent_id):
            return None

        # Start free trial
        subscription = start_free_trial(db, parent_id, student_id, subject_id)

        return subscription

    def calculate_subscription_cost(
        self, num_students: int, num_subjects: int, is_trial: bool = False
    ) -> float:
        """Calculate the monthly subscription cost"""
        if is_trial:
            return 0.0

        return num_students * num_subjects * self.PRICE_PER_STUDENT_PER_SUBJECT

    def create_monthly_subscription(
        self, db: Session, parent_id: int, student_ids: List[int],
        subject_ids: List[int], payment_method: str = "credit_card"
    ) -> List[Any]:
        """Create monthly subscriptions for students and subjects"""
        subscriptions = []

        for student_id in student_ids:
            for subject_id in subject_ids:
                # Check if subscription already exists
                existing_subs = get_subscriptions_by_parent(db, parent_id)
                existing_sub = next((sub for sub in existing_subs
                                   if sub.student_id == student_id and sub.subject_id == subject_id), None)

                if existing_sub and existing_sub.status in ["active", "trial"]:
                    continue

                # Calculate end date (1 month from now)
                start_date = datetime.now()
                end_date = start_date + timedelta(days=30)

                subscription_data = SubscriptionCreate(
                    parent_id=parent_id,
                    student_id=student_id,
                    subject_id=subject_id,
                    status="active",
                    price=self.PRICE_PER_STUDENT_PER_SUBJECT,
                    payment_method=payment_method,
                    end_date=end_date
                )

                subscription = create_subscription(db, subscription_data, parent_id)
                subscriptions.append(subscription)

        return subscriptions

    def process_monthly_payments(self, db: Session) -> Dict[str, Any]:
        """Process monthly payments for all active subscriptions"""
        # This would typically be run as a scheduled job

        # Get all parents with active subscriptions
        all_users = db.query(User).filter(User.role == "parent").all()

        results = {
            "total_processed": 0,
            "total_amount": 0.0,
            "successful_payments": 0,
            "failed_payments": 0
        }

        for parent in all_users:
            active_subs = get_subscriptions_by_parent(db, parent.id)
            active_subs = [sub for sub in active_subs if sub.status == "active"]

            if not active_subs:
                continue

            # Get default payment method
            billing_info = get_default_billing_info(db, parent.id)
            if not billing_info:
                continue

            # Calculate total amount
            total_amount = sum(float(sub.price) for sub in active_subs)

            # Create payment
            payment_data = PaymentCreate(
                subscription_id=active_subs[0].id,  # Use first subscription as reference
                amount=total_amount,
                currency="USD",
                payment_method=billing_info.payment_method or "credit_card",
                description=f"Monthly subscription payment for {len(active_subs)} subjects"
            )

            payment = create_payment(db, payment_data)

            # In a real implementation, this would call the payment gateway
            # For now, we'll simulate successful payment
            paid_payment = mark_payment_as_paid(db, payment.id, f"simulated_{payment.id}")

            results["total_processed"] += 1
            results["total_amount"] += total_amount
            results["successful_payments"] += 1

        return results

    def get_billing_summary(self, db: Session, parent_id: int) -> Dict[str, Any]:
        """Get a comprehensive billing summary for a parent"""
        subscriptions = get_subscriptions_by_parent(db, parent_id)
        billing_info = get_billing_info_by_user(db, parent_id)

        active_subs = [sub for sub in subscriptions if sub.status in ["active", "trial"]]
        trial_subs = [sub for sub in subscriptions if sub.status == "trial"]
        past_due_subs = [sub for sub in subscriptions if sub.status == "past_due"]

        # Calculate metrics
        total_monthly_cost = sum(float(sub.price) for sub in active_subs)

        # Find next payment date
        next_payment_date = None
        if active_subs:
            # Find the earliest end date among active subscriptions
            active_subs_sorted = sorted(active_subs, key=lambda x: x.end_date if x.end_date else datetime.max)
            if active_subs_sorted and active_subs_sorted[0].end_date:
                next_payment_date = active_subs_sorted[0].end_date

        # Check trial status
        in_trial = len(trial_subs) > 0
        trial_end_date = None
        if trial_subs:
            trial_subs_sorted = sorted(trial_subs, key=lambda x: x.trial_end_date if x.trial_end_date else datetime.max)
            if trial_subs_sorted and trial_subs_sorted[0].trial_end_date:
                trial_end_date = trial_subs_sorted[0].trial_end_date

        return {
            "active_subscriptions": len(active_subs),
            "trial_subscriptions": len(trial_subs),
            "past_due_subscriptions": len(past_due_subs),
            "total_monthly_cost": total_monthly_cost,
            "next_payment_date": next_payment_date,
            "in_free_trial": in_trial,
            "trial_end_date": trial_end_date,
            "days_remaining_in_trial": (trial_end_date - datetime.now()).days if trial_end_date and trial_end_date > datetime.now() else 0,
            "payment_methods": len(billing_info),
            "has_payment_method": len(billing_info) > 0,
            "students_enrolled": len(set(sub.student_id for sub in subscriptions)),
            "subjects_subscribed": len(set(sub.subject_id for sub in subscriptions if sub.subject_id))
        }

    def check_subscription_status(self, db: Session, parent_id: int, student_id: int, subject_id: Optional[int] = None) -> Dict[str, Any]:
        """Check the subscription status for a specific student/subject"""
        subscriptions = get_subscriptions_by_parent(db, parent_id)

        # Find the specific subscription
        target_sub = None
        for sub in subscriptions:
            if sub.student_id == student_id and (subject_id is None or sub.subject_id == subject_id):
                target_sub = sub
                break

        if not target_sub:
            return {
                "has_subscription": False,
                "status": "none",
                "can_access": False,
                "message": "No subscription found"
            }

        now = datetime.now()
        can_access = False
        status_details = ""

        if target_sub.status == "trial":
            if target_sub.trial_end_date and target_sub.trial_end_date > now:
                can_access = True
                status_details = f"Free trial active until {target_sub.trial_end_date}"
            else:
                status_details = "Free trial expired"

        elif target_sub.status == "active":
            if not target_sub.end_date or target_sub.end_date > now:
                can_access = True
                status_details = "Active subscription"
            else:
                status_details = "Subscription expired"

        elif target_sub.status == "past_due":
            status_details = "Payment overdue"

        elif target_sub.status == "cancelled":
            status_details = "Subscription cancelled"

        return {
            "has_subscription": True,
            "status": target_sub.status,
            "can_access": can_access,
            "status_details": status_details,
            "subscription_id": target_sub.id,
            "trial_end_date": target_sub.trial_end_date,
            "end_date": target_sub.end_date,
            "price": float(target_sub.price)
        }

    def get_pricing_options(self) -> Dict[str, Any]:
        """Get available pricing options"""
        return {
            "base_price_per_student_per_subject": self.PRICE_PER_STUDENT_PER_SUBJECT,
            "currency": "USD",
            "free_trial_days": self.FREE_TRIAL_DAYS,
            "billing_cycle": "monthly",
            "features_included": [
                "Unlimited assessments",
                "Personalized learning paths",
                "Progress tracking",
                "AI tutor access",
                "Parent dashboard",
                "Detailed reports"
            ],
            "example_pricing": {
                "1_student_1_subject": {
                    "price": 25.00,
                    "description": "1 student, 1 subject"
                },
                "1_student_3_subjects": {
                    "price": 75.00,
                    "description": "1 student, 3 subjects"
                },
                "2_students_2_subjects": {
                    "price": 100.00,
                    "description": "2 students, 2 subjects each"
                }
            }
        }

    def validate_free_trial_eligibility(self, db: Session, parent_id: int) -> Dict[str, Any]:
        """Check if a parent is eligible for a free trial"""
        parent = get_user(db, parent_id)
        if not parent:
            return {"eligible": False, "reason": "Parent not found"}

        # Check if already used trial
        if is_in_free_trial(db, parent_id):
            return {"eligible": False, "reason": "Already in free trial"}

        # Check if parent already had a trial in the past
        subscriptions = get_subscriptions_by_parent(db, parent_id)
        past_trials = [sub for sub in subscriptions if sub.status == "trial"]

        if past_trials:
            return {"eligible": False, "reason": "Free trial already used"}

        # Check if parent already has paid subscriptions
        paid_subs = [sub for sub in subscriptions if sub.status == "active" and sub.payment_status == "paid"]
        if paid_subs:
            return {"eligible": False, "reason": "Already has paid subscription"}

        return {
            "eligible": True,
            "reason": "Eligible for free trial",
            "trial_days": self.FREE_TRIAL_DAYS,
            "trial_end_date": (datetime.now() + timedelta(days=self.FREE_TRIAL_DAYS)).strftime("%Y-%m-%d")
        }

# Singleton instance for easy access
billing_service = BillingService()