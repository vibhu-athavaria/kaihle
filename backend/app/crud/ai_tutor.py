from sqlalchemy.orm import Session
from app.models.ai_tutor import TutorSession, TutorInteraction, StudentAnswer
from app.schemas.ai_tutor import TutorSessionCreate, TutorInteractionCreate, AnswerSubmission
from typing import Optional, List

def create_tutor_session(db: Session, session: TutorSessionCreate) -> TutorSession:
    db_session = TutorSession(**session.dict())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_tutor_session(db: Session, session_id: int) -> Optional[TutorSession]:
    return db.query(TutorSession).filter(TutorSession.id == session_id).first()

def get_active_session_by_student(db: Session, student_id: int, session_type: str) -> Optional[TutorSession]:
    return db.query(TutorSession).filter(
        TutorSession.student_id == student_id,
        TutorSession.session_type == session_type,
        TutorSession.is_active == True
    ).first()

def create_tutor_interaction(db: Session, interaction: TutorInteractionCreate, ai_response: str) -> TutorInteraction:
    db_interaction = TutorInteraction(
        **interaction.dict(),
        ai_response=ai_response
    )
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

def get_session_interactions(db: Session, session_id: int) -> List[TutorInteraction]:
    return db.query(TutorInteraction).filter(
        TutorInteraction.session_id == session_id
    ).order_by(TutorInteraction.created_at).all()

def create_student_answer(db: Session, answer_data: AnswerSubmission, evaluation: dict) -> StudentAnswer:
    db_answer = StudentAnswer(
        student_id=answer_data.student_id,
        lesson_id=answer_data.lesson_id,
        question=answer_data.question,
        student_answer=answer_data.student_answer,
        correct_answer=answer_data.correct_answer,
        ai_evaluation=evaluation.get("feedback", ""),
        score=evaluation.get("score"),
        feedback=evaluation.get("feedback", "")
    )
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer

def get_student_answers(db: Session, student_id: int, lesson_id: Optional[int] = None) -> List[StudentAnswer]:
    query = db.query(StudentAnswer).filter(StudentAnswer.student_id == student_id)
    if lesson_id:
        query = query.filter(StudentAnswer.lesson_id == lesson_id)
    return query.order_by(StudentAnswer.created_at.desc()).all()

def update_interaction_feedback(db: Session, interaction_id: int, feedback_score: int) -> Optional[TutorInteraction]:
    interaction = db.query(TutorInteraction).filter(TutorInteraction.id == interaction_id).first()
    if interaction:
        interaction.feedback_score = feedback_score
        db.commit()
        db.refresh(interaction)
    return interaction
