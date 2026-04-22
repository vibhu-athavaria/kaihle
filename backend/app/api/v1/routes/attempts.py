"""Student attempt API routes — the assessment-taking flow.

An attempt is the record of one student taking one assessment.
Lifecycle: NOT_STARTED → IN_PROGRESS (on first answer) → COMPLETED.

The diagnostic endpoint GET /classes/{id}/diagnostic is here because it is
student-facing and returns an AttemptResponse — it logically belongs with
the attempt lifecycle, not with class management.
"""

import uuid as _uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_full_access, require_role
from app.models.assessment import Assessment, StudentAttempt
from app.models.curriculum import QuestionBank
from app.models.school import Class, ClassEnrollment
from app.models.user import ParentStudent, User, UserRole
from app.schemas.assessments import AssessmentQuestion, QuestionOption
from app.schemas.attempts import (
    AnswerSubmitRequest,
    AttemptResponse,
    AttemptResultResponse,
    AttemptSubmitRequest,
    StudentAttemptHistoryItem,
)
from app.schemas.common import Page
from app.services.attempt_service import (
    AttemptAccessDeniedError,
    AttemptAlreadyCompletedError,
    AttemptNotFoundError,
    AttemptService,
    DuplicateResponseError,
    QuestionNotInAssessmentError,
)
from app.services.onboarding_service import OnboardingService

router = APIRouter(tags=["attempts"])


def _questions_to_schema(questions: list[QuestionBank]) -> list[AssessmentQuestion]:
    """Convert QuestionBank rows to student-facing AssessmentQuestion schema.

    Correct answers are expected to already be stripped (None) by the service.
    """
    result = []
    for q in questions:
        options: list[QuestionOption] = []
        if q.options:
            # q.options is JSONB stored as list[{"key": ..., "text": ...}].
            # The model declares JSONB as dict[str, Any] but the runtime value
            # is a list of option dicts. Use cast for correct typing.
            from typing import cast as _cast

            raw_options = _cast(list[dict[str, str]], q.options)
            for opt in raw_options:
                options.append(QuestionOption(key=opt["key"], text=opt["text"]))
        result.append(
            AssessmentQuestion(
                question_id=q.id,
                question_text=q.question_text,
                question_type=q.question_type,
                options=options,
            )
        )
    return result


