from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.billing import Subscription, Payment, BillingInfo, Invoice
from app.schemas.billing import (
    SubscriptionCreate, SubscriptionUpdate, PaymentCreate, PaymentUpdate,
    BillingInfoCreate, BillingInfoUpdate, InvoiceCreate, InvoiceUpdate
)
from app.models.user import User

# Subscription CRUD operations

def create_subscription(db: Session, subscription: SubscriptionCreate, parent_id: int):
    """Create a new subscription for a parent"""
    db_subscription = Subscription(
        parent_id=parent_id,
        student_id=subscription.student_id,
        subject_id=subscription.subject_id,
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

def get_subscription(db: Session, subscription_id: int) -> Optional[Subscription]:
    """Get a subscription by ID"""
    return db.query(Subscription).filter(Subscription.id == subscription_id).first()

def get_subscriptions_by_parent(db: Session, parent_id: int) -> List[Subscription]:
    """Get all subscriptions for a parent"""
    return db.query(Subscription).filter(Subscription.parent_id == parent_id).all()

def get_subscriptions_by_student(db: Session, student_id: int) -> List[Subscription]:
    """Get all subscriptions for a student"""
    return db.query(Subscription).filter(Subscription.student_id == student_id).all()

def update_subscription(db: Session, subscription_id: int, subscription_update: SubscriptionUpdate):
    """Update a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return None

    for key, value in subscription_update.dict(exclude_unset=True).items():
        setattr(db_subscription, key, value)

    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def cancel_subscription(db: Session, subscription_id: int):
    """Cancel a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return None

    db_subscription.status = "cancelled"
    db_subscription.end_date = datetime.now()
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def delete_subscription(db: Session, subscription_id: int) -> bool:
    """Delete a subscription"""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return False

    db.delete(db_subscription)
    db.commit()
    return True

def get_active_subscriptions(db: Session, parent_id: int) -> List[Subscription]:
    """Get all active subscriptions for a parent"""
    return db.query(Subscription).filter(
        Subscription.parent_id == parent_id,
        Subscription.status.in_(["active", "trial"])
    ).all()

def get_trial_subscriptions(db: Session, parent_id: int) -> List[Subscription]:
    """Get all trial subscriptions for a parent"""
    return db.query(Subscription).filter(
        Subscription.parent_id == parent_id,
        Subscription.status == "trial"
    ).all()

def is_in_free_trial(db: Session, parent_id: int) -> bool:
    """Check if parent has any active trial subscriptions"""
    trial_subs = get_trial_subscriptions(db, parent_id)
    now = datetime.now()

    for sub in trial_subs:
        if sub.trial_end_date and sub.trial_end_date > now:
            return True

    return False

def start_free_trial(db: Session, parent_id: int, student_id: int, subject_id: Optional[int] = None) -> Subscription:
    """Start a free trial for a parent"""
    trial_end_date = datetime.now() + timedelta(days=15)

    subscription_create = SubscriptionCreate(
        parent_id=parent_id,
        student_id=student_id,
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

def get_payment(db: Session, payment_id: int) -> Optional[Payment]:
    """Get a payment by ID"""
    return db.query(Payment).filter(Payment.id == payment_id).first()

def get_payments_by_subscription(db: Session, subscription_id: int) -> List[Payment]:
    """Get all payments for a subscription"""
    return db.query(Payment).filter(Payment.subscription_id == subscription_id).all()

def get_payments_by_user(db: Session, user_id: int) -> List[Payment]:
    """Get all payments for a user (parent)"""
    # Get all subscriptions for the user
    subscriptions = get_subscriptions_by_parent(db, user_id)
    subscription_ids = [sub.id for sub in subscriptions]

    if not subscription_ids:
        return []

    return db.query(Payment).filter(Payment.subscription_id.in_(subscription_ids)).all()

def update_payment(db: Session, payment_id: int, payment_update: PaymentUpdate):
    """Update a payment"""
    db_payment = get_payment(db, payment_id)
    if not db_payment:
        return None

    for key, value in payment_update.dict(exclude_unset=True).items():
        setattr(db_payment, key, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment

def mark_payment_as_paid(db: Session, payment_id: int, transaction_id: str):
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

def mark_payment_as_failed(db: Session, payment_id: int, reason: str):
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

def get_billing_info(db: Session, billing_id: int) -> Optional[BillingInfo]:
    """Get billing information by ID"""
    return db.query(BillingInfo).filter(BillingInfo.id == billing_id).first()

def get_billing_info_by_user(db: Session, user_id: int) -> List[BillingInfo]:
    """Get all billing information for a user"""
    return db.query(BillingInfo).filter(BillingInfo.user_id == user_id).all()

def get_default_billing_info(db: Session, user_id: int) -> Optional[BillingInfo]:
    """Get the default billing information for a user"""
    return db.query(BillingInfo).filter(
        BillingInfo.user_id == user_id,
        BillingInfo.is_default == True
    ).first()

def update_billing_info(db: Session, billing_id: int, billing_update: BillingInfoUpdate):
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

def delete_billing_info(db: Session, billing_id: int) -> bool:
    """Delete billing information"""
    db_billing = get_billing_info(db, billing_id)
    if not db_billing:
        return False

    db.delete(db_billing)
    db.commit()
    return True

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

def get_invoice(db: Session, invoice_id: int) -> Optional[Invoice]:
    """Get an invoice by ID"""
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()

def get_invoices_by_user(db: Session, user_id: int) -> List[Invoice]:
    """Get all invoices for a user"""
    return db.query(Invoice).filter(Invoice.user_id == user_id).order_by(Invoice.created_at.desc()).all()

def get_invoices_by_subscription(db: Session, subscription_id: int) -> List[Invoice]:
    """Get all invoices for a subscription"""
    return db.query(Invoice).filter(Invoice.subscription_id == subscription_id).order_by(Invoice.created_at.desc()).all()

def update_invoice(db: Session, invoice_id: int, invoice_update: InvoiceUpdate):
    """Update an invoice"""
    db_invoice = get_invoice(db, invoice_id)
    if not db_invoice:
        return None

    for key, value in invoice_update.dict(exclude_unset=True).items():
        setattr(db_invoice, key, value)

    db.commit()
    db.refresh(db_invoice)
    return db_invoice

def mark_invoice_as_paid(db: Session, invoice_id: int):
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

def get_billing_summary(db: Session, user_id: int):
    """Get a summary of billing information for a user"""
    subscriptions = get_subscriptions_by_parent(db, user_id)
    payments = get_payments_by_user(db, user_id)
    billing_info = get_billing_info_by_user(db, user_id)

    active_subs = [sub for sub in subscriptions if sub.status in ["active", "trial"]]
    trial_subs = [sub for sub in subscriptions if sub.status == "trial"]
    past_due_subs = [sub for sub in subscriptions if sub.status == "past_due"]

    # Calculate total due
    total_due = 0.0
    for sub in past_due_subs:
        total_due += float(sub.price)

    # Find next payment date
    pending_payments = [p for p in payments if p.status == "pending"]
    next_payment_date = None
    if pending_payments:
        # Find the earliest due payment
        next_payment_date = min(p.payment_date for p in pending_payments if p.payment_date)

    return {
        "active_subscriptions": len(active_subs),
        "trial_subscriptions": len(trial_subs),
        "past_due_subscriptions": len(past_due_subs),
        "total_due": total_due,
        "next_payment_date": next_payment_date,
        "payment_methods": len(billing_info)
    }