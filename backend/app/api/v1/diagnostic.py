"""
Diagnostic Assessment API Router.

Phase 7 REST API Layer - 6 endpoints for diagnostic assessment flow.

Endpoints:
  POST /diagnostic/initialize      - Initialize diagnostic assessments (idempotent)
  GET  /diagnostic/status/{student_id} - Overall status across all subjects
  GET  /diagnostic/{assessment_id}/next-question - Get next adaptive question
  POST /diagnostic/{assessment_id}/answer - Submit answer
  GET  /diagnostic/report/{student_id} - Full diagnostic report (202 while generating)
  GET  /diagnostic/study-plan/{student_id} - Generated study plan (202 while generating)
"""

import logging
import os
from typing import Optional
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.assessment import Assessment, AssessmentReport, AssessmentStatus, AssessmentType
from app.models.study_plan import StudyPlan
from app.models.subject import Subject
from app.models.user import StudentProfile, User, UserRole
from app.schemas.diagnostic import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    DiagnosticAbandonResponse,
    DiagnosticInitRequest,
    DiagnosticInitResponse,
    DiagnosticReportResponse,
    DiagnosticStatusResponse,
    GenerationStatusResponse,
    KnowledgeGapItem,
    NextQuestionResponse,
    QuestionItem,
    QuestionOption,
    SessionSummaryItem,
    StrengthItem,
    StudyPlanCourseItem,
    StudyPlanResponse,
    SubjectReportItem,
    SubjectStatusItem,
    SubtopicProgress,
    get_difficulty_label,
    DIFFICULTY_LABELS,
)
from app.services.diagnostic.session_manager import DiagnosticSessionManager
from app.services.diagnostic.response_handler import DiagnosticResponseHandler

logger = logging.getLogger(__name__)

router = APIRouter()

REDIS_GENERATION_KEY_PREFIX = "kaihle:diagnostic:generating"
REDIS_GENERATION_TTL = 2 * 60 * 60


def get_redis_client():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


def _authorize_student_access(current_user: User, student_id: UUID, db: Session) -> StudentProfile:
    """
    Authorize access to student data.
    
    Rules:
    - Students can access their own data only
    - Parents can access their children's data only
    - Admins have full access
    """
    student = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    
    if current_user.role == UserRole.ADMIN:
        return student
    
    if current_user.role == UserRole.STUDENT:
        if not current_user.student_profile or current_user.student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this student's data"
            )
        return student
    
    if current_user.role == UserRole.PARENT:
        if student.parent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this student's data"
            )
        return student
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access student data"
    )


def _get_generation_status(redis_client, student_id: UUID) -> Optional[str]:
    """Get the current generation status from Redis."""
    key = f"{REDIS_GENERATION_KEY_PREFIX}:{student_id}"
    raw_status = redis_client.get(key)
    if raw_status:
        return raw_status.decode("utf-8") if isinstance(raw_status, bytes) else raw_status
    return None


def _build_question_response(question, assessment_id: UUID, session_state: dict, subject_id: UUID) -> NextQuestionResponse:
    """Build the response for the next-question endpoint. Never includes correct_answer/explanation."""
    if not question:
        return NextQuestionResponse(
            assessment_id=assessment_id,
            subject_id=subject_id,
            question=None,
            status=session_state.get("status", AssessmentStatus.COMPLETED.value),
            answered_count=session_state.get("answered_count", 0),
            total_questions=session_state.get("total_questions", 0),
            subtopics=[
                SubtopicProgress(
                    subtopic_id=st["subtopic_id"],
                    subtopic_name=st["subtopic_name"],
                    questions_total=st["questions_total"],
                    questions_answered=st["questions_answered"],
                    current_difficulty=st["current_difficulty"],
                    difficulty_label=get_difficulty_label(st["current_difficulty"]),
                )
                for st in session_state.get("subtopics", [])
            ],
            current_subtopic_index=session_state.get("current_subtopic_index", 0),
        )

    options = None
    if question.options and isinstance(question.options, dict):
        options = [
            QuestionOption(key=k, value=v)
            for k, v in question.options.items()
        ]

    current_index = session_state.get("current_subtopic_index", 0)
    subtopics = session_state.get("subtopics", [])
    current_subtopic = subtopics[current_index] if current_index < len(subtopics) else None

    question_response = QuestionItem(
        question_id=question.id,
        question_bank_id=question.id,
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty_level=question.difficulty_level,
        difficulty_label=get_difficulty_label(question.difficulty_level),
        options=options,
        question_number=session_state.get("answered_count", 0) + 1,
        subtopic_name=current_subtopic.get("subtopic_name") if current_subtopic else None,
        estimated_time_seconds=question.estimated_time_seconds,
    )

    return NextQuestionResponse(
        assessment_id=assessment_id,
        subject_id=subject_id,
        question=question_response,
        status=session_state.get("status", AssessmentStatus.IN_PROGRESS.value),
        answered_count=session_state.get("answered_count", 0),
        total_questions=session_state.get("total_questions", 0),
        subtopics=[
            SubtopicProgress(
                subtopic_id=st["subtopic_id"],
                subtopic_name=st["subtopic_name"],
                questions_total=st["questions_total"],
                questions_answered=st["questions_answered"],
                current_difficulty=st["current_difficulty"],
                difficulty_label=get_difficulty_label(st["current_difficulty"]),
            )
            for st in subtopics
        ],
        current_subtopic_index=current_index,
    )


