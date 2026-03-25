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

    def test_get_option_by_key_q6_design(self):
        result = get_option_by_key("q6_to_q10", "design")
        assert result is not None
        assert result["key"] == "design"
        assert result["text"] == "Design"
        assert result["emoji"] == "🎨"

    def test_get_option_by_key_q6_fashion_not_exists(self):
        result = get_option_by_key("q6_to_q10", "fashion")
        assert result is None

    def test_get_option_by_key_nonexistent_question(self):
        result = get_option_by_key("nonexistent", "watch_video")
        assert result is None


class TestSubjectInterestMap:
    def test_subject_interest_map_math_has_six_interests(self):
        assert "MATH" in SUBJECT_INTEREST_MAP
        assert len(SUBJECT_INTEREST_MAP["MATH"]) == 6

    def test_subject_interest_map_all_subjects_have_at_least_two(self):
        for subject, interests in SUBJECT_INTEREST_MAP.items():
            assert len(interests) >= 2, f"{subject} has fewer than 2 interests"

    def test_subject_interest_map_design_not_in_math(self):
        assert "design" not in SUBJECT_INTEREST_MAP["MATH"]


class TestGetCompatibleInterests:
    def test_get_compatible_when_student_has_relevant_interests_then_returns_them(
        self,
    ):
        result = get_compatible_interests("MATH", ["sports", "design", "gaming"])
        assert "sports" in result
        assert "gaming" in result
        assert "design" not in result

    def test_get_compatible_when_no_relevant_interests_then_returns_empty(self):
        result = get_compatible_interests("MATH", ["design", "travel"])
        assert result == []

    def test_get_compatible_when_empty_interests_then_returns_empty(self):
        assert get_compatible_interests("BIO", []) == []

    def test_get_compatible_when_unknown_subject_then_returns_empty(self):
        assert get_compatible_interests("UNKNOWN_SUBJECT", ["sports", "music"]) == []

    def test_get_compatible_is_case_insensitive_on_subject_code(self):
        assert get_compatible_interests("math", ["sports"]) == get_compatible_interests("MATH", ["sports"])

    def test_get_compatible_returns_max_available_not_capped(self):
        all_math = ["sports", "music", "gaming", "cooking", "art", "technology"]
        result = get_compatible_interests("MATH", all_math)
        assert len(result) == 6

    def test_get_compatible_preserves_order_from_student_interests(self):
        result = get_compatible_interests("MATH", ["gaming", "sports", "music"])
        assert result == ["gaming", "sports", "music"]

    def test_get_compatible_math_maps_to_six_interests(self):
        result = get_compatible_interests(
            "MATH", ["sports", "music", "gaming", "cooking", "art", "technology", "design"]
        )
        assert len(result) == 6
        assert "design" not in result
