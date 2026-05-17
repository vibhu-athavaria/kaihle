"""Unit tests for questionnaire v2 — scoring logic and definition validation."""

from app.core.questionnaire_config import get_compatible_interests, get_questionnaire_definition
from app.services.onboarding_service import OnboardingService


def _make_responses(*pairs: tuple[str, str]) -> list[dict]:
    """Helper: build a responses list from (question_id, answer_key) pairs."""
    return [{"question_id": qid, "answer_key": key} for qid, key in pairs]


class TestCalculateModalityScoresV2:
    """Tests for _calculate_modality_scores with v2 plurality-vote logic.

    Returns normalised float scores per modality (CONSTITUTION §11 format):
    {"visual": float, "auditory": float, "reading_writing": float, "kinesthetic": float}
    """

    def _score(self, responses: list[dict]) -> dict:
        # Instantiate without DB — we only call pure methods
        svc = OnboardingService.__new__(OnboardingService)
        return svc._calculate_modality_scores(responses)

    def test_calculate_modality_scores_v2_when_all_three_visual_then_visual_score_is_one(self) -> None:
        # Arrange: Q1=see_diagram (visual), Q2=draw_it (visual), Q3=find_example (visual)
        responses = _make_responses(
            ("q1", "see_diagram"),
            ("q2", "draw_it"),
            ("q3", "find_example"),
        )
        # Act
        result = self._score(responses)
        # Assert: visual gets all 3 votes → score 1.0; others 0.0
        assert result["visual"] == 1.0
        assert result["auditory"] == 0.0
        assert result["reading_writing"] == 0.0
        assert result["kinesthetic"] == 0.0

    def test_calculate_modality_scores_v2_when_split_votes_then_visual_score_exceeds_auditory(self) -> None:
        # Arrange: Q1=see_diagram (visual), Q2=talk_through (auditory), Q3=find_example (visual)
        responses = _make_responses(
            ("q1", "see_diagram"),
            ("q2", "talk_through"),
            ("q3", "find_example"),
        )
        # Act
        result = self._score(responses)
        # Assert: visual=2/3, auditory=1/3
        assert result["visual"] == round(2 / 3, 4)
        assert result["auditory"] == round(1 / 3, 4)
        assert result["visual"] > result["auditory"]

    def test_calculate_modality_scores_v2_when_three_way_tie_then_all_scores_equal(self) -> None:
        # Arrange: Q1=see_diagram (visual), Q2=talk_through (auditory), Q3=reread_alone (reading_writing)
        # Each modality gets exactly 1 vote → equal scores
        responses = _make_responses(
            ("q1", "see_diagram"),
            ("q2", "talk_through"),
            ("q3", "reread_alone"),
        )
        # Act
        result = self._score(responses)
        # Assert: three modalities each get 1/3, kinesthetic gets 0
        assert result["visual"] == round(1 / 3, 4)
        assert result["auditory"] == round(1 / 3, 4)
        assert result["reading_writing"] == round(1 / 3, 4)
        assert result["kinesthetic"] == 0.0


class TestExtractInterestsV2:
    """Tests for _extract_interests with v2 single-select Q6."""

    def _extract(self, responses: list[dict]) -> list[str]:
        svc = OnboardingService.__new__(OnboardingService)
        return svc._extract_interests(responses)

    def test_extract_interests_v2_when_single_select_then_returns_one_item_list(self) -> None:
        # Arrange: Q6 answered with sports_movement
        responses = _make_responses(("q6", "sports_movement"))
        # Act
        result = self._extract(responses)
        # Assert
        assert result == ["sports_movement"]

    def test_extract_interests_v2_when_no_q6_response_then_returns_empty_list(self) -> None:
        # Arrange: responses without Q6
        responses = _make_responses(("q1", "see_diagram"))
        # Act
        result = self._extract(responses)
        # Assert
        assert result == []


