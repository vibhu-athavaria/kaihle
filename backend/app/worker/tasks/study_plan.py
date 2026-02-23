"""
AI-Powered Study Plan Generation Celery Task.

This task generates a personalised StudyPlan asynchronously via Celery + LLM.
It runs after all 4 diagnostic assessments are complete and reports are generated.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import celery_app
from app.core.config import settings
from app.models.assessment import Assessment, AssessmentReport, AssessmentStatus
from app.models.course import Course
from app.models.study_plan import StudyPlan, StudyPlanCourse
from app.models.user import StudentProfile
from app.services.llm.provider import get_llm_provider

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def calculate_recommended_weeks(gaps: List[Dict[str, Any]]) -> int:
    """
    Calculate recommended study plan duration in weeks based on knowledge gaps.

    Formula:
        weeks = (high * 1.0) + (medium * 0.5) + (low * 0.25)
        Clamped to 4-16 weeks range.

    Args:
        gaps: List of knowledge gap dictionaries with 'priority' key

    Returns:
        int: Recommended weeks (4-16 range)
    """
    high = sum(1 for g in gaps if g.get("priority") == "high")
    medium = sum(1 for g in gaps if g.get("priority") == "medium")
    low = sum(1 for g in gaps if g.get("priority") == "low")

    weeks = (high * 1.0) + (medium * 0.5) + (low * 0.25)
    return max(4, min(round(weeks) + 1, 16))


def build_llm_prompt(
    gaps: List[Dict[str, Any]],
    strengths: List[Dict[str, Any]],
    student_profile: Dict[str, Any],
    available_courses: List[Dict[str, Any]],
    total_weeks: int,
) -> str:
    """
    Build the LLM prompt for study plan generation.

    Args:
        gaps: List of knowledge gaps from all subjects
        strengths: List of strengths from all subjects
        student_profile: Student profile data (grade, curriculum, learning style)
        available_courses: List of available courses matching gap subtopics
        total_weeks: Recommended study plan duration

    Returns:
        str: Formatted LLM prompt
    """
    prompt = f"""You are an expert Cambridge curriculum learning designer for grades 5–12.
Generate a personalised study plan as structured JSON.
Return ONLY valid JSON. No markdown, no explanation.

STUDENT PROFILE:
- Grade: {student_profile.get('grade_level', 'Unknown')}
- Curriculum: {student_profile.get('curriculum', 'Cambridge')}
- Learning Style: {student_profile.get('learning_style', 'General')}

KNOWLEDGE GAPS (prioritize these):
{json.dumps(gaps, indent=2)}

STRENGTHS (build upon these):
{json.dumps(strengths, indent=2)}

AVAILABLE COURSES:
{json.dumps(available_courses, indent=2)}

STUDY PLAN PARAMETERS:
- Total weeks: {total_weeks}
- Days per week: 5 (Monday-Friday)
- Sessions per day: 1-2

OUTPUT FORMAT (strict JSON):
{{
  "title": "Personalised Study Plan for [Student Name]",
  "summary": "Brief overview of the plan focus areas",
  "total_weeks": {total_weeks},
  "courses": [
    {{
      "course_id": "uuid or null",
      "title": "Activity title",
      "description": "What the student will learn",
      "topic_id": "uuid or null",
      "subtopic_id": "uuid or null",
      "week": 1,
      "day": 1,
      "sequence_order": 1,
      "suggested_duration_mins": 20,
      "activity_type": "lesson|practice|review|assessment"
    }}
  ]
}}

