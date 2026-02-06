from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from app.crud.user import get_user
from app.models.billing import Subscription, Payment, BillingInfo, Invoice, SubscriptionPlan, PlanFeature, PlanSubject, TrialExtension
from app.schemas.billing import (
    SubscriptionCreate, SubscriptionUpdate, PaymentCreate, PaymentUpdate,
    BillingInfoCreate, BillingInfoUpdate, InvoiceCreate, InvoiceUpdate,
    SubscriptionPlanCreate, SubscriptionPlanUpdate, PlanFeatureCreate, PlanFeatureUpdate,
    PlanSubjectCreate, TrialExtensionCreate
)

from app.constants.constants import (
    BASIC_PLAN_PRICE_PER_SUBJECT, PREMIUM_PLAN_PRICE, DEFAULT_YEARLY_DISCOUNT_PERCENTAGE,
    BILLING_CYCLE_ANNUAL, DEFAULT_TRIAL_PERIOD_DAYS, DEFAULT_YEARLY_DISCOUNT_PERCENTAGE,
    PAYMENT_PLAN_BASIC
)

# Subscription CRUD operations

def create_trial_subscription(db: Session, parent_id: UUID, student_id: UUID, trial_end_date: datetime) -> Subscription:
    db_subscription = Subscription(
        parent_id=parent_id,
        student_id=student_id,
        subject_ids='[]',  # Empty list for trial
        status=subscription.status,
        price=subscription.price,
        currency=subscription.currency,
        payment_method=subscription.payment_method,
        trial_end_date=subscription.trial_end_date,
        end_date=subscription.end_date
    )

    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def create_subscription(db: Session, subscription: SubscriptionCreate, user_id: UUID):
    """Create a new subscription for a parent"""

    db_subscription = Subscription(
        user_id=user_id,
        student_id=subscription.student_id,
        subject_ids=subscription.subject_ids,
        status=subscription.status,
        price=subscription.price,
        currency=subscription.currency,
        payment_method=subscription.payment_method,
        trial_end_date=subscription.trial_end_date,
        end_date=subscription.end_date
    )

    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def get_subscription(db: Session, subscription_id: UUID) -> Optional[Subscription]:
    """Get a subscription by ID"""
    return db.query(Subscription).filter(Subscription.id == subscription_id).first()

def get_subscriptions_by_user(db: Session, user_id: UUID) -> List[Subscription]:
    """Get all subscriptions for a parent"""
    return db.query(Subscription).filter(Subscription.user_id == user_id).all()

def get_subscriptions_by_student(db: Session, student_id: UUID) -> List[Subscription]:
    """Get all subscriptions for a student"""
    return db.query(Subscription).filter(Subscription.student_id == student_id).all()

def get_all_subscriptions(db: Session) -> List[Subscription]:
    """Get all subscriptions"""
    return db.query(Subscription).all()

