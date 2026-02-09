from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.crud.badge import get_all_badges, create_badge
from app.schemas.badge import BadgeResponse, BadgeCreate
from app.models.user import User as UserModel
from app.core.deps import get_current_active_user, get_current_admin_user

router = APIRouter()


@router.get("/", response_model=List[BadgeResponse])
def get_all_badges(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    """
    Retrieve all active badges.
    """
    return get_all_badges(db)

@router.post("/", response_model=BadgeResponse)
def create_new_badge(
    badge: BadgeCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Create a new badge (admin only)"""
    return create_badge(db, badge)
