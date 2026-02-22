# app/services/assessment.py
import pandas as pd
import json
import math, random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from venv import logger
from sqlalchemy.dialects import postgresql
from sqlalchemy import func, select, text, asc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.assessment import (
    Assessment,
    AssessmentType,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentReport,
    QuestionBank,
    StudentKnowledgeProfile
)
from app.models.user import StudentProfile  # adjust import to match your structure
from app.models.curriculum import CurriculumTopic, Subtopic
from app.services.llm_service import llm_service as llm

from app.constants.constants import (
    TOTAL_QUESTIONS_PER_ASSESSMENT,
    ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC as MAX_PER_TOPIC
)


# basic expected probability (sigmoid)
def expected_prob(skill: float, difficulty: float) -> float:
    return 1.0 / (1.0 + math.exp(-8.0 * (skill - difficulty)))

def update_mastery(skill: float, difficulty: float, correct: bool, alpha: float = 0.12) -> float:
    exp = expected_prob(skill, difficulty)
    lr = alpha * (1.0 - skill)
    delta = lr * ((1.0 if correct else 0.0) - exp)
    new_skill = max(0.0, min(1.0, skill + delta))
    return new_skill

# Difficulty scale: Integer 1-5
# 1 = Beginner, 2 = Easy, 3 = Medium, 4 = Hard, 5 = Expert

DIFFICULTY_LABELS = {
    1: "beginner",
    2: "easy",
    3: "medium",
    4: "hard",
    5: "expert"
}

def difficulty_label_from_int(value: int) -> str:
    """Convert integer difficulty (1-5) to label."""
    return DIFFICULTY_LABELS.get(value, "unknown")


def difficulty_int_from_label(label: str) -> int:
    """Convert difficulty label to integer (1-5)."""
    if not label:
        return 3  # Default to medium
    label_lower = label.lower()
    label_map = {
        "beginner": 1,
        "easy": 2,
        "medium": 3,
        "hard": 4,
        "expert": 5
    }
    return label_map.get(label_lower, 3)

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


def get_subtopics_for_grade(db:Session, subject_id: UUID, grade_id: UUID) -> List[str]:
    """
    Return a list of subtopics for a subject and grade.
    """
    subtopics = (db.query(Subtopic)
        .join(CurriculumTopic, Subtopic.topic_id == CurriculumTopic.topic_id)
        .filter(
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.grade_id == grade_id
        )
    ).all()

    subtopics = [s.name for s in subtopics]
    return subtopics


def get_subtopics_for_grade_and_subject(
    db: Session,
    grade_id: UUID,
    subject_id: UUID,
    curriculum_id: Optional[UUID] = None
) -> List[Subtopic]:
    """
    Query subtopics from the database for a specific grade and subject.

    Joins through CurriculumTopic to get grade/subject filtering.
    Optionally filters by curriculum_id if provided.

    Args:
        db: SQLAlchemy session
        grade_id: UUID of the grade to filter by
        subject_id: UUID of the subject to filter by
        curriculum_id: Optional UUID of the curriculum to filter by

    Returns:
        List of Subtopic objects with their relationships loaded.
        Returns empty list if no subtopics are found.
    """
    query = (
        db.query(Subtopic)
        .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
        .filter(
            CurriculumTopic.grade_id == grade_id,
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.is_active == True,
            Subtopic.is_active == True
        )
    )

    # Optionally filter by curriculum if provided
    if curriculum_id is not None:
        query = query.filter(CurriculumTopic.curriculum_id == curriculum_id)

    # Order by sequence_order and load the curriculum_topic relationship
    subtopics = (
        query
        .options(joinedload(Subtopic.curriculum_topic))
        .order_by(Subtopic.sequence_order)
        .all()
    )

    return subtopics if subtopics else []


