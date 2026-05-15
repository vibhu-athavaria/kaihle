"""Static questionnaire configuration for student learning profile onboarding.

This module defines the questionnaire structure used to collect
student learning preferences during onboarding.
"""

from typing import Any, cast

# Questionnaire version identifier
QUESTIONNAIRE_VERSION = "v2"

# ---------------------------------------------------------------------------
# V2 Questionnaire — 7 questions
# Q1-Q3: scenario-based modality (plurality vote → dominant/secondary)
# Q4-Q5: work style (short_sessions, concept_first)
# Q6: interest category (direct single-select → canonical interest key)
# Q7: challenge response (persists/paces/collaborative/avoidant)
# ---------------------------------------------------------------------------
QUESTIONNAIRE_V2: dict[str, Any] = {
    "version": "v2",
    "questions": [
        {
            "id": "q1",
            "text": "Your teacher just introduced a concept you've never heard of. Which would help you most right now?",
            "type": "single_select",
            "options": [
                {
                    "key": "watch_walkthrough",
                    "text": "Watch a short video walkthrough",
                    "maps_to": {"modality": "auditory"},
                },
                {
                    "key": "read_explanation",
                    "text": "Read a clear written explanation with examples",
                    "maps_to": {"modality": "reading_writing"},
                },
                {
                    "key": "try_problems",
                    "text": "Try some practice problems straight away",
                    "maps_to": {"modality": "kinesthetic"},
                },
                {
                    "key": "see_diagram",
                    "text": "See a diagram showing how it connects to things I know",
                    "maps_to": {"modality": "visual"},
                },
            ],
        },
        {
            "id": "q2",
            "text": "You have to explain what you just learned to a friend. How do you naturally do it?",
            "type": "single_select",
            "options": [
                {
                    "key": "draw_it",
                    "text": "Draw it out or sketch a diagram",
                    "maps_to": {"modality": "visual"},
                },
                {
                    "key": "talk_through",
                    "text": "Talk through it step by step",
                    "maps_to": {"modality": "auditory"},
                },
                {
                    "key": "write_points",
                    "text": "Write out the key points",
                    "maps_to": {"modality": "reading_writing"},
                },
                {
                    "key": "show_example",
                    "text": "Show them a worked example",
                    "maps_to": {"modality": "kinesthetic"},
                },
            ],
        },
        {
            "id": "q3",
            "text": "You're stuck on a problem. What's your first move?",
            "type": "single_select",
            "options": [
                {
                    "key": "reread_alone",
                    "text": "Re-read the question and think it through alone",
                    "maps_to": {"modality": "reading_writing"},
                },
                {
                    "key": "find_example",
                    "text": "Look for a worked example to guide me",
                    "maps_to": {"modality": "visual"},
                },
                {
                    "key": "ask_someone",
                    "text": "Ask someone to talk it through with me",
                    "maps_to": {"modality": "auditory"},
                },
                {
                    "key": "try_different",
                    "text": "Try a slightly different problem first",
                    "maps_to": {"modality": "kinesthetic"},
                },
            ],
        },
        {
            "id": "q4",
            "text": "Which study setup feels most like you?",
            "type": "single_select",
            "options": [
                {
                    "key": "short_focused",
                    "text": "Headphones in, short focused bursts, then a break",
                    "maps_to": {"work_style": "short_sessions", "value": True},
                },
                {
                    "key": "long_deep",
                    "text": "Long uninterrupted session at a desk",
                    "maps_to": {"work_style": "short_sessions", "value": False},
                },
                {
                    "key": "with_friends",
                    "text": "Studying with friends or in a group",
                    "maps_to": {"work_style": "prefers_solo", "value": False},
                },
                {
                    "key": "on_the_move",
                    "text": "Moving around — I can't sit still for long",
                    "maps_to": {"work_style": "short_sessions", "value": True},
                },
            ],
        },
        {
            "id": "q5",
            "text": "When you start a new unit, what do you prefer?",
            "type": "single_select",
            "options": [
                {
                    "key": "big_picture",
                    "text": "Understand the big picture first, then the details",
                    "maps_to": {"work_style": "concept_first", "value": True},
                },
                {
                    "key": "dive_in",
                    "text": "Dive straight into examples and problems",
                    "maps_to": {"work_style": "concept_first", "value": False},
                },
                {
                    "key": "either_way",
                    "text": "Either works — depends on the topic",
                    "maps_to": {"work_style": "concept_first", "value": None},
                },
            ],
        },
        {
            "id": "q6",
            "text": "If your lessons could use examples from one of these, which would feel most exciting to you?",
            "type": "single_select",
            "maps_to": "interest_category",
            "options": [
                {"key": "sports_movement", "text": "Sports, fitness and movement", "emoji": "⚽"},
                {"key": "tech_gaming", "text": "Technology, gaming and how things are built", "emoji": "💻"},
                {"key": "nature_animals", "text": "Nature, animals and the living world", "emoji": "🌿"},
                {"key": "arts_culture", "text": "Art, music, stories and culture", "emoji": "🎨"},
            ],
        },
        {
            "id": "q7",
            "text": "When something feels really hard, what do you usually do?",
            "type": "single_select",
            "maps_to": "challenge_response",
            "options": [
                {"key": "persists", "text": "Keep trying — I get more determined"},
                {"key": "paces", "text": "Take a break and come back to it"},
                {"key": "collaborative", "text": "Ask for help straight away"},
                {"key": "avoidant", "text": "I usually feel like giving up"},
            ],
        },
    ],
}

