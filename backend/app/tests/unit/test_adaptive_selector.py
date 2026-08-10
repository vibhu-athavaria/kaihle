"""Unit tests for the pure adaptive question selector."""

import uuid

from app.services.adaptive_selector import (
    DEFAULT_START_DIFFICULTY,
    Candidate,
    ladder_position,
    select_next,
)

MIN_D = 1
MAX_D = 5


def _topic() -> uuid.UUID:
    return uuid.uuid4()


def _candidates(topic_id: uuid.UUID, difficulties: list[int]) -> list[Candidate]:
    """Build one candidate per requested difficulty, all in the same topic."""
    return [Candidate(question_id=uuid.uuid4(), curriculum_topic_id=topic_id, difficulty_level=d) for d in difficulties]


# ---------------------------------------------------------------------------
# ladder_position
# ---------------------------------------------------------------------------


def test_ladder_position_when_no_outcomes_then_starts_at_default() -> None:
    assert ladder_position([], MIN_D, MAX_D) == DEFAULT_START_DIFFICULTY


def test_ladder_position_when_two_consecutive_correct_then_steps_up() -> None:
    assert ladder_position([True, True], MIN_D, MAX_D) == DEFAULT_START_DIFFICULTY + 1


def test_ladder_position_when_one_correct_only_then_holds() -> None:
    assert ladder_position([True], MIN_D, MAX_D) == DEFAULT_START_DIFFICULTY


def test_ladder_position_when_one_incorrect_then_steps_down() -> None:
    assert ladder_position([False], MIN_D, MAX_D) == DEFAULT_START_DIFFICULTY - 1


def test_ladder_position_when_correct_then_incorrect_then_streak_resets() -> None:
    # A single correct followed by a wrong answer must not bank the correct
    # toward a later step up.
    assert ladder_position([True, False, True], MIN_D, MAX_D) == DEFAULT_START_DIFFICULTY - 1


def test_ladder_position_when_at_max_and_correct_then_clamps() -> None:
    assert ladder_position([True] * 20, MIN_D, MAX_D) == MAX_D


def test_ladder_position_when_at_min_and_incorrect_then_clamps() -> None:
    assert ladder_position([False] * 20, MIN_D, MAX_D) == MIN_D


def test_ladder_position_when_narrow_range_then_stays_within_bounds() -> None:
    # Assessment configured for difficulty 2-3 only; start (3) is already in range.
    assert ladder_position([True, True, True, True], 2, 3) == 3
    assert ladder_position([False, False, False], 2, 3) == 2


def test_ladder_position_when_start_outside_range_then_clamped_into_range() -> None:
    # Default start of 3 must be pulled into a 4-5 assessment range.
    assert ladder_position([], 4, 5) == 4


def test_ladder_position_when_replayed_twice_then_returns_same_value() -> None:
    outcomes = [True, True, False, True, True, True]
    assert ladder_position(outcomes, MIN_D, MAX_D) == ladder_position(outcomes, MIN_D, MAX_D)


# ---------------------------------------------------------------------------
# select_next
# ---------------------------------------------------------------------------


def test_select_next_when_no_prior_responses_then_starts_at_default_difficulty() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2, 3, 4, 5])

    result = select_next(candidates, set(), {}, MIN_D, MAX_D, question_count=10)

    assert result is not None
    assert result.difficulty_level == DEFAULT_START_DIFFICULTY


def test_select_next_when_two_correct_then_serves_harder_question() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2, 3, 4, 5])
    answered = {candidates[2].question_id}  # the difficulty-3 question

    result = select_next(candidates, answered, {topic: [True, True]}, MIN_D, MAX_D, question_count=10)

    assert result is not None
    assert result.difficulty_level == 4


def test_select_next_when_incorrect_then_serves_easier_question() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2, 3, 4, 5])
    answered = {candidates[2].question_id}

    result = select_next(candidates, answered, {topic: [False]}, MIN_D, MAX_D, question_count=10)

    assert result is not None
    assert result.difficulty_level == 2


def test_select_next_when_target_difficulty_exhausted_then_returns_nearest_available() -> None:
    topic = _topic()
    # No difficulty-3 question exists at all; nearest to target 3 is 4 (harder wins ties).
    candidates = _candidates(topic, [1, 2, 4, 5])

    result = select_next(candidates, set(), {}, MIN_D, MAX_D, question_count=10)

    assert result is not None
    assert result.difficulty_level == 4