def count_questions_per_subtopic(
    db: Session,
    assessment_id: UUID
) -> Dict[UUID, int]:
    """
    Count how many questions have been asked per subtopic for an assessment.

    Queries AssessmentQuestion joined with QuestionBank to get subtopic_id,
    then groups by subtopic_id to get counts.

    Args:
        db: SQLAlchemy session
        assessment_id: UUID of the assessment to count questions for

    Returns:
        Dictionary mapping subtopic_id (UUID) to count (int).
        Returns empty dict if no questions exist for the assessment.
    """
    results = (
        db.query(
            QuestionBank.subtopic_id,
            func.count(AssessmentQuestion.id).label('count')
        )
        .join(AssessmentQuestion, QuestionBank.id == AssessmentQuestion.question_bank_id)
        .filter(AssessmentQuestion.assessment_id == assessment_id)
        .filter(QuestionBank.subtopic_id.isnot(None))  # Only count questions with subtopics
        .group_by(QuestionBank.subtopic_id)
        .all()
    )

    return {row.subtopic_id: row.count for row in results}


def select_subtopic_by_priority(
    subtopics: List[Subtopic],
    questions_per_subtopic: Dict[UUID, int],
    student_knowledge_profile: List[StudentKnowledgeProfile],
    max_questions_per_subtopic: int = MAX_PER_TOPIC
) -> Optional[Subtopic]:
    """
    Select a subtopic based on priority (lower mastery = higher priority).

    Filters out subtopics that already have max_questions_per_subtopic questions,
    then selects based on student's mastery level per subtopic.

    Args:
        subtopics: List of Subtopic objects to choose from
        questions_per_subtopic: Dict mapping subtopic_id to question count
        student_knowledge_profile: List of StudentKnowledgeProfile objects for the student
        max_questions_per_subtopic: Maximum questions allowed per subtopic (default: 5)

    Returns:
        Selected Subtopic object, or None if all subtopics are at max questions.
    """
    if not subtopics:
        return None

    # Create a lookup for mastery levels by subtopic_id
    mastery_by_subtopic: Dict[UUID, float] = {}
    for profile in student_knowledge_profile:
        if profile.subtopic_id:
            mastery_by_subtopic[profile.subtopic_id] = profile.mastery_level or 0.5

    # Filter out subtopics that have reached max questions
    available_subtopics = [
        s for s in subtopics
        if questions_per_subtopic.get(s.id, 0) < max_questions_per_subtopic
    ]

    if not available_subtopics:
        return None

    # Score each subtopic: lower mastery = higher priority
    # Add small random factor to avoid determinism
    scored_subtopics = []
    for subtopic in available_subtopics:
        mastery = mastery_by_subtopic.get(subtopic.id, 0.5)  # Default to 0.5 if no profile exists
        # Invert mastery so lower mastery = higher priority
        priority = 1.0 - mastery
        # Add small random factor (±0.05) to break ties and avoid determinism
        priority += 0.05 * (0.5 - random.random())
        scored_subtopics.append((subtopic, priority))

    # Sort by priority descending (highest priority first)
    scored_subtopics.sort(key=lambda x: x[1], reverse=True)

    return scored_subtopics[0][0]


# ---------- Question Selection Helpers ----------

def get_recent_answers_for_subtopic(
    db: Session,
    assessment_id: UUID,
    subtopic_id: UUID,
    limit: int = 5
) -> List[AssessmentQuestion]:
    """
    Get the most recent answered questions for a specific subtopic within an assessment.

    Joins AssessmentQuestion with QuestionBank to filter by subtopic, then returns
    the most recent answers ordered by answered_at descending.

    Args:
        db: SQLAlchemy session
        assessment_id: UUID of the assessment to query
        subtopic_id: UUID of the subtopic to filter by
        limit: Maximum number of answers to return (default: 5)

    Returns:
        List of AssessmentQuestion objects that have been answered (is_correct is not None).
        Returns empty list if no answers exist for the subtopic in this assessment.
    """
    recent_answers = (
        db.query(AssessmentQuestion)
        .join(QuestionBank, AssessmentQuestion.question_bank_id == QuestionBank.id)
        .filter(
            AssessmentQuestion.assessment_id == assessment_id,
            QuestionBank.subtopic_id == subtopic_id,
            AssessmentQuestion.is_correct.isnot(None)  # Only answered questions
        )
        .order_by(AssessmentQuestion.answered_at.desc())
        .limit(limit)
        .all()
    )

    return recent_answers if recent_answers else []


