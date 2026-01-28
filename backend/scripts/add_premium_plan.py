#!/usr/bin/env python3
"""
Add Premium subscription plan to database
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import engine
from app.schemas.billing import SubscriptionPlanCreate, PlanFeatureCreate
from app.crud.billing import create_subscription_plan, create_plan_feature, get_subscription_plan_by_name

def add_premium_plan():
    """Add Premium subscription plan"""
    with Session(engine) as db:
        print("Checking for Premium plan...")

        # Check if Premium plan already exists
        premium_plan = get_subscription_plan_by_name(db, "Premium")

        if premium_plan:
            print("Premium plan already exists. Skipping.")
            return

        print("Creating Premium Plan...")

        # Create Premium Plan
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
        print("Premium plan seeding completed successfully!")

if __name__ == "__main__":
    add_premium_plan()