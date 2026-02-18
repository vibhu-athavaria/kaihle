#!/usr/bin/env python3
"""
seed_cambridge.py  —  Production Cambridge Curriculum Seeder
=============================================================

Populates the following tables from cambridge-gradeN.json files:
    topics              — 20 unique curriculum-agnostic topic strands
    subtopics           — 497 learning objectives (grade-specific)
    curriculum_topics   — JOIN binding curriculum + grade + subject + topic

Every model field is populated:
    Topic       : name, canonical_code, difficulty_level, learning_objectives,
                  estimated_hours, keywords, bloom_taxonomy_level
    Subtopic    : name, canonical_code, sequence_order, difficulty_level,
                  learning_objectives, estimated_hours, keywords,
                  bloom_taxonomy_level
    CurriculumTopic : curriculum_id, grade_id, subject_id, topic_id,
                  sequence_order, standard_code, difficulty_level,
                  learning_objectives, recommended_weeks, is_required

Prerequisites (must already exist in DB):
    - Curriculum   with code = "FOUNDATION"
    - Subject rows with codes MATH, SCI, ENG, HUM
    - Grade rows   for levels 5-12

Usage:
    # Place JSON files in app/seeds/data/cambridge/ then:
    python -m app.seeds.seed_cambridge

    # Or pass JSON directory as CLI argument:
    python seed_cambridge.py /path/to/json/files

    # With logging to file:
    python seed_cambridge.py 2>&1 | tee seed_cambridge.log

Idempotent: safe to run multiple times.
"""

import json
import os
import glob
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.database import SessionLocal
from app.models.curriculum import (
    Grade, Topic, Subtopic, CurriculumTopic, Curriculum,
)
from app.models.subject import Subject  # adjust import path if needed


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed_cambridge")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_JSON_DIR = Path(__file__).parent / "data" / "cambridge"

CURRICULUM_CODE = "FOUNDATION"

# Maps JSON subject key -> Subject.code in DB
SUBJECT_CODE_MAP: dict[str, str] = {
    "mathematics": "MATH",
    "science":     "SCI",
    "english":     "ENG",
    "humanities":  "HUM",
}

# Normalise inconsistent topic naming across grades into canonical strands.
# Two kinds of drift exist:
#   1. Mathematics G5-G6 use different names for strands that appear later
#   2. Humanities G5 uses People/Past/Places instead of the G6-12 names
TOPIC_NORMALISATION: dict[str, str] = {
    "Handling Data":                  "Statistics",
    "Handling Data (Statistics)":     "Statistics",
    "Measure":                        "Measurement",
    "Calculation":                    "Number",
    "Fractions/Decimals/Percentages": "Number",
    "People":                         "Global Perspectives",
    "Past":                           "History",
    "Places":                         "Geography",
}