def calculate_subtopic_difficulty(
    db: Session,
    assessment_id: UUID,
    subtopic_id: UUID,
    initial_difficulty: int = 3
) -> int:
    """
    Calculate the appropriate difficulty level for a subtopic based on recent answers.

    Uses a sliding window of the last 3-5 answers to adjust difficulty:
    - Starts from initial_difficulty (default 3 = middle)
    - For each wrong answer, decrease difficulty (min 1)
    - For each correct answer, increase difficulty (max 5)

    Args:
        db: SQLAlchemy session
        assessment_id: UUID of the assessment
        subtopic_id: UUID of the subtopic to calculate difficulty for
        initial_difficulty: Starting difficulty level (default: 3, range: 1-5)

    Returns:
        Integer difficulty level from 1 (easiest) to 5 (hardest).
        Returns initial_difficulty if no answers exist for the subtopic.
    """
    # Get recent answers (using 5 as window size for better adaptation)
    recent_answers = get_recent_answers_for_subtopic(
        db, assessment_id, subtopic_id, limit=5
    )

    if not recent_answers:
        return initial_difficulty

    # Start from initial difficulty and adjust based on answers
    difficulty = initial_difficulty

    # Process answers in reverse chronological order (most recent first)
    # Use only the last 3 answers for more responsive adaptation
    answers_to_consider = recent_answers[:3]

    for answer in answers_to_consider:
        if answer.is_correct:
            # Correct answer - increase difficulty
            difficulty = min(5, difficulty + 1)
        else:
            # Wrong answer - decrease difficulty
            difficulty = max(1, difficulty - 1)

    return difficulty


def find_existing_question(
    db: Session,
    subtopic_id: UUID,
    difficulty: int,
    grade_id: UUID,
    subject_id: UUID,
    exclude_ids: Optional[set] = None
) -> Optional[QuestionBank]:
    """
    Find a question in QuestionBank matching the given criteria.

    Searches for questions matching subtopic, grade, and subject, with difficulty
    at the exact level or within ±1 range. Prioritizes exact difficulty matches.

    Args:
        db: SQLAlchemy session
        subtopic_id: UUID of the subtopic to filter by
        difficulty: Target difficulty level (1-5 integer scale)
        grade_id: UUID of the grade to filter by
        subject_id: UUID of the subject to filter by
        exclude_ids: Optional set of question IDs to exclude (already used questions)

    Returns:
        A single QuestionBank object matching the criteria, or None if not found.
        Prioritizes exact difficulty match over ±1 range matches.
    """

    # Build base query
    base_query = (
        db.query(QuestionBank)
        .filter(
            QuestionBank.subtopic_id == subtopic_id,
            QuestionBank.grade_id == grade_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.is_active == True
        )
    )

    # Exclude specified question IDs
    if exclude_ids:
        base_query = base_query.filter(~QuestionBank.id.in_(exclude_ids))

    # First, try to find exact difficulty match
    exact_match = base_query.filter(
        QuestionBank.difficulty_level == difficulty
    ).first()

    if exact_match:
        return exact_match

    print("No exact match found, trying ±1 range")
    # If no exact match, try ±1 difficulty range
    # Calculate min/max difficulty for ±1 range
    min_difficulty = max(1, difficulty - 1)
    max_difficulty = min(5, difficulty + 1)

    range_match = (
        db.query(QuestionBank)
        .filter(
            QuestionBank.subtopic_id == subtopic_id,
            QuestionBank.grade_id == grade_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.is_active == True,
            QuestionBank.difficulty_level >= min_difficulty,
            QuestionBank.difficulty_level <= max_difficulty
        )
    )

    if exclude_ids:
        range_match = range_match.filter(~QuestionBank.id.in_(exclude_ids))

    return range_match.first()


def get_used_question_ids(
    db: Session,
    assessment_id: UUID
) -> set:
    """
    Get all question_ids already used in an assessment.

    Queries AssessmentQuestion for the given assessment and returns
    a set of question_bank_id UUIDs for questions that have been used.

    Args:
        db: SQLAlchemy session
        assessment_id: UUID of the assessment to query

    Returns:
        Set of question_bank_id UUIDs (as UUID objects).
        Returns empty set if no questions have been used.
    """
    used_questions = (
        db.query(AssessmentQuestion.question_bank_id)
        .filter(AssessmentQuestion.assessment_id == assessment_id)
        .all()
    )

    return {row.question_bank_id for row in used_questions}


