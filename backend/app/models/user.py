# app/models/user.py
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.core.database import Base
import enum
from app.crud.mixin import SerializerMixin



class UserRole(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"
    TEACHER = "teacher"
    SCHOOL_ADMIN = "school_admin"
    SUPER_ADMIN = "super_admin"

class User(Base, SerializerMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(Enum(UserRole), nullable=False, index=True)

    # Store AI-detected personality traits
    personality = Column(JSONB, nullable=True)  # Make nullable initially

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="StudentProfile.user_id",
        cascade="all, delete-orphan"
    )

    children_profiles = relationship(
        "StudentProfile",
        back_populates="parent",
        foreign_keys="StudentProfile.parent_id"
    )

    user_subscriptions = relationship(
        "Subscription",
        back_populates="user",
        foreign_keys="Subscription.user_id"
    )

class StudentProfile(Base, SerializerMixin):
    __tablename__ = "student_profiles"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)

    age = Column(Integer, nullable=True)
    has_completed_assessment = Column(Boolean, default=False)

    curriculum_id = Column(UUID(as_uuid=True), ForeignKey("curricula.id"), nullable=True)

    # AI-detected learning patterns
    learning_profile = Column(JSONB, nullable=True)
    """
        {
            "instructional_preferences": {
                "scaffolding_level": "high",
                "example_dependency": true,
                "exploration_tolerance": "low"
            },
            "attention_profile": {
                "focus_duration_minutes": 15,
                "preferred_chunk_size_minutes": 5
            },
            "accessibility_flags": {
                "reading_load_sensitive": true,
                "attention_regulation_support": false,
                "auditory_memory_support": true,
                "visual_simplicity_required": false
            },
            "interest_signals": ["technology_ai", "stories_characters"],
            "expression_preferences": ["explain_own_words"],
            "confidence_notes": {
                "is_diagnostic": false,
                "self_reported": true
            }
        }

    """

    registration_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    parent = relationship("User", back_populates="children_profiles", foreign_keys=[parent_id])
    grade = relationship("Grade", back_populates="student_profiles", lazy="joined")
    curriculum = relationship("Curriculum")
    school = relationship("School", back_populates="students")

    assessments = relationship("Assessment", back_populates="student", cascade="all, delete-orphan")
    study_plans = relationship("StudyPlan", back_populates="student", cascade="all, delete-orphan")
    knowledge_profiles = relationship("StudentKnowledgeProfile", back_populates="student", cascade="all, delete-orphan")

    student_badges = relationship("StudentBadge", back_populates="student", cascade="all, delete-orphan")
    course_progress = relationship("StudentCourseProgress", back_populates="student", cascade="all, delete-orphan")
    student_subscriptions = relationship("Subscription", back_populates="student", foreign_keys="Subscription.student_profile_id", cascade="all, delete-orphan")
    school_registrations = relationship("StudentSchoolRegistration", back_populates="student")