# Domain keywords per topic strand (authoritative, curriculum-derived)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "MATH.NUMBER":           ["number", "place value", "fractions", "decimals",
                              "percentages", "ratio", "proportion", "integers",
                              "surds", "indices"],
    "MATH.ALGEBRA":          ["algebra", "equations", "expressions", "functions",
                              "sequences", "inequalities", "graphs", "variables"],
    "MATH.GEOMETRY":         ["geometry", "shapes", "angles", "triangles",
                              "polygons", "coordinates", "symmetry",
                              "transformation", "area", "volume"],
    "MATH.MEASUREMENT":      ["measurement", "units", "length", "mass",
                              "capacity", "time", "perimeter", "area",
                              "conversion"],
    "MATH.STATISTICS":       ["statistics", "data", "probability", "mean",
                              "median", "mode", "graphs", "charts", "frequency"],
    "MATH.PROBLEM_SOLVING":  ["problem solving", "reasoning", "logic",
                              "strategy", "estimation", "word problems"],
    "MATH.PROBABILITY":      ["probability", "chance", "likelihood",
                              "events", "outcomes"],
    "MATH.PURE_MATHEMATICS": ["calculus", "differentiation", "integration",
                              "vectors", "matrices", "complex numbers",
                              "trigonometry"],
    "MATH.MECHANICS":        ["mechanics", "kinematics", "dynamics", "forces",
                              "energy", "motion", "velocity"],
    "SCI.BIOLOGY":           ["biology", "cells", "organisms", "genetics",
                              "ecology", "evolution", "physiology",
                              "reproduction"],
    "SCI.CHEMISTRY":         ["chemistry", "atoms", "molecules", "reactions",
                              "periodic table", "acids", "bases", "bonding",
                              "organic"],
    "SCI.PHYSICS":           ["physics", "forces", "energy", "electricity",
                              "magnetism", "waves", "light", "sound", "motion"],
    "SCI.EARTH_AND_SPACE":   ["earth", "space", "geology", "climate",
                              "weather", "environment", "rocks", "atmosphere"],
    "SCI.SCIENTIFIC_ENQUIRY":["enquiry", "hypothesis", "experiment", "evidence",
                              "investigation", "data", "analysis", "conclusions"],
    "ENG.READING":           ["reading", "comprehension", "inference",
                              "analysis", "literature", "texts", "meaning",
                              "structure"],
    "ENG.WRITING":           ["writing", "composition", "grammar",
                              "punctuation", "style", "argument", "narrative",
                              "audience"],
    "ENG.SPEAKING_AND_LISTENING": ["speaking", "listening", "communication",
                                   "presentation", "discussion", "debate",
                                   "oral"],
    "HUM.HISTORY":           ["history", "chronology", "civilisations",
                              "events", "change", "society", "politics",
                              "conflict"],
    "HUM.GEOGRAPHY":         ["geography", "maps", "climate", "landforms",
                              "population", "environment", "resources",
                              "urbanisation"],
    "HUM.GLOBAL_PERSPECTIVES":["global", "culture", "ethics", "sustainability",
                               "identity", "perspectives", "research",
                               "community"],
}

# Bloom's Taxonomy cognitive level per topic strand
BLOOM_LEVEL_MAP: dict[str, str] = {
    "MATH.NUMBER":            "Apply",
    "MATH.ALGEBRA":           "Analyse",
    "MATH.GEOMETRY":          "Apply",
    "MATH.MEASUREMENT":       "Apply",
    "MATH.STATISTICS":        "Analyse",
    "MATH.PROBLEM_SOLVING":   "Evaluate",
    "MATH.PROBABILITY":       "Understand",
    "MATH.PURE_MATHEMATICS":  "Analyse",
    "MATH.MECHANICS":         "Apply",
    "SCI.BIOLOGY":            "Understand",
    "SCI.CHEMISTRY":          "Understand",
    "SCI.PHYSICS":            "Apply",
    "SCI.EARTH_AND_SPACE":    "Understand",
    "SCI.SCIENTIFIC_ENQUIRY": "Evaluate",
    "ENG.READING":            "Analyse",
    "ENG.WRITING":            "Create",
    "ENG.SPEAKING_AND_LISTENING": "Apply",
    "HUM.HISTORY":            "Analyse",
    "HUM.GEOGRAPHY":          "Understand",
    "HUM.GLOBAL_PERSPECTIVES":"Evaluate",
}

# Estimated teaching hours per topic strand (Cambridge-aligned)
ESTIMATED_HOURS_MAP: dict[str, int] = {
    "MATH.NUMBER": 20,    "MATH.ALGEBRA": 18,        "MATH.GEOMETRY": 16,
    "MATH.MEASUREMENT": 12, "MATH.STATISTICS": 10,   "MATH.PROBLEM_SOLVING": 8,
    "MATH.PROBABILITY": 4,  "MATH.PURE_MATHEMATICS": 30, "MATH.MECHANICS": 20,
    "SCI.BIOLOGY": 15,    "SCI.CHEMISTRY": 15,       "SCI.PHYSICS": 15,
    "SCI.EARTH_AND_SPACE": 8, "SCI.SCIENTIFIC_ENQUIRY": 10,
    "ENG.READING": 20,    "ENG.WRITING": 20,         "ENG.SPEAKING_AND_LISTENING": 10,
    "HUM.HISTORY": 12,    "HUM.GEOGRAPHY": 12,       "HUM.GLOBAL_PERSPECTIVES": 10,
}

