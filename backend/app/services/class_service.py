"""Class management and enrollment service layer."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Grade
from app.models.gap import GapState
from app.models.school import Class, ClassEnrollment, SchoolCurriculum
from app.models.user import StudentProfile, User, UserRole
from app.schemas.class_enrollment import (
    ClassCreate,
    EnrollResponse,
    StudentSummary,
    TeacherStudentItem,
)
from app.tasks.onboarding_tasks import trigger_onboarding_diagnostics

if TYPE_CHECKING:
    from app.schemas.class_enrollment import ClassUpdate


class _StudentClassData(TypedDict):
    class_ids: list[uuid.UUID]
    class_names: list[str]


class ClassService:
    """Service for managing classes and enrollments."""

    def __init__(self, db: AsyncSession):
        self.db = db

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

        # Verify the school is subscribed to the requested curriculum
        sub_result = await self.db.execute(
            select(SchoolCurriculum).where(
                SchoolCurriculum.school_id == school_id,
                SchoolCurriculum.curriculum_id == data.curriculum_id,
            )
        )
        if not sub_result.scalar_one_or_none():
            raise ValueError("School is not subscribed to this curriculum")

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

        if data.student_ids:
            await self._enroll_students_no_diagnostic(class_.id, school_id, data.student_ids)

        return class_

    async def _enroll_students_no_diagnostic(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> None:
        """Enroll students atomically during class creation without triggering diagnostics.

        Diagnostics are now teacher-designed — not auto-generated on enrollment.
        """
        result = await self.db.execute(
            select(User.id).where(
                User.id.in_(student_ids),
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
            )
        )
        valid_ids = set(result.scalars().all())

        existing_result = await self.db.execute(
            select(ClassEnrollment.student_id).where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.student_id.in_(valid_ids),
            )
        )
        existing = set(existing_result.scalars().all())

        new_enrollments = [
            ClassEnrollment(class_id=class_id, student_id=sid, is_active=True)
            for sid in valid_ids
            if sid not in existing
        ]
        if new_enrollments:
            self.db.add_all(new_enrollments)
            await self.db.flush()

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

    async def update_class(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        data: ClassUpdate,
    ) -> Class:
        """Update editable fields on a class.

        Locked fields (grade_id, subject_id, curriculum_id) are never touched.
        Only fields explicitly set in data are applied.

        Raises:
            ValueError: If class not found or belongs to a different school.
        """
        class_ = await self.db.get(Class, class_id)
        if not class_ or class_.school_id != school_id:
            raise ValueError("Class not found")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(class_, field, value)

        await self.db.flush()
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
            raise ValueError("Class not found")
        return class_

    async def enroll_students(
        self,
        class_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> EnrollResponse:
        """Enroll students in a class.

        Optimized to use batch queries instead of N+1 queries.

        Args:
            class_id: The class UUID
            student_ids: List of student UUIDs to enroll

        Returns:
            EnrollResponse with enrolled count, skipped count, and any errors
        """
        class_ = await self.get_class(class_id)
        school_id = class_.school_id

        enrolled = 0
        skipped = 0
        errors: list[str] = []

        # Batch 1: Fetch ALL students in ONE query
        result = await self.db.execute(
            select(User).where(
                User.id.in_(student_ids),
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
            )
        )
        valid_students = {u.id: u for u in result.scalars().all()}

        # Track which students were not found
        for student_id in student_ids:
            if student_id not in valid_students:
                errors.append(f"Student {student_id} not found in this school")

        # Batch 2: Fetch existing enrollments only for valid students
        if valid_students:
            result = await self.db.execute(
                select(ClassEnrollment.student_id).where(
                    ClassEnrollment.class_id == class_id,
                    ClassEnrollment.student_id.in_(valid_students.keys()),
                )
            )
            existing = set(result.scalars().all())
        else:
            existing = set()

        # Batch 3: Create all new enrollments
        new_enrollments = []
        for student_id in valid_students.keys():
            if student_id in existing:
                skipped += 1
                continue
            new_enrollments.append(
                ClassEnrollment(
                    class_id=class_id,
                    student_id=student_id,
                    is_active=True,
                )
            )
            enrolled += 1

        # Batch add all + flush in transaction
        if new_enrollments:
            self.db.add_all(new_enrollments)
            await self.db.flush()

            # Trigger diagnostics for new enrollments
            for enrollment in new_enrollments:
                trigger_onboarding_diagnostics.delay(str(enrollment.student_id), str(class_id))

        return EnrollResponse(enrolled=enrolled, skipped=skipped, errors=errors)

    async def get_class_students(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> list[StudentSummary]:
        """Get list of students enrolled in a class.

        Args:
            class_id: The class UUID
            school_id: The school UUID — enforces tenant isolation at service layer

        Returns:
            List of StudentSummary
        """
        await self.verify_class_school(class_id, school_id)

        # Fetch enrollments joined with StudentProfile→Grade for grade_level
        query = (
            select(
                User,
                ClassEnrollment.onboarding_diagnostic_status,
                Grade.level.label("grade_level"),
            )
            .join(ClassEnrollment, ClassEnrollment.student_id == User.id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .outerjoin(Grade, Grade.id == StudentProfile.grade_id)
            .where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.is_active.is_(True),
            )
            .order_by(User.last_name, User.first_name)
        )
        result = await self.db.execute(query)
        rows = result.all()

        student_ids = [row.User.id for row in rows]

        # Get worst mastery scores from gap states for these students in this class
        worst_mastery_map: dict[uuid.UUID, float | None] = {}
        if student_ids:
            gap_query = select(GapState.student_id, GapState.mastery_score).where(
                GapState.student_id.in_(student_ids),
                GapState.class_id == class_id,
            )
            gap_result = await self.db.execute(gap_query)
            gap_rows = gap_result.all()

            mastery_by_student: dict[uuid.UUID, list[float]] = defaultdict(list)
            for student_id, mastery in gap_rows:
                if mastery is not None:
                    mastery_by_student[student_id].append(mastery)

            for student_id in student_ids:
                scores = mastery_by_student.get(student_id, [])
                worst_mastery_map[student_id] = min(scores) if scores else None

        return [
            StudentSummary(
                id=row.User.id,
                email=row.User.email,
                first_name=row.User.first_name,
                last_name=row.User.last_name,
                worst_mastery=worst_mastery_map.get(row.User.id),
                diagnostic_completed=row.onboarding_diagnostic_status == "COMPLETED",
                grade_level=row.grade_level,
            )
            for row in rows
        ]

    async def get_teacher_students(
        self,
        teacher_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> list[TeacherStudentItem]:
        """Get all students enrolled in a teacher's active classes.

        Aggregates students across all classes, collecting class_ids and class_names
        per student. Returns lightweight summaries (no mastery/learning profile data).

        Args:
            teacher_id: The teacher's UUID
            school_id: The school UUID for scoping

        Returns:
            List of TeacherStudentItem
        """
        # Fetch all active classes for this teacher
        classes_result = await self.db.execute(
            select(Class).where(
                Class.teacher_id == teacher_id,
                Class.school_id == school_id,
                Class.is_active.is_(True),
            )
        )
        classes = classes_result.scalars().all()

        if not classes:
            return []

        class_ids = [c.id for c in classes]
        class_name_map = {c.id: c.name for c in classes}

        # Fetch all enrollments for these classes
        enrollments_result = await self.db.execute(
            select(ClassEnrollment).where(
                ClassEnrollment.class_id.in_(class_ids),
                ClassEnrollment.is_active.is_(True),
            )
        )
        enrollments = enrollments_result.scalars().all()

        if not enrollments:
            return []

        enrollment_student_ids = [e.student_id for e in enrollments]

        # Fetch all students in one query
        students_result = await self.db.execute(
            select(User).where(
                User.id.in_(enrollment_student_ids),
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
            )
        )
        students = {s.id: s for s in students_result.scalars().all()}

        # Aggregate: student_id -> {class_ids, class_names}
        student_classes: dict[uuid.UUID, _StudentClassData] = {}
        for enrollment in enrollments:
            sid = enrollment.student_id
            cid = enrollment.class_id
            if sid not in student_classes:
                student_classes[sid] = {"class_ids": [], "class_names": []}
            student_classes[sid]["class_ids"].append(cid)
            student_classes[sid]["class_names"].append(class_name_map[cid])

        return [
            TeacherStudentItem(
                id=student_id,
                first_name=students[student_id].first_name,
                last_name=students[student_id].last_name,
                email=students[student_id].email,
                class_ids=data["class_ids"],
                class_names=data["class_names"],
            )
            for student_id, data in student_classes.items()
            if student_id in students
        ]

    async def update_teacher(
        self,
        class_id: uuid.UUID,
        teacher_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Class:
        """Update the teacher assigned to a class.

        Args:
            class_id: The class UUID
            teacher_id: The new teacher UUID
            school_id: The school UUID for scoping

        Returns:
            The updated Class model

        Raises:
            ValueError: If the class or teacher is not found in this school
        """
        class_ = await self.verify_class_school(class_id, school_id)

        # Verify teacher belongs to this school and is active
        result = await self.db.execute(
            select(User).where(
                User.id == teacher_id,
                User.school_id == school_id,
                User.role == UserRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        teacher = result.scalar_one_or_none()
        if not teacher:
            raise ValueError("Teacher not found in this school")

        class_.teacher_id = teacher_id
        await self.db.flush()
        return class_

    async def unenroll_students(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> None:
        """Soft-delete enrollments by setting is_active = False.

        Preserves assessment history (gap states, diagnostic results) tied to the enrollment.

        Raises:
            ValueError: If class not found or belongs to a different school.
        """
        from sqlalchemy import select

        from app.models.school import ClassEnrollment

        class_ = await self.db.get(Class, class_id)
        if not class_ or class_.school_id != school_id:
            raise ValueError("Class not found")

        stmt = select(ClassEnrollment).where(
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.student_id.in_(student_ids),
            ClassEnrollment.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        enrollments = result.scalars().all()

        for enrollment in enrollments:
            enrollment.is_active = False

        await self.db.flush()
