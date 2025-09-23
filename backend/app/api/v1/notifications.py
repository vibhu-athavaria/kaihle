from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.community import (
    get_user_notifications, get_unread_notifications, mark_notification_read,
    mark_notifications_read, mark_all_notifications_read, get_notification_count
)
from app.schemas.community import Notification, MarkNotificationsRead
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[Notification])
def get_notifications(
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get notifications for the current user"""
    if unread_only:
        return get_unread_notifications(db, current_user.id)
    else:
        return get_user_notifications(db, current_user.id, skip=skip, limit=limit)

@router.get("/count")
def get_notification_count_endpoint(
    unread_only: bool = True,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get notification count for the current user"""
    count = get_notification_count(db, current_user.id, unread_only=unread_only)
    return {"count": count}

@router.post("/mark-read/{notification_id}")
def mark_notification_read_endpoint(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark a specific notification as read"""
    notification = mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read"}

@router.post("/mark-read")
def mark_notifications_read_endpoint(
    request: MarkNotificationsRead,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark multiple notifications as read"""
    updated_count = mark_notifications_read(db, request.notification_ids, current_user.id)
    return {"message": f"{updated_count} notifications marked as read"}

@router.post("/mark-all-read")
def mark_all_notifications_read_endpoint(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark all notifications as read for the current user"""
    updated_count = mark_all_notifications_read(db, current_user.id)
    return {"message": f"{updated_count} notifications marked as read"}
