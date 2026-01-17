from sqlalchemy import (
    Column, Integer, String, ForeignKey,
    TIMESTAMP, JSON, text
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.crud.mixin import SerializerMixin

class MicroCourse(Base, SerializerMixin):
    __tablename__ = "micro_courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)

    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    # grade_id = Column(Integer, ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    # topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"))
    # subtopic_id = Column(Integer, ForeignKey("subtopics.id", ondelete="SET NULL"))

    learning_objectives = Column(JSON)
    duration_minutes = Column(Integer, server_default="15")

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="micro_courses")
    sections = relationship("MicroCourseSection", back_populates="micro_course", cascade="all, delete")
    questions = relationship("MicroCourseQuestionLink", back_populates="micro_course", cascade="all, delete")


class MicroCourseSection(Base):
    __tablename__ = "micro_course_sections"

    id = Column(Integer, primary_key=True, index=True)
    micro_course_id = Column(Integer, ForeignKey("micro_courses.id", ondelete="CASCADE"), nullable=False)

    section_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=True)

    content = Column(JSON, nullable=False)
    position = Column(Integer, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    micro_course = relationship("MicroCourse", back_populates="sections")


class MicroCourseQuestionLink(Base):
    __tablename__ = "micro_course_question_links"

    id = Column(Integer, primary_key=True, index=True)
    micro_course_id = Column(Integer, ForeignKey("micro_courses.id", ondelete="CASCADE"), nullable=False)
    question_bank_id = Column(Integer, ForeignKey("question_bank.id", ondelete="CASCADE"), nullable=False)

    position = Column(Integer, nullable=False)

    # Relationships
    micro_course = relationship("MicroCourse", back_populates="questions")