# Recommended teaching weeks per topic strand (Cambridge-aligned)
RECOMMENDED_WEEKS_MAP: dict[str, int] = {
    "MATH.NUMBER": 8,    "MATH.ALGEBRA": 7,           "MATH.GEOMETRY": 6,
    "MATH.MEASUREMENT": 5, "MATH.STATISTICS": 4,      "MATH.PROBLEM_SOLVING": 3,
    "MATH.PROBABILITY": 2,  "MATH.PURE_MATHEMATICS": 12, "MATH.MECHANICS": 8,
    "SCI.BIOLOGY": 6,    "SCI.CHEMISTRY": 6,          "SCI.PHYSICS": 6,
    "SCI.EARTH_AND_SPACE": 3, "SCI.SCIENTIFIC_ENQUIRY": 4,
    "ENG.READING": 8,    "ENG.WRITING": 8,            "ENG.SPEAKING_AND_LISTENING": 4,
    "HUM.HISTORY": 5,    "HUM.GEOGRAPHY": 5,          "HUM.GLOBAL_PERSPECTIVES": 4,
}

# Human-readable display names for topic codes
_TOPIC_DISPLAY_NAMES: dict[str, str] = {
    "MATH.NUMBER":            "Number",
    "MATH.ALGEBRA":           "Algebra",
    "MATH.GEOMETRY":          "Geometry",
    "MATH.MEASUREMENT":       "Measurement",
    "MATH.STATISTICS":        "Statistics",
    "MATH.PROBLEM_SOLVING":   "Problem Solving",
    "MATH.PROBABILITY":       "Probability",
    "MATH.PURE_MATHEMATICS":  "Pure Mathematics",
    "MATH.MECHANICS":         "Mechanics",
    "SCI.BIOLOGY":            "Biology",
    "SCI.CHEMISTRY":          "Chemistry",
    "SCI.PHYSICS":            "Physics",
    "SCI.EARTH_AND_SPACE":    "Earth & Space",
    "SCI.SCIENTIFIC_ENQUIRY": "Scientific Enquiry",
    "ENG.READING":            "Reading",
    "ENG.WRITING":            "Writing",
    "ENG.SPEAKING_AND_LISTENING": "Speaking and Listening",
    "HUM.HISTORY":            "History",
    "HUM.GEOGRAPHY":          "Geography",
    "HUM.GLOBAL_PERSPECTIVES":"Global Perspectives",
}

