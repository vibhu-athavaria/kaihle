from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.billing import (
    create_subscription, get_subscription, get_subscriptions_by_parent,
    update_subscription, cancel_subscription, delete_subscription,
    get_active_subscriptions, get_trial_subscriptions, is_in_free_trial,
    start_free_trial, create_payment, get_payment, get_payments_by_subscription,
    get_payments_by_user, update_payment, mark_payment_as_paid, mark_payment_as_failed,
    create_billing_info, get_billing_info, get_billing_info_by_user,
    get_default_billing_info, update_billing_info, delete_billing_info,
    create_invoice, get_invoice, get_invoices_by_user, get_invoices_by_subscription,
    update_invoice, mark_invoice_as_paid, get_billing_summary,
    create_subscription_plan, get_subscription_plan, get_subscription_plan_by_name,
    get_all_subscription_plans, get_active_subscription_plans, update_subscription_plan,
    delete_subscription_plan, create_plan_feature, get_plan_feature, get_plan_features_by_plan,
    update_plan_feature, delete_plan_feature, create_plan_subject, get_plan_subject,
    get_plan_subjects_by_plan, get_plan_subjects_by_subject, delete_plan_subject,
    calculate_subscription_price, get_total_subjects_count
)
from app.schemas.billing import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    PaymentCreate, PaymentUpdate, PaymentResponse,
    BillingInfoCreate, BillingInfoUpdate, BillingInfoResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    SubscriptionWithPayments, UserBillingSummary, PaymentMethodResponse,
    SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanResponse,
    PlanFeatureCreate, PlanFeatureUpdate, PlanFeatureResponse,
    PlanSubjectCreate, PlanSubjectResponse, PricingCalculationResponse
)
from app.models.user import User as UserModel
from app.schemas.user import User

router = APIRouter(prefix="/billing", tags=["billing"])

# Subscription Endpoints

@router.post("/subscriptions", response_model=SubscriptionResponse)
def create_new_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new subscription"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can create subscriptions"
        )

    return create_subscription(db, subscription, current_user.id)

@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def get_my_subscriptions(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user's subscriptions (for parents)"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access subscription information"
        )

    return get_subscriptions_by_parent(db, current_user.id)

@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription_details(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get subscription details"""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Check if user has access to this subscription
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this subscription"
        )

    return subscription

@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription_details(
    subscription_id: int,
    subscription_update: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update subscription details"""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Check if user has access to this subscription
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this subscription"
        )

    updated_subscription = update_subscription(db, subscription_id, subscription_update)
    if not updated_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    return updated_subscription

@router.delete("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def cancel_my_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Cancel a subscription"""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Check if user has access to this subscription
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this subscription"
        )

    cancelled_subscription = cancel_subscription(db, subscription_id)
    if not cancelled_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    return cancelled_subscription

@router.get("/subscriptions/active", response_model=List[SubscriptionResponse])
def get_active_subscriptions_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get active subscriptions for current user"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access subscription information"
        )

    return get_active_subscriptions(db, current_user.id)

@router.get("/subscriptions/trial", response_model=List[SubscriptionResponse])
def get_trial_subscriptions_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get trial subscriptions for current user"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access subscription information"
        )

    return get_trial_subscriptions(db, current_user.id)

@router.get("/subscriptions/free-trial-status", response_model=dict)
def check_free_trial_status(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Check if user is in free trial"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access trial information"
        )

    in_trial = is_in_free_trial(db, current_user.id)

    # Get trial subscriptions
    trial_subs = get_trial_subscriptions(db, current_user.id)
    trial_info = []

    for sub in trial_subs:
        trial_info.append({
            "subscription_id": sub.id,
            "student_id": sub.student_id,
            "subject_id": sub.subject_id,
            "trial_end_date": sub.trial_end_date,
            "days_remaining": (sub.trial_end_date - datetime.now()).days if sub.trial_end_date else 0
        })

    return {
        "in_free_trial": in_trial,
        "trial_info": trial_info
    }

@router.post("/subscriptions/start-free-trial", response_model=SubscriptionResponse)
def start_free_trial_endpoint(
    student_id: int,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Start a free trial for a student"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can start free trials"
        )

    # Check if already in trial for this student/subject
    trial_subs = get_trial_subscriptions(db, current_user.id)
    for sub in trial_subs:
        if sub.student_id == student_id and (subject_id is None or sub.subject_id == subject_id):
            if sub.trial_end_date and sub.trial_end_date > datetime.now():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Free trial already active for this student/subject"
                )

    return start_free_trial(db, current_user.id, student_id, subject_id)

# Payment Endpoints

@router.post("/payments", response_model=PaymentResponse)
def create_new_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new payment"""
    # Check if user has access to the subscription
    subscription = get_subscription(db, payment.subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create payment for this subscription"
        )

    return create_payment(db, payment)

@router.get("/payments", response_model=List[PaymentResponse])
def get_my_payments(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user's payments"""
    return get_payments_by_user(db, current_user.id)

