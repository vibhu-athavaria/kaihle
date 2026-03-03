# M0-4-T1 — School Management API (KaihleAdmin)
**Milestone:** M0 — Foundations
**Epic:** M0-4 — School & User Management
**Task ID:** M0-4-T1
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

Kaihle Admin creates and manages schools. This is the first point of entry for any new school — a school record must exist before users, classes, or assessments can be created for it.

**Depends on:** M0-2-T2 (School ORM model), M0-3-T3 (auth middleware)

---

## User Story

As a Kaihle Admin, I want to create and manage schools so that new schools can be onboarded onto the platform.

---

## What To Build

### `/backend/app/services/school_service.py`

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolUpdate


class SchoolService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(self, data: SchoolCreate) -> School:
        existing = await self.db.scalar(
            select(School).where(School.slug == data.slug)
        )
        if existing:
            raise ValueError(f"School slug '{data.slug}' already exists")

        school = School(
            name=data.name,
            slug=data.slug,
            country=data.country,
            timezone=data.timezone or "UTC",
            is_active=True,
        )
        self.db.add(school)
        await self.db.flush()
        return school

    async def list_schools(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[School], int]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(School).order_by(School.created_at.desc())
            .offset(offset).limit(page_size)
        )
        schools = result.scalars().all()
        total = await self.db.scalar(
            select(func.count()).select_from(School)
        )
        return list(schools), total or 0

    async def get_school(self, school_id: uuid.UUID) -> School:
        school = await self.db.get(School, school_id)
        if not school:
            raise ValueError("School not found")
        return school

    async def update_school(
        self, school_id: uuid.UUID, data: SchoolUpdate
    ) -> School:
        school = await self.get_school(school_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(school, field, value)
        await self.db.flush()
        return school
```

---

### `/backend/app/schemas/school.py`

```python
import uuid
from typing import Optional
from pydantic import BaseModel


class SchoolCreate(BaseModel):
    name: str
    slug: str          # URL-safe identifier e.g. "bali-green-school"
    country: Optional[str] = None
    timezone: Optional[str] = "UTC"


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class SchoolResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    country: Optional[str]
    timezone: str
    is_active: bool

    model_config = {"from_attributes": True}


class SchoolListResponse(BaseModel):
    schools: list[SchoolResponse]
    total: int
    page: int
    page_size: int
```

---

### `/backend/app/api/v1/routes/schools.py`

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role, get_current_user
from app.schemas.school import SchoolCreate, SchoolListResponse, SchoolResponse, SchoolUpdate
from app.services.school_service import SchoolService

router = APIRouter(prefix="/admin/schools", tags=["schools"])


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreate,
    _=Depends(require_role("KAIHLE_ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    service = SchoolService(db)
    try:
        return await service.create_school(body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=SchoolListResponse)
async def list_schools(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(require_role("KAIHLE_ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    service = SchoolService(db)
    schools, total = await service.list_schools(page, page_size)
    return SchoolListResponse(schools=schools, total=total, page=page, page_size=page_size)


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # KaihleAdmin can see any school. SchoolAdmin can see own school only.
    if current_user.role not in ("KAIHLE_ADMIN", "SCHOOL_ADMIN"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if current_user.role == "SCHOOL_ADMIN" and current_user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    service = SchoolService(db)
    try:
        return await service.get_school(school_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: uuid.UUID,
    body: SchoolUpdate,
    _=Depends(require_role("KAIHLE_ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    service = SchoolService(db)
    try:
        return await service.update_school(school_id, body)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
```

---

## Files To Create

```
/backend/app/services/school_service.py
/backend/app/schemas/school.py
/backend/app/api/v1/routes/schools.py
```

Also register the router in `main.py`:
```python
from app.api.v1.routes import schools
app.include_router(schools.router, prefix="/api/v1")
```

---

## Acceptance Criteria

- [ ] Integration test: KaihleAdmin creates school → returns 201 with `id`, `name`, `slug`
- [ ] Integration test: duplicate slug returns 409
- [ ] Integration test: KaihleAdmin lists schools with pagination — `total` and `schools` correct
- [ ] Integration test: Teacher calling `POST /api/v1/admin/schools` returns 403
- [ ] Integration test: SchoolAdmin can `GET /api/v1/admin/schools/{own_school_id}` — returns 200
- [ ] Integration test: SchoolAdmin cannot `GET /api/v1/admin/schools/{other_school_id}` — returns 403

---

## Dependencies

- M0-2-T2 — `School` ORM model
- M0-3-T3 — `require_role` dependency

## Output (What Next Tasks Can Use)

- Schools can be created in the system — required before M0-4-T2 (user management) and M0-4-T3 (classes)
- `SchoolService.get_school()` reused by other services for school validation