# Subject-to-interest compatibility mapping.
#
# Purpose: prevents injecting irrelevant student interests into quiz generation prompts.
# quiz_generator.py calls get_compatible_interests() before building the LLM prompt.
# Only interests that fit the subject's Cambridge curriculum content are passed through.
#
# If a student's interests produce an empty list for the current subject, the quiz
# is generated without personalisation. A plain quiz is always better than a
# forced scenario that damages question quality.
#
# Decision rationale: docs/tasks/M0/M0-6-T5_questionnaire_content_review.md
# Vidhya review: docs/design/QUESTIONNAIRE_DESIGN_RATIONALE.md
#
# Note: v2 interest keys (sports_movement, tech_gaming, nature_animals, arts_culture)
# are canonical category keys, not the fine-grained v1 keys. The map below preserves
# v1 keys for backward compatibility with existing profiles. v2 category keys return
# empty lists — callers skip personalisation for now (no crash).
SUBJECT_INTEREST_MAP: dict[str, list[str]] = {
    "MATH": ["sports", "music", "gaming", "cooking", "art", "technology"],
    "SCI": ["animals", "cooking", "nature", "sports"],
    "ENG": ["travel", "music", "art", "nature"],
    "BIO": ["animals", "nature", "cooking", "sports"],
    "CHEM": ["cooking", "nature", "technology"],
    "PHY": ["sports", "music", "gaming", "technology"],
    "ENGL": ["travel", "music", "art"],
    # Note: 'fashion' is absent from all subjects intentionally.
    # Students who select it receive unpersonalised quizzes — not a bug.
}


def get_compatible_interests(
    subject_code: str,
    student_interests: list[str],
) -> list[str]:
    """Return the student's interests that are compatible with the given subject.

    Called by quiz_generator.py before building the personalisation prompt section.
    Returns an empty list if no compatible interests exist — the caller then skips
    personalisation entirely rather than injecting a mismatched interest.

    Args:
        subject_code: Cambridge subject code e.g. "MATH", "BIO", "PHY".
                      Case-insensitive — "math" and "MATH" produce the same result.
        student_interests: List of interest keys from student_learning_profiles.interests.
                           Preserves the student's original preference order.

    Returns:
        Filtered list of interest keys compatible with this subject.
        Empty list if none match or if subject_code is unknown.

    Example:
        student has interests = ["fashion", "sports", "music"]

        get_compatible_interests("PHY", ["fashion", "sports", "music"])
        → ["sports", "music"]   # fashion excluded; sports + music in PHY map

        get_compatible_interests("PHY", ["fashion"])
        → []   # no compatible interests → caller skips personalisation
    """
    compatible = SUBJECT_INTEREST_MAP.get(subject_code.upper(), [])
    return [interest for interest in student_interests if interest in compatible]


def get_questionnaire_definition() -> dict[str, Any]:
    """Return the full questionnaire definition.

    Returns:
        Dictionary containing questionnaire version and questions.
    """
    return QUESTIONNAIRE_V2


def get_question_by_id(question_id: str) -> dict[str, Any] | None:
    """Get a specific question by its ID.

    Args:
        question_id: The question identifier (e.g., "q1", "q2", etc.)

    Returns:
        Question dictionary or None if not found.
    """
    for question in QUESTIONNAIRE_V2["questions"]:
        if question["id"] == question_id:
            return cast(dict[str, Any], question)
    return None


def get_option_by_key(question_id: str, option_key: str) -> dict[str, Any] | None:
    """Get a specific option by question ID and option key.

    Args:
        question_id: The question identifier.
        option_key: The option key (e.g., "watch_walkthrough", "draw_it", etc.)

    Returns:
        Option dictionary or None if not found.
    """
    question = get_question_by_id(question_id)
    if not question:
        return None

    for option in question.get("options", []):
        if option["key"] == option_key:
            return cast(dict[str, Any], option)
    return None


# ---------------------------------------------------------------------------
# Interest category mapping
# ---------------------------------------------------------------------------
# Used to tag subtopic_content with interest categories for personalisation.
# Maps interest keys to category names.
# v1 fine-grained keys and v2 canonical category keys are both supported.
# Service layer resolves names to UUIDs.

INTEREST_KEY_TO_CATEGORY: dict[str, str] = {
    # v1 fine-grained keys (backward compatibility)
    "travel": "Adventure & Exploration",
    "music": "Music & Arts",
    "art": "Music & Arts",
    "nature": "Nature & Science",
    "animals": "Nature & Science",
    "cooking": "Everyday Life",
    "sports": "Sports & Fitness",
    "technology": "Technology & Innovation",
    "gaming": "Technology & Innovation",
    "fashion": "Everyday Life",
    # v2 canonical category keys
    "sports_movement": "Sports & Fitness",
    "tech_gaming": "Technology & Innovation",
    "nature_animals": "Nature & Science",
    "arts_culture": "Music & Arts",
}


def get_interest_category(interest_key: str) -> str | None:
    """Return the interest category name for a given interest key.

    Used when tagging subtopic_content rows with an interest_category_id
    during content generation so that content can be personalised for
    students who share that interest.

    Args:
        interest_key: An interest option key from the onboarding questionnaire.
                     Supports both v1 fine-grained keys (e.g. "sports", "music")
                     and v2 canonical category keys (e.g. "sports_movement").

    Returns:
        The matching interest category name, or None if the key is unknown.

    Example:
        get_interest_category("sports")          → "Sports & Fitness"
        get_interest_category("sports_movement") → "Sports & Fitness"
        get_interest_category("unknown")         → None
    """
    return INTEREST_KEY_TO_CATEGORY.get(interest_key.lower())


def get_all_interest_categories() -> list[str]:
    """Return the set of all distinct interest category names."""
    return sorted(set(INTEREST_KEY_TO_CATEGORY.values()))
