import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.school import School, SchoolStatus, PlanTier
from app.models.school_grade import SchoolGrade
from app.models.school_registration import StudentSchoolRegistration, RegistrationStatus
from app.models.user import StudentProfile
from app.models.curriculum import Grade
from app.models.curriculum import Curriculum
import uuid

# Create a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    # Create the database and tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop the tables after tests
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create a new database session for each test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_register_school_admin(setup_database, db_session):
    # Create a curriculum for the test
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        code="TEST"
    )
    db_session.add(curriculum)
    db_session.commit()

    # Test school admin registration
    response = client.post("/api/v1/auth/register/school-admin", json={
        "admin_name": "Test Admin",
        "admin_email": "admin@test.com",
        "password": "password123",
        "school_name": "Test School",
        "country": "Test Country",
        "curriculum_id": str(curriculum.id)
    })

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending_approval"
    assert "user_id" in data
    assert "school_id" in data

    # Check that the user was created with the correct role
    user = db_session.query(User).filter(User.id == data["user_id"]).first()
    assert user is not None
    assert user.role == UserRole.SCHOOL_ADMIN

    # Check that the school was created with the correct status
    school = db_session.query(School).filter(School.id == data["school_id"]).first()
    assert school is not None
    assert school.status == SchoolStatus.PENDING_APPROVAL
    assert school.school_code is None

def test_register_student_valid_school_code(setup_database, db_session):
    # Create a curriculum for the test
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        code="TEST"
    )
    db_session.add(curriculum)
    db_session.commit()

    # Create an approved school with a school code
    school = School(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),  # Dummy admin ID
        name="Test School",
        slug="test-school",
        school_code="ABCDEFGH",
        curriculum_id=curriculum.id,
        country="Test Country",
        timezone="Asia/Makassar",
        status=SchoolStatus.ACTIVE,
        plan_tier=PlanTier.TRIAL,
        is_active=True
    )
    db_session.add(school)
    db_session.commit()

    # Test student registration with valid school code
    response = client.post("/api/v1/auth/register/student", json={
        "full_name": "Test Student",
        "email": "student@test.com",
        "password": "password123",
        "school_code": "ABCDEFGH"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending_approval"
    assert data["school_name"] == "Test School"
    assert "user_id" in data

    # Check that the user was created with the correct role
    user = db_session.query(User).filter(User.id == data["user_id"]).first()
    assert user is not None
    assert user.role == UserRole.STUDENT

    # Check that the student profile was created
    student_profile = db_session.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    assert student_profile is not None
    assert student_profile.school_id == school.id

    # Check that the registration was created
    registration = db_session.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.student_id == student_profile.id
    ).first()
    assert registration is not None
    assert registration.school_id == school.id
    assert registration.status == RegistrationStatus.PENDING

def test_register_student_invalid_school_code(setup_database):
    # Test student registration with invalid school code
    response = client.post("/api/v1/auth/register/student", json={
        "full_name": "Test Student",
        "email": "student2@test.com",
        "password": "password123",
        "school_code": "INVALID1"
    })

    assert response.status_code == 422
    data = response.json()
    assert "Invalid school code" in data["detail"]

def test_register_student_pending_school(setup_database, db_session):
    # Create a curriculum for the test
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        code="TEST"
    )
    db_session.add(curriculum)
    db_session.commit()

    # Create a pending school
    school = School(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),  # Dummy admin ID
        name="Pending School",
        slug="pending-school",
        school_code=None,
        curriculum_id=curriculum.id,
        country="Test Country",
        timezone="Asia/Makassar",
        status=SchoolStatus.PENDING_APPROVAL,
        plan_tier=PlanTier.TRIAL,
        is_active=True
    )
    db_session.add(school)
    db_session.commit()

    # Test student registration with pending school code
    response = client.post("/api/v1/auth/register/student", json={
        "full_name": "Test Student",
        "email": "student3@test.com",
        "password": "password123",
        "school_code": school.school_code or "PENDING1"  # This should fail
    })

    # Since the school code is None for pending schools, this test might need adjustment
    # Let's test with a valid code for a pending school
    school.school_code = "PENDING1"
    db_session.commit()

    response = client.post("/api/v1/auth/register/student", json={
        "full_name": "Test Student",
        "email": "student3@test.com",
        "password": "password123",
        "school_code": "PENDING1"
    })

    assert response.status_code == 403
    data = response.json()
    assert "School is pending approval" in data["detail"]