# ---------- Difficulty helpers ----------

def calculate_difficulty_from_history(db: Session, assessment: Assessment, subtopic: str) -> int:
    """
    Calculate difficulty based on recent answers for a subtopic.
    Returns integer difficulty 1-5.
    """
    last_three = (
        db.query(AssessmentQuestion)
        .join(Assessment, AssessmentQuestion.assessment_id == Assessment.id)
        .join(QuestionBank, AssessmentQuestion.question_bank_id == QuestionBank.id)
        .filter(
            AssessmentQuestion.answered_at.isnot(None),
            AssessmentQuestion.assessment_id == assessment.id,
            func.lower(QuestionBank.subtopic) == func.lower(subtopic)
        ).order_by(AssessmentQuestion.answered_at.desc()).limit(3)
        .all()
    )

    wrong_count = sum(1 for q in last_three if not q.is_correct)

    # Adjust difficulty based on wrong answers
    # More wrong = easier questions
    if wrong_count >= 3:
        return 1  # Beginner - student struggling
    elif wrong_count >= 2:
        return 2  # Easy
    elif wrong_count >= 1:
        return 3  # Medium
    else:
        return 4  # Hard - student doing well


# Legacy functions kept for backward compatibility during transition
def difficulty_float_from_label(label: str) -> float:
    """
    DEPRECATED: Use difficulty_int_from_label instead.
    Kept for backward compatibility.
    """
    if not label:
        return 0.5
    l = label.lower()
    if l == "beginner":
        return 0.15
    if l == "easy":
        return 0.25
    if l == "medium":
        return 0.5
    if l == "hard":
        return 0.75
    if l == "expert":
        return 0.9
    try:
        # maybe it's numeric string
        return float(label)
    except Exception:
        return 0.5


def difficulty_label_from_value(val: float) -> str:
    """
    DEPRECATED: Use difficulty_label_from_int instead.
    Kept for backward compatibility. Converts float (0.0-1.0) to label.
    """
    if val <= 0.20:
        return "beginner"
    if val <= 0.35:
        return "easy"
    if val <= 0.60:
        return "medium"
    if val <= 0.80:
        return "hard"
    return "expert"

###################################
## Assessment Reated
###################################
def create_assessment(
    db: Session,
    student_id: UUID,
    subject_id: UUID,
    assessment_type: AssessmentType,
    total_questions_configurable: int=None
) -> Assessment:

    assessment = Assessment(
        student_id=student_id,
        subject_id=subject_id,
        assessment_type=assessment_type
    )
    if total_questions_configurable:
        assessment.total_questions_configurable = total_questions_configurable

    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return assessment

