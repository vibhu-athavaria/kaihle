from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.billing import (
    create_subscription, get_subscription, get_subscriptions_by_parent,
    update_subscription, cancel_subscription, get_all_subscriptions,
    get_active_subscriptions, get_trial_subscriptions, is_in_free_trial,
    start_free_trial, create_payment, get_payment, get_payments_by_subscription,
    get_payments_by_user, update_payment, mark_payment_as_paid, mark_payment_as_failed,
    create_billing_info, get_billing_info, get_billing_info_by_user,
    get_default_billing_info, update_billing_info, delete_billing_info,
    create_invoice, get_invoice, get_invoices_by_user,
    mark_invoice_as_paid, get_billing_summary,
    create_subscription_plan, get_subscription_plan, get_subscriptions_by_student,
    get_all_subscription_plans, get_active_subscription_plans, update_subscription_plan,
    delete_subscription_plan, create_plan_feature, get_plan_feature, get_plan_features_by_plan,
    update_plan_feature, delete_plan_feature, create_plan_subject, get_plan_subject,
    get_plan_subjects_by_plan, get_plan_subjects_by_subject, delete_plan_subject,
    calculate_subscription_price, get_total_subjects_count, create_trial_extension,
    get_trial_extensions_by_subscription
)
from app.schemas.billing import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    PaymentCreate, PaymentUpdate, PaymentResponse,
    BillingInfoCreate, BillingInfoUpdate, BillingInfoResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    SubscriptionWithPayments, UserBillingSummary, PaymentMethodResponse,
    SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanResponse,
    PlanFeatureCreate, PlanFeatureUpdate, PlanFeatureResponse,
    PlanSubjectCreate, PlanSubjectResponse, PricingCalculationResponse,
    TrialExtensionCreate, TrialExtensionResponse
)
from app.models.user import User as UserModel
from app.schemas.user import User
from app.services.access_control_service import access_control_service


router = APIRouter(tags=["billing"])

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
    if current_user.role == "parent":
        return get_subscriptions_by_parent(db, current_user.id)
    elif current_user.role == "student":
        return get_subscriptions_by_student(db, current_user.id)
    elif current_user.role == "admin":
        return get_all_subscriptions(db)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view subscriptions"
        )

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
    """Get active subscriptions for a specific user"""
    # Check if user has access to this user's data
    if current_user.role != "admin" and current_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's subscription information"
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

@router.post("/trial-extensions", response_model=TrialExtensionResponse)
def create_trial_extension_endpoint(
    trial_extension: TrialExtensionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Extend a student's trial period"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can extend trials"
        )

    # Check if subscription exists and is a trial
    subscription = get_subscription(db, trial_extension.subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    if subscription.status != "trial":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot extend non-trial subscription"
        )

    # Create trial extension
    extension = create_trial_extension(db, trial_extension)

    return extension

@router.get("/trial-extensions/{subscription_id}", response_model=List[TrialExtensionResponse])
def get_trial_extensions_endpoint(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all trial extensions for a subscription"""
    # Check if user has access to this subscription
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    if current_user.role != "admin" and subscription.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this subscription's trial extensions"
        )

    extensions = get_trial_extensions_by_subscription(db, subscription_id)
    return extensions

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

@router.post("/create-payment-intent")
def create_payment_intent(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a Stripe payment intent for subscription payment"""
    import stripe
    from app.core.config import settings

    # Set your secret key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    plan_id = payment_data.plan_id
    billing_cycle = payment_data.billing_cycle
    student_ids = payment_data.student_ids
    subject_ids = payment_data.subject_ids

    # Get plan details
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Validate subject selection based on plan type
    if plan.plan_type == "basic" and (not subject_ids or len(subject_ids) == 0):
        raise HTTPException(status_code=400, detail="Subject is required for Basic plan")

    if plan.plan_type == "premium" and subject_ids:
        raise HTTPException(status_code=400, detail="Subject should not be specified for Premium plan")

    # Calculate price per student
    base_price = calculate_subscription_price(db, plan_id, len(subject_ids), billing_cycle)
    total_price = base_price * len(student_ids)

    try:
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(total_price * 100),  # Amount in cents
            currency='usd',
            metadata={
                'plan_id': plan_id,
                'billing_cycle': billing_cycle,
                'user_id': current_user.id,
                'student_ids': ','.join(map(str, student_ids)),
                'subject_ids': ','.join(map(str, subject_ids)) if subject_ids else ''
            }
        )

        return {
            'client_secret': intent.client_secret,
            'amount': total_price,
            'currency': 'usd'
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/summary", response_model=UserBillingSummary)
def get_billing_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get billing summary for current user"""
    return get_billing_summary(db, current_user.id)

@router.get("/access-status/{student_id}", response_model=dict)
def get_student_access_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get access status for a student"""
    # Check if user has access to this student's data
    from app.crud.user import get_student_profile
    student_profile = get_student_profile(db, student_id)

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Parents can only access their own children
    if current_user.role == "parent" and student_profile.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this student's information"
        )

    return access_control_service.get_student_access_status(db, student_id)

@router.get("/parent-dashboard-status", response_model=dict)
def get_parent_dashboard_status(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get access status for all students of a parent"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access dashboard status"
        )

    return access_control_service.get_parent_dashboard_status(db, current_user.id)

