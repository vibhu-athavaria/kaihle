from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class UserRole(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)   # required for parents/admins, optional for students
    username = Column(String, unique=True, index=True, nullable=True) # required for students, optional for others
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student_profile = relationship("StudentProfile", uselist=False, back_populates="user")
    children = relationship("User", back_populates="parent", foreign_keys="User.parent_id")
    parent = relationship("User", back_populates="children", remote_side=[id])

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    age = Column(Integer, nullable=True)
    grade_level = Column(String, nullable=True)

    # Example: storing checkpoints per subject later
    math_checkpoint = Column(Integer, nullable=True)
    science_checkpoint = Column(Integer, nullable=True)
    english_checkpoint = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="student_profile")
    progress_records = relationship("Progress", back_populates="student")
    study_plans = relationship("StudyPlan", back_populates="student")