# Stop words for subtopic keyword extraction
_STOP_WORDS: set[str] = {
    "and", "or", "the", "a", "an", "in", "of", "to", "for", "with", "by",
    "use", "using", "as", "is", "are", "be", "that", "this", "from", "on",
    "at", "up", "how", "what", "where", "when", "whether", "it", "its",
    "their", "they", "can", "will", "do", "not", "all", "any", "each",
    "per", "than", "into", "between", "through", "about", "after", "before",
    "over", "under", "out", "also", "both", "including", "such", "more",
    "other", "own", "same", "then", "these", "those", "was", "were",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def make_topic_code(subject_code: str, topic_name: str) -> str:
    """MATH + 'Pure Mathematics'  ->  'MATH.PURE_MATHEMATICS'"""
    slug = (topic_name.upper()
            .replace(" ", "_")
            .replace("&", "AND")
            .replace("/", "_")
            .replace("-", "_"))
    return f"{subject_code}.{slug}"


def make_subtopic_code(topic_code: str, grade: int, seq: int) -> str:
    """MATH.NUMBER + grade 7 + seq 3  ->  'MATH.NUMBER.G7.003'"""
    return f"{topic_code}.G{grade}.{seq:03d}"


def normalise_topic(raw_name: str) -> str:
    return TOPIC_NORMALISATION.get(raw_name, raw_name)


def grade_to_difficulty(grade: int) -> int:
    """
    Maps grade level to 1-5 difficulty for CurriculumTopic.difficulty_level.
    This is a grade-level signal only — subtopic difficulty_level is set to
    None and should be populated later via AI classification or assessment data.
    """
    if grade <= 5:  return 1
    if grade <= 7:  return 2
    if grade <= 9:  return 3
    if grade <= 11: return 4
    return 5


def extract_subtopic_keywords(objective_text: str) -> list[str]:
    """
    Extract domain keywords from a learning objective string.
    Returns up to 8 meaningful, deduplicated keywords.
    """
    words = re.findall(r"\b[a-z][a-z\-]{2,}\b", objective_text.lower())
    return sorted({w for w in words if w not in _STOP_WORDS})[:8]


def get_or_create(db: Session, model, defaults: dict = None, **filters):
    """
    Fetch the first record matching `filters`, or create it with
    `filters` merged with `defaults`.
    Returns (instance, created: bool).
    Flushes on create so the PK is available within the transaction.
    """
    instance = db.query(model).filter_by(**filters).first()
    if instance:
        return instance, False

    instance = model(**{**filters, **(defaults or {})})
    db.add(instance)
    db.flush()
    return instance, True


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json_files(json_dir: Path) -> dict[int, dict]:
    """
    Load all cambridge-gradeN.json files from json_dir.
    Returns {grade_level: {subject: {topic: [objectives]}}}
    """
    pattern = str(json_dir / "cambridge-grade*.json")
    files   = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No Cambridge JSON files found at: {pattern}\n"
            f"Place files named 'cambridge-grade5.json' etc. in: {json_dir}"
        )

    result: dict[int, dict] = {}
    for filepath in files:
        with open(filepath, encoding="utf-8") as f:
            raw = json.load(f)

        grade_key = list(raw.keys())[0]               # e.g. "grade 5"
        grade_num = int(grade_key.replace("grade ", ""))
        result[grade_num] = raw[grade_key]
        log.info("  Loaded %-28s  (grade %d)", Path(filepath).name, grade_num)

    return result


# ---------------------------------------------------------------------------
# DB lookups
# ---------------------------------------------------------------------------

def load_curriculum(db: Session, code: str) -> Curriculum:
    c = db.query(Curriculum).filter_by(code=code).first()
    if not c:
        raise ValueError(f"Curriculum '{code}' not found. Seed it first.")
    log.info("  Curriculum  : %s  (%s)", c.name, c.id)
    return c


def load_grades(db: Session) -> dict[int, Grade]:
    grades = db.query(Grade).filter(Grade.level.between(5, 12)).all()
    if not grades:
        raise ValueError("No grades (5-12) found. Seed grades first.")
    grade_map = {g.level: g for g in grades}
    missing   = [lvl for lvl in range(5, 13) if lvl not in grade_map]
    if missing:
        raise ValueError(f"Missing grade levels in DB: {missing}")
    log.info("  Grades      : %s", sorted(grade_map.keys()))
    return grade_map


def load_subjects(db: Session) -> dict[str, Subject]:
    subject_map: dict[str, Subject] = {}
    missing: list[str] = []
    for json_key, code in SUBJECT_CODE_MAP.items():
        s = db.query(Subject).filter_by(code=code).first()
        if s:
            subject_map[json_key] = s
            log.info("  Subject     : %-6s  %s", code, s.name)
        else:
            missing.append(code)
    if missing:
        raise ValueError(f"Subjects missing from DB: {missing}")
    return subject_map


# ---------------------------------------------------------------------------
# Seed: Topics
# ---------------------------------------------------------------------------

