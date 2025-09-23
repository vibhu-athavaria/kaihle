from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.community import (
    get_post, get_posts, get_posts_by_user, create_post, update_post, delete_post,
    get_comments_by_post, create_comment, update_comment, delete_comment,
    create_system_notification
)
from app.schemas.community import Post, PostCreate, PostUpdate, Comment, CommentCreate, CommentUpdate
from app.models.user import User as UserModel

router = APIRouter()

# Post endpoints
@router.get("/posts", response_model=List[Post])
def read_posts(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all community posts"""
    posts = get_posts(db, skip=skip, limit=limit)
    
    # Add author information to each post
    for post in posts:
        post.author = {
            "id": post.author.id,
            "username": post.author.username,
            "full_name": post.author.full_name,
            "role": post.author.role
        }
        
        # Add author info to comments
        for comment in post.comments:
            comment.author = {
                "id": comment.author.id,
                "username": comment.author.username,
                "full_name": comment.author.full_name,
                "role": comment.author.role
            }
    
    return posts

@router.get("/posts/{post_id}", response_model=Post)
def read_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get a specific post with comments"""
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Add author information
    post.author = {
        "id": post.author.id,
        "username": post.author.username,
        "full_name": post.author.full_name,
        "role": post.author.role
    }
    
    # Get comments for the post
    comments = get_comments_by_post(db, post_id)
    for comment in comments:
        comment.author = {
            "id": comment.author.id,
            "username": comment.author.username,
            "full_name": comment.author.full_name,
            "role": comment.author.role
        }
    
    post.comments = comments
    return post

@router.post("/posts", response_model=Post)
def create_new_post(
    post: PostCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new community post"""
    created_post = create_post(db, post, current_user.id)
    
    # Add author information
    created_post.author = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role
    }
    
    return created_post

@router.put("/posts/{post_id}", response_model=Post)
def update_post_endpoint(
    post_id: int,
    post_update: PostUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update a post (only by the author)"""
    updated_post = update_post(db, post_id, post_update, current_user.id)
    if not updated_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or not authorized to update"
        )
    
    # Add author information
    updated_post.author = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role
    }
    
    return updated_post

@router.delete("/posts/{post_id}")
def delete_post_endpoint(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Delete a post (only by the author or admin)"""
    # Allow admins to delete any post
    if current_user.role == "admin":
        post = get_post(db, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        post.is_active = False
        db.commit()
        success = True
    else:
        success = delete_post(db, post_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or not authorized to delete"
        )
    
    return {"message": "Post deleted successfully"}

@router.get("/users/{user_id}/posts", response_model=List[Post])
def read_user_posts(
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get posts by a specific user"""
    posts = get_posts_by_user(db, user_id, skip=skip, limit=limit)
    
    # Add author information to each post
    for post in posts:
        post.author = {
            "id": post.author.id,
            "username": post.author.username,
            "full_name": post.author.full_name,
            "role": post.author.role
        }
    
    return posts

# Comment endpoints
@router.post("/comments", response_model=Comment)
def create_new_comment(
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new comment on a post"""
    # Verify the post exists
    post = get_post(db, comment.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    created_comment = create_comment(db, comment, current_user.id)
    
    # Add author information
    created_comment.author = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role
    }
    
    # Create notification for post author (if not commenting on own post)
    if post.user_id != current_user.id:
        create_system_notification(
            db=db,
            user_id=post.user_id,
            title="New Comment",
            message=f"{current_user.full_name} commented on your post: {post.title}"
        )
    
    return created_comment

@router.put("/comments/{comment_id}", response_model=Comment)
def update_comment_endpoint(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update a comment (only by the author)"""
    updated_comment = update_comment(db, comment_id, comment_update, current_user.id)
    if not updated_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or not authorized to update"
        )
    
    # Add author information
    updated_comment.author = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role
    }
    
    return updated_comment

@router.delete("/comments/{comment_id}")
def delete_comment_endpoint(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Delete a comment (only by the author or admin)"""
    # Allow admins to delete any comment
    if current_user.role == "admin":
        from app.crud.community import get_comment
        comment = get_comment(db, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        comment.is_active = False
        db.commit()
        success = True
    else:
        success = delete_comment(db, comment_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or not authorized to delete"
        )
    
    return {"message": "Comment deleted successfully"}
