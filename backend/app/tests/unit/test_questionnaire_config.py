"""Unit tests for questionnaire_config module."""

from app.core.questionnaire_config import (
    SUBJECT_INTEREST_MAP,
    get_compatible_interests,
    get_option_by_key,
    get_question_by_id,
    get_questionnaire_definition,
)


class TestGetQuestionnaireDefinition:
    def test_get_questionnaire_definition_returns_dict(self):
        result = get_questionnaire_definition()
        assert isinstance(result, dict)
        assert "version" in result
        assert "questions" in result
        assert result["version"] == "v1"

    def test_get_questionnaire_definition_has_six_question_entries(self):
        result = get_questionnaire_definition()
        # 6 question entries: q1, q2, q3, q4, q5, q6_to_q10
        # q6_to_q10 is a multi-select with 10 interest options
        assert len(result["questions"]) == 6


class TestGetQuestionById:
    def test_get_question_by_id_q1_returns_question(self):
        result = get_question_by_id("q1")
        assert result is not None
        assert result["id"] == "q1"
        assert result["type"] == "single_select"

    def test_get_question_by_id_q6_returns_interests_question(self):
        result = get_question_by_id("q6_to_q10")
        assert result is not None
        assert result["type"] == "multi_select"
        assert result["maps_to"] == "interests"

    def test_get_question_by_id_nonexistent_returns_none(self):
        result = get_question_by_id("nonexistent")
        assert result is None


class TestGetOptionByKey:
    def test_get_option_by_key_q1_watch_video(self):
        result = get_option_by_key("q1", "watch_video")
        assert result is not None
        assert result["key"] == "watch_video"
        assert result["maps_to"]["modality"] == "visual"

    def test_get_option_by_key_q6_fashion_exists(self):
        result = get_option_by_key("q6_to_q10", "fashion")
        assert result is not None
        assert result["key"] == "fashion"
        assert result["text"] == "Fashion"
        assert result["emoji"] == "👗"

    def test_get_option_by_key_q6_design_not_exists(self):
        result = get_option_by_key("q6_to_q10", "design")
        assert result is None

    def test_get_option_by_key_nonexistent_question(self):
        result = get_option_by_key("nonexistent", "watch_video")
        assert result is None


KNOWN_INTEREST_KEYS = {
    "sports",
    "music",
    "gaming",
    "animals",
    "cooking",
    "art",
    "technology",
    "nature",
    "fashion",
    "travel",
}

EXPECTED_SUBJECT_CODES = {"MATH", "SCI", "ENG", "BIO", "CHEM", "PHY", "ENGL"}


class TestSubjectInterestMap:
    def test_map_contains_exactly_seven_cambridge_subject_codes(self) -> None:
        assert set(SUBJECT_INTEREST_MAP.keys()) == EXPECTED_SUBJECT_CODES

    def test_all_interest_values_are_known_option_keys(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            unknown = set(interests) - KNOWN_INTEREST_KEYS
            assert unknown == set(), f"{subject} contains unknown interest keys: {unknown}"

    def test_fashion_not_in_any_subject(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            assert "fashion" not in interests, f"'fashion' must not appear in {subject} — see M0-6-T5 rationale"

    def test_each_subject_has_at_least_two_interests(self) -> None:
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            assert len(interests) >= 2, (
                f"{subject} has only {len(interests)} compatible interest(s) — "
                f"minimum 2 required for personalisation to be meaningful"
            )


class TestGetCompatibleInterests:
    def test_returns_matching_interests_preserving_student_order(self) -> None:
        result = get_compatible_interests("PHY", ["sports", "fashion", "music"])
        assert result == ["sports", "music"]  # fashion excluded, order preserved

    def test_returns_empty_when_no_interests_compatible(self) -> None:
        result = get_compatible_interests("MATH", ["fashion"])
        assert result == []

    def test_returns_empty_when_student_has_no_interests(self) -> None:
        assert get_compatible_interests("BIO", []) == []

    def test_returns_empty_for_unknown_subject_code(self) -> None:
        assert get_compatible_interests("UNKNOWN", ["sports", "music"]) == []

    def test_case_insensitive_subject_code(self) -> None:
        assert get_compatible_interests("math", ["sports"]) == get_compatible_interests("MATH", ["sports"])

    def test_returns_all_matching_uncapped(self) -> None:
        # get_compatible_interests does not cap — caller does [:2]
        all_math = ["sports", "music", "gaming", "cooking", "art", "technology"]
        result = get_compatible_interests("MATH", all_math)
        assert len(result) == 6

    def test_caller_slice_pattern(self) -> None:
        # Confirm the top-2 pattern used in quiz_generator.py works correctly
        result = get_compatible_interests("PHY", ["sports", "music", "gaming", "technology"])
        assert result[:2] == ["sports", "music"]

    def test_sci_map(self) -> None:
        assert get_compatible_interests("SCI", ["animals", "fashion", "cooking"]) == [
            "animals",
            "cooking",
        ]

    def test_engl_map_smallest_set(self) -> None:
        # ENGL has only 3 compatible interests
        assert get_compatible_interests("ENGL", ["sports", "travel", "gaming", "art"]) == [
            "travel",
            "art",
        ]

    def test_chem_map(self) -> None:
        assert get_compatible_interests("CHEM", ["sports", "cooking", "nature", "gaming"]) == [
            "cooking",
            "nature",
        ]
