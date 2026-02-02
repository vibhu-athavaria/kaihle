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
    ADMIN = "admin"


class User(Base, SerializerMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
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

    # Community
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class StudentProfile(Base, SerializerMixin):
    __tablename__ = "student_profiles"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True)

    age = Column(Integer, nullable=True)

    has_completed_assessment = Column(Boolean, default=False)

    # Checkpoints removed - use knowledge profiles instead
    interests = Column(JSONB, nullable=True)

    # Learning preferences
    preferred_format = Column(String(50), nullable=True)  # visual, auditory, kinesthetic, reading
    preferred_session_length = Column(Integer, nullable=True)  # in minutes

    # AI-powered persona
    learning_style = Column(JSONB, nullable=True)  # AI-detected learning patterns
    """
    Example:
    {
        "pace": "fast",
        "depth_preference": "conceptual",
        "error_patterns": ["rushes_through", "skips_steps"],
        "strengths": ["problem_solving", "visual_thinking"],
        "challenges": ["attention_to_detail", "showing_work"]
    }
    """

    motivation_profile = Column(JSONB, nullable=True)
    """
    Example:
    {
        "primary_motivators": ["achievement", "curiosity"],
        "engagement_triggers": ["real_world_applications", "competitive_elements"],
        "frustration_points": ["repetitive_practice", "time_pressure"]
    }
    """

    registration_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    parent = relationship("User", back_populates="children_profiles", foreign_keys=[parent_id])
    grade = relationship("Grade", back_populates="student_profiles")

    assessments = relationship("Assessment", back_populates="student", cascade="all, delete-orphan")
    study_plans = relationship("StudyPlan", back_populates="student", cascade="all, delete-orphan")
    knowledge_profiles = relationship("StudentKnowledgeProfile", back_populates="student", cascade="all, delete-orphan")
    progress_records = relationship("Progress", back_populates="student", cascade="all, delete-orphan")
    student_badges = relationship("StudentBadge", back_populates="student", cascade="all, delete-orphan")
    course_progress = relationship("StudentCourseProgress", back_populates="student", cascade="all, delete-orphan")
    tutor_sessions = relationship("TutorSession", back_populates="student", cascade="all, delete-orphan")
    answers = relationship("StudentAnswer", back_populates="student", cascade="all, delete-orphan")