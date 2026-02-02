from sqlalchemy.orm import Session
from app.models.ai_tutor import TutorSession, TutorInteraction
from app.schemas.ai_tutor import TutorSessionCreate, TutorInteractionCreate
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


def update_interaction_feedback(db: Session, interaction_id: int, feedback_score: int) -> Optional[TutorInteraction]:
    interaction = db.query(TutorInteraction).filter(TutorInteraction.id == interaction_id).first()
    if interaction:
        interaction.feedback_score = feedback_score
        db.commit()
        db.refresh(interaction)
    return interaction
