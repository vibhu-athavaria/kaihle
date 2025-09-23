from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LessonBase(BaseModel):
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    difficulty_level: Optional[str] = None
    subject: Optional[str] = None
    points_value: int = 10

class LessonCreate(LessonBase):
    pass

class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    difficulty_level: Optional[str] = None
    subject: Optional[str] = None
    points_value: Optional[int] = None
    is_active: Optional[bool] = None

class Lesson(LessonBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class StudyPlanBase(BaseModel):
    name: str
    description: Optional[str] = None

class StudyPlanCreate(StudyPlanBase):
    student_id: int
    lesson_ids: List[int] = []

class StudyPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class StudyPlanLessonBase(BaseModel):
    lesson_id: int
    order_index: int

class StudyPlanLessonCreate(StudyPlanLessonBase):
    pass

class StudyPlanLessonUpdate(BaseModel):
    is_completed: Optional[bool] = None

class StudyPlanLesson(StudyPlanLessonBase):
    id: int
    study_plan_id: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    lesson: Lesson
    
    class Config:
        from_attributes = True

class StudyPlan(StudyPlanBase):
    id: int
    student_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    lessons: List[StudyPlanLesson] = []
    
    class Config:
        from_attributes = True
