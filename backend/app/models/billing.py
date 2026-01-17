from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, DECIMAL
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
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    price = Column(DECIMAL(10, 2), default=25.00)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("User", foreign_keys=[parent_id], backref="parent_subscriptions")
    student = relationship("User", foreign_keys=[student_id], backref="student_subscriptions")
    subject = relationship("Subject", back_populates="subscriptions")
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