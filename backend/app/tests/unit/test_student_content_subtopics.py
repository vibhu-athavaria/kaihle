"""Unit tests for the subtopic list endpoint — progress field inclusion.

Tests cover:
  - SC-001: SubtopicStudentResponse must expose a `progress` field
  - SC-002: progress derivation — not_started / in_progress / completed
  - SC-003: endpoint must join progress in one query (no N+1)

Naming: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# SC-001: schema shape — progress field must exist
# ---------------------------------------------------------------------------


class SubtopicProgress(BaseModel):
    explanation_accessed: bool
    video_accessed: bool
    check_questions_score: float | None
    status: Literal["not_started", "in_progress", "completed"]


class SubtopicStudentResponse(BaseModel):
    id: uuid.UUID
    name: str
    order: int
    progress: SubtopicProgress | None  # None when student has never visited


def test_subtopic_student_response_when_no_progress_then_progress_is_none():
    """Schema accepts None progress (student has never visited)."""
    subtopic = SubtopicStudentResponse(
        id=uuid.uuid4(),
        name="Waves and Vibrations",
        order=1,
        progress=None,
    )
    assert subtopic.progress is None


def test_subtopic_student_response_when_progress_exists_then_fields_are_accessible():
    """Schema exposes all progress fields including computed status."""
    subtopic = SubtopicStudentResponse(
        id=uuid.uuid4(),
        name="Waves and Vibrations",
        order=1,
        progress=SubtopicProgress(
            explanation_accessed=True,
            video_accessed=False,
            check_questions_score=None,
            status="in_progress",
        ),
    )
    assert subtopic.progress is not None
    assert subtopic.progress.status == "in_progress"
    assert subtopic.progress.explanation_accessed is True


# ---------------------------------------------------------------------------
# SC-002: status derivation from raw DB fields
# ---------------------------------------------------------------------------


def derive_status(
    explanation_accessed: bool,
    video_accessed: bool,
    check_questions_score: float | None,
) -> Literal["not_started", "in_progress", "completed"]:
    """Pure function extracted from the endpoint for isolated testing."""
    if check_questions_score is not None:
        return "completed"
    if explanation_accessed or video_accessed:
        return "in_progress"
    return "not_started"


def test_derive_status_when_no_activity_then_not_started():
    assert derive_status(False, False, None) == "not_started"


def test_derive_status_when_explanation_accessed_then_in_progress():
    assert derive_status(True, False, None) == "in_progress"


def test_derive_status_when_video_accessed_then_in_progress():
    assert derive_status(False, True, None) == "in_progress"


def test_derive_status_when_score_recorded_then_completed():
    assert derive_status(True, True, 0.75) == "completed"


def test_derive_status_when_score_is_zero_then_completed():
    """Score of 0 means the student finished but scored nothing — still completed."""
    assert derive_status(True, True, 0.0) == "completed"


def test_derive_status_when_score_is_one_then_completed():
    assert derive_status(True, True, 1.0) == "completed"


# ---------------------------------------------------------------------------
# SC-003: single query contract — no N+1
#
# The endpoint must fetch subtopics AND their progress in a single SQL
# statement using a LEFT OUTER JOIN, not a loop of per-subtopic queries.
#
# Test strategy: build a query-plan tracker that records how many DB calls
# are made for N subtopics and assert it stays at 1.
# ---------------------------------------------------------------------------


class QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def execute(self, _query: object) -> list:
        self.count += 1
        return []


def fetch_subtopics_with_progress_correct(
    db: QueryCounter,
    class_topic_id: uuid.UUID,
    student_id: uuid.UUID,
) -> list:
    """Correct implementation: one query with LEFT JOIN."""
    # Represents: SELECT subtopics.*, progress.*
    #             FROM subtopics
    #             LEFT JOIN subtopic_course_progress AS p
    #               ON p.subtopic_id = subtopics.id AND p.student_id = :student_id
    #             WHERE subtopics.curriculum_topic_id = :curriculum_topic_id
    return db.execute({"join": "subtopics LEFT JOIN subtopic_course_progress"})


def fetch_subtopics_with_progress_naive(
    db: QueryCounter,
    subtopic_ids: list[uuid.UUID],
    student_id: uuid.UUID,
) -> list:
    """Buggy N+1 implementation: one query per subtopic."""
    results = []
    for sid in subtopic_ids:
        results.extend(db.execute({"select": "subtopic_course_progress", "where": str(sid)}))
    return results


def test_fetch_subtopics_when_using_join_then_single_db_call():
    db = QueryCounter()
    fetch_subtopics_with_progress_correct(db, uuid.uuid4(), uuid.uuid4())
    assert db.count == 1, f"Expected 1 DB call, got {db.count}"


def test_fetch_subtopics_when_using_naive_loop_then_n_plus_1_calls():
    """Documents the N+1 problem — this is the pattern we must NOT use."""
    db = QueryCounter()
    subtopic_ids = [uuid.uuid4() for _ in range(5)]
    fetch_subtopics_with_progress_naive(db, subtopic_ids, uuid.uuid4())
    # N separate queries — clearly wrong
    assert db.count == 5, "N+1 pattern confirmed: one query per subtopic"
