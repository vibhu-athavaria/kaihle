from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# -------------------
# SCHOOL SCHEMAS
# -------------------
class SchoolBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    admin_id: UUID
    is_active: Optional[bool] = True


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    admin_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class School(SchoolBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    # teachers: Optional[List["Teacher"]] = None
    # students: Optional[List["StudentProfileResponse"]] = None