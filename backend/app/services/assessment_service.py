# app/services/assessment_service.py
import pandas as pd
import json
import math, random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from venv import logger
from sqlalchemy.orm import Session
from sqlalchemy import func, select, text
from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentReport,
    QuestionBank,
    StudentKnowledgeProfile
)
from app.models.user import StudentProfile  # adjust import to match your structure
from app.services.llm_service import llm_service as llm

from app.constants import (
    ASSESSMENT_SUBJECTS,
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
    skps = db.query(StudentKnowledgeProfile).join(QuestionBank).filter(
        StudentKnowledgeProfile.student_id == student_id,
        QuestionBank.subject == subject
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


# ---------- Topic/Subtopic selection ----------
# A small canonical mapping for grade -> common subtopics (fallback)
BUILTIN_SUBTOPICS = {
  "math": {
    "5": ["arithmetic", "fractions", "basic geometry", "word problems"],
    "6": ["ratios and proportions", "decimals", "area and perimeter", "basic statistics"],
    "7": ["integers", "pre-algebra", "geometry basics", "rational numbers"],
    "8": ["algebra", "linear equations", "functions", "geometry applications"],
    "9": ["algebra I", "quadratic equations", "functions and graphs", "statistics basics"],
    "10": ["geometry", "algebra II", "probability", "data interpretation"],
    "11": ["pre-calculus", "trigonometry", "statistics", "analytic geometry"],
    "12": ["calculus basics", "advanced algebra", "mathematical modeling", "applied statistics"]
  },
  "science": {
    "5": ["life science", "earth science", "human body systems", "simple machines"],
    "6": ["ecosystems", "matter and its properties", "weather and climate", "forces and motion"],
    "7": ["cells and organisms", "basic physics forces", "the water cycle", "energy transfer"],
    "8": ["chemistry basics", "energy and heat", "electricity", "scientific inquiry"],
    "9": ["biology intro", "physics intro", "atoms and molecules", "environmental science"],
    "10": ["chemistry", "genetics", "ecology", "cell biology"],
    "11": ["physics", "organic chemistry", "evolution", "astronomy"],
    "12": ["advanced biology", "advanced physics", "biotechnology", "sustainability"]
  },
  "english": {
    "5": ["reading comprehension", "grammar basics", "story elements", "vocabulary building"],
    "6": ["vocabulary", "writing paragraphs", "reading fluency", "summarizing texts"],
    "7": ["literary devices", "essay structure", "narrative writing", "poetry appreciation"],
    "8": ["analysis", "argument writing", "research skills", "persuasive writing"],
    "9": ["literature study", "creative writing", "grammar refinement", "critical response essays"],
    "10": ["shaping arguments", "critical reading", "public speaking", "comparative literature"],
    "11": ["advanced composition", "literary analysis", "academic writing", "rhetorical techniques"],
    "12": ["rhetoric", "college-level writing", "literary criticism", "speech and debate"]
  },
  "humanities": {
    "5": ["history basics", "maps and geography", "ancient civilizations", "community and culture"],
    "6": ["civilizations overview", "cultural traditions", "early religions", "geography skills"],
    "7": ["world geography", "early history", "trade and exploration", "ancient empires"],
    "8": ["medieval history", "cultural studies", "colonialism", "global connections"],
    "9": ["modern history intro", "industrial revolution", "global conflicts", "nationalism"],
    "10": ["world history", "revolutions", "economic systems", "political ideologies"],
    "11": ["historical analysis", "philosophy basics", "sociology", "human rights movements"],
    "12": ["deep historical themes", "comparative cultures", "globalization", "modern world issues"]
  },
  "entrepreneurship": {
    "5": ["understanding needs and wants", "saving and spending", "teamwork", "creative thinking"],
    "6": ["problem solving", "introduction to business", "goal setting", "basic budgeting"],
    "7": ["identifying opportunities", "customer understanding", "simple business plans", "marketing basics"],
    "8": ["entrepreneurial mindset", "value creation", "product development", "financial literacy"],
    "9": ["market research", "branding", "basic accounting", "pitching ideas"],
    "10": ["business models", "social entrepreneurship", "operations and logistics", "team leadership"],
    "11": ["financial planning", "startup case studies", "marketing strategy", "scaling a business"],
    "12": ["innovation and design thinking", "funding and investment", "global entrepreneurship", "sustainable ventures"]
  }
}


def get_subtopics_for_grade(subject: str, grade_level: int) -> List[str]:
    """
    Return a list of subtopics for a subject and grade.
    Prefer built-in mapping; try LLM (generate_study_plan or fallback) for more detail if available.
    """
    g = str(grade_level)
    subject_key = subject.lower()
    if subject_key in BUILTIN_SUBTOPICS and g in BUILTIN_SUBTOPICS[subject_key]:
        base = BUILTIN_SUBTOPICS[subject_key][g]
    else:
        base = ["General"]

    # # Attempt to get refined subtopics from LLM (non-blocking fallback)
    # try:
    #     # Use generate_study_plan with empty mastery_map to ask for recommended subtopics
    #     # Note: llm.generate_study_plan may return a JSON/structure; adapt as needed.
    #     plan = llm.generate_study_plan({}, subject, grade_level)
    #     # Expect plan to be dict with keys 'subtopics' or similar; try to parse defensively
    #     if isinstance(plan, dict):
    #         sub = plan.get("subtopics") or plan.get("topics") or []
    #         if isinstance(sub, list) and sub:
    #             return [s for s in sub]
    # except Exception:
    #     # ignore LLM failure and use builtin
    #     pass

    return base


# ---------- Difficulty helpers ----------

def calculate_difficulty_from_history(db: Session, assessment: Assessment, subtopic: str) -> float:
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

    # Lower difficulty if student got 2 or more wrong in last 3
    if wrong_count >= 3:
        difficulty_val = 0.25  # force to easy-ish
    elif wrong_count >= 1:
        difficulty_val = 0.50   # allow medium/hard if doing well
    else:
        difficulty_val = 0.85   # allow medium if mixed results

    return difficulty_val


def difficulty_float_from_label(label: str) -> float:
    if not label:
        return 0.5
    l = label.lower()
    if l == "easy":
        return 0.25
    if l == "medium":
        return 0.5
    if l == "hard":
        return 0.85
    try:
        # maybe it's numeric string
        return float(label)
    except Exception:
        return 0.5


def difficulty_label_from_value(val: float) -> str:
    if val <= 0.33:
        return "easy"
    if val <= 0.66:
        return "medium"
    return "hard"


# ---------- Checkpoint utilities ----------
def ensure_profile_checkpoints(profile: StudentProfile) -> Dict[str, Any]:
    """
    Ensure math/science/english/humanities checkpoint fields exist as JSON structure.
    Return them combined as a dict-like view.
    Each field will be JSON string in DB; we convert to dict objects in memory.
    Example structure stored in DB: {"algebra": {"grade_level": 5, "mastery": 0.4}, ...}
    """
    changed = False
    result = {}
    for subject in ASSESSMENT_SUBJECTS:
        field_name = f"{subject.value}_checkpoint"
        raw = getattr(profile, field_name, None)
        if not raw:
            obj = {}
            setattr(profile, field_name, json.dumps(obj))
            changed = True
        else:
            try:
                obj = raw if isinstance(raw, dict) else json.loads(raw)
            except Exception:
                obj = {}
                setattr(profile, field_name, json.dumps(obj))
                changed = True
        result[subject] = obj
    if changed:
        profile.updated_at = datetime.now(timezone.utc)
    return result


def save_profile_checkpoints(db: Session, profile: StudentProfile, checkpoints: Dict[str, Any]):
    """Persist the checkpoint dicts back onto the StudentProfile as JSON strings."""
    for subject, obj in checkpoints.items():
        setattr(profile, f"{subject}_checkpoint", json.dumps(obj))
    profile.updated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    db.refresh(profile)


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


# ---------- Topic selection & difficulty logic ----------
def pick_next_topic_and_difficulty(db: Session, student_id: int, subject: str, assessment: Optional[Assessment] = None) -> Dict[str, Any]:
    """
    Central logic to pick next (topic, subtopic, difficulty).
    - Uses student's profile checkpoints.
    - Avoids topics with >= MAX_PER_TOPIC questions in the assessment.
    - Uses StudentKnowledgeProfile to prefer weaker topics.
    - Returns dict: {topic, subtopic, difficulty}
    """
    # Load student profile
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if not profile:
        # create an empty profile record if none exists (optional behavior)
        profile = StudentProfile(student_id=student_id)
        db.add(profile); db.commit(); db.refresh(profile)

    # Ensure checkpoints present
    checkpoints = ensure_profile_checkpoints(profile)

    # Obtain a list of candidate topics/subtopics for this subject and student's grade
    grade = assessment.grade_level if assessment else None
    try:
        grade_int = int(grade) if grade else 7
    except Exception:
        grade_int = 7

    subtopics = get_subtopics_for_grade(subject, grade_int)

    # Build a scoring / priority for topics: prefer topics where mastery is lower, but also avoid overused topics in this assessment
    topic_scores = []
    for t in subtopics:
        # compute perceived mastery: check StudentKnowledgeProfile aggregated for KAs with this topic
        skps = db.query(StudentKnowledgeProfile).join(QuestionBank).filter(
            StudentKnowledgeProfile.student_id == student_id,
            func.lower(QuestionBank.subtopic) == func.lower(t)
        ).all()
        if skps:
            avg_mastery = sum((s.mastery_level or 0.5) for s in skps) / len(skps)
        else:
            avg_mastery = 0.5

        # reduce score if we've already generated MAX_PER_TOPIC for this topic in this assessment
        used = 0
        if assessment:
            used = count_questions_for_topic(db, assessment, t)

        if used >= MAX_PER_TOPIC:
            continue

        # lower mastery => higher priority (so we invert)
        priority = 1.0 - avg_mastery
        # small randomization to avoid deterministic selection
        priority = priority + (0.01 * (0.5 - random.random()))
        topic_scores.append((t, priority, used))

    if not topic_scores:
        # fallback to 'General'
        chosen_topic = "General"
    else:
        # choose highest priority
        topic_scores.sort(key=lambda x: x[1], reverse=True)
        chosen_topic = topic_scores[0][0]

    # choose a subtopic under chosen_topic (prefer checkpoint if present)
    subject_key = subject.lower()
    checkpoint_obj = checkpoints.get(subject_key, {}) if checkpoints else {}
    if isinstance(checkpoint_obj, dict) and checkpoint_obj:
        # pick the top checkpoint subtopic if it exists
        ck = next(iter(checkpoint_obj.keys()), None)
        if ck:
            chosen_subtopic = ck
        else:
            chosen_subtopic = (subtopics[0] if isinstance(subtopics, list) and subtopics else None)
    else:
        chosen_subtopic = (subtopics[0] if isinstance(subtopics, list) and subtopics else None)

    # difficulty: derive from assessment.difficulty_level if present, else medium
    if assessment and assessment.difficulty_level:
        d_val = difficulty_float_from_label(assessment.difficulty_level)
    else:
        d_val = 0.5

    # Make small adjustments: if topic has many wrong recent answers, decrease difficulty
    # Get last 3 answered questions for this student & topic across assessments
    last_three = (
        db.query(AssessmentQuestion)
        .join(QuestionBank, AssessmentQuestion.knowledge_area_id == QuestionBank.id)
        .join(Assessment, AssessmentQuestion.assessment_id == Assessment.id)
        .filter(
            Assessment.student_id == student_id,
            func.lower(QuestionBank.subtopic) == func.lower(chosen_topic),
            AssessmentQuestion.answered_at.isnot(None)
        )
        .order_by(AssessmentQuestion.answered_at.desc())
        .limit(3)
        .all()
    )
    wrong_count = sum(1 for q in last_three if not q.is_correct)
    if wrong_count >= 2:
        d_val = min(d_val, 0.3)

    return {"topic": chosen_topic, "subtopic": chosen_subtopic, "difficulty": d_val}


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
                WHERE problem_signature = CAST(:sig AS json)
                LIMIT 1
            """),
            {"sig": json.dumps(problem_signature)}
        ).first()
        if q:
            result["signature_match"] = q[0]
            return result

    return result

async def create_question(db: Session, assessment: Assessment) -> AssessmentQuestion:
    """
    Create a question using LLM and persist it.
    This enforces the MAX_PER_TOPIC limit and returns the created AssessmentQuestion.
    """

    total_assessment_questions = len(assessment.questions)

    if total_assessment_questions >= TOTAL_QUESTIONS_PER_ASSESSMENT:
        raise ValueError("Max questions per assessment reached")

    subtopic_list = get_subtopics_for_grade(assessment.subject, assessment.grade_level)
    # For simplicity, pick subtopic in round-robin fashion based on order
    subtopic_index = int(total_assessment_questions / int(TOTAL_QUESTIONS_PER_ASSESSMENT / len(subtopic_list))) if subtopic_list and len(subtopic_list) > 1 else 0
    subtopic = subtopic_list[subtopic_index] if subtopic_list else None

    difficulty = calculate_difficulty_from_history(db, assessment, subtopic) if subtopic else 0.5

    # Ask LLM to generate question object
    # Expected return: dict with question_text, question_type, options, correct_answer, difficulty_level, ai_feedback, topic, subtopic
    try:
        payload = await llm.generate_question(
            assessment.subject,
            assessment.grade_level,
            subtopic,
            difficulty_label_from_value(difficulty)
        )
        logger.debug("LLM generated question payload: %s", payload)
    except Exception as e:
        raise ValueError("Failed to generate question from LLM. Error: {}".format(str(e)))

    duplicates = find_duplicates_question(
        db,
        assessment.subject,
        str(assessment.grade_level),
        payload.get("canonical_form"),
        payload.get("problem_signature")
    )

    if duplicates["canonical_match"]:
        question_bank = db.query(QuestionBank).filter(QuestionBank.id == duplicates["canonical_match"]).first()
        existing_q = True
    elif duplicates["signature_match"]:
        question_bank = db.query(QuestionBank).filter(QuestionBank.id == duplicates["signature_match"]).first()
        existing_q = True
    else:
        question_bank = None
        existing_q = False

    q_text = payload.get("question_text")
    q_type = payload.get("question_type")
    options = payload.get("options")
    correct_answer = payload.get("correct_answer")
    difficulty_level = difficulty_float_from_label(payload.get("difficulty_level"))
    learning_objectives = payload.get("learning_objectives")
    description = payload.get("description")
    prerequisites = payload.get("prerequisites")
    subtopic = subtopic
    subject = payload.get("subject")

    if not existing_q:
        question_bank = QuestionBank(
            subject=subject,
            subtopic=subtopic,
            grade_level=str(assessment.grade_level),
            prerequisites=prerequisites,
            description=description,
            learning_objectives=learning_objectives,
            question_text=q_text,
            question_type=q_type,
            options=options,
            correct_answer=correct_answer,
            difficulty_level=difficulty_level,
            created_at=datetime.now(timezone.utc),
        )
        db.add(question_bank)
        db.commit()
        db.refresh(question_bank)


    aq = AssessmentQuestion(
        assessment_id=assessment.id,
        question_bank_id=question_bank.id,
        question_number=total_assessment_questions+1
    )

    db.add(aq)
    db.commit()
    db.refresh(aq)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return aq


# ---------- Answer scoring and adaptive update ----------
async def score_answer_and_maybe_next(db: Session, assessment: Assessment, question: AssessmentQuestion, answer_text: str, time_taken: Optional[int] = None) -> Dict[str, Any]:
    """
    Score the given answer, update mastery and assessment state, and optionally
    create & return the next question.

    Returns a dict:
    {
        "question": <updated question>,
        "is_correct": bool,
        "next_question": <AssessmentQuestion or None>,
        "assessment_completed": bool
    }
    """
    # Normalize
    provided = (answer_text or "").strip()
    correct = (question.correct_answer or "").strip()
    is_correct = False
    if correct:
        is_correct = provided.lower() == correct.lower()
    # Update question record
    question.student_answer = provided
    question.is_correct = is_correct
    question.score = 1.0 if is_correct else 0.0
    question.answered_at = datetime.now(timezone.utc)
    question.time_taken = time_taken
    db.add(question)
    db.commit()
    db.refresh(question)

    # Update StudentKnowledgeProfile for this knowledge area
    ka = question.knowledge_area
    skp = db.query(StudentKnowledgeProfile).filter_by(student_id=assessment.student_id, knowledge_area_id=ka.id).first()
    if not skp:
        skp = StudentKnowledgeProfile(student_id=assessment.student_id, knowledge_area_id=ka.id, mastery_level=0.5, assessment_count=0)
    cur_skill = skp.mastery_level or 0.5
    diff_val = difficulty_float_from_label(question.difficulty_level)
    # update_mastery function: small ELO-like update (simple)
    # delta = learning rate * (outcome - expected)
    expected = cur_skill
    outcome = 1.0 if is_correct else 0.0
    lr = 0.12 + (0.05 * (1.0 - cur_skill))  # slightly larger LR for lower mastery
    new_skill = cur_skill + lr * (outcome - expected)
    # clamp
    new_skill = max(0.01, min(0.99, new_skill))
    skp.mastery_level = new_skill
    skp.assessment_count = (skp.assessment_count or 0) + 1
    skp.last_assessed = datetime.now(timezone.utc)
    db.add(skp)
    db.commit()
    db.refresh(skp)

    # Update the assessment counters
    assessment.questions_answered = (assessment.questions_answered or 0) + 1

    # Update assessment-level difficulty (guides next question)
    try:
        cur_val = difficulty_float_from_label(assessment.difficulty_level or "medium")
    except Exception:
        cur_val = 0.5

    if is_correct:
        cur_val = min(1.0, cur_val + 0.12)
    else:
        cur_val = max(0.05, cur_val - 0.2)
    assessment.difficulty_level = difficulty_label_from_value(cur_val)

    # Update student's subject checkpoint if necessary
    # Load student profile
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == assessment.student_id).first()
    if profile:
        cps = ensure_profile_checkpoints(profile)
        subj = ka.subject.lower() if ka.subject else "english"
        # if the mastery for this KA dropped low, set checkpoint to this KA.subtopic
        if skp.mastery_level < 0.35:
            # set checkpoint entry for this subtopic
            key = ka.subtopic or ka.topic
            cps[subj][key] = {"grade_level": ka.grade_level, "mastery": skp.mastery_level, "updated_at": datetime.now(timezone.utc).isoformat()}
            save_profile_checkpoints(db, profile, cps)

    # Decide if assessment should finish
    if assessment.questions_answered >= MAX_QUESTIONS_PER_ASSESSMENT:
        assessment.status = "completed"
        assessment.completed_at = datetime.now(timezone.utc)
        answers_scores = [q.score or 0.0 for q in assessment.questions]
        assessment.overall_score = (sum(answers_scores) / len(answers_scores)) * 100 if answers_scores else None
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return {
            "question": question,
            "is_correct": is_correct,
            "next_question": None,
            "assessment_completed": True
        }

    # Otherwise pick next topic & difficulty
    sel = pick_next_topic_and_difficulty(db, assessment.student_id, assessment.subject, assessment=assessment)
    # ensure not exceeding per-topic cap - if so, pick again (simple loop with safety)
    attempts = 0
    while attempts < 3 and count_questions_for_topic(db, assessment, sel["topic"]) >= MAX_PER_TOPIC:
        sel = pick_next_topic_and_difficulty(db, assessment.student_id, assessment.subject, assessment=assessment)
        attempts += 1

    if count_questions_for_topic(db, assessment, sel["topic"]) >= MAX_PER_TOPIC:
        # can't generate more questions for any topic (fall back to end)
        assessment.status = "completed"
        assessment.completed_at = datetime.now(timezone.utc)
        answers_scores = [q.score or 0.0 for q in assessment.questions]
        assessment.overall_score = (sum(answers_scores) / len(answers_scores)) * 100 if answers_scores else None
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return {
            "question": question,
            "is_correct": is_correct,
            "next_question": None,
            "assessment_completed": True
        }

    # Create next question
    next_order = _next_question_number(db, assessment)
    next_q = await create_question(db, assessment, sel.get("topic"), sel.get("subtopic"), sel.get("difficulty"), order=next_order)

    # Return updated question and the next question
    return {
        "question": question,
        "is_correct": is_correct,
        "next_question": next_q,
        "assessment_completed": False
    }

# ---------- Process completed assessment and generate summary ----------
def get_subtopic_mastery_results_for_assessment(db: Session, assessment_id: int):
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

def get_or_create_assessment_report(db: Session, assessment_id: int, student_name: str, grade_level: int) -> Dict[str, Any]:
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


def process_completed_assessment(db: Session, assessment_id :int, student_name: str, grade_level: int) -> Dict[str, Any]:

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


def db_query_for_diagnostic(db: Session, assessment_id: int):
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
        from assessment_questions inner join question_bank as qb on qb.id = question_bank_id  where assessment_id = 7
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
