from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    role: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class StudentCreate(BaseModel):
    name: str
    age: int
    grade_level: str
    username: str
    password: str

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    grade_level: Optional[str] = None

class Student(BaseModel):
    id: int
    name: str
    age: Optional[int] = None
    grade_level: Optional[str] = None
    parent_id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True
