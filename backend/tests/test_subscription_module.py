import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, StudentProfile
from app.models.billing import Subscription, SubscriptionPlan, TrialExtension
from app.services.billing_service import billing_service
from app.services.access_control_service import access_control_service
from app.services.validation_service import validation_service

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test database
Base.metadata.create_all(bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Test fixtures
def create_test_parent(db):
    """Create a test parent user"""
    parent = User(
        email="parent@example.com",
        username="testparent",
        hashed_password="hashed_password",
        full_name="Test Parent",
        role="parent",
        is_active=True
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return parent

def create_test_student(db, parent_id):
    """Create a test student user"""
    student = User(
        username="teststudent",
        hashed_password="hashed_password",
        full_name="Test Student",
        role="student",
        parent_id=parent_id,
        is_active=True
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # Create student profile
    student_profile = StudentProfile(
        user_id=student.id,
        parent_id=parent_id,
        age=12,
        grade_level="7",
        registration_completed_at=datetime.now()
    )
    db.add(student_profile)
    db.commit()
    db.refresh(student_profile)

    return student

def create_test_subject(db, name="Math"):
    """Create a test subject"""
    from app.models.subject import Subject
    subject = Subject(
        name=name,
        description=f"{name} subject"
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject

def create_basic_plan(db):
    """Create a basic subscription plan"""
    plan = SubscriptionPlan(
        name="Basic Plan",
        description="Basic subscription plan",
        base_price=25.00,
        discount_percentage=0.00,
        currency="USD",
        trial_days=15,
        yearly_discount=20.00,
        is_active=True,
        sort_order=1,
        plan_type="basic"
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

def create_premium_plan(db):
    """Create a premium subscription plan"""
    plan = SubscriptionPlan(
        name="Premium Plan",
        description="Premium subscription plan",
        base_price=80.00,
        discount_percentage=0.00,
        currency="USD",
        trial_days=15,
        yearly_discount=20.00,
        is_active=True,
        sort_order=2,
        plan_type="premium"
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

# Test cases
class TestTrialManagement:
    """Test trial management functionality"""

    def test_trial_start_on_registration(self, db):
        """Test that trial starts automatically on registration completion"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Check that trial was created
        subscriptions = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).all()

        assert len(subscriptions) == 1
        trial = subscriptions[0]
        assert trial.parent_id == parent.id
        assert trial.student_id == student.id
        assert trial.status == "trial"
        assert trial.trial_end_date > datetime.now()

    def test_trial_extension(self, db):
        """Test that admin can extend trial"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Get the trial subscription
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        original_end = trial.trial_end_date

        # Create admin user
        admin = User(
            email="admin@example.com",
            hashed_password="hashed_password",
            full_name="Test Admin",
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Extend trial
        extension_result = billing_service.extend_trial(
            db, trial.id, admin.id, 7, "Testing extension"
        )

        assert extension_result["success"] is True
        assert extension_result["new_trial_end"] == original_end + timedelta(days=7)

        # Check extension record
        extensions = db.query(TrialExtension).filter(
            TrialExtension.subscription_id == trial.id
        ).all()

        assert len(extensions) == 1
        extension = extensions[0]
        assert extension.extension_days == 7
        assert extension.extended_by_admin_id == admin.id
        assert extension.reason == "Testing extension"

class TestAccessControl:
    """Test access control functionality"""

    def test_access_during_trial(self, db):
        """Test that student has full access during trial"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Check access
        can_access = access_control_service.can_access_courses(db, student.id)
        assert can_access is True

        notification = access_control_service.get_access_restriction_notification(db, student.id)
        assert notification is None

    def test_access_after_trial_expiry(self, db):
        """Test that student has restricted access after trial expiry"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Expire the trial
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        trial.trial_end_date = datetime.now() - timedelta(days=1)
        db.commit()

        # Check access
        can_access = access_control_service.can_access_courses(db, student.id)
        assert can_access is False

        notification = access_control_service.get_access_restriction_notification(db, student.id)
        assert notification is not None
        assert "paused" in notification.lower()

class TestSubscriptionPlans:
    """Test subscription plan functionality"""

    def test_basic_plan_pricing(self, db):
        """Test Basic plan pricing calculation"""
        basic_plan = create_basic_plan(db)

        # Test monthly pricing
        monthly_price = billing_service.calculate_subscription_cost(
            db, basic_plan.id, billing_cycle="monthly"
        )
        assert monthly_price == 25.00

        # Test yearly pricing (20% discount)
        yearly_price = billing_service.calculate_subscription_cost(
            db, basic_plan.id, billing_cycle="yearly"
        )
        expected_yearly = 25.00 * 12 * 0.8  # $240
        assert yearly_price == expected_yearly

    def test_premium_plan_pricing(self, db):
        """Test Premium plan pricing calculation"""
        premium_plan = create_premium_plan(db)

        # Test monthly pricing
        monthly_price = billing_service.calculate_subscription_cost(
            db, premium_plan.id, billing_cycle="monthly"
        )
        assert monthly_price == 80.00

        # Test yearly pricing (20% discount)
        yearly_price = billing_service.calculate_subscription_cost(
            db, premium_plan.id, billing_cycle="yearly"
        )
        expected_yearly = 80.00 * 12 * 0.8  # $768
        assert yearly_price == expected_yearly

class TestValidation:
    """Test validation functionality"""

    def test_validate_subscription_creation(self, db):
        """Test subscription creation validation"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)
        basic_plan = create_basic_plan(db)
        math_subject = create_test_subject(db, "Math")

        # Valid Basic plan subscription
        validation = validation_service.validate_subscription_creation(
            db, parent.id, student.id, basic_plan.id, math_subject.id
        )
        assert validation["valid"] is True

        # Invalid: Basic plan without subject
        validation = validation_service.validate_subscription_creation(
            db, parent.id, student.id, basic_plan.id, None
        )
        assert validation["valid"] is False
        assert "Subject is required for Basic plan" in validation["errors"]

    def test_validate_trial_extension(self, db):
        """Test trial extension validation"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        # Create admin
        admin = User(
            email="admin@example.com",
            hashed_password="hashed_password",
            full_name="Test Admin",
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Valid extension
        validation = validation_service.validate_trial_extension(
            db, trial.id, admin.id
        )
        assert validation["valid"] is True

        # Invalid: non-admin user
        validation = validation_service.validate_trial_extension(
            db, trial.id, parent.id
        )
        assert validation["valid"] is False
        assert "Invalid admin" in validation["errors"]

class TestAPIEndpoints:
    """Test API endpoints"""

    def test_create_trial_extension_endpoint(self, db):
        """Test trial extension API endpoint"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        # Create admin user for authentication
        admin = User(
            email="admin@example.com",
            hashed_password="hashed_password",
            full_name="Test Admin",
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Test as admin
        response = client.post(
            "/api/v1/trial-extensions",
            json={
                "subscription_id": trial.id,
                "extended_by_admin_id": admin.id,
                "extension_days": 5,
                "reason": "Testing"
            },
            headers={"X-User-ID": str(admin.id), "X-User-Role": "admin"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["subscription_id"] == trial.id
        assert data["extension_days"] == 5

    def test_access_check_endpoint(self, db):
        """Test access check API endpoint"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Test access during trial
        response = client.get(
            f"/api/v1/access-check/{student.id}",
            headers={"X-User-ID": str(parent.id), "X-User-Role": "parent"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_access_courses"] is True
        assert data["restriction_notification"] is None

class TestIntegration:
    """Test integration scenarios"""

    def test_student_registration_to_trial_start(self, db):
        """Test the complete workflow from student registration to trial start"""
        parent = create_test_parent(db)

        # Create student (this should automatically start trial)
        student = create_test_student(db, parent.id)

        # Verify trial was created
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        assert trial is not None
        assert trial.status == "trial"
        assert trial.student_id == student.id
        assert trial.parent_id == parent.id

        # Verify access is granted
        can_access = access_control_service.can_access_courses(db, student.id)
        assert can_access is True

    def test_trial_expiry_to_access_restriction(self, db):
        """Test the workflow from trial expiry to access restriction"""
        parent = create_test_parent(db)
        student = create_test_student(db, parent.id)

        # Verify initial access
        can_access = access_control_service.can_access_courses(db, student.id)
        assert can_access is True

        # Expire trial
        trial = db.query(Subscription).filter(
            Subscription.student_id == student.id,
            Subscription.status == "trial"
        ).first()

        trial.trial_end_date = datetime.now() - timedelta(days=1)
        db.commit()

        # Verify access is restricted
        can_access = access_control_service.can_access_courses(db, student.id)
        assert can_access is False

        notification = access_control_service.get_access_restriction_notification(db, student.id)
        assert notification is not None
        assert "paused" in notification.lower()

# Cleanup
def cleanup_test_data(db):
    """Clean up test data"""
    db.query(TrialExtension).delete()
    db.query(Subscription).delete()
    db.query(SubscriptionPlan).delete()
    db.query(StudentProfile).delete()
    db.query(User).delete()
    db.commit()

# Run cleanup after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup():
    db = next(override_get_db())
    try:
        yield
    finally:
        cleanup_test_data(db)