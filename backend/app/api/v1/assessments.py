# app/api/v1/assessments.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.assessment import Assessment, AssessmentReport, AssessmentQuestion, AssessmentStatus, AssessmentType
from app.models.user import User, StudentProfile
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentOut,
    AssessmentQuestionBase,
    AnswerOut,
    AnswerSubmit,
    AssessmentReportResponse
)
from app.crud.assessment import (
    create_assessment,
    resolve_diagnostic_assessment,
    resolve_question,
    get_or_create_assessment_report
)
from app.constants.constants import (
    TOTAL_QUESTIONS_PER_ASSESSMENT
)

router = APIRouter()

@router.post("/", response_model=AssessmentOut)
def create_assessment_api(payload: AssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """
    This endpoint **only creates the non-diagnostic assessment**
    Use POST /resolve to create diagnostic assessments.
    """

    if payload.assessment_type == AssessmentType.DIAGNOSTIC:
        raise HTTPException(status_code=400, detail="Use POST /resolve to create diagnostic assessments")

    student = db.query(StudentProfile).filter(StudentProfile.id == payload.student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    assessment = create_assessment(
        db,
        payload.student_id,
        payload.subject_id,
        payload.assessment_type,
        payload.total_questions_configurable
    )
    return assessment

@router.post("/resolve", response_model=AssessmentOut)
def resolve_diagnostic_assessment_api(
    payload: AssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.assessment_type != AssessmentType.DIAGNOSTIC:
        raise HTTPException(status_code=400, detail="Use POST / to create non-diagnostic assessments")

    student = db.query(StudentProfile).filter(StudentProfile.id == payload.student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return resolve_diagnostic_assessment(
        db=db,
        student_id=payload.student_id,
        subject_id=payload.subject_id,
        total_questions_configurable=payload.total_questions_configurable,
    )


@router.post("/{assessment_id}/questions/resolve", response_model=AssessmentQuestionBase)
async def get_or_create_assessment_question(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """
    Returns:
    - last unanswered question
    - OR creates next question
    - OR None if assessment complete
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status not in [AssessmentStatus.IN_PROGRESS, AssessmentStatus.STARTED]:
        raise HTTPException(status_code=400, detail="Assessment is not in progress")

    # Finally get the last unanswered question or create one
    question = await resolve_question(db, assessment, current_user.student_profile.grade_id)

    return question


@router.post("/{assessment_id}/questions/{question_id}/answer", response_model=AnswerOut)
async def check_answer_and_next(assessment_id: UUID, question_id: UUID, payload: AnswerSubmit, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """
    Submit an answer for a question:
    - Update the question record (is_correct/score/answered_at/time_taken).
    - Update StudentKnowledgeProfile mastery.
    - Update assessment.questions_answered.
    - Update assessment.difficulty_level based on performance (to guide next question).
    - Return next question (if any) or None.
    """
    # Load question
    question = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.id == question_id
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    assessment = question.assessment
    question_bank = question.question_bank
    if not assessment or assessment.id != assessment_id:
        raise HTTPException(status_code=400, detail="Mismatched assessment for question")

    # Record student's answer
    provided = (payload.answer_text or "").strip()
    correct_answer = (question_bank.correct_answer or "").strip()
    is_correct = (provided.lower() == correct_answer.lower()) if correct_answer else False

    question.student_answer = provided
    question.is_correct = is_correct
    question.score = 1.0 if is_correct else 0.0
    question.answered_at = datetime.now(timezone.utc)
    question.time_taken = payload.time_taken
    db.add(question)
    db.commit()
    db.refresh(question)


    # Update assessment counters
    assessment.questions_answered = (assessment.questions_answered or 0) + 1

    # Adjust assessment difficulty_level for next question:
    # Integer 1-5 scale: 1=Beginner, 2=Easy, 3=Medium, 4=Hard, 5=Expert
    # - if correct, increase difficulty (max 5)
    # - if wrong, decrease difficulty (min 1)
    cur_difficulty = assessment.difficulty_level or 3  # Default to medium
    if is_correct:
        # increase by 1 up to 5
        new_difficulty = min(5, cur_difficulty + 1)
    else:
        # decrease by 1 down to 1
        new_difficulty = max(1, cur_difficulty - 1)

    assessment.difficulty_level = new_difficulty

    # Possibly mark assessment complete
    max_questions = assessment.total_questions_configurable or TOTAL_QUESTIONS_PER_ASSESSMENT
    if assessment.questions_answered >= max_questions:
        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.now(timezone.utc)
        # compute overall score
        answers_scores = [q.score or 0.0 for q in assessment.questions]
        assessment.overall_score = (sum(answers_scores) / len(answers_scores)) * 100 if answers_scores else None
        db.add(assessment)
        db.commit()
        # return final result with no next question
        return {
            "question_id": question.id,
            "is_correct": question.is_correct,
            "score": question.score,
            "feedback": question.ai_feedback,
            "next_question": None,
            "status": assessment.status
        }

    # create next question
    next_q = await create_question(db, assessment)
    assessment.total_questions = (assessment.total_questions or 0) + 1

    db.add(assessment)
    db.commit()
    db.refresh(next_q)
    db.refresh(assessment)

    return {
        "question_id": question.id,
        "is_correct": is_correct,
        "score": question.score,
        "feedback": question.ai_feedback,
        "next_question": next_q,
        "status": assessment.status
    }


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.put("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(assessment_id: UUID, payload: AssessmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Update fields if provided
    if payload.total_questions_configurable is not None:
        assessment.total_questions_configurable = payload.total_questions_configurable

    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/completed", response_model=AssessmentReportResponse)
def complete_assessment(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status != AssessmentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Assessment is not marked as completed yet")

    student_name = assessment.student.user.full_name
    grade_level = assessment.grade_level

    return get_or_create_assessment_report(db, assessment_id, student_name, grade_level)

@router.get("/{assessment_id}/report", response_model=AssessmentReportResponse)
def get_assessment_report(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):

    #Load Assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id
    ).first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # If not completed → return a minimal response
    if assessment.status != "completed":
        return {
            "subject": assessment.subject,
            "assessment_id": assessment.id,
            "completed": False,
            "assessment_report": None,
            "diagnostic_summary": None,
        }

    # Get latest AssessmentReport
    report = (
        db.query(AssessmentReport)
        .filter(AssessmentReport.assessment_id == assessment_id)
        .order_by(AssessmentReport.created_at.desc())
        .first()
    )

    if not report:
        raise HTTPException(404, "No report generated yet")

    mastery_rows = report.mastery_table_json or []

    # Compute overall score + topic list
    score = sum(row.get("correct", 0) for row in mastery_rows)
    total = sum(row.get("total_questions", 0) for row in mastery_rows)

    topics = [
        {
            "name": row.get("subtopic").title(),
            "correct": row.get("correct", 0),
            "total": row.get("total_questions", 0),
        }
        for row in mastery_rows
    ]

    # Final response matching your React UI
    return {
        "completed": True,
        "subject": assessment.subject,
        "assessment_id": assessment.id,
        "assessment_report": {
            "score": score,
            "total": total,
            "topics": topics,
        },
        "diagnostic_summary": report.diagnostic_summary,
    }