RULES:
1. Order courses by gap priority (high → medium → low)
2. Spread activities across the available weeks
3. Include review sessions for strengths
4. Use available course_ids where possible
5. sequence_order must be sequential (1, 2, 3...)
6. week must be between 1 and {total_weeks}
7. day must be between 1 and 5
8. suggested_duration_mins should be 15-30 minutes
"""
    return prompt


def validate_llm_response(
    response_data: Dict[str, Any],
    total_weeks: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Validate and sanitize the LLM response.

    Args:
        response_data: Parsed JSON response from LLM
        total_weeks: Expected total weeks
        db: Database session for UUID validation

    Returns:
        Dict: Validated and sanitized response data
    """
    if not isinstance(response_data, dict):
        raise ValueError("LLM response must be a JSON object")

    # Validate required fields
    if "courses" not in response_data:
        raise ValueError("LLM response must contain 'courses' array")

    courses = response_data.get("courses", [])
    if not isinstance(courses, list):
        raise ValueError("'courses' must be an array")

    validated_courses = []
    seen_sequence = set()

    for i, course in enumerate(courses):
        if not isinstance(course, dict):
            continue

        validated_course = {
            "title": course.get("title", f"Activity {i + 1}"),
            "description": course.get("description"),
            "topic_id": None,
            "subtopic_id": None,
            "course_id": None,
            "week": 1,
            "day": 1,
            "sequence_order": i + 1,
            "suggested_duration_mins": course.get("suggested_duration_mins", 20),
            "activity_type": course.get("activity_type", "lesson"),
        }

        # Validate and nullify invalid UUIDs
        for field in ["topic_id", "subtopic_id", "course_id"]:
            value = course.get(field)
            if value:
                try:
                    uuid_value = UUID(str(value))
                    # Verify UUID exists in DB
                    if field == "course_id":
                        exists = db.query(Course).filter(Course.id == uuid_value).first()
                        if exists:
                            validated_course[field] = str(uuid_value)
                    else:
                        validated_course[field] = str(uuid_value)
                except (ValueError, TypeError):
                    pass  # Keep as None

        # Validate week (1 to total_weeks)
        week = course.get("week", 1)
        validated_course["week"] = max(1, min(int(week), total_weeks))

        # Validate day (1-5)
        day = course.get("day", 1)
        validated_course["day"] = max(1, min(int(day), 5))

        # Ensure unique sequence_order
        seq = i + 1
        while seq in seen_sequence:
            seq += 1
        seen_sequence.add(seq)
        validated_course["sequence_order"] = seq

        # Validate duration (15-60 minutes)
        duration = course.get("suggested_duration_mins", 20)
        validated_course["suggested_duration_mins"] = max(15, min(int(duration), 60))

        # Validate activity_type
        valid_types = ["lesson", "practice", "review", "assessment"]
        activity_type = course.get("activity_type", "lesson")
        validated_course["activity_type"] = activity_type if activity_type in valid_types else "lesson"

        validated_courses.append(validated_course)

    response_data["courses"] = validated_courses
    response_data["total_weeks"] = total_weeks

    return response_data


