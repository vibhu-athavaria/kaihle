from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, DECIMAL, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.crud.mixin import SerializerMixin
import enum

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"
    PAST_DUE = "past_due"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"

class Subscription(Base, SerializerMixin):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    billing_cycle = Column(String(20), default="monthly")  # monthly or yearly
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    price = Column(DECIMAL(10, 2))  # Price will be calculated based on plan
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("User", foreign_keys=[parent_id], backref="parent_subscriptions")
    student = relationship("User", foreign_keys=[student_id], backref="student_subscriptions")
    subject = relationship("Subject", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")

class Payment(Base, SerializerMixin):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(100), nullable=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_date = Column(DateTime(timezone=True), nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    subscription = relationship("Subscription", back_populates="payments")

class BillingInfo(Base, SerializerMixin):
    __tablename__ = "billing_info"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payment_method = Column(String(50), nullable=True)
    card_last_four = Column(String(4), nullable=True)
    card_brand = Column(String(20), nullable=True)
    card_expiry = Column(String(10), nullable=True)
    billing_address = Column(String(500), nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(100), nullable=True)
    billing_postal_code = Column(String(20), nullable=True)
    billing_country = Column(String(100), nullable=True)
    is_default = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="billing_info")

class SubscriptionPlan(Base, SerializerMixin):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    base_price = Column(DECIMAL(10, 2), nullable=True)  # For Basic plan
    discount_percentage = Column(DECIMAL(5, 2), default=0.00)  # For Premium plan
    currency = Column(String(3), default="USD")
    trial_days = Column(Integer, default=15)
    yearly_discount = Column(DECIMAL(5, 2), default=10.00)  # 10% discount for yearly
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    plan_type = Column(String(20), nullable=False)  # "basic" or "premium"

    # Features included in this plan (many-to-many relationship)
    features = relationship("PlanFeature", back_populates="plan")

    # For Basic plan: which subject is included
    # For Premium plan: this will be ignored (all subjects included)
    subjects = relationship("PlanSubject", back_populates="plan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PlanFeature(Base, SerializerMixin):
    __tablename__ = "plan_features"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    feature_name = Column(String(100), nullable=False)
    feature_description = Column(Text, nullable=True)
    is_included = Column(Boolean, default=True)

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="features")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PlanSubject(Base, SerializerMixin):
    __tablename__ = "plan_subjects"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="subjects")
    subject = relationship("Subject")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Invoice(Base, SerializerMixin):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    invoice_number = Column(String(50), unique=True, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), default="draft")  # draft, paid, void, uncollectible
    due_date = Column(DateTime(timezone=True), nullable=True)
    paid_date = Column(DateTime(timezone=True), nullable=True)
    pdf_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="invoices")
    subscription = relationship("Subscription", backref="invoices")