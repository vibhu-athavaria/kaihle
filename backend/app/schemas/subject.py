# app/schemas/subject.py
from pydantic import BaseModel
from uuid import UUID


class SubjectCreate(BaseModel):
    name: str
    code: str | None
    icon: str | None
    color: str | None
    gradient_key: str | None


class SubjectResponse(SubjectCreate):
    id: UUID
    is_active: bool

    class Config:
        orm_mode = True