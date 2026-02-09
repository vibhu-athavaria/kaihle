# app/api/v1/assessments.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.assessment import Assessment, AssessmentReport, AssessmentQuestion
from app.models.user import User, StudentProfile
from app.schemas.assessment import AssessmentCreate, AssessmentOut, QuestionOut, AnswerOut, AnswerSubmit, AssessmentReportResponse
from app.services.assessment_service import (
    create_question,
    difficulty_float_from_label,
    difficulty_label_from_value,
    get_or_create_assessment_report
)
from app.constants.constants import (
    ASSESSMENT_STATUS_PROGRESS,
    ASSESSMENT_STATUS_COMPLETED,
    ASSESSMENT_TYPES,
    ASSESSMENT_SUBJECTS,
    TOTAL_QUESTIONS_PER_ASSESSMENT
)

router = APIRouter()

@router.post("/", response_model=AssessmentOut)
def create_assessment(payload: AssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Create a new assessment record. This endpoint **only creates the assessment**
    (no question generation). Use POST /{id}/questions to create questions.
    """
    print(f"Creating assessment for student_id={payload.student_id}, subject={payload.subject }")

    student = db.query(StudentProfile).filter(StudentProfile.id == payload.student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # check if there is already an in-progress assessment for this student
    existing = (
        db.query(Assessment)
        .filter(
            Assessment.student_id == payload.student_id,
            Assessment.status == ASSESSMENT_STATUS_PROGRESS,
            Assessment.subject == payload.subject,
            Assessment.grade_level == student.grade_level
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if existing:
        # If an in-progress assessment exists, return it (useful for idempotency)
        return existing

    grade_level = student.grade_level
    assessment = Assessment(
        student_id=payload.student_id,
        subject=payload.subject,
        grade_level=grade_level,
        assessment_type=ASSESSMENT_TYPES[0],  # default to "diagnostic"
        # difficulty_level="medium",
        status=ASSESSMENT_STATUS_PROGRESS,
        total_questions=0,
        questions_answered=0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/questions", response_model=QuestionOut)
async def create_assessment_question(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Create a new question for an existing assessment.

    Rules implemented:
    - Will not create more than 8 questions within the same topic for this assessment.
    - If student has repeated wrong answers for this subject, pick lower difficulty.
    - Uses student_profile checkpoint fields as preference hints (if present).
    - Returns the created question or raises error if limits reached or assessment closed.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status != ASSESSMENT_STATUS_PROGRESS:
        raise HTTPException(status_code=400, detail="Assessment is not in progress")

    if not assessment.subject in ASSESSMENT_SUBJECTS:
        raise HTTPException(status_code=400, detail="Invalid subject for assessment")

    # Finally create the question using existing create_question service
    question = await create_question(db, assessment)

    return question


@router.post("/{assessment_id}/questions/{question_id}/answer", response_model=AnswerOut)
async def check_answer_and_next(assessment_id: UUID, question_id: UUID, payload: AnswerSubmit, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    # Simple rule:
    # - if correct, gently increase difficulty
    # - if wrong, decrease difficulty
    try:
        cur_val = difficulty_float_from_label(assessment.difficulty_level or "medium")
    except Exception:
        cur_val = 0.5
    if is_correct:
        # increase by 0.15 up to 1.0
        new_val = min(1.0, cur_val + 0.15)
    else:
        # decrease by 0.2 down to 0.05
        new_val = max(0.05, cur_val - 0.2)

    assessment.difficulty_level = difficulty_label_from_value(new_val)

    # Possibly mark assessment complete
    if assessment.questions_answered >= TOTAL_QUESTIONS_PER_ASSESSMENT:
        assessment.status = ASSESSMENT_STATUS_COMPLETED
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
def get_assessment(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.post("/{assessment_id}/completed", response_model=AssessmentReportResponse)
def complete_assessment(assessment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status != ASSESSMENT_STATUS_COMPLETED:
        raise HTTPException(status_code=400, detail="Assessment is not marked as completed yet")

    student_name = assessment.student.user.full_name
    grade_level = assessment.grade_level

    return get_or_create_assessment_report(db, assessment_id, student_name, grade_level)

@router.get("/{assessment_id}/report", response_model=AssessmentReportResponse)
def get_assessment_report(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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