@router.get("/classes/{class_id}/diagnostic", response_model=AttemptResponse)
async def get_class_diagnostic(
    class_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    """Return the student's Tier 1 diagnostic attempt for the given class.

    This endpoint is intentionally NOT gated by require_diagnostic_complete —
    students must be able to access it in order to complete the diagnostic.
    """
    assert current_user.school_id is not None, "Student must belong to a school"
    service = AttemptService(db)
    try:
        attempt, questions = await service.get_class_diagnostic(
            class_id=class_id,
            student_id=current_user.id,
            school_id=current_user.school_id,
        )
    except AttemptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AttemptResponse(
        id=attempt.id,
        assessment_id=attempt.assessment_id,
        student_id=attempt.student_id,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.completed_at,
        score=attempt.overall_score,
        questions=_questions_to_schema(questions),
    )


@router.post("/assessments/{assessment_id}/start", response_model=AttemptResponse, status_code=status.HTTP_200_OK)
async def start_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    """Get or create a Tier 2 attempt for the requesting student.

    Idempotent — calling this multiple times returns the same attempt.
    Returns 403 if the student is not enrolled in the assessment's class.
    Returns 404 if the assessment is not found or not ACTIVE.
    """
    assert current_user.school_id is not None, "Student must belong to a school"
    service = AttemptService(db)
    try:
        attempt, questions = await service.get_or_create_attempt(
            assessment_id=assessment_id,
            student_id=current_user.id,
            school_id=current_user.school_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        if "not enrolled" in msg.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc

    return AttemptResponse(
        id=attempt.id,
        assessment_id=attempt.assessment_id,
        student_id=attempt.student_id,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.completed_at,
        score=attempt.overall_score,
        questions=_questions_to_schema(questions),
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    """Return an existing attempt with its questions.

    Tier 1 attempts are pre-created at enrollment; Tier 2 attempts are
    created at publish time by a separate mechanism. This endpoint reads
    an existing attempt — it does not create one.
    """
    from sqlalchemy import select

    from app.models.assessment import Assessment, StudentAttempt

    result = await db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

    # Authorization: KAIHLE_ADMIN bypasses school check; all others must match school.
    # STUDENT additionally must own the attempt.
    if current_user.role != UserRole.KAIHLE_ADMIN:
        assessment_result = await db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None or assessment.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if current_user.role == UserRole.STUDENT and attempt.student_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    service = AttemptService(db)
    questions = await service._load_questions(attempt.assessment_id, strip_answers=True)

    return AttemptResponse(
        id=attempt.id,
        assessment_id=attempt.assessment_id,
        student_id=attempt.student_id,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.completed_at,
        score=attempt.overall_score,
        questions=_questions_to_schema(questions),
    )


@router.post("/attempts/{attempt_id}/responses", status_code=status.HTTP_204_NO_CONTENT)
async def submit_response(
    attempt_id: UUID,
    body: AnswerSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record a single answer for an in-progress attempt.

    Returns 204 No Content on success. Idempotent within an attempt —
    submitting the same question twice returns 409.
    """
    assert current_user.school_id is not None, "Student must belong to a school"
    service = AttemptService(db)
    try:
        await service.submit_response(
            attempt_id=attempt_id,
            student_id=current_user.id,
            school_id=current_user.school_id,
            question_id=body.question_id,
            selected_key=body.selected_key,
        )
        await db.commit()
    except AttemptAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateResponseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except QuestionNotInAssessmentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResultResponse)
async def submit_attempt(
    attempt_id: UUID,
    body: AttemptSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AttemptResultResponse:
    """Submit all answers at once and finalise the attempt.

    Scores all answers (MCQ deterministic comparison), fires the
    calculate_gap_states Celery task, and — for Tier 1 diagnostics —
    calls check_and_update_onboarding_complete.
    """
    assert current_user.school_id is not None, "Student must belong to a school"
    service = AttemptService(db)
    onboarding_service = OnboardingService(db)

    # Convert Pydantic answer objects to plain dicts for the service layer
    answers = [{"question_id": a.question_id, "selected_key": a.selected_key} for a in body.answers]

    try:
        result = await service.submit_attempt(
            attempt_id=attempt_id,
            student_id=current_user.id,
            school_id=current_user.school_id,
            answers=answers,
            onboarding_service=onboarding_service,
        )
        await db.commit()
    except AttemptAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return result


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResultResponse)
async def get_attempt_results(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> AttemptResultResponse:
    """Return the scored results for a completed attempt.

    Access: students may only view their own results. Teachers and admins
    may view any result within their school.
    """
    service = AttemptService(db)
    # KAIHLE_ADMIN has no school_id; for all other roles school_id must be set.
    # The service handles the KAIHLE_ADMIN bypass — pass a sentinel UUID when None.
    school_id = current_user.school_id if current_user.school_id is not None else _uuid.UUID(int=0)
    try:
        return await service.get_attempt_results(
            attempt_id=attempt_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
            school_id=school_id,
        )
    except AttemptAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/students/{student_id}/attempts", response_model=Page[StudentAttemptHistoryItem])
async def get_student_attempts(
    student_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> Page[StudentAttemptHistoryItem]:
    """Paginated attempt history for a student. Used by Student Profile → Assessments tab.

    Ordered newest first. Role-based access:
    - STUDENT: own attempts only.
    - TEACHER: student must be enrolled in one of their classes.
    - SCHOOL_ADMIN: student must belong to their school.
    - PARENT: student must be linked to this parent.
    - KAIHLE_ADMIN: unrestricted.
    """
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own attempts.",
            )

    elif current_user.role == UserRole.TEACHER:
        result = await db.execute(
            select(ClassEnrollment.student_id)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                ClassEnrollment.student_id == student_id,
                Class.teacher_id == current_user.id,
                ClassEnrollment.is_active.is_(True),
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student is not enrolled in any of your classes.",
            )

    elif current_user.role == UserRole.SCHOOL_ADMIN:
        student = await db.get(User, student_id)
        if student is None or student.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    elif current_user.role == UserRole.PARENT:
        link = await db.execute(
            select(ParentStudent).where(
                ParentStudent.parent_id == current_user.id,
                ParentStudent.student_id == student_id,
            )
        )
        if link.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view attempts for linked students.",
            )

    base_query = (
        select(
            StudentAttempt,
            Assessment.title.label("assessment_title"),
            Assessment.assessment_type,
            Assessment.class_id,
            Class.name.label("class_name"),
        )
        .join(Assessment, Assessment.id == StudentAttempt.assessment_id)
        .join(Class, Class.id == Assessment.class_id)
        .where(StudentAttempt.student_id == student_id)
        .order_by(StudentAttempt.created_at.desc())
    )

    total = (await db.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()

    rows = (await db.execute(base_query.offset((page - 1) * page_size).limit(page_size))).all()

    items = [
        StudentAttemptHistoryItem(
            attempt_id=row.StudentAttempt.id,
            assessment_id=row.StudentAttempt.assessment_id,
            assessment_title=row.assessment_title,
            assessment_type=row.assessment_type,
            class_id=row.class_id,
            class_name=row.class_name,
            score=float(row.StudentAttempt.overall_score) if row.StudentAttempt.overall_score is not None else None,
            status=row.StudentAttempt.status,
            submitted_at=row.StudentAttempt.completed_at,
            created_at=row.StudentAttempt.created_at,
        )
        for row in rows
    ]

    return Page(data=items, total=total, page=page, page_size=page_size)