def _update_redis_flag(student_id: str, status: str) -> None:
    """Update Redis generation flag."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(redis_url)

    key = f"kaihle:diagnostic:generating:{student_id}"
    client.setex(key, 2 * 60 * 60, status)

    logger.info("Set Redis flag '%s' for student %s", status, student_id)


def _call_llm(prompt: str, student_id: str) -> Dict[str, Any]:
    """
    Call the LLM provider and return the response.

    Uses the configured LLM provider via the unified LLMProvider abstraction.
    Implements caching and logging per AGENTS.md requirements.

    Args:
        prompt: The prompt to send to the LLM
        student_id: UUID string of the student (for logging)

    Returns:
        Dict: Parsed JSON response

    Raises:
        Exception: If LLM call fails or response is invalid
    """
    system_prompt = "You are an expert Cambridge curriculum learning designer. Return ONLY valid JSON."

    try:
        llm = get_llm_provider()
        response = llm.complete(system_prompt, prompt)

        logger.info(
            "LLM call completed",
            extra={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "service": "worker",
                "task": "tasks.generate_study_plan",
                "student_id": student_id,
                "provider": response.provider,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cached": response.cached,
            }
        )

        return json.loads(response.content)

    except Exception as e:
        logger.exception("LLM call failed")
        raise


def _generate_study_plan_impl(student_id: str, db: Session) -> StudyPlan:
    """
    Core implementation of study plan generation.

    Args:
        student_id: UUID string of the student
        db: Database session

    Returns:
        StudyPlan: The generated study plan
    """
    student_uuid = UUID(student_id)

    # 1. Load student profile
    student = db.query(StudentProfile).filter(StudentProfile.id == student_uuid).first()
    if not student:
        raise ValueError(f"Student profile not found: {student_id}")

    # 2. Load all AssessmentReports for this student
    reports = (
        db.query(AssessmentReport)
        .join(Assessment, AssessmentReport.assessment_id == Assessment.id)
        .filter(Assessment.student_id == student_uuid)
        .all()
    )

    if not reports:
        raise ValueError(f"No assessment reports found for student: {student_id}")

    # 3. Aggregate gaps and strengths from all subjects
    all_gaps = []
    all_strengths = []

    for report in reports:
        if report.knowledge_gaps:
            all_gaps.extend(report.knowledge_gaps)
        if report.strengths:
            all_strengths.extend(report.strengths)

    # 4. Calculate recommended weeks
    total_weeks = calculate_recommended_weeks(all_gaps)

    # 5. Load available courses matching gap subtopics
    gap_subtopic_ids = []
    for gap in all_gaps:
        subtopic_id = gap.get("subtopic_id")
        if subtopic_id:
            try:
                gap_subtopic_ids.append(UUID(str(subtopic_id)))
            except (ValueError, TypeError):
                pass

    available_courses = []
    if gap_subtopic_ids:
        courses = (
            db.query(Course)
            .filter(Course.subtopic_id.in_(gap_subtopic_ids))
            .filter(Course.is_active == True)
            .limit(50)
            .all()
        )
        available_courses = [
            {
                "course_id": str(c.id),
                "title": c.title,
                "subject_id": str(c.subject_id),
                "topic_id": str(c.topic_id) if c.topic_id else None,
                "subtopic_id": str(c.subtopic_id) if c.subtopic_id else None,
                "duration_minutes": c.duration_minutes,
                "difficulty_level": c.difficulty_level,
            }
            for c in courses
        ]

    # 6. Build student profile dict for LLM
    student_profile_data = {
        "grade_level": student.grade.level if student.grade else None,
        "curriculum": student.curriculum.name if student.curriculum else "Cambridge",
        "learning_style": getattr(student, 'learning_style', None),
    }

    # 7. Build LLM prompt
    prompt = build_llm_prompt(
        gaps=all_gaps,
        strengths=all_strengths,
        student_profile=student_profile_data,
        available_courses=available_courses,
        total_weeks=total_weeks,
    )

    # 8. Call LLM
    llm_response = _call_llm(prompt, student_id)

    # 9. Validate response
    validated_data = validate_llm_response(llm_response, total_weeks, db)

    # 10. Create StudyPlan and StudyPlanCourses in transaction
    study_plan = StudyPlan(
        student_id=student_uuid,
        title=validated_data.get("title", "Personalised Study Plan"),
        summary=validated_data.get("summary"),
        total_weeks=total_weeks,
        status="active",
        generation_metadata={
            "gaps_count": len(all_gaps),
            "strengths_count": len(all_strengths),
            "model": getattr(settings, 'LLM_MODEL', 'gpt-4o-mini'),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(study_plan)
    db.flush()  # Get the ID

    # Create StudyPlanCourses
    for course_data in validated_data.get("courses", []):
        sp_course = StudyPlanCourse(
            study_plan_id=study_plan.id,
            course_id=UUID(course_data["course_id"]) if course_data.get("course_id") else None,
            title=course_data["title"],
            description=course_data.get("description"),
            topic_id=UUID(course_data["topic_id"]) if course_data.get("topic_id") else None,
            subtopic_id=UUID(course_data["subtopic_id"]) if course_data.get("subtopic_id") else None,
            week=course_data["week"],
            day=course_data["day"],
            sequence_order=course_data["sequence_order"],
            suggested_duration_mins=course_data["suggested_duration_mins"],
            activity_type=course_data["activity_type"],
        )
        db.add(sp_course)

    db.commit()
    db.refresh(study_plan)

    logger.info(
        "Generated study plan %s for student %s with %d courses",
        study_plan.id, student_id, len(validated_data.get("courses", []))
    )

    return study_plan


# =============================================================================
# Celery Task
# =============================================================================

@celery_app.task(bind=True, max_retries=3, name="tasks.generate_study_plan")
def generate_study_plan(self, student_id: str) -> str:
    """
    Generate a personalised StudyPlan using LLM.

    This task runs after generate_assessment_reports completes.
    It loads all diagnostic results, builds an LLM prompt, and creates
    a StudyPlan with StudyPlanCourses.

    Args:
        student_id: UUID string of the student

    Returns:
        student_id (for potential task chaining)

    Updates Redis flag: kaihle:diagnostic:generating:{student_id} = "complete"
    On failure: sets flag to "failed" and creates StudyPlan with status "generation_failed"
    """
    logger.info("Starting study plan generation for student %s", student_id)

    # Create database session
    database_url = os.environ.get("DATABASE_URL", "postgresql://localhost/kaihle")
    # Convert async URL to sync for Celery
    sync_url = database_url.replace("+asyncpg", "")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Update Redis flag
        _update_redis_flag(student_id, "study_plan")

        # Generate the study plan
        study_plan = _generate_study_plan_impl(student_id, db)

        # Update Redis flag to complete
        _update_redis_flag(student_id, "complete")

        logger.info(
            "Study plan generation complete for student %s, plan_id=%s",
            student_id, study_plan.id
        )

        return student_id

    except json.JSONDecodeError as e:
        logger.error("JSON parsing error in study plan generation: %s", e)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except SQLAlchemyError as e:
        logger.error("Database error in study plan generation: %s", e)
        db.rollback()
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        logger.exception("Unexpected error in study plan generation")

        # On max retries, create a failed study plan
        if self.request.retries >= self.max_retries:
            try:
                db.rollback()

                # Create a failed study plan record
                failed_plan = StudyPlan(
                    student_id=UUID(student_id),
                    title="Study Plan Generation Failed",
                    status="generation_failed",
                    generation_metadata={
                        "error": str(e),
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                db.add(failed_plan)
                db.commit()

                _update_redis_flag(student_id, "failed")
                logger.error("Study plan generation failed after max retries for student %s", student_id)

            except Exception as inner_e:
                logger.exception("Failed to create failure record")
                db.rollback()

            return student_id

        # Retry
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        db.close()
