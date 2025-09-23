from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.community import Post, Comment, Notification
from app.schemas.community import PostCreate, PostUpdate, CommentCreate, CommentUpdate, NotificationCreate
from typing import Optional, List

# Post CRUD operations
def get_post(db: Session, post_id: int) -> Optional[Post]:
    return db.query(Post).filter(Post.id == post_id, Post.is_active == True).first()

def get_posts(db: Session, skip: int = 0, limit: int = 20) -> List[Post]:
    return db.query(Post).filter(Post.is_active == True).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> List[Post]:
    return db.query(Post).filter(
        Post.user_id == user_id, 
        Post.is_active == True
    ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()

def create_post(db: Session, post: PostCreate, user_id: int) -> Post:
    db_post = Post(**post.dict(), user_id=user_id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def update_post(db: Session, post_id: int, post_update: PostUpdate, user_id: int) -> Optional[Post]:
    db_post = db.query(Post).filter(Post.id == post_id, Post.user_id == user_id).first()
    if not db_post:
        return None
    
    update_data = post_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_post, field, value)
    
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int, user_id: int) -> bool:
    db_post = db.query(Post).filter(Post.id == post_id, Post.user_id == user_id).first()
    if not db_post:
        return False
    
    # Soft delete
    db_post.is_active = False
    db.commit()
    return True

# Comment CRUD operations
def get_comment(db: Session, comment_id: int) -> Optional[Comment]:
    return db.query(Comment).filter(Comment.id == comment_id, Comment.is_active == True).first()

def get_comments_by_post(db: Session, post_id: int) -> List[Comment]:
    return db.query(Comment).filter(
        Comment.post_id == post_id, 
        Comment.is_active == True
    ).order_by(Comment.created_at).all()

def create_comment(db: Session, comment: CommentCreate, user_id: int) -> Comment:
    db_comment = Comment(**comment.dict(), user_id=user_id)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def update_comment(db: Session, comment_id: int, comment_update: CommentUpdate, user_id: int) -> Optional[Comment]:
    db_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user_id).first()
    if not db_comment:
        return None
    
    update_data = comment_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_comment, field, value)
    
    db.commit()
    db.refresh(db_comment)
    return db_comment

def delete_comment(db: Session, comment_id: int, user_id: int) -> bool:
    db_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user_id).first()
    if not db_comment:
        return False
    
    # Soft delete
    db_comment.is_active = False
    db.commit()
    return True

# Notification CRUD operations
def create_notification(db: Session, notification: NotificationCreate) -> Notification:
    db_notification = Notification(**notification.dict())
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

def get_user_notifications(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[Notification]:
    return db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()

def get_unread_notifications(db: Session, user_id: int) -> List[Notification]:
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).order_by(desc(Notification.created_at)).all()

def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    
    if notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    
    return notification

def mark_notifications_read(db: Session, notification_ids: List[int], user_id: int) -> int:
    updated_count = db.query(Notification).filter(
        Notification.id.in_(notification_ids),
        Notification.user_id == user_id
    ).update({"is_read": True}, synchronize_session=False)
    
    db.commit()
    return updated_count

def mark_all_notifications_read(db: Session, user_id: int) -> int:
    updated_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).update({"is_read": True}, synchronize_session=False)
    
    db.commit()
    return updated_count

def get_notification_count(db: Session, user_id: int, unread_only: bool = False) -> int:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.count()

# Helper function to create system notifications
def create_system_notification(db: Session, user_id: int, title: str, message: str) -> Notification:
    notification_data = NotificationCreate(
        user_id=user_id,
        title=title,
        message=message
    )
    return create_notification(db, notification_data)
