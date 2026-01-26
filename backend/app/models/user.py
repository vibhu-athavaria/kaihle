from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum
from app.crud.mixin import SerializerMixin

class UserRole(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"
    ADMIN = "admin"


class User(Base, SerializerMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)   # required for parents/admins, optional for students
    username = Column(String, unique=True, index=True, nullable=True) # required for students, optional for others
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    has_completed_assessment = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # --- Relationships ---
    # 1-to-1: A student has exactly one StudentProfile
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="StudentProfile.user_id"
    )

    # 1-to-many: A parent has many students (via StudentProfile)
    children_profiles = relationship(
        "StudentProfile",
        back_populates="parent",
        foreign_keys="StudentProfile.parent_id"
    )

    # Posts
    # posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")

    # Comments
    # comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")

    # Notifications
    # notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class StudentProfile(Base, SerializerMixin):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # <-- one parent per student
    age = Column(Integer, nullable=True)
    grade_level = Column(String, nullable=True)
    math_checkpoint = Column(String, nullable=True)
    science_checkpoint = Column(String, nullable=True)
    english_checkpoint = Column(String, nullable=True)
    interests = Column(JSON, nullable=True)
    preferred_format = Column(String, nullable=True)
    preferred_session_length = Column(Integer, nullable=True)
    registration_completed_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    user = relationship(
        "User",
        back_populates="student_profile",
        foreign_keys=[user_id]
    )
    parent = relationship(
        "User",
        back_populates="children_profiles",
        foreign_keys=[parent_id]
    )
    # Assessments
    assessments = relationship("Assessment", back_populates="student", lazy="selectin",cascade="all, delete-orphan")

     # Progress tracking
    # progress_records = relationship("Progress", back_populates="student")

    # Study Plans
    # study_plans = relationship("StudyPlan", back_populates="student", cascade="all, delete-orphan")

    # tutor_sessions = relationship("TutorSession", back_populates="student", cascade="all, delete-orphan")
    # answers = relationship("StudentAnswer", back_populates="student", cascade="all, delete-orphan")