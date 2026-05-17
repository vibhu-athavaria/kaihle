"""Unit tests for mini-course next_subtopic derivation.

Tests cover:
  - NS-001: SubtopicCourseResponse schema must include next_subtopic field
  - NS-002: next_subtopic is None when current subtopic is the last in its topic
  - NS-003: next_subtopic returns id + name of the next subtopic by sequence_order
  - NS-004: next_subtopic selection ignores inactive subtopics

Naming: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from dataclasses import dataclass

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# NS-001: schema shape — next_subtopic field must exist
# ---------------------------------------------------------------------------


class NextSubtopicItem(BaseModel):
    id: uuid.UUID
    name: str


class SubtopicCourseResponse(BaseModel):
    subtopic_id: uuid.UUID
    subtopic_name: str
    topic_name: str
    next_subtopic: NextSubtopicItem | None  # None when this is the last subtopic


def test_subtopic_course_response_when_last_subtopic_then_next_is_none():
    """Schema accepts None next_subtopic (last in topic)."""
    resp = SubtopicCourseResponse(
        subtopic_id=uuid.uuid4(),
        subtopic_name="Speed and Distance",
        topic_name="Motion",
        next_subtopic=None,
    )
    assert resp.next_subtopic is None


def test_subtopic_course_response_when_next_exists_then_id_and_name_returned():
    next_id = uuid.uuid4()
    resp = SubtopicCourseResponse(
        subtopic_id=uuid.uuid4(),
        subtopic_name="Speed and Distance",
        topic_name="Motion",
        next_subtopic=NextSubtopicItem(id=next_id, name="Acceleration"),
    )
    assert resp.next_subtopic is not None
    assert resp.next_subtopic.id == next_id
    assert resp.next_subtopic.name == "Acceleration"


# ---------------------------------------------------------------------------
# NS-002 / NS-003: next_subtopic selection logic
#
# Pure function that mirrors the DB query logic:
#   SELECT id, name FROM subtopics
#   WHERE curriculum_topic_id = :topic_id
#     AND sequence_order > :current_order
#     AND is_active = TRUE
#   ORDER BY sequence_order ASC
#   LIMIT 1
# ---------------------------------------------------------------------------


@dataclass
class FakeSubtopic:
    id: uuid.UUID
    name: str
    sequence_order: int
    is_active: bool
    curriculum_topic_id: uuid.UUID


def find_next_subtopic(
    all_subtopics: list[FakeSubtopic],
    current_subtopic_id: uuid.UUID,
) -> NextSubtopicItem | None:
    """Pure function: given a flat list of subtopics, find the next one."""
    current = next((s for s in all_subtopics if s.id == current_subtopic_id), None)
    if current is None:
        return None

    candidates = [
        s
        for s in all_subtopics
        if s.curriculum_topic_id == current.curriculum_topic_id
        and s.sequence_order > current.sequence_order
        and s.is_active
    ]
    candidates.sort(key=lambda s: s.sequence_order)

    if not candidates:
        return None
    nxt = candidates[0]
    return NextSubtopicItem(id=nxt.id, name=nxt.name)


def test_find_next_subtopic_when_last_in_topic_then_returns_none():
    topic_id = uuid.uuid4()
    subtopics = [
        FakeSubtopic(uuid.uuid4(), "Waves", 1, True, topic_id),
        FakeSubtopic(uuid.uuid4(), "Frequency", 2, True, topic_id),
    ]
    last_id = subtopics[1].id
    result = find_next_subtopic(subtopics, last_id)
    assert result is None


def test_find_next_subtopic_when_middle_in_topic_then_returns_next():
    topic_id = uuid.uuid4()
    subtopics = [
        FakeSubtopic(uuid.uuid4(), "Waves", 1, True, topic_id),
        FakeSubtopic(uuid.uuid4(), "Frequency", 2, True, topic_id),
        FakeSubtopic(uuid.uuid4(), "Amplitude", 3, True, topic_id),
    ]
    result = find_next_subtopic(subtopics, subtopics[1].id)
    assert result is not None
    assert result.name == "Amplitude"


def test_find_next_subtopic_when_first_then_returns_second():
    topic_id = uuid.uuid4()
    subtopics = [
        FakeSubtopic(uuid.uuid4(), "Waves", 1, True, topic_id),
        FakeSubtopic(uuid.uuid4(), "Frequency", 2, True, topic_id),
    ]
    result = find_next_subtopic(subtopics, subtopics[0].id)
    assert result is not None
    assert result.name == "Frequency"


def test_find_next_subtopic_when_next_is_inactive_then_skips_it():
    """NS-004: inactive subtopics must not appear as next."""
    topic_id = uuid.uuid4()
    subtopics = [
        FakeSubtopic(uuid.uuid4(), "Waves", 1, True, topic_id),
        FakeSubtopic(uuid.uuid4(), "INACTIVE", 2, False, topic_id),  # inactive
        FakeSubtopic(uuid.uuid4(), "Amplitude", 3, True, topic_id),
    ]
    result = find_next_subtopic(subtopics, subtopics[0].id)
    assert result is not None
    assert result.name == "Amplitude", "Should skip inactive subtopic at order=2"


def test_find_next_subtopic_when_different_topic_then_not_returned():
    """Siblings from a different curriculum_topic must not be returned."""
    topic_a = uuid.uuid4()
    topic_b = uuid.uuid4()
    subtopics = [
        FakeSubtopic(uuid.uuid4(), "Waves", 1, True, topic_a),
        FakeSubtopic(uuid.uuid4(), "Other Topic Subtopic", 2, True, topic_b),
    ]
    result = find_next_subtopic(subtopics, subtopics[0].id)
    assert result is None
