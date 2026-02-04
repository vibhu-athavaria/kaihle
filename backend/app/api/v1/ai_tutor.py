from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.services.ai_tutor import ai_tutor_service
from app.crud.ai_tutor import (
    create_tutor_session, get_active_session_by_student, create_tutor_interaction,
    update_interaction_feedback
)
from app.crud.student import get_student_by_parent_and_id, get_student
from app.schemas.ai_tutor import (
    RecommendationRequest, RecommendationResponse, ChatMessage, ChatResponse, TutorSessionCreate
)
from app.models.user import User as UserModel

router = APIRouter()

@router.post("/recommendations", response_model=RecommendationResponse)
def get_personalized_recommendations(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get personalized learning recommendations for a student"""

    # Verify access permissions
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, request.student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        student = get_student(db, request.student_id)
        if not student or student.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to get recommendations for this student"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Create or get existing recommendation session
    session = get_active_session_by_student(db, request.student_id, "recommendation")
    if not session:
        session_data = TutorSessionCreate(
            student_id=request.student_id,
            session_type="recommendation"
        )
        session = create_tutor_session(db, session_data)

    # Get recommendations from AI service
    recommendations = ai_tutor_service.get_personalized_recommendations(
        db=db,
        student_id=request.student_id,
        subject=request.subject,
        difficulty_preference=request.difficulty_preference,
        learning_goals=request.learning_goals
    )

    return recommendations

@router.post("/chat", response_model=ChatResponse)
def chat_with_tutor(
    message: ChatMessage,
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Chat with the AI tutor"""

    # Verify access permissions
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        student = get_student(db, student_id)
        if not student or student.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to chat for this student"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Create or get existing chat session
    session = get_active_session_by_student(db, student_id, "chat")
    if not session:
        session_data = TutorSessionCreate(
            student_id=student_id,
            session_type="chat"
        )
        session = create_tutor_session(db, session_data)

    # Generate AI response
    ai_response = ai_tutor_service.generate_chat_response(
        message=message.message,
        context=message.context,
        student_id=student_id
    )

    # Store the interaction
    from app.schemas.ai_tutor import TutorInteractionCreate
    interaction_data = TutorInteractionCreate(
        session_id=session.id,
        user_message=message.message,
        context_data=message.context
    )
    create_tutor_interaction(db, interaction_data, ai_response)

    return ChatResponse(
        response=ai_response,
        session_id=session.id,
        suggestions=["Ask me about any topic you're studying!", "Need help with a specific question?"]
    )

@router.post("/feedback/{interaction_id}")
def provide_feedback(
    interaction_id: UUID,
    feedback_score: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Provide feedback on an AI tutor interaction"""

    if feedback_score < 1 or feedback_score > 5:
        raise HTTPException(
            status_code=400,
            detail="Feedback score must be between 1 and 5"
        )

    interaction = update_interaction_feedback(db, interaction_id, feedback_score)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    return {"message": "Feedback recorded successfully"}
