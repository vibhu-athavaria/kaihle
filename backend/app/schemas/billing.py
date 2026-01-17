from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

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
    parent_id: int
    student_id: int
    subject_id: Optional[int] = None
    status: SubscriptionStatus = SubscriptionStatus.active
    price: float = 25.00
    currency: str = "USD"
    payment_method: Optional[str] = None

class SubscriptionCreate(SubscriptionBase):
    trial_end_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SubscriptionUpdate(BaseModel):
    status: Optional[SubscriptionStatus] = None
    payment_method: Optional[str] = None
    price: Optional[float] = None
    trial_end_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SubscriptionResponse(SubscriptionBase):
    id: int
    start_date: datetime
    trial_end_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_status: PaymentStatus = PaymentStatus.pending
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentBase(BaseModel):
    subscription_id: int
    amount: float
    currency: str = "USD"
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    description: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: int
    status: PaymentStatus = PaymentStatus.pending
    payment_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BillingInfoBase(BaseModel):
    user_id: int
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
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    user_id: int
    subscription_id: int
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
    id: int
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
    total_due: float = 0.0
    next_payment_date: Optional[datetime] = None
    payment_methods: int = 0

class PaymentMethodResponse(BaseModel):
    id: int
    payment_method: str
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    card_expiry: Optional[str] = None
    is_default: bool = False