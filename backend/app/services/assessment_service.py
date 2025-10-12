# app/services/assessment_service.py
from sqlalchemy.orm import Session
from app.models.assessment import Assessment, AssessmentQuestion, KnowledgeArea, StudentKnowledgeProfile
from app.services.llm_service import LLMService
from datetime import datetime
import math, random

llm = LLMService()


# helper to get or create KnowledgeArea (normalized match)
def get_or_create_knowledge_area(db: Session, subject: str, topic: str, subtopic: str, grade_level: str) -> KnowledgeArea:
    q = db.query(KnowledgeArea).filter(
        KnowledgeArea.subject == subject,
        KnowledgeArea.topic == topic,
        KnowledgeArea.subtopic == subtopic,
        KnowledgeArea.grade_level == grade_level
    ).first()
    if q:
        return q
    ka = KnowledgeArea(subject=subject, topic=topic or "General", subtopic=subtopic, grade_level=grade_level)
    db.add(ka)
    db.commit()
    db.refresh(ka)
    return ka

# basic expected probability (sigmoid)
def expected_prob(skill: float, difficulty: float) -> float:
    return 1.0 / (1.0 + math.exp(-8.0 * (skill - difficulty)))

def update_mastery(skill: float, difficulty: float, correct: bool, alpha: float = 0.12) -> float:
    exp = expected_prob(skill, difficulty)
    lr = alpha * (1.0 - skill)
    delta = lr * ((1.0 if correct else 0.0) - exp)
    new_skill = max(0.0, min(1.0, skill + delta))
    return new_skill

# Difficulty mapping helpers
def difficulty_float_from_label(label: str) -> float:
    if not label: return 0.5
    label = label.lower()
    if label == "easy": return 0.25
    if label == "medium": return 0.5
    if label == "hard": return 0.8
    try:
        return float(label)
    except:
        return 0.5

def pick_next_topic_and_difficulty(db: Session, student_id: int, subject: str):
    # get student's knowledge profiles for subject
    skps = db.query(StudentKnowledgeProfile).join(KnowledgeArea).filter(
        StudentKnowledgeProfile.student_id == student_id,
        KnowledgeArea.subject == subject
    ).all()
    if skps:
        # choose the knowledge area with lowest mastery
        skps_sorted = sorted(skps, key=lambda s: s.mastery_level)
        target = skps_sorted[0].knowledge_area
        # propose difficulty based on mastery (lower mastery -> easier)
        difficulty = max(0.2, 1.0 - skps_sorted[0].mastery_level)
        return {"topic": target.topic, "subtopic": target.subtopic, "difficulty": difficulty}
    # fallback default
    return {"topic": None, "subtopic": None, "difficulty": 0.5}

async def create_question(db: Session, assessment: Assessment, topic: str, subtopic: str, difficulty: float, order: int) -> AssessmentQuestion:
    payload = await llm.generate_question(assessment.subject, assessment.grade_level, topic, difficulty)
    # Normalize and ensure required fields
    q_topic = payload.get("topic") or topic or "General"
    q_subtopic = payload.get("subtopic")
    diff_label = payload.get("difficulty_level") or ("easy" if difficulty < 0.4 else ("medium" if difficulty < 0.75 else "hard"))
    # get/create knowledge area
    ka = get_or_create_knowledge_area(db, assessment.subject, q_topic, q_subtopic, assessment.grade_level)
    aq = AssessmentQuestion(
        assessment_id = assessment.id,
        knowledge_area_id = ka.id,
        question_number = order,
        difficulty_level = diff_label,
        question_text = payload["question_text"],
        question_type = payload.get("question_type", "multiple_choice"),
        options = payload.get("options"),
        correct_answer = payload.get("correct_answer")
    )
    db.add(aq)
    db.commit()
    db.refresh(aq)
    return aq

def choose_grade_by_age(student_age:int) -> int:
    # simple mapping (tweak to match your locale)
    if student_age <= 5: return 0
    if student_age <= 6: return 1
    if student_age <= 7: return 2
    if student_age <= 8: return 3
    if student_age <= 9: return 4
    if student_age <= 10: return 5
    if student_age <= 11: return 6
    if student_age <= 12: return 7
    if student_age <= 13: return 8
    if student_age <= 14: return 9
    if student_age <= 15: return 10
    if student_age <= 16: return 11
    return 12
