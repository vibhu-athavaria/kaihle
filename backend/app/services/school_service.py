"""School management service layer."""

import uuid
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import Class, ClassEnrollment, School
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole
from app.schemas.school import (
    ClassCreate,
    EnrollResponse,
    SchoolCreate,
    SchoolUpdate,
    StudentSummary,
)
from app.tasks.onboarding_tasks import trigger_onboarding_diagnostics


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

    # ===========================================
    # Class Management Methods
    # ===========================================

    async def create_class(
        self,
        school_id: uuid.UUID,
        data: ClassCreate,
    ) -> Class:
        """Create a new class for a school.

        Args:
            school_id: The school UUID
            data: Class creation data

        Returns:
            The created Class model

        Raises:
            ValueError: If the teacher doesn't belong to this school
        """
        # Verify teacher belongs to this school and is active
        result = await self.db.execute(
            select(User).where(
                User.id == data.teacher_id,
                User.school_id == school_id,
                User.role == UserRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        teacher = result.scalar_one_or_none()
        if not teacher:
            raise ValueError("Teacher not found in this school")

        class_ = Class(
            school_id=school_id,
            grade_id=data.grade_id,
            subject_id=data.subject_id,
            curriculum_id=data.curriculum_id,
            teacher_id=data.teacher_id,
            name=data.name,
            academic_year=data.academic_year,
            is_active=True,
        )
        self.db.add(class_)
        await self.db.flush()
        return class_

    async def list_classes(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
    ) -> list[Class]:
        """List classes for a school.

        Args:
            school_id: The school UUID
            teacher_id: Optional filter - if provided, only return classes for this teacher

        Returns:
            List of Class models
        """
        query = select(Class).where(
            Class.school_id == school_id,
            Class.is_active.is_(True),
        )

        # Filter by teacher if provided (for teacher role)
        if teacher_id:
            query = query.where(Class.teacher_id == teacher_id)

        result = await self.db.execute(query.order_by(Class.name))
        return list(result.scalars().all())

    async def get_class(self, class_id: uuid.UUID) -> Class:
        """Get a class by ID.

        Args:
            class_id: The class UUID

        Returns:
            The Class model

        Raises:
            ValueError: If the class is not found
        """
        class_ = await self.db.get(Class, class_id)
        if not class_:
            raise ValueError("Class not found")
        return class_

    async def verify_class_school(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Class:
        """Verify a class belongs to a school.

        Args:
            class_id: The class UUID
            school_id: The school UUID

        Returns:
            The Class model

        Raises:
            ValueError: If the class is not found or doesn't belong to the school
        """
        class_ = await self.get_class(class_id)
        if class_.school_id != school_id:
            raise ValueError("Class does not belong to this school")
        return class_

    # ===========================================
    # Enrollment Methods
    # ===========================================

    async def enroll_students(
        self,
        class_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> EnrollResponse:
        """Enroll students in a class.

        Args:
            class_id: The class UUID
            student_ids: List of student UUIDs to enroll

        Returns:
            EnrollResponse with enrolled count, skipped count, and any errors
        """
        # Get the class to find the school_id
        class_ = await self.get_class(class_id)
        school_id = class_.school_id

        enrolled = 0
        skipped = 0
        errors: list[str] = []

        for student_id in student_ids:
            try:
                # 1. Validate student belongs to this school
                result = await self.db.execute(
                    select(User).where(
                        User.id == student_id,
                        User.school_id == school_id,
                        User.role == UserRole.STUDENT,
                    )
                )
                student = result.scalar_one_or_none()
                if not student:
                    errors.append(f"Student {student_id} not found in this school")
                    continue

                # 2. Check if already enrolled (skip if already enrolled)
                result = await self.db.execute(
                    select(ClassEnrollment).where(
                        ClassEnrollment.class_id == class_id,
                        ClassEnrollment.student_id == student_id,
                    )
                )
                existing_enrollment = result.scalar_one_or_none()
                if existing_enrollment:
                    skipped += 1
                    continue

                # 4. Insert class_enrollments row
                enrollment = ClassEnrollment(
                    class_id=class_id,
                    student_id=student_id,
                    is_active=True,
                )
                self.db.add(enrollment)
                enrolled += 1

                # 5. Check onboarding status and trigger diagnostics
                # Only trigger if status is PENDING (not IN_PROGRESS or COMPLETED)
                result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
                # Note: scalar_one_or_none() returns Any due to SQLAlchemy type stubs limitations
                # The cast clarifies the expected type for the type checker
                student_profile = cast(StudentProfile | None, result.scalar_one_or_none())
                if student_profile and student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING:
                    # Trigger onboarding diagnostics task
                    trigger_onboarding_diagnostics(str(student_id), str(class_id))

            except Exception as e:
                errors.append(f"Error enrolling student {student_id}: {str(e)}")

        await self.db.flush()
        return EnrollResponse(enrolled=enrolled, skipped=skipped, errors=errors)

    async def get_class_students(
        self,
        class_id: uuid.UUID,
    ) -> list[StudentSummary]:
        """Get list of students enrolled in a class.

        Args:
            class_id: The class UUID

        Returns:
            List of StudentSummary
        """
        # First verify class exists
        await self.get_class(class_id)

        query = (
            select(User)
            .join(ClassEnrollment, ClassEnrollment.student_id == User.id)
            .where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.is_active.is_(True),
            )
            .order_by(User.last_name, User.first_name)
        )
        result = await self.db.execute(query)
        students = result.scalars().all()

        return [
            StudentSummary(
                id=student.id,
                email=student.email,
                first_name=student.first_name,
                last_name=student.last_name,
            )
            for student in students
        ]
