"""Adaptive question selection — pure rule-based multistage logic.

Implements a per-topic 1-up/2-down staircase for diagnostic assessments.
Two consecutive correct answers within a topic step that topic's difficulty up;
a single incorrect answer steps it down. This converges on roughly 70% correct,
which aligns with the "Strong" mastery threshold in packages/types/src/mastery.ts.

Design notes:
- Every function here is PURE: no DB, no I/O, no clock, no randomness. The
  caller loads state and persists nothing on behalf of this module.
- Difficulty is REPLAYED from the response outcome log on every call rather than
  stored on the attempt. This makes selection idempotent under retries: calling
  twice without an intervening answer returns the same question, and there is no
  mutable ladder column that can drift out of sync with student_responses.
- Topic rotation is least-answered-first, not strict round-robin. Strict rotation
  starves later topics when an earlier one exhausts its question pool; picking the
  least-answered topic self-corrects and keeps per-subtopic denominators in
  gap_service.calculate_gap_states_for_attempt from getting too thin to be
  meaningful (a subtopic scored on one response yields mastery of exactly 0.0
  or 1.0).
"""

import uuid
from dataclasses import dataclass

# Ladder starts mid-range so the first question is maximally uninformative-neutral:
# we have no prior on the student, so we probe the middle and let answers move us.
DEFAULT_START_DIFFICULTY = 3

# 1-up/2-down: two consecutive correct to advance, one incorrect to retreat.
# Asymmetry is deliberate — it targets ~70% correct rather than the ~50% a
# symmetric 1-up/1-down staircase converges on. 50% is correct for maximising
# psychometric information but demoralising for an 11-18 audience.
CONSECUTIVE_CORRECT_TO_STEP_UP = 2


@dataclass(frozen=True)
class Candidate:
    """One question available for selection, with the attributes selection needs."""

    question_id: uuid.UUID
    curriculum_topic_id: uuid.UUID
    difficulty_level: int


def ladder_position(
    outcomes: list[bool],
    minimum_difficulty: int,
    maximum_difficulty: int,
    start: int = DEFAULT_START_DIFFICULTY,
) -> int:
    """Replay a topic's outcome sequence to derive its current difficulty level.

    Args:
        outcomes: Correct/incorrect flags for this topic, oldest first.
        minimum_difficulty: Lower clamp (assessment.minimum_difficulty).
        maximum_difficulty: Upper clamp (assessment.maximum_difficulty).
        start: Difficulty to begin the walk at, clamped into range.

    Returns:
        The difficulty level the next question for this topic should target.
    """
    level = max(minimum_difficulty, min(maximum_difficulty, start))
    consecutive_correct = 0

    for is_correct in outcomes:
        if is_correct:
            consecutive_correct += 1
            if consecutive_correct >= CONSECUTIVE_CORRECT_TO_STEP_UP:
                level = min(level + 1, maximum_difficulty)
                consecutive_correct = 0
        else:
            level = max(level - 1, minimum_difficulty)
            consecutive_correct = 0

    return level


def _closest_by_difficulty(candidates: list[Candidate], target: int) -> Candidate:
    """Pick the candidate nearest the target difficulty.

    Ties break toward the harder question first, then by question_id so the
    choice is deterministic across calls and across processes.
    """
    return min(
        candidates,
        key=lambda c: (abs(c.difficulty_level - target), -c.difficulty_level, str(c.question_id)),
    )


def select_next(
    candidates: list[Candidate],
    answered_question_ids: set[uuid.UUID],
    outcomes_by_topic: dict[uuid.UUID, list[bool]],
    minimum_difficulty: int,
    maximum_difficulty: int,
    question_count: int,
) -> Candidate | None:
    """Choose the next question to serve, or None when the attempt is complete.

    Selection order:
      1. Stop if the student has already answered question_count questions.
      2. Pick the topic with the fewest answered questions (ties break on the
         topic's first appearance in `candidates`, which is itself ordered
         deterministically by the caller).
      3. Target that topic's ladder difficulty; take the nearest available
         unanswered question within the topic.
      4. If the chosen topic is exhausted, fall through to the next-least-answered
         topic. If every topic is exhausted, return None.

    Args:
        candidates: Full question pool for the assessment.
        answered_question_ids: Questions already served and answered.
        outcomes_by_topic: Per-topic correct/incorrect history, oldest first.
        minimum_difficulty: Lower clamp for the ladder.
        maximum_difficulty: Upper clamp for the ladder.
        question_count: Total questions the student is asked.

    Returns:
        The next Candidate, or None if the attempt is complete or the pool is dry.
    """
    if len(answered_question_ids) >= question_count:
        return None

    # Preserve caller-supplied ordering for deterministic tie-breaks.
    topic_order: list[uuid.UUID] = []
    remaining_by_topic: dict[uuid.UUID, list[Candidate]] = {}
    for candidate in candidates:
        if candidate.curriculum_topic_id not in remaining_by_topic:
            remaining_by_topic[candidate.curriculum_topic_id] = []
            topic_order.append(candidate.curriculum_topic_id)
        if candidate.question_id not in answered_question_ids:
            remaining_by_topic[candidate.curriculum_topic_id].append(candidate)

    # Least-answered first; ties resolved by position in topic_order.
    ranked_topics = sorted(
        topic_order,
        key=lambda t: (len(outcomes_by_topic.get(t, [])), topic_order.index(t)),
    )

    for topic_id in ranked_topics:
        available = remaining_by_topic[topic_id]
        if not available:
            continue  # topic exhausted — fall through to the next one
        target = ladder_position(
            outcomes_by_topic.get(topic_id, []),
            minimum_difficulty,
            maximum_difficulty,
        )
        return _closest_by_difficulty(available, target)

    return None