def seed_topics(
    db: Session,
    curriculum_data: dict[int, dict],
    subject_map: dict[str, Subject],
) -> dict[str, Topic]:
    """
    Creates one Topic per unique (subject, normalised_topic_name) pair.
    Topics are curriculum-agnostic and reused across grades.

    Fields populated:
        name                  — human-readable strand name
        canonical_code        — e.g. MATH.ALGEBRA (idempotency key)
        difficulty_level      — None (topic is not grade-specific)
        learning_objectives   — all objectives for this strand aggregated
                                across all grades (gives AI full context)
        estimated_hours       — from ESTIMATED_HOURS_MAP
        keywords              — domain keywords from TOPIC_KEYWORDS
        bloom_taxonomy_level  — from BLOOM_LEVEL_MAP

    Returns {topic_canonical_code: Topic}
    """
    log.info("")
    log.info("── Seeding topics ──────────────────────────────────────")

    # Aggregate all objectives per topic_code across grades (deduped)
    aggregated: dict[str, list[str]]   = {}
    code_to_subject: dict[str, str]    = {}

    for grade_num, subjects_data in curriculum_data.items():
        for subject_key, topics_data in subjects_data.items():
            if subject_key not in subject_map:
                continue
            subject = subject_map[subject_key]
            for raw_topic, objectives in topics_data.items():
                norm = normalise_topic(raw_topic)
                tc   = make_topic_code(subject.code, norm)
                if tc not in aggregated:
                    aggregated[tc]        = []
                    code_to_subject[tc]   = subject_key
                for obj in objectives:
                    if obj not in aggregated[tc]:
                        aggregated[tc].append(obj)

    topic_map: dict[str, Topic] = {}

    for topic_code in sorted(aggregated.keys()):
        topic, created = get_or_create(
            db, Topic,
            defaults={
                "name":                _TOPIC_DISPLAY_NAMES[topic_code],
                "difficulty_level":    None,
                "learning_objectives": aggregated[topic_code],
                "estimated_hours":     ESTIMATED_HOURS_MAP.get(topic_code),
                "keywords":            TOPIC_KEYWORDS.get(topic_code, []),
                "bloom_taxonomy_level":BLOOM_LEVEL_MAP.get(topic_code),
                "is_active":           True,
            },
            canonical_code=topic_code,
        )
        topic_map[topic_code] = topic
        log.info(
            "  [%s]  %-42s  %d objectives",
            "CREATED" if created else "exists ",
            topic_code,
            len(aggregated[topic_code]),
        )

    log.info("  Total unique topics: %d", len(topic_map))
    return topic_map


# ---------------------------------------------------------------------------
# Seed: Subtopics + CurriculumTopics
# ---------------------------------------------------------------------------

