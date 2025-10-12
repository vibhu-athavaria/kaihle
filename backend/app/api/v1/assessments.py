# app/api/v1/assessments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app import models
from app.schemas import assessment as schemas
from app.services.assessment_service import (
    create_question,
    choose_grade_by_age,
    pick_next_topic_and_difficulty,
    update_mastery,
    difficulty_float_from_label,
    llm
)
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=schemas.AssessmentOut)
async def start_assessment(payload: schemas.AssessmentCreate, db: Session = Depends(get_db)):
    """
    Start or resume an assessment for student.
    - If in-progress exists -> return it and the next unanswered question inside returned AssessmentOut.questions (or provide endpoint to fetch next question).
    - Else create new assessment and create first question.
    """
    # 1) try to find existing in-progress assessment
    assessment = db.query(models.Assessment).filter(
        models.Assessment.student_id == payload.student_id,
        models.Assessment.status == "in_progress"
    ).order_by(models.Assessment.created_at.desc()).first()

    if assessment:
        # Ensure relationship is loaded (important for lazy-load models)
        _ = assessment.questions
        # load next unanswered question (if any) and attach it to return payload via relationship
        unanswered_questions = [q for q in assessment.questions if not q.answered_at]
        if unanswered_questions:
            # return existing assessment with next unanswered question
            return assessment
        elif assessment.questions_answered >= settings.MAX_QUESTIONS_PER_ASSESSMENT:
            # all questions answered but assessment not marked complete (maybe due to error)
            assessment.status = "completed"
            assessment.completed_at = datetime.now()
            # compute overall score
            answers_scores = [item.score or 0.0 for item in assessment.questions]
            assessment.overall_score = (sum(answers_scores)/len(answers_scores))*100 if answers_scores else None
            db.add(assessment)
            db.commit()
            db.refresh(assessment)
            return assessment



    # choose starting grade_level by student age if not provided
    grade_level = choose_grade_by_age(payload.student_age)

    # 2) create a new assessment
    if not assessment:
        assessment = models.Assessment(
            student_id = payload.student_id,
            subject = payload.subject,
            grade_level = grade_level,
            assessment_type = payload.assessment_type,
            difficulty_level = "medium",
            status = "in_progress",
            total_questions = 0,
            questions_answered = 0
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

    # pick initial topic/difficulty
    sel = pick_next_topic_and_difficulty(db, payload.student_id, payload.subject)
    # create first question (async)
    await create_question(db, assessment, sel.get("topic"), sel.get("subtopic"), sel.get("difficulty"), order=1)
    # update assessment counts
    assessment.total_questions = (assessment.total_questions or 0) + 1
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment

@router.get("/{assessment_id}", response_model=schemas.AssessmentOut)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).filter(models.Assessment.id==assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment

@router.post("/{assessment_id}/questions/{question_id}/answer", response_model=schemas.AnswerOut)
async def submit_answer(assessment_id: int, question_id: int, payload: schemas.AnswerSubmit, db: Session = Depends(get_db)):
    question = db.query(models.AssessmentQuestion).filter(
        models.AssessmentQuestion.id==question_id,
        models.AssessmentQuestion.assessment_id==assessment_id
        ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    assessment = question.assessment
    if not assessment or assessment.id != assessment_id:
        raise HTTPException(status_code=400, detail="Mismatched assessment for question")

    correct = question.correct_answer.strip().lower() == payload.answer_text.strip().lower()
    question.student_answer = payload.answer_text.strip().lower()
    question.is_correct = correct
    question.score = 1.0 if correct else 0.0
    question.answered_at = datetime.now()
    question.time_taken = payload.time_taken
    db.add(question)
    db.commit()
    db.refresh(question)
    # update StudentKnowledgeProfile
    # find or create SKP
    ka = question.knowledge_area
    skp = db.query(models.StudentKnowledgeProfile).filter_by(student_id=assessment.student_id, knowledge_area_id=ka.id).first()
    if not skp:
        skp = models.StudentKnowledgeProfile(student_id=assessment.student_id, knowledge_area_id=ka.id, mastery_level=0.5, assessment_count=0)
    current_skill = skp.mastery_level or 0.5
    diff_val = difficulty_float_from_label(question.difficulty_level)
    new_skill = update_mastery(current_skill, diff_val, correct)
    skp.mastery_level = new_skill
    skp.assessment_count = (skp.assessment_count or 0) + 1
    skp.last_assessed = datetime.now()
    db.add(skp)

    # update assessment counters and maybe finish
    assessment.questions_answered = (assessment.questions_answered or 0) + 1
    assessment.total_questions = (assessment.total_questions or 0)  # set on start/created

    # generate next question unless finished
    if assessment.questions_answered >= settings.MAX_QUESTIONS_PER_ASSESSMENT:
        assessment.status = "completed"
        assessment.completed_at = datetime.now()
        # compute overall score
        answers_scores = [item.score or 0.0 for item in assessment.questions]
        assessment.overall_score = (sum(answers_scores)/len(answers_scores))*100 if answers_scores else None
        db.add(assessment)
        db.commit()
        return {"question_id": question.id, "is_correct": question.is_correct, "score": question.score, "feedback": question.ai_feedback, "next_question": None}
    # else create next
    sel = pick_next_topic_and_difficulty(db, assessment.student_id, assessment.subject)
    order = (question.question_number or 1) + 1
    next_q = await create_question(db, assessment, sel.get("topic"), sel.get("subtopic"), sel.get("difficulty"), order=order)
    assessment.total_questions = (assessment.total_questions or 0) + 1
    db.add(assessment)
    db.commit()
    # return answer + next question
    return {
        "question_id": question.id,
        "is_correct": correct,
        "score": question.score,
        "feedback": question.ai_feedback,
        "next_question": next_q
    }

@router.post("/{assessment_id}/complete", response_model=schemas.AssessmentOut)
def complete_assessment(assessment_id: int, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).filter(models.Assessment.id==assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    # Build mastery_map
    skps = db.query(models.StudentKnowledgeProfile).join(models.KnowledgeArea).filter(
        models.StudentKnowledgeProfile.student_id==assessment.student_id,
        models.KnowledgeArea.subject==assessment.subject
    ).all()
    mastery_map = {skp.knowledge_area.topic: skp.mastery_level for skp in skps}
    plan_payload = llm.generate_study_plan(mastery_map, assessment.subject, assessment.grade_level)
    assessment.recommendations = plan_payload
    assessment.status = "completed"
    assessment.completed_at = datetime.utcnow()
    db.add(assessment); db.commit(); db.refresh(assessment)
    return assessment
