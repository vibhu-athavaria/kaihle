"""Static questionnaire configuration for student learning profile onboarding.

This module defines the v1 questionnaire structure used to collect
student learning preferences during onboarding.
"""

from typing import Any

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
            return question
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
            return option
    return None
