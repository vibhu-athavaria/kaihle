"""Static questionnaire configuration for student learning profile onboarding.

This module defines the v1 questionnaire structure used to collect
student learning preferences during onboarding.
"""

from typing import Any, cast

# Questionnaire version identifier
QUESTIONNAIRE_VERSION = "v1"

# Questionnaire definition with 10 questions total
# Q1-Q2: modality questions (visual/auditory/reading_writing/kinesthetic)
# Q3-Q5: work style questions (prefers_solo, short_sessions, concept_first/task_based)
# Q6-Q10: interests multi-select (10 interest options)
QUESTIONNAIRE_V1: dict[str, Any] = {
    "version": "v1",
    "questions": [
        {
            "id": "q1",
            "text": "When learning something new, I prefer to...",
            "type": "single_select",
            "options": [
                {
                    "key": "watch_video",
                    "text": "Watch a video explaining it",
                    "maps_to": {"modality": "visual"},
                },
                {
                    "key": "read_about_it",
                    "text": "Read about it",
                    "maps_to": {"modality": "reading_writing"},
                },
                {
                    "key": "try_it_out",
                    "text": "Try it out hands-on",
                    "maps_to": {"modality": "kinesthetic"},
                },
                {
                    "key": "discuss_it",
                    "text": "Discuss it with someone",
                    "maps_to": {"modality": "auditory"},
                },
            ],
        },
        {
            "id": "q2",
            "text": "I remember things best when...",
            "type": "single_select",
            "options": [
                {
                    "key": "see_diagrams",
                    "text": "I see diagrams or charts",
                    "maps_to": {"modality": "visual"},
                },
                {
                    "key": "hear_explained",
                    "text": "I hear them explained aloud",
                    "maps_to": {"modality": "auditory"},
                },
                {
                    "key": "write_notes",
                    "text": "I write notes about them",
                    "maps_to": {"modality": "reading_writing"},
                },
                {
                    "key": "do_exercise",
                    "text": "I do an exercise or activity",
                    "maps_to": {"modality": "kinesthetic"},
                },
            ],
        },
        {
            "id": "q3",
            "text": "I prefer to study...",
            "type": "single_select",
            "options": [
                {
                    "key": "solo",
                    "text": "Alone",
                    "maps_to": {"work_style": "prefers_solo", "value": True},
                },
                {
                    "key": "group",
                    "text": "With friends",
                    "maps_to": {"work_style": "prefers_solo", "value": False},
                },
            ],
        },
        {
            "id": "q4",
            "text": "I prefer study sessions that are...",
            "type": "single_select",
            "options": [
                {
                    "key": "short",
                    "text": "Short and frequent (20–30 min)",
                    "maps_to": {"work_style": "short_sessions", "value": True},
                },
                {
                    "key": "long",
                    "text": "Long and deep (1+ hour)",
                    "maps_to": {"work_style": "short_sessions", "value": False},
                },
            ],
        },
        {
            "id": "q5",
            "text": "I learn better by...",
            "type": "single_select",
            "options": [
                {
                    "key": "concept_first",
                    "text": "Understanding the theory first",
                    "maps_to": {"work_style": "concept_first", "value": True},
                },
                {
                    "key": "task_based",
                    "text": "Jumping straight into tasks",
                    "maps_to": {"work_style": "concept_first", "value": False},
                },
            ],
        },
        {
            "id": "q6_to_q10",
            "text": "Pick topics that interest you most (choose as many as you like)",
            "type": "multi_select",
            "maps_to": "interests",
            "options": [
                {"key": "sports", "text": "Sports", "emoji": "⚽"},
                {"key": "music", "text": "Music", "emoji": "🎵"},
                {"key": "gaming", "text": "Gaming", "emoji": "🎮"},
                {"key": "animals", "text": "Animals", "emoji": "🐾"},
                {"key": "cooking", "text": "Cooking", "emoji": "🍳"},
                {"key": "art", "text": "Art & Design", "emoji": "🎨"},
                {"key": "technology", "text": "Technology", "emoji": "💻"},
                {"key": "nature", "text": "Nature", "emoji": "🌿"},
                {"key": "fashion", "text": "Fashion", "emoji": "👗"},
                {"key": "travel", "text": "Travel", "emoji": "✈️"},
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
    return QUESTIONNAIRE_V1


def get_question_by_id(question_id: str) -> dict[str, Any] | None:
    """Get a specific question by its ID.

    Args:
        question_id: The question identifier (e.g., "q1", "q2", etc.)

    Returns:
        Question dictionary or None if not found.
    """
    for question in QUESTIONNAIRE_V1["questions"]:
        if question["id"] == question_id:
            return cast(dict[str, Any], question)
    return None


def get_option_by_key(question_id: str, option_key: str) -> dict[str, Any] | None:
    """Get a specific option by question ID and option key.

    Args:
        question_id: The question identifier.
        option_key: The option key (e.g., "watch_video", "solo", etc.)

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