@router.post("/initialize", response_model=DiagnosticInitResponse)
def initialize_diagnostic(
    payload: DiagnosticInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Initialize diagnostic assessments for a student.
    
    Idempotent: If diagnostics already exist, returns existing sessions.
    Creates one assessment per subject (typically 4 subjects).
    """
    _authorize_student_access(current_user, payload.student_id, db)

    redis_client = get_redis_client()
    manager = DiagnosticSessionManager(db, redis_client=redis_client)

    try:
        result = manager.initialize_diagnostic(payload.student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    subject_names = {}
    for session in result["sessions"]:
        subject = db.query(Subject).filter(Subject.id == session["subject_id"]).first()
        if subject:
            subject_names[str(session["subject_id"])] = subject.name

    sessions = [
        SessionSummaryItem(
            assessment_id=session["assessment_id"],
            subject_id=session["subject_id"],
            subject_name=subject_names.get(str(session["subject_id"])),
            status=session["status"],
            total_questions=session["total_questions"],
            answered_count=session["answered_count"],
            current_subtopic_index=session["current_subtopic_index"],
            subtopics_count=session["subtopics_count"],
            started_at=session.get("started_at"),
            last_activity=session.get("last_activity"),
        )
        for session in result["sessions"]
    ]

    return DiagnosticInitResponse(
        sessions=sessions,
        student_id=result["student_id"],
        grade_id=result.get("grade_id"),
        curriculum_id=result.get("curriculum_id"),
        existing=result.get("existing", False),
    )


@router.get("/status/{student_id}", response_model=DiagnosticStatusResponse)
def get_diagnostic_status(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get overall diagnostic status across all subjects.
    
    Returns status for each subject assessment, completion percentages,
    and generation status for reports/study plan.
    """
    student = _authorize_student_access(current_user, student_id, db)

    assessments = db.query(Assessment).filter(
        Assessment.student_id == student_id,
        Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
    ).all()

    redis_client = get_redis_client()
    manager = DiagnosticSessionManager(db, redis_client=redis_client)

    subjects = []
    all_complete = True
    
    for assessment in assessments:
        subject = db.query(Subject).filter(Subject.id == assessment.subject_id).first()
        subject_name = subject.name if subject else None
        
        try:
            state = manager.get_session_state(assessment.id)
            answered = state.get("answered_count", 0)
            total = state.get("total_questions", 1)
            progress = (answered / total * 100) if total > 0 else 0.0
            subj_status = state.get("status", assessment.status.value)
            
            current_index = state.get("current_subtopic_index", 0)
            subtopics = state.get("subtopics", [])
            current_difficulty = 3
            if current_index < len(subtopics):
                current_difficulty = subtopics[current_index].get("current_difficulty", 3)
            
            if subj_status != AssessmentStatus.COMPLETED.value:
                all_complete = False
            
            subjects.append(SubjectStatusItem(
                assessment_id=assessment.id,
                subject_id=assessment.subject_id,
                subject_name=subject_name,
                status=subj_status,
                total_questions=total,
                answered_count=answered,
                progress_percentage=round(progress, 1),
                current_difficulty=current_difficulty,
                started_at=assessment.created_at,
                completed_at=assessment.completed_at,
            ))
        except ValueError:
            if assessment.status != AssessmentStatus.COMPLETED:
                all_complete = False
            subjects.append(SubjectStatusItem(
                assessment_id=assessment.id,
                subject_id=assessment.subject_id,
                subject_name=subject_name,
                status=assessment.status.value,
                total_questions=0,
                answered_count=0,
                progress_percentage=0.0,
                current_difficulty=3,
                started_at=assessment.created_at,
                completed_at=assessment.completed_at,
            ))

    generation_status = _get_generation_status(redis_client, student_id)
    
    reports_ready = generation_status in ("complete", None) and all_complete
    study_plan_ready = generation_status == "complete"
    
    generation_status_label = None
    if generation_status:
        status_labels = {
            "reports": "Generating reports",
            "study_plan": "Generating study plan",
            "complete": "Generation complete",
            "failed": "Generation failed",
        }
        generation_status_label = status_labels.get(generation_status, generation_status)

    overall_status = "completed" if all_complete else "in_progress"
    if not assessments:
        overall_status = "not_started"

    return DiagnosticStatusResponse(
        student_id=student_id,
        overall_status=overall_status,
        has_completed_assessment=student.has_completed_assessment or False,
        subjects=subjects,
        all_complete=all_complete,
        reports_ready=reports_ready,
        study_plan_ready=study_plan_ready,
        generation_status=generation_status,
        generation_status_label=generation_status_label,
    )


@router.get("/{assessment_id}/next-question")
def get_next_question(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the next adaptive question for an assessment.
    
    Returns:
      - 200 with question data if question available
      - 204 No Content if assessment is complete
    
    CRITICAL: Never exposes correct_answer, explanation, or is_correct.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    _authorize_student_access(current_user, assessment.student_id, db)

    if assessment.assessment_type != AssessmentType.DIAGNOSTIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for diagnostic assessments"
        )

    if assessment.status == AssessmentStatus.COMPLETED:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if assessment.status == AssessmentStatus.ABANDONED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment has been abandoned"
        )

    redis_client = get_redis_client()
    manager = DiagnosticSessionManager(db, redis_client=redis_client)

    try:
        question, session_state = manager.get_current_question(assessment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not question:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return _build_question_response(question, assessment_id, session_state, assessment.subject_id)


@router.post("/{assessment_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    assessment_id: UUID,
    payload: AnswerSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Submit an answer for the current question.
    
    Returns correctness, score, difficulty adjustment, and session progress.
    
    Error codes:
      - 400: Assessment completed, abandoned, or invalid state
      - 404: No current question available
      - 409: Question already answered
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    _authorize_student_access(current_user, assessment.student_id, db)

    if assessment.assessment_type != AssessmentType.DIAGNOSTIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for diagnostic assessments"
        )

    if assessment.status == AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is already completed"
        )

    if assessment.status == AssessmentStatus.ABANDONED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment has been abandoned"
        )

    redis_client = get_redis_client()
    manager = DiagnosticSessionManager(db, redis_client=redis_client)
    session_state = manager.get_session_state(assessment_id)

    current_question_id = session_state.get("current_question_bank_id")
    if not current_question_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current question available. Request a new question first."
        )

    handler = DiagnosticResponseHandler(db, redis_client=redis_client)

    try:
        result = handler.submit_answer(
            assessment_id=assessment_id,
            question_bank_id=current_question_id,
            student_answer=payload.answer_text,
            time_taken_seconds=payload.time_taken_seconds,
        )
    except ValueError as e:
        error_message = str(e)
        if "already been answered" in error_message:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message)
        if "not the current question" in error_message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)

    return AnswerSubmitResponse(
        is_correct=result.is_correct,
        score=result.score,
        difficulty_level=result.difficulty_level,
        difficulty_label=get_difficulty_label(result.difficulty_level),
        next_difficulty=result.next_difficulty,
        next_difficulty_label=get_difficulty_label(result.next_difficulty),
        questions_answered=result.questions_answered,
        total_questions=result.total_questions,
        subtopic_complete=result.subtopic_complete,
        assessment_status=result.assessment_status,
        all_subjects_complete=result.all_subjects_complete,
    )


