from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.crud.subject import get_all_subject
from app.schemas.subject import SubjectResponse

router = APIRouter()


@router.get("/", response_model=List[SubjectResponse])
def get_all_subjects(db: Session = Depends(get_db)):
    """
    Retrieve all active subjects.
    """
    return get_all_subject(db)