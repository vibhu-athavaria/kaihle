from decimal import Decimal
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID
from app.constants.constants import BILLING_CYCLE_ANNUAL

class SubscriptionStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    trial = "trial"
    past_due = "past_due"

class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"
    disputed = "disputed"

class SubscriptionBase(BaseModel):
    parent_id: UUID
    student_id: UUID
    subject_ids: List[UUID] = None
    status: SubscriptionStatus = SubscriptionStatus.active
    price: float
    currency: str = "USD"
    payment_method: str

class SubscriptionCreate(SubscriptionBase):
    trial_end_date: Optional[datetime] = None
    end_date: datetime

class SubscriptionUpdate(BaseModel):
    status: Optional[SubscriptionStatus] = None
    payment_method: Optional[str] = None
    price: Optional[float] = None
    trial_end_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SubscriptionResponse(SubscriptionBase):
    id: UUID
    start_date: datetime
    trial_end_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_status: PaymentStatus = PaymentStatus.pending
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentBase(BaseModel):
    subscription_id: UUID
    amount: float
    currency: str = "USD"
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    description: Optional[str] = None

class PaymentCreate(PaymentBase):
    plan_id: UUID
    billing_cycle: str = BILLING_CYCLE_ANNUAL  # monthly or annual
    student_ids: List[UUID] = []
    subject_ids: Optional[List[UUID]] = None

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: UUID
    status: PaymentStatus = PaymentStatus.pending
    payment_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BillingInfoBase(BaseModel):
    user_id: UUID
    payment_method: Optional[str] = None
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    card_expiry: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    is_default: bool = True

class BillingInfoCreate(BillingInfoBase):
    pass

class BillingInfoUpdate(BaseModel):
    payment_method: Optional[str] = None
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    card_expiry: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    is_default: Optional[bool] = None

class BillingInfoResponse(BillingInfoBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    user_id: UUID
    subscription_id: UUID
    invoice_number: str
    amount: float
    currency: str = "USD"
    status: str = "draft"
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    pdf_url: Optional[str] = None

class InvoiceCreate(InvoiceBase):
    pass

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    pdf_url: Optional[str] = None

class InvoiceResponse(InvoiceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SubscriptionWithPayments(SubscriptionResponse):
    payments: List[PaymentResponse] = []

class UserBillingSummary(BaseModel):
    active_subscriptions: int = 0
    trial_subscriptions: int = 0
    past_due_subscriptions: int = 0
    total_monthly_cost: float = 0.0
    next_payment_date: Optional[datetime] = None
    in_free_trial: bool = False
    trial_end_date: Optional[datetime] = None
    trial_start_date: Optional[datetime] = None
    days_remaining_in_trial: int = 0
    payment_methods: int = 0
    has_payment_method: bool = False

class PaymentMethodResponse(BaseModel):
    id: UUID
    payment_method: str
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    card_expiry: Optional[str] = None
    is_default: bool = False

# Subscription Plan Schemas
class SubscriptionPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    base_price: float
    discount_percentage: float = 0.00
    currency: str = "USD"
    trial_days: int = 15
    yearly_discount: float = 10.00
    is_active: bool = True
    sort_order: int = 0
    plan_type: str  # "basic" or "premium"

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class TrialExtensionBase(BaseModel):
    subscription_id: UUID
    extended_by_admin_id: UUID
    extension_days: int
    reason: Optional[str] = None

class TrialExtensionCreate(TrialExtensionBase):
    pass

class TrialExtensionResponse(TrialExtensionBase):
    id: UUID
    original_trial_end: datetime
    new_trial_end: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    currency: Optional[str] = None
    trial_days: Optional[int] = None
    yearly_discount: Optional[float] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    plan_type: Optional[str] = None

class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: UUID
    yearly_price: Optional[Decimal] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PlanFeatureBase(BaseModel):
    plan_id: UUID
    feature_name: str
    feature_description: Optional[str] = None
    is_included: bool = True

class PlanFeatureCreate(PlanFeatureBase):
    pass

class PlanFeatureUpdate(BaseModel):
    feature_name: Optional[str] = None
    feature_description: Optional[str] = None
    is_included: Optional[bool] = None

class PlanFeatureResponse(PlanFeatureBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PlanSubjectBase(BaseModel):
    plan_id: UUID
    subject_id: UUID

class PlanSubjectCreate(PlanSubjectBase):
    pass

class PlanSubjectResponse(PlanSubjectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PricingCalculationResponse(BaseModel):
    plan_id: UUID
    plan_name: str
    plan_type: str
    num_subjects: int
    billing_cycle: str
    price: float
    currency: str
    base_price: float
    discount_percentage: float
    yearly_discount: float