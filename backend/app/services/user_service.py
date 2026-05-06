"""User management service layer."""

import secrets
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_magic_link_token,
    hash_password,
    hash_token,
    store_magic_link_token,
)
from app.models.curriculum import Curriculum, Grade, Subject, Subtopic
from app.models.gap import GapState
from app.models.school import Class, ClassEnrollment, School
from app.models.user import ParentStudent, StudentProfile, TeacherProfile, User, UserRole
from app.schemas.students import EnrolledClassInfo, StudentClassResponse, StudentInfoResponse
from app.schemas.user import UserDirectCreate, UserInvite, UserSelfUpdate, UserUpdate
from app.schemas.user_detail import (
    AssignedClassSummary,
    ClassEnrollmentDetail,
    GapStateDetail,
    LinkedStudentSummary,
    ParentDetailResponse,
    StudentDetailResponse,
    TeacherDetailResponse,
)
from app.services.class_service import ClassService
from app.services.email_service import EmailService

logger = structlog.get_logger()


class UserNotFoundError(ValueError):
    """Raised when a user cannot be found."""


class CrossSchoolAccessError(PermissionError):
    """Raised when a school-scoped caller accesses a user from another school."""


class UserService:
    """Service for managing users within a school."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_user(
        self,
        school_id: uuid.UUID,
        data: UserInvite,
        base_url: str,
    ) -> User:
        """
        Create a user record and send a magic link to activate their account.
        User is created with is_active=True and a random unusable password.
        They activate via the magic link.
        """
        # Validate role is allowed for invitation
        allowed_roles = {UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PARENT}
        if data.role not in allowed_roles:
            raise ValueError(f"Cannot invite user with role '{data.role}'")

        # Check email uniqueness within school
        existing = await self.db.scalar(
            select(User).where(
                User.email == data.email,
                User.school_id == school_id,
            )
        )
        if existing:
            raise ValueError(f"Email '{data.email}' is already registered at this school")

        # Create user with a random unusable password (they log in via magic link)
        user = User(
            email=data.email,
            hashed_password=hash_password(secrets.token_hex(32)),
            role=data.role,
            school_id=school_id,
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()

        # Create role-specific profile
        if data.role == UserRole.TEACHER:
            profile = TeacherProfile(
                user_id=user.id,
                qualifications={"subjects": data.subjects or []},
            )
            self.db.add(profile)
            await self.db.flush()

        # Create parent-student links if role is PARENT and student_ids provided
        if data.role == UserRole.PARENT and data.student_ids:
            valid_result = await self.db.scalars(
                select(User.id).where(
                    User.id.in_(data.student_ids),
                    User.school_id == school_id,
                    User.role == UserRole.STUDENT,
                )
            )
            valid_ids = set(valid_result.all())
            invalid = [str(sid) for sid in data.student_ids if sid not in valid_ids]
            if invalid:
                raise ValueError(f"Student IDs not found in this school: {invalid}")
            for sid in data.student_ids:
                self.db.add(ParentStudent(parent_id=user.id, student_id=sid))
            await self.db.flush()

        # Send magic link welcome email
        token = create_magic_link_token(user.id, expires_in_minutes=72 * 60)  # 72-hour welcome link
        token_hash = hash_token(token)
        await store_magic_link_token(self.db, user.id, token_hash, expires_minutes=72 * 60)

        logger.info(
            "user_invited",
            user_id=str(user.id),
            school_id=str(school_id),
            role=user.role,
            email=user.email,
        )

        await self._send_welcome_email(user, token, base_url)

        return user

    async def create_user_direct(
        self,
        school_id: uuid.UUID,
        data: UserDirectCreate,
    ) -> User:
        """Create a user with an admin-set password. No magic link is sent.
        User will be required to change password on first login (must_change_password=True).
        """

        # Check email uniqueness within school
        result = await self.db.execute(
            select(User).where(
                User.email == data.email,
                User.school_id == school_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"A user with email '{data.email}' already exists in this school")

        raw_password = data.password  # captured before hashing for welcome email

        user = User(
            school_id=school_id,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            role=data.role,
            hashed_password=hash_password(raw_password),
            is_active=True,
            must_change_password=True,
        )
        self.db.add(user)
        await self.db.flush()  # get user.id before creating related rows

        if data.role == UserRole.STUDENT:
            profile = StudentProfile(
                user_id=user.id,
                grade_id=data.grade_id,
                age=data.age,
                is_learning_profile_complete=False,
            )
            self.db.add(profile)

        elif data.role == UserRole.TEACHER:
            if data.class_ids:
                cs = ClassService(db=self.db)
                for class_id in data.class_ids:
                    await cs.update_teacher(
                        class_id=class_id,
                        teacher_id=user.id,
                        school_id=school_id,
                    )

        elif data.role == UserRole.PARENT:
            if data.student_ids:
                for student_id in data.student_ids:
                    self.db.add(ParentStudent(parent_id=user.id, student_id=student_id))

        await self._send_credentials_email(user, raw_password, school_id)
        return user

    async def list_users(
        self,
        school_id: uuid.UUID,
        role: UserRole | None = None,
        page: int = 1,
        page_size: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """List users in a school with optional role and active-status filters, plus pagination."""
        conditions = [User.school_id == school_id]
        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))
        else:
            conditions.append(User.is_active.is_(True))

        stmt = select(User).where(*conditions)
        if role:
            # User.role is Mapped[str]; SQLAlchemy serialises the enum to its .value for comparison.
            stmt = stmt.where(User.role == role.value)

        offset = (page - 1) * page_size
        result = await self.db.execute(stmt.order_by(User.last_name, User.first_name).offset(offset).limit(page_size))
        users = result.scalars().all()

        count_stmt = select(func.count()).select_from(User).where(*conditions)
        if role:
            count_stmt = count_stmt.where(User.role == role.value)
        total = await self.db.scalar(count_stmt) or 0
        return list(users), total

    async def get_user(self, user_id: uuid.UUID, school_id: uuid.UUID | None = None) -> User:
        """Get a user by ID, ensuring they belong to the specified school."""
        # Fetch user with both user_id and school_id in single query
        stmt = select(User).where(User.id == user_id)
        if school_id is not None:
            stmt = stmt.where(User.school_id == school_id)

        user = await self.db.scalar(stmt)
        if not user:
            raise ValueError("User not found")
        return user

    async def update_user(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> User:
        """Update user information."""
        user = await self.get_user(user_id, school_id)
        previous_state = {"first_name": user.first_name, "last_name": user.last_name, "is_active": user.is_active}

        # Extract password separately - don't let it pass through the generic loop
        update_data = data.model_dump(exclude_unset=True)
        new_password = update_data.pop("password", None)

        # Extract grade_id separately - requires student profile update
        grade_id = update_data.pop("grade_id", None)

        # Email uniqueness check — only when email is actually changing
        new_email = update_data.get("email")
        if new_email is not None and new_email != user.email:
            conflict = await self.db.scalar(
                select(User).where(
                    User.school_id == school_id,
                    User.email == new_email,
                    User.id != user_id,
                )
            )
            if conflict:
                raise ValueError(f"Email '{new_email}' is already registered at this school")

        for field, value in update_data.items():
            setattr(user, field, value)

        # Handle password update - hash and store separately
        if new_password is not None:
            user.hashed_password = hash_password(new_password)

        # Handle grade_id update for students
        if grade_id is not None:
            profile = await self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))
            if profile is None:
                raise ValueError("Student profile not found")
            profile.grade_id = grade_id

        await self.db.flush()

        logger.info(
            "user_updated",
            user_id=str(user.id),
            school_id=str(school_id),
            previous_state=previous_state,
            new_state={"first_name": user.first_name, "last_name": user.last_name, "is_active": user.is_active},
            password_changed=new_password is not None,
            grade_changed=grade_id is not None,
        )

        return user

    async def deactivate_user(self, school_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft delete — sets is_active=False. User cannot log in after this."""
        user = await self.get_user(user_id, school_id)
        previous_state = user.is_active
        user.is_active = False
        await self.db.flush()

        logger.info(
            "user_deactivated",
            user_id=str(user.id),
            school_id=str(school_id),
            previous_state=previous_state,
            new_state=False,
        )

    async def _send_welcome_email(self, user: User, token: str, base_url: str) -> None:
        """Send magic link welcome email via EmailService."""
        verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"
        email_service = EmailService()
        try:
            await email_service.send(
                to=user.email,
                subject="Welcome to Kaihle — activate your account",
                template="magic_link.html.jinja2",
                ctx={"first_name": user.first_name, "verify_url": verify_url},
            )
        except Exception as e:
            logger.error(
                "failed_to_send_welcome_email",
                user_id=str(user.id),
                error_type=type(e).__name__,
                error_message=str(e),
            )

    async def _send_credentials_email(self, user: User, raw_password: str, school_id: uuid.UUID) -> None:
        """Send welcome email containing login credentials to a newly created user."""
        school = await self.db.get(School, school_id)
        school_name = school.name if school else "your school"

        role_url_map: dict[str, str] = {
            "TEACHER": settings.teacher_app_url,
            "STUDENT": settings.student_app_url,
            "PARENT": settings.parent_app_url,
            "SCHOOL_ADMIN": settings.school_admin_app_url,
            "KAIHLE_ADMIN": settings.kaihle_admin_app_url,
        }
        app_url = role_url_map.get(user.role, settings.school_admin_app_url)
        login_url = f"{app_url}/login"

        email_service = EmailService()
        try:
            await email_service.send(
                to=user.email,
                subject="Your Kaihle account is ready",
                template="welcome_credentials.html.jinja2",
                ctx={
                    "first_name": user.first_name,
                    "email": user.email,
                    "temp_password": raw_password,
                    "login_url": login_url,
                    "school_name": school_name,
                },
            )
        except Exception as e:
            logger.error(
                "failed_to_send_credentials_email",
                user_id=str(user.id),
                error_type=type(e).__name__,
                error_message=str(e),
            )

    async def get_me(self, user_id: uuid.UUID) -> User:
        """Get the current user's own record."""
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        return user

    async def update_me(self, user_id: uuid.UUID, data: UserSelfUpdate) -> User:
        """Update the current user's own first_name and/or last_name.

        Email, role, and school_id are NOT updatable here — never touch them.
        """
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        # email, role, school_id are NOT updatable here — never touch them
        await self.db.flush()
        return user

    async def get_student_detail(
        self,
        student_id: uuid.UUID,
        caller_school_id: uuid.UUID | None,
    ) -> StudentDetailResponse:
        """Return full student profile with class enrollments and gap states.

        Raises UserNotFoundError if the student doesn't exist.
        Raises CrossSchoolAccessError if caller_school_id is set and doesn't match.
        """
        student = await self.db.scalar(select(User).where(User.id == student_id, User.role == UserRole.STUDENT))
        if student is None:
            raise UserNotFoundError("Student not found")
        if caller_school_id is not None and student.school_id != caller_school_id:
            raise CrossSchoolAccessError("Access denied")

        # Grade comes from student_profiles — the single source of truth for student grade.
        # outerjoin so students without a profile row (or with grade_id=NULL) return None cleanly.
        profile_row = (
            await self.db.execute(
                select(StudentProfile.grade_id, Grade.level, Grade.name)
                .outerjoin(Grade, Grade.id == StudentProfile.grade_id)
                .where(StudentProfile.user_id == student_id)
            )
        ).one_or_none()
        grade_id: uuid.UUID | None = profile_row[0] if profile_row else None
        grade_level: int | None = profile_row[1] if profile_row else None
        grade_name: str | None = profile_row[2] if profile_row else None

        enrollment_query = (
            select(ClassEnrollment, Class, Curriculum, User)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .join(Curriculum, Curriculum.id == Class.curriculum_id)
            .outerjoin(User, User.id == Class.teacher_id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
            )
            .order_by(ClassEnrollment.enrolled_at)
        )
        enrollment_rows = (await self.db.execute(enrollment_query)).all()

        # Fetch all gap states in one query, then group by class_id in Python
        gap_rows = (
            await self.db.execute(
                select(GapState, Subtopic)
                .join(Subtopic, Subtopic.id == GapState.subtopic_id)
                .where(GapState.student_id == student_id)
                .order_by(GapState.class_id, Subtopic.name)
            )
        ).all()
        gap_by_class: dict[uuid.UUID, list[GapStateDetail]] = {}
        for gap, subtopic in gap_rows:
            gap_by_class.setdefault(gap.class_id, []).append(
                GapStateDetail(subtopic_name=subtopic.name, mastery_score=gap.mastery_score)
            )

        curriculum_name: str = ""
        earliest_enrolled_at: str = ""
        class_enrollments: list[ClassEnrollmentDetail] = []

        for enrollment, class_, curriculum, teacher in enrollment_rows:
            if curriculum_name == "" and curriculum:
                curriculum_name = curriculum.name
            if earliest_enrolled_at == "" and enrollment.enrolled_at:
                earliest_enrolled_at = enrollment.enrolled_at.isoformat()
            teacher_name = f"{teacher.first_name} {teacher.last_name}".strip() if teacher else ""
            class_enrollments.append(
                ClassEnrollmentDetail(
                    class_id=class_.id,
                    class_name=class_.name,
                    teacher_name=teacher_name,
                    gap_states=gap_by_class.get(class_.id, []),
                )
            )

        logger.info(
            "student_detail_requested",
            target_student_id=str(student_id),
            class_count=len(class_enrollments),
        )
        return StudentDetailResponse(
            id=student.id,
            first_name=student.first_name or "",
            last_name=student.last_name or "",
            email=student.email or "",
            is_active=student.is_active if student.is_active is not None else True,
            grade_id=str(grade_id) if grade_id else None,
            grade_level=grade_level,
            grade_name=grade_name,
            curriculum_name=curriculum_name,
            enrolled_at=earliest_enrolled_at,
            last_login_at=student.last_login_at.isoformat() if student.last_login_at else None,
            class_enrollments=class_enrollments,
        )

    async def get_teacher_detail(
        self,
        teacher_id: uuid.UUID,
        caller_school_id: uuid.UUID | None,
    ) -> TeacherDetailResponse:
        """Return teacher profile with assigned classes.

        Raises UserNotFoundError if the teacher doesn't exist.
        Raises CrossSchoolAccessError if caller_school_id is set and doesn't match.
        """
        teacher = await self.db.scalar(select(User).where(User.id == teacher_id, User.role == UserRole.TEACHER))
        if teacher is None:
            raise UserNotFoundError("Teacher not found")
        if caller_school_id is not None and teacher.school_id != caller_school_id:
            raise CrossSchoolAccessError("Access denied")

        class_rows = (
            await self.db.execute(
                select(Class, Subject, Grade)
                .join(Subject, Subject.id == Class.subject_id)
                .join(Grade, Grade.id == Class.grade_id)
                .where(Class.teacher_id == teacher_id, Class.is_active.is_(True))
                .order_by(Class.name)
            )
        ).all()

        class_ids = [c.id for c, _, _ in class_rows]
        counts: dict[uuid.UUID, int] = {}
        avgs: dict[uuid.UUID, float | None] = {}

        if class_ids:
            for row in (
                await self.db.execute(
                    select(ClassEnrollment.class_id, func.count(ClassEnrollment.class_id).label("cnt"))
                    .where(ClassEnrollment.class_id.in_(class_ids), ClassEnrollment.is_active.is_(True))
                    .group_by(ClassEnrollment.class_id)
                )
            ).all():
                counts[row.class_id] = row.cnt

            for row in (
                await self.db.execute(
                    select(GapState.class_id, func.avg(GapState.mastery_score).label("avg"))
                    .where(GapState.class_id.in_(class_ids))
                    .group_by(GapState.class_id)
                )
            ).all():
                avgs[row.class_id] = row.avg

        assigned_classes = [
            AssignedClassSummary(
                class_id=c.id,
                class_name=c.name,
                subject_name=subject.name if subject else "",
                grade_level=grade.level if grade else 0,
                grade_name=grade.name if grade else "",
                student_count=counts.get(c.id, 0),
                avg_mastery=avgs.get(c.id),
            )
            for c, subject, grade in class_rows
        ]

        logger.info(
            "teacher_detail_requested",
            target_teacher_id=str(teacher_id),
            class_count=len(assigned_classes),
        )
        return TeacherDetailResponse(
            id=teacher.id,
            first_name=teacher.first_name or "",
            last_name=teacher.last_name or "",
            email=teacher.email,
            is_active=teacher.is_active,
            assigned_classes=assigned_classes,
        )

    async def get_parent_detail(
        self,
        parent_id: uuid.UUID,
        caller_school_id: uuid.UUID | None,
    ) -> ParentDetailResponse:
        """Return parent profile with linked students.

        Raises UserNotFoundError if the parent doesn't exist.
        Raises CrossSchoolAccessError if caller_school_id is set and doesn't match.
        """
        parent = await self.db.scalar(select(User).where(User.id == parent_id, User.role == UserRole.PARENT))
        if parent is None:
            raise UserNotFoundError("Parent not found")
        if caller_school_id is not None and parent.school_id != caller_school_id:
            raise CrossSchoolAccessError("Access denied")

        link_rows = (
            await self.db.execute(
                select(ParentStudent, User)
                .join(User, User.id == ParentStudent.student_id)
                .where(ParentStudent.parent_id == parent_id)
                .order_by(User.first_name, User.last_name)
            )
        ).all()

        student_ids = [s.id for _, s in link_rows]
        class_counts: dict[uuid.UUID, int] = {}
        worst_masteries: dict[uuid.UUID, float | None] = {}

        if student_ids:
            for count_row in (
                await self.db.execute(
                    select(ClassEnrollment.student_id, func.count(ClassEnrollment.class_id).label("cnt"))
                    .where(ClassEnrollment.student_id.in_(student_ids), ClassEnrollment.is_active.is_(True))
                    .group_by(ClassEnrollment.student_id)
                )
            ).all():
                class_counts[count_row.student_id] = count_row.cnt

            for mastery_row in (
                await self.db.execute(
                    select(GapState.student_id, func.min(GapState.mastery_score).label("worst"))
                    .where(GapState.student_id.in_(student_ids))
                    .group_by(GapState.student_id)
                )
            ).all():
                worst_masteries[mastery_row.student_id] = mastery_row.worst

        linked_students = [
            LinkedStudentSummary(
                student_id=s.id,
                first_name=s.first_name or "",
                last_name=s.last_name or "",
                worst_mastery=worst_masteries.get(s.id),
                class_count=class_counts.get(s.id, 0),
            )
            for _, s in link_rows
        ]

        logger.info(
            "parent_detail_requested",
            target_parent_id=str(parent_id),
            linked_student_count=len(linked_students),
        )
        return ParentDetailResponse(
            id=parent.id,
            first_name=parent.first_name or "",
            last_name=parent.last_name or "",
            email=parent.email,
            is_active=parent.is_active,
            linked_students=linked_students,
        )

    async def get_student_info(self, student: User) -> StudentInfoResponse:
        """Return basic student info including enrolled classes.

        Authorization checks must be performed by the caller before invoking this method.
        """
        enrollment_query = (
            select(ClassEnrollment, Class, Subject, Grade, Curriculum)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .join(Subject, Subject.id == Class.subject_id)
            .join(Grade, Grade.id == Class.grade_id)
            .join(Curriculum, Curriculum.id == Class.curriculum_id)
            .where(
                ClassEnrollment.student_id == student.id,
                ClassEnrollment.is_active.is_(True),
            )
            .order_by(ClassEnrollment.enrolled_at)
        )
        enrollment_rows = (await self.db.execute(enrollment_query)).all()

        grade_name = ""
        curriculum_name = ""
        class_id = None
        enrolled_classes: list[EnrolledClassInfo] = []

        for _, class_, subject, grade, curriculum in enrollment_rows:
            if class_id is None:
                class_id = class_.id
            if not curriculum_name:
                curriculum_name = curriculum.name if curriculum else ""
            if not grade_name and grade:
                grade_name = grade.name
            enrolled_classes.append(
                EnrolledClassInfo(
                    class_id=class_.id,
                    class_name=class_.name,
                    subject_id=class_.subject_id,
                    subject_name=subject.name if subject else "",
                    grade_name=grade.name if grade else "",
                )
            )

        logger.debug(
            "student_info_retrieved",
            student_id=str(student.id),
            enrolled_class_count=len(enrolled_classes),
        )
        return StudentInfoResponse(
            first_name=student.first_name or "",
            last_name=student.last_name or "",
            email=student.email,
            grade_name=grade_name,
            curriculum_name=curriculum_name,
            class_id=class_id,
            streak_days=None,
            is_enrolled=len(enrolled_classes) > 0,
            enrolled_classes=enrolled_classes,
        )

    async def get_student_classes(self, student: User) -> list[StudentClassResponse]:
        """Return all active enrolled classes for a student with full details."""
        query = (
            select(ClassEnrollment, Class, Subject, Grade, User)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .join(Subject, Subject.id == Class.subject_id)
            .join(Grade, Grade.id == Class.grade_id)
            .join(User, User.id == Class.teacher_id)
            .where(
                ClassEnrollment.student_id == student.id,
                ClassEnrollment.is_active.is_(True),
            )
            .order_by(ClassEnrollment.enrolled_at)
        )
        rows = (await self.db.execute(query)).all()

        return [
            StudentClassResponse(
                id=class_.id,
                name=class_.name,
                subject_id=class_.subject_id,
                subject_name=subject.name if subject else "",
                grade_name=grade.name if grade else "",
                teacher_name=f"{teacher.first_name} {teacher.last_name}".strip() if teacher else "",
                curriculum_id=class_.curriculum_id,
                academic_year=class_.academic_year or "",
                is_active=enrollment.is_active,
                onboarding_diagnostic_status=enrollment.onboarding_diagnostic_status,
                diagnostic_attempt_id=None,
            )
            for enrollment, class_, subject, grade, teacher in rows
        ]

    async def list_platform_users(
        self,
        q: str | None = None,
        role: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[User], int]:
        """List all platform users with optional filters.

        KAIHLE_ADMIN bypass — returns users from ALL schools (Rule 12 explicit).
        LEFT JOIN schools for school_name.

        Args:
            q: Search query for name or email (case-insensitive ILIKE)
            role: Filter by user role
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (list of users, total count)
        """
        from app.models.school import School

        # Build base query with school join
        stmt = select(User, School.name.label("school_name")).outerjoin(School, User.school_id == School.id)

        # Apply search filter
        if q:
            search_pattern = f"%{q}%"
            stmt = stmt.where(
                (User.email.ilike(search_pattern))
                | (User.first_name.ilike(search_pattern))
                | (User.last_name.ilike(search_pattern))
            )

        # Apply role filter — ignore sentinel values like "ALL" or unknown roles
        role_filter: UserRole | None = None
        if role:
            try:
                role_filter = UserRole(role)
            except ValueError:
                pass

        if role_filter:
            stmt = stmt.where(User.role == role_filter)

        # Get total count before pagination
        count_stmt = select(func.count()).select_from(User)
        if q:
            search_pattern = f"%{q}%"
            count_stmt = count_stmt.where(
                (User.email.ilike(search_pattern))
                | (User.first_name.ilike(search_pattern))
                | (User.last_name.ilike(search_pattern))
            )
        if role_filter:
            count_stmt = count_stmt.where(User.role == role_filter)

        total = await self.db.scalar(count_stmt) or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Attach school_name to user objects for convenience
        users = []
        for user, school_name in rows:
            # Store school_name as a dynamic attribute for response mapping
            user.school_name = school_name  # type: ignore[attr-defined]
            users.append(user)

        logger.info(
            "platform_users_listed",
            q=q,
            role=role,
            page=page,
            page_size=page_size,
            total=total,
            returned=len(users),
        )

        return users, total
