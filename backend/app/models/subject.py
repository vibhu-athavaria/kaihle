from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.crud.mixin import SerializerMixin

class Subject(Base, SerializerMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    micro_courses = relationship("MicroCourse", back_populates="subject")
    subscriptions = relationship("Subscription", back_populates="subject")