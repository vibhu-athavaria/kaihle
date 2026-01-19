#!/usr/bin/env python3
"""
Seed script for creating initial subscription plans
This script creates the Basic and Premium plans with their features
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.billing import SubscriptionPlan, PlanFeature, PlanSubject
from app.models.subject import Subject
from app.crud.billing import (
    create_subscription_plan, create_plan_feature, create_plan_subject,
    get_subscription_plan_by_name
)

def seed_subscription_plans():
    """Create initial subscription plans"""
    with Session(engine) as db:
        print("Starting subscription plan seeding...")

        # Check if plans already exist
        basic_plan = get_subscription_plan_by_name(db, "Basic")
        premium_plan = get_subscription_plan_by_name(db, "Premium")

        if basic_plan and premium_plan:
            print("Subscription plans already exist. Skipping seeding.")
            return

        # Create Basic Plan
        print("Creating Basic Plan...")
        from app.schemas.billing import SubscriptionPlanCreate
        basic_plan = create_subscription_plan(db, SubscriptionPlanCreate(
            name="Basic",
            description="Perfect for one student and one subject",
            base_price=25.00,
            discount_percentage=0.00,
            currency="USD",
            trial_days=15,
            yearly_discount=10.00,
            is_active=True,
            sort_order=1,
            plan_type="basic"
        ))

        # Add features to Basic Plan
        basic_features = [
            {"feature_name": "1 student profile", "feature_description": "Access for one student"},
            {"feature_name": "1 subject access", "feature_description": "Choose one subject"},
            {"feature_name": "Basic progress tracking", "feature_description": "Track learning progress"},
            {"feature_name": "Standard assessments", "feature_description": "Regular assessments"},
            {"feature_name": "Email support", "feature_description": "Customer support via email"}
        ]

        for feature in basic_features:
            create_plan_feature(db, PlanFeatureCreate(
                plan_id=basic_plan.id,
                feature_name=feature["feature_name"],
                feature_description=feature["feature_description"],
                is_included=True
            ))

        print(f"Created Basic Plan with ID: {basic_plan.id}")

        # Create Premium Plan
        print("Creating Premium Plan...")
        premium_plan = create_subscription_plan(db, SubscriptionPlanCreate(
            name="Premium",
            description="Best value for families with multiple children",
            base_price=25.00,  # Base price per subject
            discount_percentage=20.00,  # 20% discount from total basic price
            currency="USD",
            trial_days=15,
            yearly_discount=10.00,
            is_active=True,
            sort_order=2,
            plan_type="premium"
        ))

        # Add features to Premium Plan
        premium_features = [
            {"feature_name": "All subjects access", "feature_description": "Access to all available subjects"},
            {"feature_name": "Advanced progress tracking", "feature_description": "Detailed progress analytics"},
            {"feature_name": "Personalized learning paths", "feature_description": "AI-powered learning paths"},
            {"feature_name": "Priority support", "feature_description": "24/7 priority customer support"},
            {"feature_name": "Detailed assessment reports", "feature_description": "Comprehensive assessment analytics"},
            {"feature_name": "Parent coaching sessions", "feature_description": "Regular coaching sessions for parents"}
        ]

        for feature in premium_features:
            create_plan_feature(db, PlanFeatureCreate(
                plan_id=premium_plan.id,
                feature_name=feature["feature_name"],
                feature_description=feature["feature_description"],
                is_included=True
            ))

        print(f"Created Premium Plan with ID: {premium_plan.id}")

        # Add subjects to Basic Plan (optional - users will choose subject during signup)
        # Get all available subjects
        subjects = db.query(Subject).all()
        if subjects:
            # For Basic plan, we don't need to associate subjects since users choose one
            # during subscription. This is just for reference.
            print(f"Found {len(subjects)} subjects in database")

        print("Subscription plan seeding completed successfully!")
        print(f"\nSummary:")
        print(f"- Basic Plan: ${basic_plan.base_price}/month per subject")
        print(f"- Premium Plan: All subjects with {premium_plan.discount_percentage}% discount")
        print(f"- Both plans include {basic_plan.trial_days}-day free trial")
        print(f"- Yearly billing gets additional {basic_plan.yearly_discount}% discount")

if __name__ == "__main__":
    seed_subscription_plans()