def _get_diagnostic_assessment_for_student(db: Session, student_id: UUID, subject_id: UUID ) -> Assessment:
    return (
        db.query(Assessment)
        .filter(
            Assessment.student_id == student_id,
            Assessment.subject_id == subject_id,
            Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )

def resolve_diagnostic_assessment(
        db: Session,
        student_id : UUID,
        subject_id : UUID,
        total_questions_configurable: int = None
    ) -> Assessment:
    """
    Idempotent:
    - returns active assessment if exists
    - otherwise creates a new one
    """

    assessment = _get_diagnostic_assessment_for_student(db, student_id, subject_id)

    if assessment:
        return assessment

    assessment = Assessment(
        student_id=student_id,
        subject_id=subject_id,
        assessment_type=AssessmentType.DIAGNOSTIC
    )
    if total_questions_configurable:
        assessment.total_questions_configurable = total_questions_configurable

    db.add(assessment)
    try:
        db.commit()
        db.refresh(assessment)
        return assessment
    except IntegrityError as e:
        db.rollback()
        assessment = _get_diagnostic_assessment_for_student(db, student_id, subject_id)
        return assessment


# ---------- QuestionBank helper ----------
def get_or_create_knowledge_area(db: Session, subject: str, subtopic: Optional[str], grade_level: str) -> QuestionBank:
    """
    Normalize and fetch or create a QuestionBank row.
    """

    ka = db.query(QuestionBank).filter(
        func.lower(QuestionBank.subject) == subject.lower(),
        (QuestionBank.subtopic == subtopic) if subtopic is not None else (QuestionBank.subtopic.is_(None)),
        func.lower(QuestionBank.grade_level) == str(grade_level).lower()
    ).first()

    if ka:
        return ka

    ka = QuestionBank(
        subject=subject,
        subtopic=subtopic,
        grade_level=str(grade_level),
        created_at=datetime.now(timezone.utc)
    )
    db.add(ka)
    db.commit()
    db.refresh(ka)
    return ka


# ---------- Topic counting ----------
def count_questions_for_topic(db: Session, assessment: Assessment, subtopic: str) -> int:
    cnt = (
        db.query(func.count(AssessmentQuestion.id))
        .join(QuestionBank, AssessmentQuestion.knowledge_area_id == QuestionBank.id)
        .filter(
            AssessmentQuestion.assessment_id == assessment.id,
            func.lower(QuestionBank.subtopic) == func.lower(subtopic)
        )
        .scalar()
    ) or 0
    return int(cnt)


# ---------- Question creation (main entrypoint used by API) ----------
def _next_question_number(db: Session, assessment: Assessment) -> int:

    last = db.query(func.max(AssessmentQuestion.question_number)).filter(AssessmentQuestion.assessment_id == assessment.id).scalar()
    if not last:
        return 1
    return int(last) + 1


def find_duplicates_question(
    db: Session,
    subject: str,
    grade_level: str,
    canonical_form: str,
    problem_signature: dict
):
    result = {
        "canonical_match": None,
        "signature_match": None
    }

    # Canonical match (fast exact check)
    if canonical_form:
        q = db.execute(
            text("SELECT id FROM question_bank WHERE canonical_form = :c LIMIT 1"),
            {"c": canonical_form}
        ).first()
        if q:
            result["canonical_match"] = q[0]
            return result

    # Exact problem_signature match
    if problem_signature:
        q = db.execute(
            text("""
                SELECT id
                FROM question_bank
                WHERE problem_signature = CAST(:sig AS jsonb)
                LIMIT 1
            """),
            {"sig": json.dumps(problem_signature)}
        ).first()
        if q:
            result["signature_match"] = q[0]
            return result

    return result

async def resolve_question(db: Session, assessment: Assessment, grade_id: UUID) -> AssessmentQuestion:
    """
    Resolve the next question for an assessment using the QuestionBank.

    This function implements an adaptive, per-subtopic question selection algorithm:
    1. Returns any existing unanswered question first
    2. Loads subtopics from the database for the student's grade and subject
    3. Tracks questions per subtopic (max 5 per subtopic)
    4. Selects subtopic based on student's mastery (lower mastery = higher priority)
    5. Calculates adaptive difficulty based on recent answers
    6. Finds an existing question from QuestionBank (no LLM generation)

    Args:
        db: SQLAlchemy session
        assessment: Assessment object with student and subject relationships
        grade_id: UUID of the grade for question filtering

    Returns:
        AssessmentQuestion with question_bank relationship loaded.

    Raises:
        ValueError: If max questions reached, no subtopics found, all subtopics at max,
                   or no questions available in QuestionBank.
    """
    # Step 1: Check for existing unanswered question
    unanswered = (
        db.query(AssessmentQuestion)
        .options(joinedload(AssessmentQuestion.question_bank))
        .filter(
            AssessmentQuestion.assessment_id == assessment.id,
            AssessmentQuestion.student_answer.is_(None),
        )
        .order_by(asc(AssessmentQuestion.question_number))
        .first()
    )

    if unanswered:
        return unanswered

    # Step 2: Check assessment limits
    max_questions = assessment.total_questions_configurable or TOTAL_QUESTIONS_PER_ASSESSMENT

    if assessment.total_questions >= max_questions:
        raise ValueError("Max questions per assessment reached")


    # Step 3: Load subtopics from database
    subtopics = get_subtopics_for_grade_and_subject(
        db,
        grade_id,
        assessment.subject_id
    )

    if not subtopics:
        raise ValueError(f"No subtopics found for grade {grade_id} and subject {assessment.subject_id}")

    # Step 4: Count questions per subtopic
    questions_per_subtopic = count_questions_per_subtopic(db, assessment.id)

    # Step 5: Get student's knowledge profile for mastery data
    student_knowledge_profiles = (
        db.query(StudentKnowledgeProfile)
        .filter(StudentKnowledgeProfile.student_id == assessment.student_id)
        .all()
    )

    # Step 6: Select a subtopic based on priority (lower mastery = higher priority)
    selected_subtopic = select_subtopic_by_priority(
        subtopics=subtopics,
        questions_per_subtopic=questions_per_subtopic,
        student_knowledge_profile=student_knowledge_profiles,
        max_questions_per_subtopic=MAX_PER_TOPIC
    )

    if not selected_subtopic:
        raise ValueError("All subtopics have reached maximum questions (5 per subtopic)")

    # Step 7: Calculate difficulty for selected subtopic
    difficulty = calculate_subtopic_difficulty(
        db,
        assessment.id,
        selected_subtopic.id,
        initial_difficulty=3  # Start at middle difficulty
    )

    # Step 8: Get used question IDs to exclude
    used_question_ids = get_used_question_ids(db, assessment.id)

    # Step 9: Find an existing question from QuestionBank
    question = find_existing_question(
        db,
        subtopic_id=selected_subtopic.id,
        difficulty=difficulty,
        grade_id=grade_id,
        subject_id=assessment.subject_id,
        exclude_ids=used_question_ids
    )

    if not question:
        raise ValueError(
            f"No question found in QuestionBank for subtopic {selected_subtopic.name} ID:{selected_subtopic.id}, "
            f"difficulty {difficulty}, grade {grade_id}, subject {assessment.subject_id}, excluded IDs: {used_question_ids}"
        )

    # Step 10: Create AssessmentQuestion
    next_number = _next_question_number(db, assessment)

    assessment_question = AssessmentQuestion(
        assessment_id=assessment.id,
        question_bank_id=question.id,
        question_number=next_number
    )

    db.add(assessment_question)

    # Update assessment total_questions count
    assessment.total_questions = (assessment.total_questions or 0) + 1
    db.add(assessment)

    db.commit()
    db.refresh(assessment_question)

    # Load the question_bank relationship for the returned object
    db.refresh(assessment_question)
    assessment_question = (
        db.query(AssessmentQuestion)
        .options(joinedload(AssessmentQuestion.question_bank))
        .filter(AssessmentQuestion.id == assessment_question.id)
        .first()
    )

    return assessment_question


# ---------- Process completed assessment and generate summary ----------
def get_subtopic_mastery_results_for_assessment(db: Session, assessment_id: UUID):
    query = (
        select(
            QuestionBank.subtopic,
            func.count().label("total_questions"),
            func.sum(AssessmentQuestion.score).label("correct"),
            func.avg(AssessmentQuestion.score).label("accuracy"),
            func.avg(QuestionBank.difficulty_level).label("avg_difficulty"),
            (
                func.sum(AssessmentQuestion.score * QuestionBank.difficulty_level) /
                func.sum(QuestionBank.difficulty_level)
            ).label("difficulty_weighted_mastery")
        )
        .join(AssessmentQuestion, AssessmentQuestion.question_bank_id == QuestionBank.id)
        .where(
            AssessmentQuestion.assessment_id == assessment_id
        )
        .group_by(QuestionBank.subtopic)
    )

    rows = db.execute(query).mappings().all()
    return rows

def compute_composite_mastery(rows):
    df = pd.DataFrame(rows)

    df["composite_mastery"] = (
        0.6 * df["difficulty_weighted_mastery"] +
        0.4 * df["accuracy"]
    )

    return df


def generate_diagnostic_summary(student_name, grade_level, df):
    strengths = df[df.composite_mastery >= 0.80]["subtopic"].tolist()
    developing = df[(df.composite_mastery >= 0.50) & (df.composite_mastery < 0.80)]["subtopic"].tolist()
    gaps = df[df.composite_mastery < 0.50]["subtopic"].tolist()

    summary = f"""
        Diagnostic Summary for {student_name} (Grade {grade_level})

        Overall Performance:
        - Strong Areas: {", ".join(strengths) if strengths else "None yet – still learning!"}
        - Developing Areas: {", ".join(developing) if developing else "None"}
        - Areas Needing Support: {", ".join(gaps) if gaps else "None"}

        What This Means:
        - Strong Areas: These are subtopics where your child has demonstrated clear understanding.
        - Developing Areas: These need more practice and reinforcement.
        - Areas Needing Support: These are the foundational concepts we will focus on next.

        We will now create a personalized learning plan to close knowledge gaps and strengthen overall mastery.
        """
    return summary


def generate_study_plan(df):

    study_plan = []

    for _, row in df.iterrows():
        subtopic = row["subtopic"]
        mastery = row["composite_mastery"]

        if mastery < 0.50:
            plan_type = "Needs Support"
            activities = [
                "Watch concept-explainer video (5–7 mins)",
                "Do guided practice problems (3–5 problems)",
                "Solve a short MCQ quiz (3–5 questions)"
            ]

        elif mastery < 0.80:
            plan_type = "Developing"
            activities = [
                "Do mixed-practice problems (5–8 problems)",
                "Solve a short MCQ quiz (5 questions)",
                "Complete 1 applied real-world example"
            ]

        else:
            plan_type = "Mastered"
            activities = [
                "Optional: Enrichment problem set",
                "Optional: Real-world application challenge"
            ]

        study_plan.append({
            "subtopic": subtopic,
            "mastery_level": plan_type,
            "recommended_activities": activities
        })

    return study_plan

def get_or_create_assessment_report(db: Session, assessment_id: UUID, student_name: str, grade_level: int) -> Dict[str, Any]:
    existing_report = db.query(AssessmentReport).filter(AssessmentReport.assessment_id == assessment_id).first()
    if existing_report:
        return existing_report

    rows = process_completed_assessment(db, assessment_id, student_name, grade_level)

    report = AssessmentReport(
        assessment_id=assessment_id,
        diagnostic_summary=rows['diagnostic_summary'],
        study_plan_json=rows['study_plan'],
        mastery_table_json=rows['mastery_table']
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return report


def process_completed_assessment(db: Session, assessment_id: UUID, student_name: str, grade_level: int) -> Dict[str, Any]:

    # Step 1: get results
    rows = get_subtopic_mastery_results_for_assessment(db, assessment_id)

    # # Step 2: compute mastery
    df = compute_composite_mastery(rows)

    # # Step 3: create diagnostic summary
    diagnostic_summary = generate_diagnostic_summary(student_name, grade_level, df)

    # # Step 4: generate study plan
    study_plan = generate_study_plan(df)

    # # Step 5: store mastery into database for future growth tracking
    # save_mastery_scores(db, student_id, assessment_id, df)

    # # Step 6: return everything to frontend / parent dashboard
    # return {
    #     "diagnostic_summary": diagnostic_summary,
    #     "study_plan": study_plan,
    #     "mastery_table": df.to_dict(orient="records")
    # }

    return {"diagnostic_summary": diagnostic_summary, "study_plan": study_plan, "mastery_table": df.to_dict(orient="records")}


def db_query_for_diagnostic(db: Session, assessment_id: UUID):
    """Helper to get diagnostic data for an assessment."""
    query = """
        WITH per_sub AS (
        SELECT
            subtopic,
            COUNT(*) AS total_questions,
            SUM(score) AS correct,
            AVG(score)::numeric AS accuracy,
            AVG(difficulty_level)::numeric AS avg_difficulty,
            SUM(score * difficulty_level)::numeric AS weighted_sum,
            SUM(difficulty_level)::numeric AS difficulty_sum
        from assessment_questions inner join question_bank as qb on qb.id = question_bank_id  where assessment_id = :assessment_id
        GROUP BY subtopic
        )
        SELECT
        subtopic,
        total_questions,
        correct,
        accuracy,
        avg_difficulty,
        (weighted_sum / NULLIF(difficulty_sum,0))::numeric(6,4) AS difficulty_weighted_mastery,
        -- composite = 0.6 * weighted + 0.4 * accuracy
        (0.6 * (weighted_sum / NULLIF(difficulty_sum,0)) + 0.4 * accuracy)::numeric(6,4) AS composite_mastery
        FROM per_sub
        ORDER BY composite_mastery ASC;
    """
    return query
