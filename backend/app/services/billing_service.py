from uuid import UUID
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.crud.billing import (
    create_subscription, get_subscriptions_by_user, is_in_free_trial,
    start_free_trial, create_payment, mark_payment_as_paid,
    get_billing_info_by_user, get_default_billing_info,
    get_active_subscription_plans, calculate_subscription_price,
    get_plan_features_by_plan, get_total_subjects_count, create_trial_extension,
    get_trial_extensions_by_subscription
)
from app.crud.user import get_user
from app.models.user import User
from app.schemas.billing import SubscriptionCreate, PaymentCreate
from app.constants.constants import BILLING_CYCLE_ANNUAL, BILLING_CYCLE_MONTHLY


class BillingService:
    """Service for handling billing and subscription logic"""

    def __init__(self):
        self.PRICE_PER_STUDENT_PER_SUBJECT = 25.00  # $25 per student per subject per month
        self.FREE_TRIAL_DAYS = 15

    def start_free_trial_for_new_parent(
        self, db: Session, parent_id: UUID, student_id: Optional[UUID] = None, subject_id: Optional[UUID] = None
    ) -> Any:
        """Start a free trial when a new parent signs up"""

        # Check if parent already has a trial
        if is_in_free_trial(db, parent_id):
            return None

        # Start free trial (student_id can be None for parent-level trial)
        subscription = start_free_trial(db, parent_id, student_id, subject_id)

        return subscription

    def calculate_subscription_cost(
        self, db: Session, plan_id: UUID, num_subjects: int = 1,
        billing_cycle: str = BILLING_CYCLE_ANNUAL, is_trial: bool = False
    ) -> float:
        """Calculate the subscription cost based on plan and billing cycle"""
        if is_trial:
            return 0.0

        # Use the new pricing calculation from CRUD
        return calculate_subscription_price(db, plan_id, num_subjects, billing_cycle)

    def create_monthly_subscription(
        self, db: Session, parent_id: UUID, student_ids: List[UUID],
        plan_id: UUID, billing_cycle: str =BILLING_CYCLE_ANNUAL, payment_method: str = "credit_card",
        subject_id: Optional[UUID] = None
    ) -> List[Any]:
        """Create subscriptions based on selected plan"""
        from app.crud.billing import get_subscription_plan

        # Get the plan details
        plan = get_subscription_plan(db, plan_id)
        if not plan:
            raise ValueError("Invalid subscription plan")

        # Validate subject selection based on plan type
        if plan.plan_type == "basic" and not subject_id:
            raise ValueError("Subject is required for Basic plan")

        if plan.plan_type == "premium" and subject_id:
            raise ValueError("Subject should not be specified for Premium plan")

        subscriptions = []

        for student_id in student_ids:
            # Calculate price based on plan
            price = calculate_subscription_price(db, plan_id, 1, billing_cycle)

            # Calculate end date based on billing cycle
            start_date = datetime.now()
            if billing_cycle == BILLING_CYCLE_MONTHLY:
                end_date = start_date + timedelta(days=30)
            else:  # yearly
                end_date = start_date + timedelta(days=365)

            subscription_data = SubscriptionCreate(
                parent_id=parent_id,
                student_id=student_id,
                subject_id=subject_id if plan.plan_type == "basic" else None,
                plan_id=plan_id,
                billing_cycle=billing_cycle,
                status="active",
                price=price,
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
            active_subs = get_subscriptions_by_user(db, parent.id)
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

    def get_billing_summary(self, db: Session, parent_id: UUID) -> Dict[str, Any]:
        """Get a comprehensive billing summary for a parent"""
        subscriptions = get_subscriptions_by_user(db, parent_id)
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

        # Calculate trial start date from user registration
        trial_start_date = None
        if user and user.created_at and in_trial:
            trial_start_date = user.created_at

        return {
            "active_subscriptions": len(active_subs),
            "trial_subscriptions": len(trial_subs),
            "past_due_subscriptions": len(past_due_subs),
            "total_monthly_cost": total_monthly_cost,
            "next_payment_date": next_payment_date,
            "in_free_trial": in_trial,
            "trial_end_date": trial_end_date,
            "trial_start_date": trial_start_date,
            "days_remaining_in_trial": (trial_end_date - datetime.now()).days if trial_end_date and trial_end_date > datetime.now() else 0,
            "payment_methods": len(billing_info),
            "has_payment_method": len(billing_info) > 0,
            "students_enrolled": len(set(sub.student_id for sub in subscriptions if sub.student_id)),
            "subjects_subscribed": len(set(sub.subject_id for sub in subscriptions if sub.subject_id))
        }

    def check_subscription_status(self, db: Session, parent_id: UUID, student_id: UUID, subject_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Check the subscription status for a specific student/subject"""
        subscriptions = get_subscriptions_by_user(db, parent_id)

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

    def get_pricing_options(self, db: Session) -> Dict[str, Any]:
        """Get available pricing options from subscription plans"""
        plans = get_active_subscription_plans(db)
        pricing_options = []

        for plan in plans:
            # Calculate monthly and yearly prices
            monthly_price = calculate_subscription_price(db, plan.id, 1, BILLING_CYCLE_MONTHLY)
            yearly_price = calculate_subscription_price(db, plan.id, 1, BILLING_CYCLE_ANNUAL)

            # Get features for this plan
            features = get_plan_features_by_plan(db, plan.id)

            # Get subjects for Basic plans
            plan_subjects = []
            if plan.plan_type == "basic":
                from app.crud.billing import get_plan_subjects_by_plan
                subjects = get_plan_subjects_by_plan(db, plan.id)
                for subject_association in subjects:
                    if subject_association.subject:
                        plan_subjects.append({
                            "subject_id": subject_association.subject.id,
                            "name": subject_association.subject.name,
                            "description": subject_association.subject.description
                        })

            pricing_options.append({
                "plan_id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "plan_type": plan.plan_type,
                "trial_days": plan.trial_days,
                "monthly_price": monthly_price,
                "yearly_price": yearly_price,
                "currency": plan.currency,
                "features": [
                    {"name": feature.feature_name, "description": feature.feature_description}
                    for feature in features
                ],
                "subjects": plan_subjects if plan.plan_type == "basic" else ["all"]
            })

        return {
            "pricing_options": pricing_options,
            "free_trial_days": self.FREE_TRIAL_DAYS,
            "available_billing_cycles": [BILLING_CYCLE_MONTHLY, BILLING_CYCLE_ANNUAL],
            "total_subjects_available": get_total_subjects_count(db),
            "plan_types": [
                {
                    "type": "basic",
                    "description": "Covers exactly one subject",
                    "price_description": "$25 USD per month per student per subject"
                },
                {
                    "type": "premium",
                    "description": "Covers all subjects (Math, Science, English, Humanities)",
                    "price_description": "$80 USD per month per student"
                }
            ]
        }

    def validate_free_trial_eligibility(self, db: Session, parent_id: UUID) -> Dict[str, Any]:
        """Check if a parent is eligible for a free trial"""
        parent = get_user(db, parent_id)
        if not parent:
            return {"eligible": False, "reason": "Parent not found"}

        # Check if already used trial
        if is_in_free_trial(db, parent_id):
            return {"eligible": False, "reason": "Already in free trial"}

        # Check if parent already had a trial in the past
        subscriptions = get_subscriptions_by_user(db, parent_id)
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

    def extend_trial(
        self, db: Session, subscription_id: UUID, admin_id: UUID,
        extension_days: int, reason: str = None
    ):
        """Extend a student's trial period"""
        from app.crud.billing import get_subscription

        subscription = get_subscription(db, subscription_id)

        if not subscription:
            raise ValueError("Subscription not found")

        if subscription.status != "trial":
            raise ValueError("Cannot extend non-trial subscription")

        if not subscription.trial_end_date:
            raise ValueError("Subscription has no trial end date")

        # Create trial extension record
        trial_extension_data = TrialExtensionCreate(
            subscription_id=subscription_id,
            extended_by_admin_id=admin_id,
            extension_days=extension_days,
            reason=reason
        )

        extension = create_trial_extension(db, trial_extension_data)

        return {
            "success": True,
            "subscription_id": subscription_id,
            "old_trial_end": extension.original_trial_end,
            "new_trial_end": extension.new_trial_end,
            "extension_days": extension_days,
            "extension_id": extension.id
        }

    def get_trial_extensions(self, db: Session, subscription_id: UUID):
        """Get all trial extensions for a subscription"""
        extensions = get_trial_extensions_by_subscription(db, subscription_id)

        return [{
            "id": ext.id,
            "subscription_id": ext.subscription_id,
            "extended_by_admin_id": ext.extended_by_admin_id,
            "original_trial_end": ext.original_trial_end,
            "new_trial_end": ext.new_trial_end,
            "extension_days": ext.extension_days,
            "reason": ext.reason,
            "created_at": ext.created_at
        } for ext in extensions]

    def start_trial_for_student(
        self, db: Session, student_id: UUID,
        plan_id: UUID = None, subject_id: UUID = None
    ):
        """Start a trial for a student when they complete registration"""
        from app.crud.user import get_student_profile
        from app.crud.billing import get_subscription_plan

        # Get student profile
        student_profile = get_student_profile(db, student_id)
        if not student_profile:
            raise ValueError("Student profile not found")

        if not student_profile.registration_completed_at:
            raise ValueError("Student registration not completed")

        # Get parent ID
        parent_id = student_profile.parent_id

        # Check if student already has a trial
        existing_trials = get_subscriptions_by_user(db, parent_id)
        existing_trials = [sub for sub in existing_trials if sub.student_id == student_id and sub.status == "trial"]

        if existing_trials:
            return {"success": False, "reason": "Student already has an active trial"}

        # Get default trial duration
        trial_duration = self.FREE_TRIAL_DAYS
        if plan_id:
            plan = get_subscription_plan(db, plan_id)
            if plan:
                trial_duration = plan.trial_days

        # Calculate trial end date
        trial_end_at = student_profile.registration_completed_at + timedelta(days=trial_duration)

        # Create trial subscription
        subscription_data = SubscriptionCreate(
            parent_id=parent_id,
            student_id=student_id,
            subject_id=subject_id,
            status="trial",
            price=0.00,  # Trial is free
            trial_end_date=trial_end_at
        )

        trial_subscription = create_subscription(db, subscription_data, parent_id)

        return {
            "success": True,
            "subscription_id": trial_subscription.id,
            "student_id": student_id,
            "parent_id": parent_id,
            "trial_end_date": trial_end_at,
            "status": "trial"
        }

# Singleton instance for easy access
billing_service = BillingService()