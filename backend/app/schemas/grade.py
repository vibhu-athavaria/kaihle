from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class GradeBase(BaseModel):
    name: str
    level: int
    description: Optional[str] = None
    is_active: bool = True

class Grade(GradeBase):
    id: UUID

    class Config:
        from_attributes = True

class GradeCreate(GradeBase):
    pass


class GradeUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
