from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    role: str

class UserLogin(BaseModel):
    identifier: str
    password: str
    role: str  # 'parent' or 'student'

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True
