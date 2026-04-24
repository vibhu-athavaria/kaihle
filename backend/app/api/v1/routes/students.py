"""Student-specific API routes.

Routes:
- GET  /api/v1/students/me/info            - Current student's own info
- GET  /api/v1/students/{student_id}/info  - Student info (teacher/admin access)
- GET  /api/v1/students/me/classes         - Current student's enrolled classes
- POST /api/v1/students/me/concept-guide   - AI-generated concept explanation
- POST /api/v1/students/me/concept-guide/answer - MCQ answer evaluation
- GET  /api/v1/students/{student_id}       - Full student detail (school admin)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.students import (
    CheckQuestion,
    ConceptGuideRequest,
    ConceptGuideResponse,
    McqAnswerRequest,
    McqAnswerResponse,
    StudentClassResponse,
    StudentInfoResponse,
)
from app.schemas.user_detail import StudentDetailResponse
from app.services.user_service import CrossSchoolAccessError, UserNotFoundError, UserService

logger = structlog.get_logger()

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me/info", response_model=StudentInfoResponse)
async def get_my_student_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentInfoResponse:
    """Get current student's own info.

    Raises:
        403: If user is not a student.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint")

    logger.info("my_student_info_requested", student_id=str(current_user.id))
    return await UserService(db).get_student_info(current_user)


@router.get("/{student_id}/info", response_model=StudentInfoResponse)
async def get_student_info(
    student_id: UUID = Path(..., description="Student ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentInfoResponse:
    """Get basic info for a student.

    Authorization:
    - STUDENT: own record only
    - TEACHER / SCHOOL_ADMIN: any student in the same school
    - KAIHLE_ADMIN: any student

    Raises:
        403: Insufficient permissions.
        404: Student not found.
    """
    student_query = select(User).where(User.id == student_id, User.role == UserRole.STUDENT)
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN):
        student_query = student_query.where(User.school_id == current_user.school_id)

    target_student = (await db.execute(student_query)).scalar_one_or_none()
    if not target_student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if current_user.role == UserRole.STUDENT and current_user.id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own student info")

    if current_user.role not in (
        UserRole.STUDENT,
        UserRole.TEACHER,
        UserRole.SCHOOL_ADMIN,
        UserRole.KAIHLE_ADMIN,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    logger.info(
        "student_info_requested",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        target_student_id=str(student_id),
    )
    return await UserService(db).get_student_info(target_student)


@router.get("/me/classes", response_model=list[StudentClassResponse])
async def get_my_classes(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudentClassResponse]:
    """Get current student's enrolled classes with full details.

    Raises:
        403: If user is not a student.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint")

    logger.info("my_classes_requested", student_id=str(current_user.id))
    return await UserService(db).get_student_classes(current_user)


@router.post("/me/concept-guide", response_model=ConceptGuideResponse)
async def get_concept_guide(
    body: ConceptGuideRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConceptGuideResponse:
    """Generate a personalised AI explanation for a subtopic.

    Raises:
        403: If user is not a student.
        404: If subtopic not found.
        502: If LLM call fails.
    """
    from app.services.concept_guide_service import generate_concept_explanation

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint")

    logger.info(
        "concept_guide_requested",
        student_id=str(current_user.id),
        subtopic_id=str(body.subtopic_id),
        has_question=body.question is not None,
    )

    try:
        result = await generate_concept_explanation(
            student=current_user,
            subtopic_id=body.subtopic_id,
            question=body.question,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("concept_guide_generation_failed", student_id=str(current_user.id), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate explanation. Please try again.",
        ) from exc

    check_question_data = result.get("check_question")
    check_question = (
        CheckQuestion(
            question=check_question_data.get("question"),
            options=check_question_data.get("options"),
            correct=check_question_data.get("correct"),
        )
        if isinstance(check_question_data, dict)
        else None
    )

    return ConceptGuideResponse(
        explanation=result["explanation"],
        subtopic_name=result["subtopic_name"],
        check_question=check_question,
    )


@router.post("/me/concept-guide/answer", response_model=McqAnswerResponse)
async def submit_concept_guide_answer(
    body: McqAnswerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> McqAnswerResponse:
    """Submit a student's MCQ answer and get a follow-up response.

    Raises:
        403: If user is not a student.
        502: If evaluation fails.
    """
    from app.services.concept_guide_service import evaluate_mcq_answer

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this endpoint")

    try:
        result = await evaluate_mcq_answer(
            subtopic_name=body.subtopic_name,
            question=body.question,
            options=body.options,
            correct=body.correct,
            student_answer=body.student_answer,
        )
    except Exception as exc:
        logger.error("concept_guide_answer_failed", student_id=str(current_user.id), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to evaluate answer. Please try again.",
        ) from exc

    return McqAnswerResponse(is_correct=result["is_correct"] == "true", response=result["response"])


@router.get("/{student_id}", response_model=StudentDetailResponse)
async def get_student_detail(
    student_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> StudentDetailResponse:
    """Get full student detail including class enrollments and gap states.

    Auth: SCHOOL_ADMIN (same school) or KAIHLE_ADMIN only.

    Raises:
        403: If SCHOOL_ADMIN accesses a student in another school.
        404: If student not found.
    """
    caller_school = current_user.school_id if current_user.role == UserRole.SCHOOL_ADMIN else None
    try:
        return await UserService(db).get_student_detail(student_id, caller_school)
    except CrossSchoolAccessError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