def test_select_next_when_called_twice_without_answering_then_returns_same_question() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2, 3, 4, 5])

    first = select_next(candidates, set(), {}, MIN_D, MAX_D, question_count=10)
    second = select_next(candidates, set(), {}, MIN_D, MAX_D, question_count=10)

    assert first is not None and second is not None
    assert first.question_id == second.question_id


def test_select_next_when_multiple_topics_then_serves_least_answered_topic() -> None:
    topic_a, topic_b = _topic(), _topic()
    candidates = _candidates(topic_a, [3, 3]) + _candidates(topic_b, [3, 3])
    answered = {candidates[0].question_id}

    result = select_next(candidates, answered, {topic_a: [True]}, MIN_D, MAX_D, question_count=10)

    assert result is not None
    assert result.curriculum_topic_id == topic_b


def test_select_next_when_topics_have_independent_ladders_then_difficulty_is_per_topic() -> None:
    # Student is strong in topic_a and weak in topic_b — the two ladders must not
    # average into a single meaningless midpoint.
    topic_a, topic_b = _topic(), _topic()
    candidates = _candidates(topic_a, [1, 2, 3, 4, 5]) + _candidates(topic_b, [1, 2, 3, 4, 5])
    outcomes = {topic_a: [True, True, True, True], topic_b: [False, False]}
    # topic_a: difficulties 1-4 used, 5 left. topic_b: difficulties 3-4 used, 1/2/5 left.
    answered = {c.question_id for c in candidates[:4]} | {c.question_id for c in candidates[7:9]}

    # topic_b has the fewest answers, so it is served next — and its own ladder
    # has walked DOWN to 1 despite topic_a's perfect run.
    result_b = select_next(candidates, answered, outcomes, MIN_D, MAX_D, question_count=20)
    assert result_b is not None
    assert result_b.curriculum_topic_id == topic_b
    assert result_b.difficulty_level == 1  # 3 -> 2 -> 1

    # Level topic_b's count up; topic_a is served next, still high on its own ladder.
    outcomes_level = {topic_a: [True, True, True, True], topic_b: [False, False, False, False]}
    result_a = select_next(candidates, answered, outcomes_level, MIN_D, MAX_D, question_count=20)
    assert result_a is not None
    assert result_a.curriculum_topic_id == topic_a
    assert result_a.difficulty_level == 5  # 3 -> 4 -> 5


def test_select_next_when_topic_exhausted_then_rotates_to_next_topic() -> None:
    topic_a, topic_b = _topic(), _topic()
    a_questions = _candidates(topic_a, [3])
    b_questions = _candidates(topic_b, [3, 4])
    candidates = a_questions + b_questions
    # topic_a has the fewest outcomes but nothing left to serve.
    answered = {a_questions[0].question_id}

    result = select_next(
        candidates, answered, {topic_a: [True], topic_b: [True, True]}, MIN_D, MAX_D, question_count=10
    )

    assert result is not None
    assert result.curriculum_topic_id == topic_b


def test_select_next_when_question_count_reached_then_returns_none() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2, 3, 4, 5])
    answered = {c.question_id for c in candidates[:3]}

    assert select_next(candidates, answered, {topic: [True] * 3}, MIN_D, MAX_D, question_count=3) is None


def test_select_next_when_all_topics_exhausted_then_returns_none() -> None:
    topic = _topic()
    candidates = _candidates(topic, [1, 2])
    answered = {c.question_id for c in candidates}

    assert select_next(candidates, answered, {topic: [True, True]}, MIN_D, MAX_D, question_count=10) is None


def test_select_next_when_pool_empty_then_returns_none() -> None:
    assert select_next([], set(), {}, MIN_D, MAX_D, question_count=10) is None


def test_select_next_when_never_repeats_then_full_walk_is_distinct() -> None:
    # Walking the whole pool must never serve the same question twice.
    topic_a, topic_b = _topic(), _topic()
    candidates = _candidates(topic_a, [1, 2, 3, 4, 5]) + _candidates(topic_b, [1, 2, 3, 4, 5])
    answered: set[uuid.UUID] = set()
    outcomes: dict[uuid.UUID, list[bool]] = {}
    served: list[uuid.UUID] = []

    for _ in range(10):
        nxt = select_next(candidates, answered, outcomes, MIN_D, MAX_D, question_count=10)
        assert nxt is not None
        served.append(nxt.question_id)
        answered.add(nxt.question_id)
        outcomes.setdefault(nxt.curriculum_topic_id, []).append(True)

    assert len(set(served)) == 10
    assert select_next(candidates, answered, outcomes, MIN_D, MAX_D, question_count=10) is None
