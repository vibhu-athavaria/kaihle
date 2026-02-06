# app/services/students.py
from typing import TypedDict, List

class LearningIntakeAnswers(TypedDict, total=False):
    instructional_support: List[str]
    attention_span: str
    learning_difficulties: List[str]
    interest_themes: List[str]
    demonstrate_learning: List[str]


class LearningStyleProfile(TypedDict):
    scaffolding_level: str  # "low" | "medium" | "high"
    example_dependency: bool
    exploration_tolerance: str  # "low" | "high"


class AttentionProfile(TypedDict):
    focus_duration_minutes: int
    preferred_chunk_size_minutes: int


class AccessibilityFlags(TypedDict):
    reading_load_sensitive: bool
    attention_regulation_support: bool
    auditory_memory_support: bool
    visual_simplicity_required: bool


class NormalizedLearningProfile(TypedDict):
    learning_style: LearningStyleProfile
    attention_profile: AttentionProfile
    accessibility_flags: AccessibilityFlags
    interest_signals: List[str]
    expression_preferences: List[str]


def normalize_learning_profile(
    raw: LearningIntakeAnswers
) -> NormalizedLearningProfile:
    instructional = raw.get("instructional_support", [])
    attention = raw.get("attention_span")

    learning_style: LearningStyleProfile = {
        "scaffolding_level": "high" if "step_by_step" in instructional else "medium",
        "example_dependency": "worked_examples" in instructional,
        "exploration_tolerance": "high" if "exploration" in instructional else "low",
    }

    attention_profile: AttentionProfile = {
        "focus_duration_minutes": {
            "lt_10": 5,
            "10_20": 15,
            "20_30": 25,
            "gt_30": 40,
        }.get(attention, 15),
        "preferred_chunk_size_minutes": 5,
    }

    accessibility_flags: AccessibilityFlags = {
        "reading_load_sensitive": "reading_text" in raw.get("learning_difficulties", []),
        "attention_regulation_support": "sustained_attention" in raw.get("learning_difficulties", []),
        "auditory_memory_support": "auditory_memory" in raw.get("learning_difficulties", []),
        "visual_simplicity_required": "visual_sensitivity" in raw.get("learning_difficulties", []),
    }

    return {
        "learning_style": learning_style,
        "attention_profile": attention_profile,
        "accessibility_flags": accessibility_flags,
        "interest_signals": raw.get("interest_themes", []),
        "expression_preferences": raw.get("demonstrate_learning", []),
    }