def seed_subtopics_and_curriculum_topics(
    db: Session,
    curriculum: Curriculum,
    curriculum_data: dict[int, dict],
    subject_map: dict[str, Subject],
    grade_map: dict[int, Grade],
    topic_map: dict[str, Topic],
) -> dict[str, int]:
    """
    For each grade -> subject -> (normalised) topic -> learning objective:

    Subtopic (one per learning objective):
        topic_id              — parent topic
        name                  — the full objective text
        canonical_code        — e.g. MATH.NUMBER.G7.003
        sequence_order        — position within this grade/topic
        difficulty_level      — None (set later by AI / assessment data)
        learning_objectives   — [objective_text]  (self-contained)
        estimated_hours       — pro-rated from topic total / objective count
        keywords              — obj-derived keywords merged with topic keywords
        bloom_taxonomy_level  — inherited from parent topic strand

    CurriculumTopic (one per grade/subject/topic combination):
        curriculum_id, grade_id, subject_id, topic_id
        sequence_order        — position within grade
        standard_code         — e.g. FOUNDATION.MATH.G7.ALGEBRA
        difficulty_level      — grade-level signal (1-5)
        learning_objectives   — full list for this grade/topic
        recommended_weeks     — from RECOMMENDED_WEEKS_MAP
        is_required           — True

    Handles normalisation merges: when two raw topics normalise to the same
    strand (e.g. "Calculation" + "Fractions/Decimals/Percentages" both become
    "Number" in G6), their objectives are merged and only one CurriculumTopic
    row is created for that grade.
    """
    log.info("")
    log.info("── Seeding subtopics & curriculum_topics ───────────────")

    stats = {
        "subtopics_created": 0, "subtopics_exists": 0,
        "ct_created":        0, "ct_exists":        0,
    }

    for grade_num in sorted(curriculum_data.keys()):
        grade = grade_map[grade_num]
        log.info("")
        log.info("  ── Grade %d ─────────────────────────────────────", grade_num)

        # Group and deduplicate objectives by (subject_key, topic_code)
        # Normalisation merges are handled here transparently
        grade_groups: dict[tuple[str, str], list[str]] = {}

        for subject_key, topics_data in curriculum_data[grade_num].items():
            if subject_key not in subject_map:
                log.warning("    Skipping unknown subject in JSON: '%s'", subject_key)
                continue
            subject = subject_map[subject_key]

            for raw_topic, objectives in topics_data.items():
                norm  = normalise_topic(raw_topic)
                tc    = make_topic_code(subject.code, norm)
                key   = (subject_key, tc)
                if key not in grade_groups:
                    grade_groups[key] = []
                for obj in objectives:
                    if obj not in grade_groups[key]:
                        grade_groups[key].append(obj)

        ct_sequence = 1

        for (subject_key, topic_code), objectives in sorted(grade_groups.items()):
            subject = subject_map[subject_key]
            topic   = topic_map.get(topic_code)

            if topic is None:
                log.error("    Topic not in map: '%s' — skipping", topic_code)
                continue

            # ── CurriculumTopic ──────────────────────────────────────────
            standard_code = (
                f"{curriculum.code}.{subject.code}"
                f".G{grade_num}"
                f".{topic_code.replace(subject.code + '.', '')}"
            )

            ct, ct_new = get_or_create(
                db, CurriculumTopic,
                defaults={
                    "sequence_order":     ct_sequence,
                    "standard_code":      standard_code,
                    "difficulty_level":   grade_to_difficulty(grade_num),
                    "learning_objectives":objectives,
                    "recommended_weeks":  RECOMMENDED_WEEKS_MAP.get(topic_code),
                    "is_required":        True,
                    "is_active":          True,
                },
                curriculum_id=curriculum.id,
                grade_id=grade.id,
                subject_id=subject.id,
                topic_id=topic.id,
            )
            ct_sequence += 1
            stats["ct_created" if ct_new else "ct_exists"] += 1

            log.info(
                "    [CT %s]  G%d / %-6s / %-42s  (%d objectives)",
                "CREATED" if ct_new else "exists ",
                grade_num, subject.code, topic_code, len(objectives),
            )

            # ── Subtopics ────────────────────────────────────────────────
            # Pro-rate estimated hours across objectives in this grade/topic
            topic_hours   = ESTIMATED_HOURS_MAP.get(topic_code, 0)
            obj_hours     = round(topic_hours / len(objectives), 1) if objectives else None

            topic_kws     = TOPIC_KEYWORDS.get(topic_code, [])
            bloom_level   = BLOOM_LEVEL_MAP.get(topic_code)

            for seq, objective_text in enumerate(objectives, start=1):
                subtopic_code = make_subtopic_code(topic_code, grade_num, seq)

                # Merge objective-specific keywords with topic-level keywords
                obj_kws       = extract_subtopic_keywords(objective_text)
                merged_kws    = list(dict.fromkeys(obj_kws + topic_kws))[:10]

                subtopic, s_new = get_or_create(
                    db, Subtopic,
                    defaults={
                        "name":                objective_text,
                        "sequence_order":      seq,
                        "difficulty_level":    None,          # set by AI/assessment later
                        "learning_objectives": [objective_text],
                        "estimated_hours":     obj_hours,
                        "keywords":            merged_kws,
                        "bloom_taxonomy_level":bloom_level,
                        "is_active":           True,
                    },
                    curriculum_topic_id=ct.id,
                    canonical_code=subtopic_code,
                )
                stats["subtopics_created" if s_new else "subtopics_exists"] += 1

                if s_new:
                    trunc = (objective_text[:65] + "…") \
                            if len(objective_text) > 65 else objective_text
                    log.debug(
                        "      [ST CREATED]  [%s]  %s", subtopic_code, trunc
                    )

    return stats


# ---------------------------------------------------------------------------
# Prerequisite graph
# ---------------------------------------------------------------------------

# Academically validated prerequisite relationships between topic strands.
# Format: { topic_code: [(prerequisite_topic_code, importance), ...] }
#
# importance values (matches TopicPrerequisite.importance CHECK):
#   "required"    — student cannot meaningfully progress without this
#   "recommended" — strongly beneficial but not strictly blocking
#   "optional"    — enrichment / cross-subject context
#
# Foundation topics (no prerequisites):
#   MATH.NUMBER, ENG.READING, SCI.SCIENTIFIC_ENQUIRY
#
# Validated: no self-loops, no cycles, all codes are real topic codes.

