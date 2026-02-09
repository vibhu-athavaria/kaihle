from typing import Optional
from pydantic import BaseModel
from uuid import UUID

class DashboardSubject(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None
    icon: Optional[str] = None
    gradient_key: Optional[str] = None


class StudentSubjectDashboardItem(BaseModel):
    subject: DashboardSubject
    status: str  # "not_started" | "in_progress" | "completed"
    description: str
    assessment_id: Optional[UUID] = None
    progress: Optional[float] = None

    class Config:
        from_attributes = True
