"""School management service layer."""

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.school import SchoolCreate, SchoolUpdate

logger = structlog.get_logger()


class SchoolService:
    """Service for managing schools."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(self, data: SchoolCreate) -> School:
        """Create a new school.

        Args:
            data: School creation data

        Returns:
            The created School model

        Raises:
            ValueError: If the slug already exists
        """
        # Check for duplicate slug
        existing = await self.db.scalar(select(School).where(School.slug == data.slug))
        if existing:
            raise ValueError(f"School slug '{data.slug}' already exists")

        # Map timezone - default to Asia/Singapore if not provided
        timezone = data.timezone or "Asia/Singapore"

        school = School(
            name=data.name,
            slug=data.slug,
            country=data.country,
            timezone=timezone,
            status="active",  # Schools created via API are active by default
        )
        self.db.add(school)
        await self.db.flush()

        # Check for duplicate admin email
        existing_user = await self.db.scalar(select(User).where(User.email == data.admin_email))
        if existing_user:
            raise ValueError(f"A user with email '{data.admin_email}' already exists")

        # Create the school admin user
        admin_user = User(
            school_id=school.id,
            email=data.admin_email,
            first_name=data.admin_first_name,
            last_name=data.admin_last_name,
            role=UserRole.SCHOOL_ADMIN,
            is_active=True,
            hashed_password=hash_password(data.admin_password) if data.admin_password else None,
        )
        self.db.add(admin_user)
        await self.db.flush()

        logger.info(
            "create_school",
            school_id=str(school.id),
            admin_email=data.admin_email,
            password_set=data.admin_password is not None,
        )

        return school

    async def list_schools(self, page: int = 1, page_size: int = 20) -> tuple[list[School], int]:
        """List schools with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of schools, total count)
        """
        offset = (page - 1) * page_size

        # Get paginated results
        result = await self.db.execute(
            select(School).order_by(School.created_at.desc()).offset(offset).limit(page_size)
        )
        schools = result.scalars().all()

        # Get total count
        total = await self.db.scalar(select(func.count()).select_from(School))

        return list(schools), total or 0

    async def get_school(self, school_id: uuid.UUID) -> School:
        """Get a school by ID.

        Args:
            school_id: The school UUID

        Returns:
            The School model

        Raises:
            ValueError: If the school is not found
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise ValueError("School not found")
        return school

    async def get_school_with_admin(self, school_id: uuid.UUID) -> tuple[School, User | None]:
        """Get a school and its first School Admin user by ID.

        Args:
            school_id: The school UUID

        Returns:
            Tuple of (School, User | None) where User is the SCHOOL_ADMIN or None

        Raises:
            ValueError: If the school is not found
        """
        school = await self.get_school(school_id)
        admin_user = await self.db.scalar(
            select(User)
            .where(User.school_id == school_id, User.role == UserRole.SCHOOL_ADMIN)
            .order_by(User.created_at.asc())
            .limit(1)
        )
        return school, admin_user

    async def update_school(self, school_id: uuid.UUID, data: SchoolUpdate) -> School:
        """Update a school.

        Args:
            school_id: The school UUID
            data: School update data

        Returns:
            The updated School model

        Raises:
            ValueError: If the school is not found
        """
        school = await self.get_school(school_id)

        update_data = data.model_dump(exclude_unset=True)

        # Handle is_active mapping to status
        if "is_active" in update_data:
            is_active = update_data.pop("is_active")
            school.status = "active" if is_active else "suspended"

        # Update other fields
        for field, value in update_data.items():
            if hasattr(school, field) and value is not None:
                setattr(school, field, value)

        await self.db.flush()
        return school