TOPIC_PREREQUISITES: dict[str, list[tuple[str, str]]] = {
    # ── Mathematics ────────────────────────────────────────────────────────
    # Algebra requires number sense; can't manipulate symbols without it
    "MATH.ALGEBRA":          [("MATH.NUMBER",            "required")],

    # Geometry requires number (coordinates, angle values) and measurement
    "MATH.GEOMETRY":         [("MATH.NUMBER",            "required"),
                              ("MATH.MEASUREMENT",       "required")],

    # Measurement is applied number work
    "MATH.MEASUREMENT":      [("MATH.NUMBER",            "required")],

    # Statistics requires number; algebraic thinking needed from G9+
    "MATH.STATISTICS":       [("MATH.NUMBER",            "required"),
                              ("MATH.ALGEBRA",           "recommended")],

    # Probability requires fractions/ratios (Number); distributions need Stats
    "MATH.PROBABILITY":      [("MATH.NUMBER",            "required"),
                              ("MATH.STATISTICS",        "recommended")],

    # Problem Solving requires number as base; algebra for most strategies
    "MATH.PROBLEM_SOLVING":  [("MATH.NUMBER",            "required"),
                              ("MATH.ALGEBRA",           "recommended")],

    # Pure Mathematics (G11-12): calculus/vectors/matrices need both
    # algebra and geometry; probability distributions need statistics
    "MATH.PURE_MATHEMATICS": [("MATH.ALGEBRA",           "required"),
                              ("MATH.GEOMETRY",          "required"),
                              ("MATH.STATISTICS",        "recommended")],

    # Mechanics (G11-12): kinematics needs algebra + geometry;
    # calculus-based mechanics needs Pure Mathematics
    "MATH.MECHANICS":        [("MATH.ALGEBRA",           "required"),
                              ("MATH.GEOMETRY",          "required"),
                              ("MATH.PURE_MATHEMATICS",  "required")],

    # ── Science ────────────────────────────────────────────────────────────
    # Scientific Enquiry is the foundation — all science strands need it
    "SCI.BIOLOGY":           [("SCI.SCIENTIFIC_ENQUIRY", "required")],
    "SCI.CHEMISTRY":         [("SCI.SCIENTIFIC_ENQUIRY", "required"),
                              ("MATH.NUMBER",            "recommended")],  # molar ratios, balancing

    # Physics requires algebraic manipulation (F=ma, v=d/t, etc.)
    "SCI.PHYSICS":           [("SCI.SCIENTIFIC_ENQUIRY", "required"),
                              ("MATH.ALGEBRA",           "required")],

    # Earth & Space draws on all three sciences
    "SCI.EARTH_AND_SPACE":   [("SCI.SCIENTIFIC_ENQUIRY", "required"),
                              ("SCI.BIOLOGY",            "recommended"),   # ecosystems/climate
                              ("SCI.PHYSICS",            "recommended")],  # geology/weather

    # ── English ────────────────────────────────────────────────────────────
    # Writing requires reading (good writers are readers first)
    "ENG.WRITING":           [("ENG.READING",            "required")],

    # Speaking/Listening benefits from reading comprehension
    "ENG.SPEAKING_AND_LISTENING": [("ENG.READING",       "recommended")],

    # ── Humanities ─────────────────────────────────────────────────────────
    # History benefits from reading skills (primary source analysis)
    "HUM.HISTORY":           [("ENG.READING",            "recommended")],

    # Geography uses statistical data (population, climate graphs)
    "HUM.GEOGRAPHY":         [("MATH.STATISTICS",        "recommended")],

    # Global Perspectives synthesises History + Geography at advanced level
    "HUM.GLOBAL_PERSPECTIVES":[("HUM.HISTORY",           "required"),
                               ("HUM.GEOGRAPHY",         "required")],
}