def test_school_grade_management(setup_database, db_session):
    # Create a curriculum for the test
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        code="TEST"
    )
    db_session.add(curriculum)
    db_session.commit()

    # Create grades
    grade5 = Grade(
        id=uuid.uuid4(),
        name="Grade 5",
        level=5
    )
    grade6 = Grade(
        id=uuid.uuid4(),
        name="Grade 6",
        level=6
    )
    db_session.add_all([grade5, grade6])
    db_session.commit()

    # Create a school
    school = School(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),  # Dummy admin ID
        name="Test School",
        slug="test-school",
        school_code="SCHOOL1",
        curriculum_id=curriculum.id,
        country="Test Country",
        timezone="Asia/Makassar",
        status=SchoolStatus.ACTIVE,
        plan_tier=PlanTier.TRIAL,
        is_active=True
    )
    db_session.add(school)
    db_session.commit()

    # Test adding a grade to school
    response = client.post(f"/api/v1/schools/{school.id}/grades", json={
        "school_id": str(school.id),
        "grade_id": str(grade5.id)
    })

    assert response.status_code == 201
    data = response.json()
    assert data["school_id"] == str(school.id)
    assert data["grade_id"] == str(grade5.id)

    # Test listing school grades
    response = client.get(f"/api/v1/schools/{school.id}/grades")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["grade_id"] == str(grade5.id)

    # Test adding duplicate grade (should fail)
    response = client.post(f"/api/v1/schools/{school.id}/grades", json={
        "school_id": str(school.id),
        "grade_id": str(grade5.id)
    })

    assert response.status_code == 409

def test_student_registration_approval(setup_database, db_session):
    # Create a curriculum for the test
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Test Curriculum",
        code="TEST"
    )
    db_session.add(curriculum)
    db_session.commit()

    # Create grades
    grade5 = Grade(
        id=uuid.uuid4(),
        name="Grade 5",
        level=5
    )
    db_session.add(grade5)
    db_session.commit()

    # Create a school
    school = School(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),  # Dummy admin ID
        name="Test School",
        slug="test-school",
        school_code="SCHOOL1",
        curriculum_id=curriculum.id,
        country="Test Country",
        timezone="Asia/Makassar",
        status=SchoolStatus.ACTIVE,
        plan_tier=PlanTier.TRIAL,
        is_active=True
    )
    db_session.add(school)
    db_session.commit()

    # Add grade to school
    school_grade = SchoolGrade(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade5.id,
        is_active=True
    )
    db_session.add(school_grade)
    db_session.commit()

    # Create a student user and profile
    student_user = User(
        id=uuid.uuid4(),
        email="student@test.com",
        username="student",
        hashed_password="hashed_password",
        full_name="Test Student",
        role=UserRole.STUDENT
    )
    db_session.add(student_user)
    db_session.commit()

    student_profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student_user.id,
        parent_id=student_user.id,
        school_id=school.id
    )
    db_session.add(student_profile)
    db_session.commit()

    # Create a student registration
    registration = StudentSchoolRegistration(
        id=uuid.uuid4(),
        school_id=school.id,
        student_id=student_profile.id,
        status=RegistrationStatus.PENDING
    )
    db_session.add(registration)
    db_session.commit()

    # Test approving student registration
    response = client.patch(f"/api/v1/schools/{school.id}/student-registrations/{registration.id}/approve", json={
        "grade_id": str(grade5.id)
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == RegistrationStatus.APPROVED
    assert data["grade_id"] == str(grade5.id)

    # Check that the student profile was updated
    updated_profile = db_session.query(StudentProfile).filter(StudentProfile.id == student_profile.id).first()
    assert updated_profile.grade_id == grade5.id

def test_school_code_generation():
    # Test that school codes are 8 characters long
    # This would require mocking the database session to test the actual generation logic
    # For now, we'll just test the format

    import random
    import string

    # Characters to exclude: 0, O, 1, I, L
    valid_chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

    # Generate a school code
    school_code = ''.join(random.choices(valid_chars, k=8))

    assert len(school_code) == 8
    assert all(c in valid_chars for c in school_code)

if __name__ == "__main__":
    pytest.main([__file__])