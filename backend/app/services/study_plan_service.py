# app/services/study_plan_service.py
from sqlalchemy.orm import Session
from app import models
from app.services.llm_service import LLMService
from typing import Dict, Any, List, Optional

llm = LLMService()

def persist_study_plan_from_llm(db: Session, assessment: models.Assessment, mastery_map: Dict[str, float], top_n: int = 5) -> models.StudyPlan:
    """
    Ask LLM to generate a study plan from mastery_map and persist it into DB.
    Returns created StudyPlan instance with lessons.
    """
    plan_payload = llm.generate_study_plan(mastery_map, assessment.subject, assessment.grade_level, top_n=top_n)
    # expected structure: {"summary": str, "lessons": [ {title, topic, suggested_duration_mins, week, details} ]}
    sp = models.StudyPlan(
        assessment_id = assessment.id,
        student_id = assessment.student_id,
        title = plan_payload.get("title") or f"Study Plan: {assessment.subject}",
        summary = plan_payload.get("summary"),
        metadata = plan_payload
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)

    lessons = plan_payload.get("lessons", [])
    for l in lessons:
        # try to match knowledge_area by subject/topic/grade (if topic present)
        ka_id = None
        topic = l.get("topic")
        if topic:
            ka = db.query(models.QuestionBank).filter_by(subject=assessment.subject, topic=topic, grade_level=assessment.grade_level).first()
            if ka:
                ka_id = ka.id
        spl = models.StudyPlanLesson(
            study_plan_id = sp.id,
            title = l.get("title") or (f"Practice {topic}" if topic else "Practice"),
            knowledge_area_id = ka_id,
            suggested_duration_mins = l.get("suggested_duration_mins"),
            week = l.get("week"),
            details = l.get("details")
        )
        db.add(spl)
    db.commit()
    db.refresh(sp)
    return sp

def create_manual_study_plan(db: Session, payload: Dict[str, Any]) -> models.StudyPlan:
    """
    Create a study plan from explicit payload (used by teachers/parents).
    payload shape matches StudyPlanCreate pydantic model.
    """
    sp = models.StudyPlan(
        assessment_id = payload.get("assessment_id"),
        student_id = payload["student_id"],
        title = payload.get("title", "Personalized Study Plan"),
        summary = payload.get("summary"),
        metadata = payload.get("metadata"),
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)

    lessons = payload.get("lessons", []) or []
    for l in lessons:
        spl = models.StudyPlanLesson(
            study_plan_id=sp.id,
            title=l.get("title"),
            knowledge_area_id=l.get("knowledge_area_id"),
            suggested_duration_mins=l.get("suggested_duration_mins"),
            week=l.get("week"),
            details=l.get("details")
        )
        db.add(spl)
    db.commit()
    db.refresh(sp)
    return sp
