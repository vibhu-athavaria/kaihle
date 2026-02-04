from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.crud.grade import get_grades
from app.schemas.grade import Grade

router = APIRouter()


@router.get("/", response_model=List[Grade])
def read_grades(db: Session = Depends(get_db)):
    """
    Retrieve all active grades.
    """
    grades = get_grades(db)
    return grades