@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment_details(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get payment details"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    # Check if user has access to this payment
    subscription = get_subscription(db, payment.subscription_id)
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this payment"
        )

    return payment

@router.put("/payments/{payment_id}", response_model=PaymentResponse)
def update_payment_details(
    payment_id: int,
    payment_update: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update payment details"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    # Check if user has access to this payment
    subscription = get_subscription(db, payment.subscription_id)
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this payment"
        )

    updated_payment = update_payment(db, payment_id, payment_update)
    if not updated_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    return updated_payment

@router.post("/payments/{payment_id}/mark-paid", response_model=PaymentResponse)
def mark_payment_paid(
    payment_id: int,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark a payment as paid"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    # Check if user has access to this payment
    subscription = get_subscription(db, payment.subscription_id)
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this payment"
        )

    paid_payment = mark_payment_as_paid(db, payment_id, transaction_id)
    if not paid_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    return paid_payment

@router.post("/payments/{payment_id}/mark-failed", response_model=PaymentResponse)
def mark_payment_failed(
    payment_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark a payment as failed"""
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    # Check if user has access to this payment
    subscription = get_subscription(db, payment.subscription_id)
    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this payment"
        )

    failed_payment = mark_payment_as_failed(db, payment_id, reason)
    if not failed_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    return failed_payment

# Billing Info Endpoints

@router.post("/billing-info", response_model=BillingInfoResponse)
def create_billing_information(
    billing_info: BillingInfoCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create billing information"""
    # Users can only create billing info for themselves
    if billing_info.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create billing information for this user"
        )

    return create_billing_info(db, billing_info)

@router.get("/billing-info", response_model=List[BillingInfoResponse])
def get_my_billing_info(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user's billing information"""
    return get_billing_info_by_user(db, current_user.id)

@router.get("/billing-info/default", response_model=BillingInfoResponse)
def get_default_billing_info_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get default billing information"""
    billing_info = get_default_billing_info(db, current_user.id)
    if not billing_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default billing information found"
        )

    return billing_info

@router.get("/billing-info/{billing_id}", response_model=BillingInfoResponse)
def get_billing_info_details(
    billing_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get billing information details"""
    billing_info = get_billing_info(db, billing_id)
    if not billing_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing information not found"
        )

    # Check if user has access to this billing info
    if current_user.role != "admin" and billing_info.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this billing information"
        )

    return billing_info

@router.put("/billing-info/{billing_id}", response_model=BillingInfoResponse)
def update_billing_information(
    billing_id: int,
    billing_update: BillingInfoUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update billing information"""
    billing_info = get_billing_info(db, billing_id)
    if not billing_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing information not found"
        )

    # Check if user has access to this billing info
    if current_user.role != "admin" and billing_info.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this billing information"
        )

    updated_billing = update_billing_info(db, billing_id, billing_update)
    if not updated_billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing information not found"
        )

    return updated_billing

@router.delete("/billing-info/{billing_id}", response_model=dict)
def delete_billing_information(
    billing_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Delete billing information"""
    billing_info = get_billing_info(db, billing_id)
    if not billing_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing information not found"
        )

    # Check if user has access to this billing info
    if current_user.role != "admin" and billing_info.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this billing information"
        )

    success = delete_billing_info(db, billing_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing information not found"
        )

    return {"message": "Billing information deleted successfully"}

# Invoice Endpoints

@router.post("/invoices", response_model=InvoiceResponse)
def create_new_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Create a new invoice (admin only)"""
    return create_invoice(db, invoice)

@router.get("/invoices", response_model=List[InvoiceResponse])
def get_my_invoices(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user's invoices"""
    return get_invoices_by_user(db, current_user.id)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice_details(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get invoice details"""
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Check if user has access to this invoice
    if current_user.role != "admin" and invoice.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this invoice"
        )

    return invoice

@router.post("/invoices/{invoice_id}/mark-paid", response_model=InvoiceResponse)
def mark_invoice_paid_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark an invoice as paid"""
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Check if user has access to this invoice
    if current_user.role != "admin" and invoice.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this invoice"
        )

    paid_invoice = mark_invoice_as_paid(db, invoice_id)
    if not paid_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    return paid_invoice

# Summary and Helper Endpoints

@router.get("/summary", response_model=UserBillingSummary)
def get_billing_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get billing summary for current user"""
    return get_billing_summary(db, current_user.id)

@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
def get_payment_methods(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all payment methods for current user"""
    billing_info_list = get_billing_info_by_user(db, current_user.id)

    payment_methods = []
    for billing_info in billing_info_list:
        payment_methods.append(PaymentMethodResponse(
            id=billing_info.id,
            payment_method=billing_info.payment_method or "unknown",
            card_last_four=billing_info.card_last_four,
            card_brand=billing_info.card_brand,
            card_expiry=billing_info.card_expiry,
            is_default=billing_info.is_default
        ))

    return payment_methods