@router.get("/access-check/{student_id}", response_model=dict)
def check_student_access(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Check if student has access to courses"""
    # Check if user has access to this student's data
    from app.crud.user import get_student_profile
    student_profile = get_student_profile(db, student_id)

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Parents can only access their own children
    if current_user.role == "parent" and student_profile.parent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this student's information"
        )

    can_access = access_control_service.can_access_courses(db, student_id)
    notification = access_control_service.get_access_restriction_notification(db, student_id)

    return {
        "can_access_courses": can_access,
        "restriction_notification": notification
    }

# Stripe Webhook Handler
@router.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events"""
    import stripe
    from app.core.config import settings

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the event
    if event.type == "payment_intent.succeeded":
        payment_intent = event.data.object
        await handle_payment_success(db, payment_intent)
    elif event.type == "payment_intent.payment_failed":
        payment_intent = event.data.object
        await handle_payment_failed(db, payment_intent)
    elif event.type == "customer.subscription.updated":
        subscription = event.data.object
        await handle_subscription_update(db, subscription)
    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        await handle_subscription_cancellation(db, subscription)

    return {"status": "success"}

async def handle_payment_success(db: Session, payment_intent):
    """Handle successful payment"""
    # Get metadata from payment intent
    metadata = payment_intent.metadata or {}

    # Create payment record
    payment_data = PaymentCreate(
        subscription_id=int(metadata.get('subscription_id', 0)),
        amount=float(payment_intent.amount / 100),  # Convert from cents
        currency=payment_intent.currency,
        payment_method=payment_intent.payment_method or 'credit_card',
        transaction_id=payment_intent.id,
        description=f"Payment for subscription {metadata.get('subscription_id', '')}"
    )

    create_payment(db, payment_data)

    # Update subscription status if this is a new subscription
    if metadata.get('subscription_id'):
        subscription = get_subscription(db, int(metadata['subscription_id']))
        if subscription:
            subscription.status = "active"
            subscription.payment_status = "paid"
            db.commit()

async def handle_payment_failed(db: Session, payment_intent):
    """Handle failed payment"""
    # Get metadata from payment intent
    metadata = payment_intent.metadata or {}

    # Find and update payment record if it exists
    payments = get_payments_by_subscription(db, int(metadata.get('subscription_id', 0)))
    for payment in payments:
        if payment.transaction_id == payment_intent.id:
            payment.status = "failed"
            payment.description = f"Payment failed: {payment_intent.last_payment_error.message if payment_intent.last_payment_error else 'Unknown error'}"
            db.commit()
            break

    # Update subscription status
    if metadata.get('subscription_id'):
        subscription = get_subscription(db, int(metadata['subscription_id']))
        if subscription:
            subscription.status = "past_due"
            subscription.payment_status = "failed"
            db.commit()

async def handle_subscription_update(db: Session, stripe_subscription):
    """Handle subscription updates from Stripe"""
    # Get metadata from subscription
    metadata = stripe_subscription.metadata or {}

    # Update subscription status in database
    if metadata.get('subscription_id'):
        subscription = get_subscription(db, int(metadata['subscription_id']))
        if subscription:
            # Map Stripe status to our status
            status_mapping = {
                'active': 'active',
                'canceled': 'canceled',
                'past_due': 'past_due',
                'unpaid': 'past_due',
                'incomplete': 'incomplete',
                'incomplete_expired': 'expired'
            }

            stripe_status = stripe_subscription.status
            db_status = status_mapping.get(stripe_status, 'active')

            subscription.status = db_status
            subscription.payment_status = 'paid' if stripe_status == 'active' else 'pending'
            db.commit()

async def handle_subscription_cancellation(db: Session, stripe_subscription):
    """Handle subscription cancellations from Stripe"""
    # Get metadata from subscription
    metadata = stripe_subscription.metadata or {}

    # Update subscription status in database
    if metadata.get('subscription_id'):
        subscription = get_subscription(db, int(metadata['subscription_id']))
        if subscription:
            subscription.status = "canceled"
            subscription.end_date = datetime.now()
            subscription.payment_status = "canceled"
            db.commit()

# Subscription Plan Endpoints

@router.get("/subscription-plans", response_model=List[SubscriptionPlanResponse])
def get_subscription_plans(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all active subscription plans"""
    from app.constants import BASIC_PLAN_PRICE_PER_SUBJECT, PREMIUM_PLAN_PRICE, DEFAULT_YEARLY_DISCOUNT_PERCENTAGE

    plans = get_all_subscription_plans(db)
    for plan in plans:
        if plan.plan_type == 'basic':
            plan.base_price = BASIC_PLAN_PRICE_PER_SUBJECT
            # For yearly pricing, apply discount to annual amount
            yearly_discount = Decimal(DEFAULT_YEARLY_DISCOUNT_PERCENTAGE / 100)
            plan.yearly_price = Decimal(plan.base_price) * Decimal(12) * (Decimal(1.0) - yearly_discount)
        elif plan.plan_type == 'premium':
            plan.base_price = PREMIUM_PLAN_PRICE
            # For yearly pricing, apply discount to annual amount
            yearly_discount = Decimal(DEFAULT_YEARLY_DISCOUNT_PERCENTAGE / 100)
            plan.yearly_price = Decimal(plan.base_price) * Decimal(12) * (Decimal(1.0) - yearly_discount)
    return plans

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