def update_subscription(db: Session, subscription_id: UUID, subscription_update: SubscriptionUpdate):
    """Update a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return None

    for key, value in subscription_update.dict(exclude_unset=True).items():
        setattr(db_subscription, key, value)

    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def cancel_subscription(db: Session, subscription_id: UUID):
    """Cancel a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return None

    db_subscription.status = "cancelled"
    db_subscription.end_date = datetime.now()
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def delete_subscription(db: Session, subscription_id: UUID) -> bool:
    """Delete a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return False

    db.delete(db_subscription)
    db.commit()
    return True

def get_active_subscriptions(db: Session, user_id: Optional[UUID] = None) -> List[Subscription]:
    """Get all active subscriptions for a user (parent or student)"""
    # Check if this is a parent user by looking for subscriptions where they are the parent
    parent_subscriptions = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status.in_(["active", "trial"])
    ).all()

    # If no parent subscriptions found, check if this is a student user
    if not parent_subscriptions:
        student_subscriptions = db.query(Subscription).filter(
            Subscription.student_id == user_id,
            Subscription.status.in_(["active", "trial"])
        ).all()
        return student_subscriptions

    return parent_subscriptions

def get_trial_subscriptions(db: Session, parent_id: UUID) -> List[Subscription]:
    """Get all trial subscriptions for a parent"""
    return db.query(Subscription).filter(
        Subscription.user_id == parent_id,
        Subscription.status == "trial"
    ).all()

def is_in_free_trial(db: Session, parent_id: UUID) -> bool:
    """Check if parent has any active trial subscriptions"""
    trial_subs = get_trial_subscriptions(db, parent_id)
    now = datetime.now()

    for sub in trial_subs:
        if sub.trial_end_date and sub.trial_end_date > now:
            return True

    return False

def start_free_trial(db: Session, parent_id: UUID, student_id: Optional[UUID] = None, subject_id: Optional[UUID] = None) -> Subscription:
    """Start a free trial for a parent"""
    trial_end_date = datetime.now() + timedelta(days=DEFAULT_TRIAL_PERIOD_DAYS)

    subscription_create = SubscriptionCreate(
        user_id=parent_id,
        student_id=student_id,  # Can be None for parent-level trials
        subject_id=subject_id,
        status="trial",
        price=25.00,
        trial_end_date=trial_end_date
    )

    return create_subscription(db, subscription_create, parent_id)

# Payment CRUD operations

def create_payment(db: Session, payment: PaymentCreate):
    """Create a new payment"""
    db_payment = Payment(
        subscription_id=payment.subscription_id,
        amount=payment.amount,
        currency=payment.currency,
        payment_method=payment.payment_method,
        transaction_id=payment.transaction_id,
        description=payment.description
    )

    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment(db: Session, payment_id: UUID) -> Optional[Payment]:
    """Get a payment by ID"""
    return db.query(Payment).filter(Payment.id == payment_id).first()

def get_payments_by_subscription(db: Session, subscription_id: UUID) -> List[Payment]:
    """Get all payments for a subscription"""
    return db.query(Payment).filter(Payment.subscription_id == subscription_id).all()

def get_payments_by_user(db: Session, user_id: UUID) -> List[Payment]:
    """Get all payments for a user (parent)"""
    # Get all subscriptions for the user
    subscriptions = get_subscriptions_by_user(db, user_id)
    subscription_ids = [sub.id for sub in subscriptions]

    if not subscription_ids:
        return []

    return db.query(Payment).filter(Payment.subscription_id.in_(subscription_ids)).all()

def update_payment(db: Session, payment_id: UUID, payment_update: PaymentUpdate):
    """Update a payment"""
    db_payment = get_payment(db, payment_id)
    if not db_payment:
        return None

    for key, value in payment_update.dict(exclude_unset=True).items():
        setattr(db_payment, key, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment

def mark_payment_as_paid(db: Session, payment_id: UUID, transaction_id: UUID):
    """Mark a payment as paid"""
    db_payment = get_payment(db, payment_id)
    if not db_payment:
        return None

    db_payment.status = "paid"
    db_payment.transaction_id = transaction_id
    db_payment.payment_date = datetime.now()

    # Update the associated subscription status
    subscription = get_subscription(db, db_payment.subscription_id)
    if subscription:
        subscription.payment_status = "paid"
        db.commit()

    db.commit()
    db.refresh(db_payment)
    return db_payment

def mark_payment_as_failed(db: Session, payment_id: UUID, reason: str):
    """Mark a payment as failed"""
    db_payment = get_payment(db, payment_id)
    if not db_payment:
        return None

    db_payment.status = "failed"
    db_payment.description = f"Payment failed: {reason}"

    # Update the associated subscription status
    subscription = get_subscription(db, db_payment.subscription_id)
    if subscription:
        subscription.payment_status = "failed"
        subscription.status = "past_due"
        db.commit()

    db.commit()
    db.refresh(db_payment)
    return db_payment

# Billing Info CRUD operations

def create_billing_info(db: Session, billing_info: BillingInfoCreate):
    """Create billing information for a user"""
    # If this is the default billing info, set all others to non-default
    if billing_info.is_default:
        db.query(BillingInfo).filter(BillingInfo.user_id == billing_info.user_id).update({"is_default": False})

    db_billing = BillingInfo(
        user_id=billing_info.user_id,
        payment_method=billing_info.payment_method,
        card_last_four=billing_info.card_last_four,
        card_brand=billing_info.card_brand,
        card_expiry=billing_info.card_expiry,
        billing_address=billing_info.billing_address,
        billing_city=billing_info.billing_city,
        billing_state=billing_info.billing_state,
        billing_postal_code=billing_info.billing_postal_code,
        billing_country=billing_info.billing_country,
        is_default=billing_info.is_default
    )

    db.add(db_billing)
    db.commit()
    db.refresh(db_billing)
    return db_billing

def get_billing_info(db: Session, billing_id: UUID) -> Optional[BillingInfo]:
    """Get billing information by ID"""
    return db.query(BillingInfo).filter(BillingInfo.id == billing_id).first()

def get_billing_info_by_user(db: Session, user_id: UUID) -> List[BillingInfo]:
    """Get all billing information for a user"""
    return db.query(BillingInfo).filter(BillingInfo.user_id == user_id).all()

def get_default_billing_info(db: Session, user_id: UUID) -> Optional[BillingInfo]:
    """Get the default billing information for a user"""
    return db.query(BillingInfo).filter(
        BillingInfo.user_id == user_id,
        BillingInfo.is_default == True
    ).first()

def update_billing_info(db: Session, billing_id: UUID, billing_update: BillingInfoUpdate):
    """Update billing information"""
    db_billing = get_billing_info(db, billing_id)
    if not db_billing:
        return None

    # If setting to default, update other records
    if billing_update.is_default:
        db.query(BillingInfo).filter(
            BillingInfo.user_id == db_billing.user_id,
            BillingInfo.id != billing_id
        ).update({"is_default": False})

    for key, value in billing_update.dict(exclude_unset=True).items():
        setattr(db_billing, key, value)

    db.commit()
    db.refresh(db_billing)
    return db_billing

def delete_billing_info(db: Session, billing_id: UUID) -> bool:
    """Delete billing information"""
    db_billing = get_billing_info(db, billing_id)
    if not db_billing:
        return False

    db.delete(db_billing)
    db.commit()
    return True

# Subscription Plan CRUD operations

def create_subscription_plan(db: Session, plan: SubscriptionPlanCreate) -> SubscriptionPlan:
    """Create a new subscription plan"""
    db_plan = SubscriptionPlan(
        name=plan.name,
        description=plan.description,
        base_price=plan.base_price,
        discount_percentage=plan.discount_percentage,
        currency=plan.currency,
        trial_days=plan.trial_days,
        yearly_discount=DEFAULT_YEARLY_DISCOUNT_PERCENTAGE,
        is_active=plan.is_active,
        sort_order=plan.sort_order,
        plan_type=plan.plan_type
    )

    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

def get_subscription_plan(db: Session, plan_id: UUID) -> Optional[SubscriptionPlan]:
    """Get a subscription plan by ID"""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

def get_subscription_plan_by_name(db: Session, name: str) -> Optional[SubscriptionPlan]:
    """Get a subscription plan by name"""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.name == name).first()

def get_all_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    """Get all subscription plans"""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.sort_order).all()

def get_active_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    """Get all active subscription plans"""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.sort_order).all()

def update_subscription_plan(db: Session, plan_id: UUID, plan_update: SubscriptionPlanUpdate) -> Optional[SubscriptionPlan]:
    """Update a subscription plan"""
    db_plan = get_subscription_plan(db, plan_id)
    if not db_plan:
        return None

    for key, value in plan_update.dict(exclude_unset=True).items():
        setattr(db_plan, key, value)

    db.commit()
    db.refresh(db_plan)
    return db_plan

def delete_subscription_plan(db: Session, plan_id: UUID) -> bool:
    """Delete a subscription plan"""
    db_plan = get_subscription_plan(db, plan_id)
    if not db_plan:
        return False

    db.delete(db_plan)
    db.commit()
    return True

# Plan Feature CRUD operations

def create_plan_feature(db: Session, feature: PlanFeatureCreate) -> PlanFeature:
    """Create a new plan feature"""
    db_feature = PlanFeature(
        plan_id=feature.plan_id,
        feature_name=feature.feature_name,
        feature_description=feature.feature_description,
        is_included=feature.is_included
    )

    db.add(db_feature)
    db.commit()
    db.refresh(db_feature)
    return db_feature

def get_plan_feature(db: Session, feature_id: UUID) -> Optional[PlanFeature]:
    """Get a plan feature by ID"""
    return db.query(PlanFeature).filter(PlanFeature.id == feature_id).first()

def get_plan_features_by_plan(db: Session, plan_id: UUID) -> List[PlanFeature]:
    """Get all features for a specific plan"""
    return db.query(PlanFeature).filter(PlanFeature.plan_id == plan_id).all()

def update_plan_feature(db: Session, feature_id: UUID, feature_update: PlanFeatureUpdate) -> Optional[PlanFeature]:
    """Update a plan feature"""
    db_feature = get_plan_feature(db, feature_id)
    if not db_feature:
        return None

    for key, value in feature_update.dict(exclude_unset=True).items():
        setattr(db_feature, key, value)

    db.commit()
    db.refresh(db_feature)
    return db_feature

def delete_plan_feature(db: Session, feature_id: UUID) -> bool:
    """Delete a plan feature"""
    db_feature = get_plan_feature(db, feature_id)
    if not db_feature:
        return False

    db.delete(db_feature)
    db.commit()
    return True

# Plan Subject CRUD operations

def create_plan_subject(db: Session, plan_subject: PlanSubjectCreate) -> PlanSubject:
    """Create a new plan subject association"""
    db_plan_subject = PlanSubject(
        plan_id=plan_subject.plan_id,
        subject_id=plan_subject.subject_id
    )

    db.add(db_plan_subject)
    db.commit()
    db.refresh(db_plan_subject)
    return db_plan_subject

def get_plan_subject(db: Session, plan_subject_id: UUID) -> Optional[PlanSubject]:
    """Get a plan subject by ID"""
    return db.query(PlanSubject).filter(PlanSubject.id == plan_subject_id).first()

def get_plan_subjects_by_plan(db: Session, plan_id: UUID) -> List[PlanSubject]:
    """Get all subjects for a specific plan"""
    return db.query(PlanSubject).filter(PlanSubject.plan_id == plan_id).all()

def get_plan_subjects_by_subject(db: Session, subject_id: UUID) -> List[PlanSubject]:
    """Get all plans that include a specific subject"""
    return db.query(PlanSubject).filter(PlanSubject.subject_id == subject_id).all()

def delete_plan_subject(db: Session, plan_subject_id: UUID) -> bool:
    """Delete a plan subject association"""
    db_plan_subject = get_plan_subject(db, plan_subject_id)
    if not db_plan_subject:
        return False

    db.delete(db_plan_subject)
    db.commit()
    return True

# Trial Extension CRUD operations

def create_trial_extension(db: Session, trial_extension: TrialExtensionCreate):
    """Create a trial extension record"""
    db_extension = TrialExtension(
        subscription_id=trial_extension.subscription_id,
        extended_by_admin_id=trial_extension.extended_by_admin_id,
        extension_days=trial_extension.extension_days,
        reason=trial_extension.reason
    )

    # Set original and new trial end dates
    subscription = get_subscription(db, trial_extension.subscription_id)
    if subscription and subscription.trial_end_date:
        db_extension.original_trial_end = subscription.trial_end_date
        db_extension.new_trial_end = subscription.trial_end_date + timedelta(days=trial_extension.extension_days)

        # Update the subscription's trial end date
        subscription.trial_end_date = db_extension.new_trial_end

    db.add(db_extension)
    db.commit()
    db.refresh(db_extension)
    return db_extension

def get_trial_extensions_by_subscription(db: Session, subscription_id: UUID):
    """Get all trial extensions for a subscription"""
    return db.query(TrialExtension).filter(TrialExtension.subscription_id == subscription_id).all()

def get_trial_extension(db: Session, extension_id: UUID):
    """Get a trial extension by ID"""
    return db.query(TrialExtension).filter(TrialExtension.id == extension_id).first()

# Pricing calculation functions

def calculate_subscription_price(db: Session, plan_id: UUID, num_subjects: int = 1, billing_cycle: str = BILLING_CYCLE_ANNUAL) -> float:
    """Calculate subscription price based on plan and billing cycle"""

    plan = get_subscription_plan(db, plan_id)

    if plan.plan_type == PAYMENT_PLAN_BASIC:
        # Basic plan: fixed price per subject ($25 per subject)
        base_price = BASIC_PLAN_PRICE_PER_SUBJECT * num_subjects
    else:  # premium
        # Premium plan: fixed price for all subjects
        base_price = PREMIUM_PLAN_PRICE

    # Apply yearly discount if applicable (20%)
    if billing_cycle == BILLING_CYCLE_ANNUAL:
        yearly_discount = Decimal(DEFAULT_YEARLY_DISCOUNT_PERCENTAGE / 100)
        final_price = Decimal(plan.base_price) * Decimal(12) * (Decimal(1.0) - yearly_discount)
    else:
        final_price = base_price

    return round(final_price, 2)

def get_total_subjects_count(db: Session) -> int:
    """Get total number of available subjects"""
    from app.models.subject import Subject
    return db.query(Subject).count()

# Invoice CRUD operations

def create_invoice(db: Session, invoice: InvoiceCreate):
    """Create a new invoice"""
    db_invoice = Invoice(
        user_id=invoice.user_id,
        subscription_id=invoice.subscription_id,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        status=invoice.status,
        due_date=invoice.due_date,
        paid_date=invoice.paid_date,
        pdf_url=invoice.pdf_url
    )

    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

def get_invoice(db: Session, invoice_id: UUID) -> Optional[Invoice]:
    """Get an invoice by ID"""
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()

def get_invoices_by_user(db: Session, user_id: UUID) -> List[Invoice]:
    """Get all invoices for a user"""
    return db.query(Invoice).filter(Invoice.user_id == user_id).order_by(Invoice.created_at.desc()).all()

def get_invoices_by_subscription(db: Session, subscription_id: UUID) -> List[Invoice]:
    """Get all invoices for a subscription"""
    return db.query(Invoice).filter(Invoice.subscription_id == subscription_id).order_by(Invoice.created_at.desc()).all()

def update_invoice(db: Session, invoice_id: UUID, invoice_update: InvoiceUpdate):
    """Update an invoice"""
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        return None

    for key, value in invoice_update.dict(exclude_unset=True).items():
        setattr(db_invoice, key, value)

    db.commit()
    db.refresh(db_invoice)
    return db_invoice

def mark_invoice_as_paid(db: Session, invoice_id: UUID):
    """Mark an invoice as paid"""
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        return None

    db_invoice.status = "paid"
    db_invoice.paid_date = datetime.now()

    db.commit()
    db.refresh(db_invoice)
    return db_invoice

# Billing Summary and Helper Functions

def check_trial_status(db: Session, user_id: UUID) -> dict:
    """Check if user has active trials and their status"""
    from datetime import datetime

    subscriptions = get_subscriptions_by_user(db, user_id)
    trial_subs = [sub for sub in subscriptions if sub.status == "trial"]

    if not trial_subs:
        return {"has_trial": False, "trial_expired": False, "days_remaining": 0}

    # Find the latest trial end date
    trial_end_dates = [sub.trial_end_date for sub in trial_subs if sub.trial_end_date]
    if not trial_end_dates:
        return {"has_trial": True, "trial_expired": False, "days_remaining": 0}

    latest_trial_end = max(trial_end_dates)
    now = datetime.now()

    if latest_trial_end > now:
        days_remaining = (latest_trial_end - now).days
        return {"has_trial": True, "trial_expired": False, "days_remaining": days_remaining}
    else:
        return {"has_trial": True, "trial_expired": True, "days_remaining": 0}

def get_billing_summary(db: Session, user_id: int):
    """Get a summary of billing information for a user"""

    subscriptions = get_subscriptions_by_user(db, user_id)
    payments = get_payments_by_user(db, user_id)
    billing_info = get_billing_info_by_user(db, user_id)
    user = get_user(db, user_id)

    active_subs = [sub for sub in subscriptions if sub.status in ["active", "trial"]]
    trial_subs = [sub for sub in subscriptions if sub.status == "trial"]
    past_due_subs = [sub for sub in subscriptions if sub.status == "past_due"]

    # Calculate total monthly cost (sum of all active subscription prices)
    total_monthly_cost = 0.0
    for sub in active_subs:
        if sub.status == "active":  # Only count paid subscriptions for monthly cost
            total_monthly_cost += float(sub.price)

    # Check if user is in free trial
    in_free_trial = len(trial_subs) > 0

    # Find trial end date and days remaining
    trial_end_date = None
    trial_start_date = None
    days_remaining_in_trial = 0
    if trial_subs:
        # Find the latest trial end date
        trial_end_dates = [sub.trial_end_date for sub in trial_subs if sub.trial_end_date]
        if trial_end_dates:
            trial_end_date = max(trial_end_dates)
            if trial_end_date > datetime.now():
                days_remaining_in_trial = (trial_end_date - datetime.now()).days
            else:
                days_remaining_in_trial = 0

        # Calculate trial start date from user registration if no explicit trial start
        if user and user.created_at:
            trial_start_date = user.created_at
    elif active_subs == 0 and user and user.created_at:
        # For users with no subscriptions, assume trial started at registration
        trial_start_date = user.created_at
        trial_end_date = user.created_at + timedelta(days=DEFAULT_TRIAL_PERIOD_DAYS)
        if trial_end_date > datetime.now():
            days_remaining_in_trial = (trial_end_date - datetime.now()).days
        else:
            days_remaining_in_trial = 0

    # Find next payment date
    pending_payments = [p for p in payments if p.status == "pending"]
    next_payment_date = None
    if pending_payments:
        # Find the earliest due payment
        next_payment_date = min(p.payment_date for p in pending_payments if p.payment_date)

    # Check if user has payment methods
    has_payment_method = len(billing_info) > 0

    return {
        "active_subscriptions": len(active_subs),
        "trial_subscriptions": len(trial_subs),
        "past_due_subscriptions": len(past_due_subs),
        "total_monthly_cost": total_monthly_cost,
        "next_payment_date": next_payment_date,
        "in_free_trial": in_free_trial,
        "trial_end_date": trial_end_date,
        "trial_start_date": trial_start_date,
        "days_remaining_in_trial": days_remaining_in_trial,
        "payment_methods": len(billing_info),
        "has_payment_method": has_payment_method
    }