"""
Assessment Report Generation Celery Task.

This task generates AssessmentReport records after all 4 diagnostic assessments
are complete. It computes mastery levels, identifies knowledge gaps and strengths,
and updates StudentKnowledgeProfile records.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import celery_app
from app.core.config import settings
from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentReport,
    AssessmentStatus,
    AssessmentType,
    QuestionBank,
    StudentKnowledgeProfile,
)
from app.models.curriculum import Subtopic, Topic

logger = logging.getLogger(__name__)


# =============================================================================
# Mastery Calculation Functions
# =============================================================================

def get_mastery_label(mastery_level: float) -> str:
    """
    Convert mastery level (0.0-1.0) to a label.

    | Range | Label |
    |-------|-------|
    | 0.00 – 0.39 | beginning |
    | 0.40 – 0.59 | developing |
    | 0.60 – 0.74 | approaching |
    | 0.75 – 0.89 | strong |
    | 0.90 – 1.00 | mastery |
    """
    if mastery_level < 0.40:
        return "beginning"
    elif mastery_level < 0.60:
        return "developing"
    elif mastery_level < 0.75:
        return "approaching"
    elif mastery_level < 0.90:
        return "strong"
    else:
        return "mastery"


def get_gap_priority(mastery_level: float) -> Optional[str]:
    """
    Get knowledge gap priority based on mastery level.

    | Mastery | Priority |
    |---------|----------|
    | < 0.40 | high |
    | 0.40 – 0.59 | medium |
    | 0.60 – 0.74 | low |
    | ≥ 0.75 | (strength, not a gap) |
    """
    if mastery_level < 0.40:
        return "high"
    elif mastery_level < 0.60:
        return "medium"
    elif mastery_level < 0.75:
        return "low"
    else:
        return None  # Not a gap, it's a strength


def calculate_subtopic_mastery(
    questions: List[Dict[str, Any]]
) -> tuple[float, List[int], List[bool], int, int]:
    """
    Calculate mastery level for a subtopic.

    mastery_level = actual_score / max_possible
    where:
        max_possible = Σ (difficulty_level / 5.0) for all questions
        actual_score = Σ score for all questions

    Returns:
        tuple: (mastery_level, difficulty_path, correct_path, correct_count, total_count)
    """
    if not questions:
        return 0.0, [], [], 0, 0

    max_possible = 0.0
    actual_score = 0.0
    difficulty_path = []
    correct_path = []
    correct_count = 0

    for q in questions:
        difficulty = q.get("difficulty_level", 3)
        score = q.get("score", 0.0)
        is_correct = q.get("is_correct", False)

        max_possible += difficulty / 5.0
        actual_score += score
        difficulty_path.append(difficulty)
        correct_path.append(is_correct)

        if is_correct:
            correct_count += 1

    if max_possible == 0:
        mastery_level = 0.0
    else:
        mastery_level = actual_score / max_possible

    return mastery_level, difficulty_path, correct_path, correct_count, len(questions)


# =============================================================================
# Report Generation Task
# =============================================================================

@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.generate_assessment_reports"
)
def generate_assessment_reports(self, student_id: str) -> str:
    """
    Generate AssessmentReport records for all 4 diagnostic assessments.

    For each of the 4 subject assessments:
      1. Load AssessmentQuestion rows with QuestionBank joins
      2. Group by subtopic → compute mastery_level
      3. Rollup to topic level
      4. Classify knowledge_gaps and strengths
      5. Build recommendations (ordered by gap priority)
      6. Build diagnostic_summary
      7. Upsert AssessmentReport
      8. Upsert StudentKnowledgeProfile (subtopic + topic level)

    Args:
        student_id: UUID string of the student

    Returns:
        student_id (for task chain)

    Updates Redis flag: kaihle:diagnostic:generating:{student_id} = "study_plan"
    """
    logger.info("Starting report generation for student %s", student_id)

    try:
        # Create database session
        database_url = settings.DATABASE_URL
        # Convert async URL to sync URL for Celery
        sync_url = database_url.replace("+asyncpg", "+psycopg2")
        engine = create_engine(sync_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            student_uuid = UUID(student_id)

            # Get all completed diagnostic assessments for this student
            assessments = db.query(Assessment).filter(
                Assessment.student_id == student_uuid,
                Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                Assessment.status == AssessmentStatus.COMPLETED,
            ).all()

            if not assessments:
                logger.warning(
                    "No completed diagnostic assessments found for student %s",
                    student_id
                )
                return student_id

            # Process each assessment
            for assessment in assessments:
                _generate_single_report(db, assessment)

            db.commit()
            logger.info(
                "Successfully generated reports for student %s",
                student_id
            )

            # Update Redis flag for next phase
            _update_redis_flag(student_id, "study_plan")

            return student_id

        finally:
            db.close()

    except SQLAlchemyError as e:
        logger.error(
            "Database error during report generation for student %s: %s",
            student_id, str(e)
        )
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error(
            "Error during report generation for student %s: %s",
            student_id, str(e)
        )
        raise self.retry(exc=e, countdown=60)


def _generate_single_report(db: Session, assessment: Assessment) -> None:
    """
    Generate a single AssessmentReport for one assessment.
    """
    # Load all answered questions with QuestionBank joins
    answered_questions = (
        db.query(AssessmentQuestion, QuestionBank)
        .join(QuestionBank, AssessmentQuestion.question_bank_id == QuestionBank.id)
        .filter(AssessmentQuestion.assessment_id == assessment.id)
        .filter(AssessmentQuestion.is_correct.isnot(None))
        .order_by(AssessmentQuestion.question_number)
        .all()
    )

    if not answered_questions:
        logger.warning(
            "No answered questions found for assessment %s",
            assessment.id
        )
        return

    # Group questions by subtopic
    subtopic_questions: Dict[UUID, List[Dict]] = {}
    subtopic_info: Dict[UUID, Dict] = {}  # Store subtopic name, topic info

    for aq, qb in answered_questions:
        if qb.subtopic_id:
            if qb.subtopic_id not in subtopic_questions:
                subtopic_questions[qb.subtopic_id] = []
            subtopic_questions[qb.subtopic_id].append({
                "question_id": qb.id,
                "difficulty_level": qb.difficulty_level,
                "score": aq.score or 0.0,
                "is_correct": aq.is_correct,
                "topic_id": qb.topic_id,
            })

            # Get subtopic info from database if not cached
            if qb.subtopic_id not in subtopic_info:
                subtopic = db.query(Subtopic).filter(
                    Subtopic.id == qb.subtopic_id
                ).first()
                if subtopic:
                    topic = db.query(Topic).filter(
                        Topic.id == subtopic.topic_id
                    ).first() if subtopic.topic_id else None
                    subtopic_info[qb.subtopic_id] = {
                        "subtopic_name": subtopic.name,
                        "topic_id": subtopic.topic_id,
                        "topic_name": topic.name if topic else "Unknown",
                    }

    # Calculate mastery per subtopic
    subtopic_results = []
    topic_aggregates: Dict[UUID, Dict] = {}

    for subtopic_id, questions in subtopic_questions.items():
        mastery_level, difficulty_path, correct_path, correct_count, total_count = \
            calculate_subtopic_mastery(questions)

        info = subtopic_info.get(subtopic_id, {})
        topic_id = info.get("topic_id")

        result = {
            "subtopic_id": str(subtopic_id),
            "subtopic_name": info.get("subtopic_name", "Unknown"),
            "topic_id": str(topic_id) if topic_id else None,
            "topic_name": info.get("topic_name", "Unknown"),
            "mastery_level": round(mastery_level, 2),
            "mastery_label": get_mastery_label(mastery_level),
            "questions_attempted": total_count,
            "questions_correct": correct_count,
            "difficulty_path": difficulty_path,
            "correct_path": correct_path,
        }
        subtopic_results.append(result)

        # Aggregate to topic level
        if topic_id:
            if topic_id not in topic_aggregates:
                topic_aggregates[topic_id] = {
                    "topic_id": str(topic_id),
                    "topic_name": info.get("topic_name", "Unknown"),
                    "mastery_levels": [],
                    "questions_attempted": 0,
                    "questions_correct": 0,
                    "subtopics": [],
                }
            topic_aggregates[topic_id]["mastery_levels"].append(mastery_level)
            topic_aggregates[topic_id]["questions_attempted"] += total_count
            topic_aggregates[topic_id]["questions_correct"] += correct_count
            topic_aggregates[topic_id]["subtopics"].append(result)

    # Calculate topic mastery (mean of subtopic mastery)
    topic_results = []
    for topic_id, data in topic_aggregates.items():
        if data["mastery_levels"]:
            topic_mastery = sum(data["mastery_levels"]) / len(data["mastery_levels"])
        else:
            topic_mastery = 0.0

        topic_result = {
            "topic_id": data["topic_id"],
            "topic_name": data["topic_name"],
            "mastery_level": round(topic_mastery, 2),
            "mastery_label": get_mastery_label(topic_mastery),
            "questions_attempted": data["questions_attempted"],
            "questions_correct": data["questions_correct"],
            "subtopics": data["subtopics"],
        }
        topic_results.append(topic_result)

    # Classify knowledge gaps and strengths
    knowledge_gaps = []
    strengths = []

    for result in subtopic_results:
        mastery = result["mastery_level"]
        priority = get_gap_priority(mastery)

        if priority:
            knowledge_gaps.append({
                "subtopic_id": result["subtopic_id"],
                "subtopic_name": result["subtopic_name"],
                "topic_name": result["topic_name"],
                "mastery_level": result["mastery_level"],
                "mastery_label": result["mastery_label"],
                "priority": priority,
                "difficulty_reached": max(result["difficulty_path"]) if result["difficulty_path"] else 1,
                "correct_count": result["questions_correct"],
                "total_count": result["questions_attempted"],
            })
        elif mastery >= 0.75:
            strengths.append({
                "subtopic_id": result["subtopic_id"],
                "subtopic_name": result["subtopic_name"],
                "topic_name": result["topic_name"],
                "mastery_level": result["mastery_level"],
                "mastery_label": result["mastery_label"],
            })

    # Sort gaps by priority (high first) then by mastery level (lowest first)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    knowledge_gaps.sort(
        key=lambda x: (priority_order.get(x["priority"], 3), x["mastery_level"])
    )

    # Sort strengths by mastery level (highest first) for strongest_subtopic selection
    strengths.sort(key=lambda x: x["mastery_level"], reverse=True)

    # Build recommendations (ordered by gap priority)
    recommendations = []
    for gap in knowledge_gaps:
        recommendations.append({
            "subtopic_id": gap["subtopic_id"],
            "subtopic_name": gap["subtopic_name"],
            "priority": gap["priority"],
            "action": f"Focus on {gap['subtopic_name']} - current mastery: {gap['mastery_label']}",
        })

    # Build diagnostic summary
    total_questions = len(answered_questions)
    total_correct = sum(1 for aq, _ in answered_questions if aq.is_correct)
    all_difficulties = [qb.difficulty_level for _, qb in answered_questions]

    overall_mastery = sum(r["mastery_level"] for r in subtopic_results) / len(subtopic_results) if subtopic_results else 0.0

    diagnostic_summary = {
        "overall_mastery": round(overall_mastery, 2),
        "mastery_label": get_mastery_label(overall_mastery),
        "total_questions": total_questions,
        "total_correct": total_correct,
        "highest_difficulty_reached": max(all_difficulties) if all_difficulties else 1,
        "average_difficulty_reached": round(
            sum(all_difficulties) / len(all_difficulties), 1
        ) if all_difficulties else 1,
        "strongest_subtopic": strengths[0]["subtopic_name"] if strengths else None,
        "weakest_subtopic": knowledge_gaps[0]["subtopic_name"] if knowledge_gaps else None,
        "completion_time_minutes": None,  # Would need to track start/end times
    }

    # Build topic breakdown
    topic_breakdown = {"topics": topic_results}

    # Upsert AssessmentReport
    existing_report = db.query(AssessmentReport).filter(
        AssessmentReport.assessment_id == assessment.id
    ).first()

    if existing_report:
        report = existing_report
    else:
        report = AssessmentReport(assessment_id=assessment.id)
        db.add(report)

    report.diagnostic_summary = diagnostic_summary
    report.knowledge_gaps = knowledge_gaps
    report.strengths = strengths
    report.recommendations = recommendations
    report.topic_breakdown = topic_breakdown

    # Upsert StudentKnowledgeProfile for each subtopic
    for result in subtopic_results:
        subtopic_uuid = UUID(result["subtopic_id"])
        topic_uuid = UUID(result["topic_id"]) if result["topic_id"] else None

        # Check for existing profile
        existing_profile = db.query(StudentKnowledgeProfile).filter(
            StudentKnowledgeProfile.student_id == assessment.student_id,
            StudentKnowledgeProfile.subject_id == assessment.subject_id,
            StudentKnowledgeProfile.subtopic_id == subtopic_uuid,
        ).first()

        if existing_profile:
            profile = existing_profile
            profile.mastery_level = result["mastery_level"]
            profile.assessment_count += 1
            profile.total_questions_attempted += result["questions_attempted"]
            profile.total_questions_correct += result["questions_correct"]
        else:
            profile = StudentKnowledgeProfile(
                student_id=assessment.student_id,
                subject_id=assessment.subject_id,
                topic_id=topic_uuid,
                subtopic_id=subtopic_uuid,
                mastery_level=result["mastery_level"],
                assessment_count=1,
                total_questions_attempted=result["questions_attempted"],
                total_questions_correct=result["questions_correct"],
            )
            db.add(profile)

        # Set needs_review flag
        profile.needs_review = result["mastery_level"] < 0.60
        profile.last_assessed = datetime.now(timezone.utc)

    logger.info(
        "Generated report for assessment %s with %d gaps, %d strengths",
        assessment.id, len(knowledge_gaps), len(strengths)
    )


def _update_redis_flag(student_id: str, status: str) -> None:
    """Update Redis generation flag."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(redis_url)

    key = f"kaihle:diagnostic:generating:{student_id}"
    client.setex(key, 2 * 60 * 60, status)

    logger.info("Set Redis flag '%s' for student %s", status, student_id)
