"""Unit tests for quiz sufficiency check in both generation paths (M3-1-T3).

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_quiz_sufficiency.py -v
"""

import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mini_course_generation_service import _QUIZ_QUESTION_TARGET

# Seed script uses argparse at module level — strip pytest args before first import.
sys.argv = sys.argv[:1]

# ---------------------------------------------------------------------------
# Tests: MiniCourseGenerationService sufficiency check (already in service)
# ---------------------------------------------------------------------------


def test_quiz_question_target_constant_is_five() -> None:
    """_QUIZ_QUESTION_TARGET must be 5 — minimum questions per subtopic."""
    assert _QUIZ_QUESTION_TARGET == 5


@pytest.mark.asyncio
async def test_generate_for_topic_when_question_bank_has_target_count_then_skips_quiz_llm() -> None:
    """When question_bank already has >= 5 questions, LLM must not be called for quiz."""
    from app.services.mini_course_generation_service import MiniCourseGenerationService

    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    subtopic_id = uuid.uuid4()

    subtopic_mock = MagicMock()
    subtopic_mock.id = subtopic_id
    subtopic_mock.name = "Linear Equations"

    service = MiniCourseGenerationService(db)

    with (
        patch.object(service, "_fetch_topic_context", return_value=("Algebra", "Mathematics", 8)),
        patch.object(service, "_fetch_subtopics", return_value=[subtopic_mock]),
        patch.object(service, "_resolve_interest_category_ids", return_value={}),
        patch.object(service, "_fetch_existing_content_pairs", return_value=set()),
        patch.object(
            service,
            "_fetch_existing_question_counts",
            return_value={subtopic_id: _QUIZ_QUESTION_TARGET},  # exactly at target
        ),
        patch.object(service, "_generate_quiz_questions") as mock_quiz_gen,
    ):
        await service.generate_for_topic(topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()))

    mock_quiz_gen.assert_not_called()


@pytest.mark.asyncio
async def test_generate_for_topic_when_question_bank_below_target_then_calls_quiz_llm() -> None:
    """When question_bank has fewer than 5 questions, quiz generation must run."""
    from app.services.mini_course_generation_service import MiniCourseGenerationService

    db = AsyncMock()
    db.commit = AsyncMock()

    subtopic_id = uuid.uuid4()
    subtopic_mock = MagicMock()
    subtopic_mock.id = subtopic_id
    subtopic_mock.name = "Linear Equations"

    service = MiniCourseGenerationService(db)

    with (
        patch.object(service, "_fetch_topic_context", return_value=("Algebra", "Mathematics", 8)),
        patch.object(service, "_fetch_subtopics", return_value=[subtopic_mock]),
        patch.object(service, "_resolve_interest_category_ids", return_value={}),
        patch.object(service, "_fetch_existing_content_pairs", return_value=set()),
        patch.object(
            service,
            "_fetch_existing_question_counts",
            return_value={subtopic_id: _QUIZ_QUESTION_TARGET - 1},  # one below target
        ),
        patch.object(service, "_generate_quiz_questions", return_value=1) as mock_quiz_gen,
    ):
        await service.generate_for_topic(topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()))

    mock_quiz_gen.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: seed script sufficiency check
# ---------------------------------------------------------------------------


def test_seed_subtopic_when_pre_gen_has_target_count_then_skips_quiz_generation() -> None:
    """seed_subtopic skips quiz generation when pre_gen_qs already has >= 5 questions."""
    from scripts.seed_subtopic_content import seed_subtopic

    subtopic_id = str(uuid.uuid4())
    subtopic = {
        "id": subtopic_id,
        "name": "Linear Equations",
        "grade_level": "Grade 8",
        "_strand_id": "Mathematics",
        "prerequisites": [],
    }
    # Pre-populate with exactly _QUIZ_QUESTION_TARGET questions
    pre_gen_qs = {
        subtopic_id: {
            "questions": [{"question_id": f"q{i}", "question_text": f"Q{i}?"} for i in range(_QUIZ_QUESTION_TARGET)]
        }
    }

    with (
        patch("scripts.seed_subtopic_content.SKIP_VIDEOS", True),
        patch("scripts.seed_subtopic_content.SKIP_EXPLANATIONS", True),
        patch("scripts.seed_subtopic_content.generate_quiz_content") as mock_gen,
        patch("scripts.seed_subtopic_content.upsert_subtopic_content", return_value=0),
    ):
        result = seed_subtopic(subtopic, pre_gen_qs, dry_run=False)

    mock_gen.assert_not_called()
    assert result.skipped >= 1


def test_seed_subtopic_when_pre_gen_below_target_then_generates_quiz() -> None:
    """seed_subtopic calls generate_quiz_content when pre_gen_qs has fewer than 5 questions."""
    from scripts.seed_subtopic_content import seed_subtopic

    subtopic_id = str(uuid.uuid4())
    subtopic = {
        "id": subtopic_id,
        "name": "Linear Equations",
        "grade_level": "Grade 8",
        "_strand_id": "Mathematics",
        "prerequisites": [],
    }
    pre_gen_qs: dict = {}  # no questions in bank

    with (
        patch("scripts.seed_subtopic_content.SKIP_VIDEOS", True),
        patch("scripts.seed_subtopic_content.SKIP_EXPLANATIONS", True),
        patch(
            "scripts.seed_subtopic_content.generate_quiz_content",
            return_value={"questions": [{"question_id": "q1"}]},
        ) as mock_gen,
        patch("scripts.seed_subtopic_content.upsert_subtopic_content", return_value=1),
    ):
        seed_subtopic(subtopic, pre_gen_qs, dry_run=False)

    mock_gen.assert_called_once()
