"""Billing SQLAlchemy models.

Covers: subscription_plans, school_subscriptions, subscription_invoices,
payments, trial_extensions
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubscriptionTier:
    """Subscription tier constants."""

    TRIAL = "TRIAL"
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    SCALE = "SCALE"


class SubscriptionStatus:
    """Subscription status constants."""

    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PaymentStatus:
    """Payment status constants."""

    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SubscriptionPlan(Base, UUIDMixin, TimestampMixin):
    """Pricing tier definitions."""

    __tablename__ = "subscription_plans"

    tier: Mapped[str] = mapped_column(
        Enum(
            SubscriptionTier.TRIAL,
            SubscriptionTier.STARTER,
            SubscriptionTier.GROWTH,
            SubscriptionTier.SCALE,
            name="subscription_tier",
        ),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_per_student_annual: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Starter: 75.00 | Growth: 100.00 | Scale: 125.00
    max_students: Mapped[int | None]
    # Starter: 100 | Growth: 500 | Scale: NULL (unlimited)
    trial_days: Mapped[int | None]
    # TRIAL tier only: 15 days. NULL for paid tiers.
    max_curricula: Mapped[int | None]
    # Starter: 1 | Growth: 2 | Scale: NULL (unlimited)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # {
    #   "parent_portal": true,
    #   "teacher_copilot": true,
    #   "api_access": false,
    #   "sla_guarantee": false,
    #   "dedicated_support": false
    # }
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int | None]


class SchoolSubscription(Base, UUIDMixin, TimestampMixin):
    """Per-school subscription."""

    __tablename__ = "school_subscriptions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.CANCELLED,
            SubscriptionStatus.EXPIRED,
            name="subscription_status",
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # agreed headcount at subscription time
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # student_count × price_per_student
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    start_date: Mapped[datetime]
    end_date: Mapped[datetime]
    trial_end_date: Mapped[datetime | None]
    # NULL for non-trial plans
    payment_status: Mapped[str] = mapped_column(
        Enum(
            PaymentStatus.PENDING,
            PaymentStatus.PAID,
            PaymentStatus.FAILED,
            PaymentStatus.REFUNDED,
            name="payment_status",
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    external_ref: Mapped[str | None] = mapped_column(String(200))
    # Stripe subscription ID


class SubscriptionInvoice(Base, UUIDMixin, TimestampMixin):
    """One invoice per billing cycle per school."""

    __tablename__ = "subscription_invoices"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # headcount at invoice time (may differ from subscription)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(
        Enum(
            PaymentStatus.PENDING,
            PaymentStatus.PAID,
            PaymentStatus.FAILED,
            PaymentStatus.REFUNDED,
            name="payment_status",
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    due_date: Mapped[datetime]
    paid_at: Mapped[datetime | None]
    pdf_url: Mapped[str | None] = mapped_column(String(500))
    external_ref: Mapped[str | None] = mapped_column(String(200))
    # Stripe invoice ID


class TrialExtension(Base, UUIDMixin):
    """Audit trail for trial extensions granted by Kaihle Admin."""

    __tablename__ = "trial_extensions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    extended_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_trial_end: Mapped[datetime]
    new_trial_end: Mapped[datetime]
    extension_days: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]

    __table_args__ = (
        CheckConstraint("extension_days > 0", name="chk_te_days"),
        CheckConstraint("new_trial_end > original_trial_end", name="chk_te_direction"),
    )