@router.get("/report/{student_id}")
def get_diagnostic_report(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the full diagnostic report for a student.
    
    Returns:
      - 200 with report data if ready
      - 202 with retry_after_seconds if still generating
      - 403 if not authorized
    """
    _authorize_student_access(current_user, student_id, db)

    redis_client = get_redis_client()
    generation_status = _get_generation_status(redis_client, student_id)

    if generation_status in ("reports", "study_plan"):
        return GenerationStatusResponse(
            status="generating",
            stage=generation_status,
            retry_after_seconds=15,
        )

    if generation_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed. Please contact support."
        )

    assessments = db.query(Assessment).filter(
        Assessment.student_id == student_id,
        Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
        Assessment.status == AssessmentStatus.COMPLETED,
    ).all()

    if not assessments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed diagnostic assessments found"
        )

    subjects = []
    for assessment in assessments:
        subject = db.query(Subject).filter(Subject.id == assessment.subject_id).first()
        subject_name = subject.name if subject else None

        report = db.query(AssessmentReport).filter(
            AssessmentReport.assessment_id == assessment.id
        ).first()

        if not report:
            continue

        diagnostic_summary = report.diagnostic_summary or {}
        knowledge_gaps = report.knowledge_gaps or []
        strengths = report.strengths or []

        subjects.append(SubjectReportItem(
            subject_id=assessment.subject_id,
            subject_name=subject_name,
            assessment_id=assessment.id,
            overall_mastery=diagnostic_summary.get("overall_mastery", 0.0),
            mastery_label=diagnostic_summary.get("mastery_label", "unknown"),
            total_questions=diagnostic_summary.get("total_questions", 0),
            total_correct=diagnostic_summary.get("total_correct", 0),
            highest_difficulty_reached=diagnostic_summary.get("highest_difficulty_reached", 1),
            average_difficulty_reached=diagnostic_summary.get("average_difficulty_reached", 1.0),
            strongest_subtopic=diagnostic_summary.get("strongest_subtopic"),
            weakest_subtopic=diagnostic_summary.get("weakest_subtopic"),
            knowledge_gaps=[
                KnowledgeGapItem(
                    subtopic_id=UUID(gap.get("subtopic_id")) if gap.get("subtopic_id") else None,
                    subtopic_name=gap.get("subtopic_name", ""),
                    topic_name=gap.get("topic_name"),
                    mastery_level=gap.get("mastery_level", 0.0),
                    mastery_label=gap.get("mastery_label", "unknown"),
                    priority=gap.get("priority", "medium"),
                    difficulty_reached=gap.get("difficulty_reached", 1),
                    correct_count=gap.get("correct_count", 0),
                    total_count=gap.get("total_count", 0),
                )
                for gap in knowledge_gaps
            ],
            strengths=[
                StrengthItem(
                    subtopic_id=UUID(s.get("subtopic_id")) if s.get("subtopic_id") else None,
                    subtopic_name=s.get("subtopic_name", ""),
                    topic_name=s.get("topic_name"),
                    mastery_level=s.get("mastery_level", 0.0),
                    mastery_label=s.get("mastery_label", "unknown"),
                )
                for s in strengths
            ],
            subtopics=[],
        ))

    return DiagnosticReportResponse(
        student_id=student_id,
        status="ready",
        subjects=subjects,
    )


@router.get("/study-plan/{student_id}")
def get_study_plan(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the generated study plan for a student.
    
    Returns:
      - 200 with study plan data if ready
      - 202 with retry_after_seconds if still generating
      - 404 if no study plan exists
    """
    _authorize_student_access(current_user, student_id, db)

    redis_client = get_redis_client()
    generation_status = _get_generation_status(redis_client, student_id)

    if generation_status in ("reports", "study_plan"):
        return GenerationStatusResponse(
            status="generating",
            stage=generation_status,
            retry_after_seconds=15,
        )

    if generation_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study plan generation failed. Please contact support."
        )

    study_plan = db.query(StudyPlan).filter(
        StudyPlan.student_id == student_id
    ).order_by(StudyPlan.created_at.desc()).first()

    if not study_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No study plan found. Complete all diagnostic assessments first."
        )

    if study_plan.status == "generation_failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study plan generation failed. Please contact support."
        )

    courses = [
        StudyPlanCourseItem(
            id=course.id,
            title=course.title,
            description=course.description,
            topic_id=course.topic_id,
            subtopic_id=course.subtopic_id,
            course_id=course.course_id,
            week=course.week or 1,
            day=course.day or 1,
            sequence_order=course.sequence_order,
            suggested_duration_mins=course.suggested_duration_mins or 20,
            activity_type=course.activity_type or "lesson",
            status=course.status or "not_started",
        )
        for course in study_plan.study_plan_courses
    ]

    return StudyPlanResponse(
        id=study_plan.id,
        student_id=study_plan.student_id,
        title=study_plan.title,
        summary=study_plan.summary,
        total_weeks=study_plan.total_weeks,
        status=study_plan.status,
        progress_percentage=study_plan.progress_percentage or 0,
        courses=courses,
    )


@router.post("/{assessment_id}/abandon", response_model=DiagnosticAbandonResponse)
def abandon_assessment(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Abandon an in-progress diagnostic assessment."""
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    _authorize_student_access(current_user, assessment.student_id, db)

    if assessment.assessment_type != AssessmentType.DIAGNOSTIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for diagnostic assessments"
        )

    if assessment.status == AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot abandon a completed assessment"
        )

    if assessment.status == AssessmentStatus.ABANDONED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is already abandoned"
        )

    redis_client = get_redis_client()
    manager = DiagnosticSessionManager(db, redis_client=redis_client)

    try:
        state = manager.abandon_session(assessment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return DiagnosticAbandonResponse(
        assessment_id=assessment_id,
        status=state.get("status", AssessmentStatus.ABANDONED.value),
        message="Assessment abandoned successfully",
    )


@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "diagnostic"}