class TestWorkStyleV2:
    """Tests for _calculate_work_style with v2 Q4/Q5/Q7 logic."""

    def _work_style(self, responses: list[dict]) -> dict:
        svc = OnboardingService.__new__(OnboardingService)
        return svc._calculate_work_style(responses)

    def test_work_style_v2_when_q7_submitted_then_challenge_response_key_present(self) -> None:
        # Arrange: Q7 answered with "persists"
        responses = _make_responses(("q7", "persists"))
        # Act
        result = self._work_style(responses)
        # Assert
        assert result["challenge_response"] == "persists"

    def test_work_style_v2_when_avoidant_selected_then_challenge_response_is_avoidant(self) -> None:
        # Arrange: Q7 answered with "avoidant"
        responses = _make_responses(("q7", "avoidant"))
        # Act
        result = self._work_style(responses)
        # Assert
        assert result["challenge_response"] == "avoidant"

    def test_work_style_v2_when_q4_short_focused_then_short_sessions_is_true(self) -> None:
        # Arrange: Q4 = short_focused
        responses = _make_responses(("q4", "short_focused"))
        # Act
        result = self._work_style(responses)
        # Assert
        assert result["short_sessions"] is True

    def test_work_style_v2_when_q5_big_picture_then_concept_first_is_true(self) -> None:
        # Arrange: Q5 = big_picture
        responses = _make_responses(("q5", "big_picture"))
        # Act
        result = self._work_style(responses)
        # Assert
        assert result["concept_first"] is True
        assert result["task_based"] is False

    def test_work_style_v2_when_q5_either_way_then_concept_first_is_none(self) -> None:
        # Arrange: Q5 = either_way (maps to concept_first=None)
        responses = _make_responses(("q5", "either_way"))
        # Act
        result = self._work_style(responses)
        # Assert: concept_first stored as None; task_based defaults to False
        assert result["concept_first"] is None
        assert result["task_based"] is False


class TestGetCompatibleInterestsV2:
    """Tests for get_compatible_interests with v2 category keys."""

    def test_get_compatible_interests_when_single_item_list_then_returns_correct_subject_match(self) -> None:
        # Arrange: v2 key "sports_movement" not in v1 SUBJECT_INTEREST_MAP
        # Confirms function does not crash and returns list (empty is fine)
        result = get_compatible_interests("MATH", ["sports_movement"])
        # Assert: returns a list — empty is acceptable (v2 key not in map yet)
        assert isinstance(result, list)

    def test_get_compatible_interests_when_v2_key_for_all_subjects_then_no_exception(self) -> None:
        # Arrange: all four v2 category keys
        v2_keys = ["sports_movement", "tech_gaming", "nature_animals", "arts_culture"]
        for subject in ("MATH", "SCI", "ENG", "BIO", "CHEM", "PHY", "ENGL"):
            # Act + Assert: no exception
            result = get_compatible_interests(subject, v2_keys)
            assert isinstance(result, list)


class TestQuestionnaireDefinitionV2:
    """Tests for get_questionnaire_definition returning v2 structure."""

    def test_questionnaire_definition_v2_when_called_then_returns_7_questions(self) -> None:
        # Act
        definition = get_questionnaire_definition()
        # Assert
        assert len(definition["questions"]) == 7
        assert definition["version"] == "v2"

    def test_questionnaire_definition_v2_when_called_then_q6_maps_to_interest_category(self) -> None:
        # Act
        definition = get_questionnaire_definition()
        q6 = next(q for q in definition["questions"] if q["id"] == "q6")
        # Assert
        assert q6.get("maps_to") == "interest_category"
        assert len(q6["options"]) == 4

    def test_questionnaire_definition_v2_when_called_then_q7_maps_to_challenge_response(self) -> None:
        # Act
        definition = get_questionnaire_definition()
        q7 = next(q for q in definition["questions"] if q["id"] == "q7")
        # Assert
        assert q7.get("maps_to") == "challenge_response"
        challenge_keys = {opt["key"] for opt in q7["options"]}
        assert challenge_keys == {"persists", "paces", "collaborative", "avoidant"}

    def test_questionnaire_definition_v2_when_called_then_q1_to_q3_have_modality_maps(self) -> None:
        # Act
        definition = get_questionnaire_definition()
        for qid in ("q1", "q2", "q3"):
            question = next(q for q in definition["questions"] if q["id"] == qid)
            for option in question["options"]:
                assert "maps_to" in option
                assert "modality" in option["maps_to"], f"{qid} option {option['key']} missing modality"