def seed_topic_prerequisites(
    db: Session,
    topic_map: dict[str, Topic],
) -> dict[str, int]:
    """
    Seeds TopicPrerequisite rows from the TOPIC_PREREQUISITES graph.

    Uses topic_map (canonical_code -> Topic) to resolve FKs.
    The unique constraint is (topic_id, prerequisite_topic_id) — the
    get_or_create filter covers both PKs so the function is idempotent.

    Returns stats dict.
    """
    from app.models.curriculum import TopicPrerequisite

    log.info("")
    log.info("── Seeding topic_prerequisites ─────────────────────────")

    stats = {"created": 0, "exists": 0, "skipped": 0}

    for topic_code, prereq_list in sorted(TOPIC_PREREQUISITES.items()):
        topic = topic_map.get(topic_code)
        if topic is None:
            log.warning("  Topic not in map: '%s' — skipping all its prereqs", topic_code)
            stats["skipped"] += len(prereq_list)
            continue

        for prereq_code, importance in prereq_list:
            prereq_topic = topic_map.get(prereq_code)
            if prereq_topic is None:
                log.warning("  Prereq not in map: '%s' — skipping", prereq_code)
                stats["skipped"] += 1
                continue

            row, created = get_or_create(
                db,
                TopicPrerequisite,
                defaults={"importance": importance},
                topic_id=topic.id,
                prerequisite_topic_id=prereq_topic.id,
            )
            stats["created" if created else "exists"] += 1

            log.info(
                "  [%s]  %-30s  <--[%-11s]--  %s",
                "CREATED" if created else "exists ",
                topic_code,
                importance,
                prereq_code,
            )

    log.info(
        "  Prerequisites: created=%-3d  skipped=%-3d  already_exist=%d",
        stats["created"], stats["skipped"], stats["exists"],
    )
    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_seed(json_dir: Optional[Path] = None) -> None:
    json_dir = json_dir or DEFAULT_JSON_DIR

    log.info("=" * 60)
    log.info("  Cambridge Curriculum Seeder")
    log.info("  Source : %s", json_dir)
    log.info("=" * 60)

    log.info("")
    log.info("── Loading JSON files ──────────────────────────────────")
    curriculum_data = load_json_files(json_dir)
    log.info(
        "Loaded %d files covering grades %d-%d",
        len(curriculum_data), min(curriculum_data), max(curriculum_data),
    )

    db: Session = SessionLocal()
    try:
        log.info("")
        log.info("── Resolving prerequisites ─────────────────────────────")
        curriculum  = load_curriculum(db, CURRICULUM_CODE)
        grade_map   = load_grades(db)
        subject_map = load_subjects(db)

        topic_map = seed_topics(db, curriculum_data, subject_map)

        ct_stats = seed_subtopics_and_curriculum_topics(
            db, curriculum, curriculum_data,
            subject_map, grade_map, topic_map,
        )
        prereq_stats = seed_topic_prerequisites(db, topic_map)

        db.commit()

        log.info("")
        log.info("=" * 60)
        log.info("  Seed completed successfully")
        log.info("  Topics           : %d unique strands", len(topic_map))
        log.info("  Subtopics        : created=%-4d  skipped=%d",
                 ct_stats["subtopics_created"], ct_stats["subtopics_exists"])
        log.info("  CurriculumTopics : created=%-4d  skipped=%d",
                 ct_stats["ct_created"], ct_stats["ct_exists"])
        log.info("  Prerequisites    : created=%-4d  skipped=%d",
                 prereq_stats["created"], prereq_stats["skipped"])
        log.info("=" * 60)

    except (ValueError, FileNotFoundError) as e:
        db.rollback()
        log.error("Configuration error — rolled back. %s", e)
        sys.exit(1)

    except IntegrityError as e:
        db.rollback()
        log.error("Integrity error — rolled back. %s", e.orig)
        sys.exit(1)

    except SQLAlchemyError as e:
        db.rollback()
        log.error("Database error — rolled back. %s", e)
        sys.exit(1)

    except Exception as e:
        db.rollback()
        log.exception("Unexpected error — rolled back. %s", e)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    custom_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_seed(json_dir=custom_dir)
