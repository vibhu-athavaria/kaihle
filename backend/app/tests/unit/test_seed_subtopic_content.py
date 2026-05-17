"""Unit tests for scripts/seed_subtopic_content.py

Covers:
  - _make_sync_db_url: asyncpg → psycopg2 URL rewriting
  - call_llm: sync litellm.completion path, error handling, logging
  - CLI flag / env-var priority for DRY_RUN / SKIP_* constants
  - SeedResult: inserted/skipped/errors tracking
  - seed_subtopic dry-run: LLM called, no DB write, result logged
  - seed_subtopic: video/explanation/quiz branches, pre-generated questions, missing id
  - _batches: correct chunking
  - build_record: video / explanation / practice field mapping
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

# sys.path manipulation must precede the import; argparse reads sys.argv at
# module load time so we reset it to a bare invocation before importing.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
sys.argv = ["seed_subtopic_content"]

import seed_subtopic_content as seed  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SUBTOPIC: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "name": "Algebra Basics",
    "grade_level": "Grade 8",
    "_strand_id": "Mathematics",
    "prerequisites": [],
}

MINIMAL_SUBTOPIC_NO_ID: dict[str, Any] = {
    "id": "",
    "name": "No ID Subtopic",
}


# ---------------------------------------------------------------------------
# _make_sync_db_url
# ---------------------------------------------------------------------------


def test_make_sync_db_url_when_asyncpg_prefix_then_replaced_with_psycopg2():
    url = "postgresql+asyncpg://user:pass@localhost:5432/kaihle"
    result = seed._make_sync_db_url(url)
    assert result == "postgresql+psycopg2://user:pass@localhost:5432/kaihle"


def test_make_sync_db_url_when_postgres_asyncpg_prefix_then_replaced():
    url = "postgres+asyncpg://user:pass@localhost:5432/kaihle"
    result = seed._make_sync_db_url(url)
    assert result == "postgresql+psycopg2://user:pass@localhost:5432/kaihle"


def test_make_sync_db_url_when_already_psycopg2_then_unchanged():
    url = "postgresql+psycopg2://user:pass@localhost:5432/kaihle"
    result = seed._make_sync_db_url(url)
    assert result == url


def test_make_sync_db_url_when_plain_postgresql_then_unchanged():
    url = "postgresql://user:pass@localhost:5432/kaihle"
    result = seed._make_sync_db_url(url)
    assert result == url


# ---------------------------------------------------------------------------
# call_llm
# ---------------------------------------------------------------------------


def test_call_llm_when_llm_returns_valid_json_then_dict_returned():
    fake_response = {"choices": [{"message": {"content": '{"explanation_text": "hello"}'}}]}
    with patch("seed_subtopic_content.litellm.completion", return_value=fake_response) as mock_llm:
        result = seed.call_llm("some prompt", model="gpt-4o-mini")
    assert result == {"explanation_text": "hello"}
    mock_llm.assert_called_once()


def test_call_llm_when_llm_raises_exception_then_none_returned(caplog):
    with patch("seed_subtopic_content.litellm.completion", side_effect=Exception("timeout")):
        with caplog.at_level("ERROR", logger="seed_subtopic_content"):
            result = seed.call_llm("some prompt")
    assert result is None
    assert "LLM call failed" in caplog.text


def test_call_llm_when_llm_returns_invalid_json_then_none_returned(caplog):
    fake_response = {"choices": [{"message": {"content": "not json"}}]}
    with patch("seed_subtopic_content.litellm.completion", return_value=fake_response):
        with caplog.at_level("ERROR", logger="seed_subtopic_content"):
            result = seed.call_llm("some prompt")
    assert result is None


def test_call_llm_uses_sync_completion_not_acompletion():
    """Regression: acompletion was called without await — must use sync completion."""
    fake_response = {"choices": [{"message": {"content": "{}"}}]}
    with patch("seed_subtopic_content.litellm.completion", return_value=fake_response) as mock_sync:
        with patch("seed_subtopic_content.litellm.acompletion") as mock_async:
            seed.call_llm("prompt")
    mock_sync.assert_called_once()
    mock_async.assert_not_called()


# ---------------------------------------------------------------------------
# SeedResult
# ---------------------------------------------------------------------------


def test_seed_result_when_no_errors_then_not_failed():
    r = seed.SeedResult("abc", "Test Subtopic")
    r.inserted = 2
    assert not r.failed
    assert r.inserted == 2


def test_seed_result_when_error_added_then_failed():
    r = seed.SeedResult("abc", "Test Subtopic")
    r.add_error("DB exploded")
    assert r.failed
    assert "DB exploded" in r.errors


# ---------------------------------------------------------------------------
# build_record
# ---------------------------------------------------------------------------


def test_build_record_when_video_type_then_video_fields_set():
    data = {
        "video_url": "https://youtube.com/watch?v=abc",
        "video_provider": "youtube",
        "video_duration_seconds": 300,
        "video_thumbnail_url": "https://img.youtube.com/vi/abc/maxresdefault.jpg",
    }
    rec = seed.build_record(MINIMAL_SUBTOPIC, seed.CONTENT_TYPE_VIDEO, data, seed.REVIEW_STATUS_APPROVED, True)
    assert rec is not None
    assert rec["video_url"] == "https://youtube.com/watch?v=abc"
    assert rec["video_provider"] == "youtube"
    assert rec["explanation_text"] is None
    assert rec["quiz_questions"] is None


def test_build_record_when_explanation_type_then_explanation_text_set():
    data = {"explanation_text": "# Algebra\n\nAlgebra is..."}
    rec = seed.build_record(MINIMAL_SUBTOPIC, seed.CONTENT_TYPE_EXPLANATION, data, seed.REVIEW_STATUS_APPROVED, True)
    assert rec is not None
    assert rec["explanation_text"] == "# Algebra\n\nAlgebra is..."
    assert rec["video_url"] is None


def test_build_record_when_practice_type_then_quiz_questions_set():
    data = {
        "questions": [
            {
                "question_id": "q1",
                "question_text": "What is x?",
                "options": ["A: 1"],
                "correct_answer": "A",
                "explanation": "",
            }
        ]
    }
    rec = seed.build_record(MINIMAL_SUBTOPIC, seed.CONTENT_TYPE_PRACTICE, data, seed.REVIEW_STATUS_PENDING, True)
    assert rec is not None
    assert rec["quiz_questions_count"] == 1
    assert rec["reviewed_at"] is None  # pending → no reviewed_at


def test_build_record_when_data_is_none_then_returns_none():
    rec = seed.build_record(MINIMAL_SUBTOPIC, seed.CONTENT_TYPE_EXPLANATION, None, seed.REVIEW_STATUS_APPROVED, True)
    assert rec is None


def test_build_record_when_subtopic_id_missing_then_returns_none():
    rec = seed.build_record(
        MINIMAL_SUBTOPIC_NO_ID,
        seed.CONTENT_TYPE_EXPLANATION,
        {"explanation_text": "x"},
        seed.REVIEW_STATUS_APPROVED,
        True,
    )
    assert rec is None


# ---------------------------------------------------------------------------
# _batches
# ---------------------------------------------------------------------------


def test_batches_when_list_divides_evenly_then_correct_chunks():
    items = list(range(9))
    batches = list(seed._batches(items, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


def test_batches_when_list_does_not_divide_evenly_then_last_batch_is_remainder():
    items = list(range(11))
    batches = list(seed._batches(items, 4))
    assert len(batches) == 3
    assert batches[-1] == [8, 9, 10]


def test_batches_when_empty_list_then_no_batches():
    assert list(seed._batches([], 5)) == []


def test_batches_when_batch_size_larger_than_list_then_single_batch():
    items = [1, 2, 3]
    batches = list(seed._batches(items, 100))
    assert batches == [[1, 2, 3]]


# ---------------------------------------------------------------------------
# seed_subtopic — missing id
# ---------------------------------------------------------------------------


def test_seed_subtopic_when_subtopic_id_missing_then_error_recorded():
    result = seed.seed_subtopic(MINIMAL_SUBTOPIC_NO_ID, {}, dry_run=True)
    assert result.failed
    assert "missing subtopic id" in result.errors[0]


# ---------------------------------------------------------------------------
# seed_subtopic — dry-run (LLM called, no DB session created)
# ---------------------------------------------------------------------------


def test_seed_subtopic_when_dry_run_and_video_found_then_no_db_write(caplog):
    fake_video = {
        "video_url": "https://youtube.com/watch?v=xyz",
        "video_provider": "youtube",
        "video_duration_seconds": 300,
        "video_thumbnail_url": "https://img.youtube.com/vi/xyz/maxresdefault.jpg",
    }
    fake_explanation = {"explanation_text": "Great explanation here"}
    fake_quiz = {
        "questions": [
            {
                "question_id": "q1",
                "question_text": "?",
                "options": ["A: yes"],
                "correct_answer": "A",
                "explanation": "",
            }
        ]
    }

    call_results = [fake_video, fake_explanation, fake_quiz]

    with patch("seed_subtopic_content.litellm.completion") as mock_llm:
        mock_llm.side_effect = [{"choices": [{"message": {"content": json.dumps(r)}}]} for r in call_results]
        with patch("seed_subtopic_content.get_session") as mock_session:
            with (
                patch("seed_subtopic_content.SKIP_VIDEOS", False),
                patch("seed_subtopic_content.SKIP_EXPLANATIONS", False),
                patch("seed_subtopic_content.SKIP_QUIZZES", False),
            ):
                with caplog.at_level("INFO", logger="seed_subtopic_content"):
                    result = seed.seed_subtopic(MINIMAL_SUBTOPIC, {}, dry_run=True)

    mock_session.assert_not_called()
    assert mock_llm.call_count == 3
    assert result.inserted == 3
    assert not result.failed
    assert "[DRY RUN]" in caplog.text


def test_seed_subtopic_when_dry_run_and_llm_returns_nothing_then_skipped_not_inserted():
    with patch(
        "seed_subtopic_content.litellm.completion",
        return_value={"choices": [{"message": {"content": '{"video_url": null}'}}]},
    ):
        with patch("seed_subtopic_content.get_session"):
            with (
                patch("seed_subtopic_content.SKIP_VIDEOS", False),
                patch("seed_subtopic_content.SKIP_EXPLANATIONS", True),
                patch("seed_subtopic_content.SKIP_QUIZZES", True),
            ):
                result = seed.seed_subtopic(MINIMAL_SUBTOPIC, {}, dry_run=True)

    assert result.inserted == 0
    assert result.skipped >= 1


# ---------------------------------------------------------------------------
# seed_subtopic — pre-generated questions used when available
# ---------------------------------------------------------------------------


def test_seed_subtopic_when_pre_gen_questions_exist_then_llm_not_called_for_quiz():
    pre_gen = {
        MINIMAL_SUBTOPIC["id"]: {
            "questions": [
                {
                    "question_id": "q1",
                    "question_text": "?",
                    "options": ["A: yes"],
                    "correct_answer": "A",
                    "explanation": "",
                }
            ]
        }
    }
    llm_calls: list[str] = []

    def fake_completion(**kwargs: Any):
        prompt = kwargs["messages"][0]["content"]
        llm_calls.append(prompt)
        return {"choices": [{"message": {"content": '{"explanation_text": "ok"}'}}]}

    with patch("seed_subtopic_content.litellm.completion", side_effect=fake_completion):
        with (
            patch("seed_subtopic_content.SKIP_VIDEOS", True),
            patch("seed_subtopic_content.SKIP_EXPLANATIONS", False),
            patch("seed_subtopic_content.SKIP_QUIZZES", False),
        ):
            result = seed.seed_subtopic(MINIMAL_SUBTOPIC, pre_gen, dry_run=True)

    assert len(llm_calls) == 1
    assert result.inserted == 2  # explanation + quiz (from pre_gen)


# ---------------------------------------------------------------------------
# seed_subtopic — error handling
# ---------------------------------------------------------------------------


def test_seed_subtopic_when_llm_raises_then_skipped_not_failed():
    """LLM exceptions are absorbed by call_llm and counted as skipped, not errors.
    Errors only appear when something outside call_llm raises (e.g. build_record crash).
    """
    with patch("seed_subtopic_content.litellm.completion", side_effect=RuntimeError("boom")):
        with (
            patch("seed_subtopic_content.SKIP_VIDEOS", False),
            patch("seed_subtopic_content.SKIP_EXPLANATIONS", True),
            patch("seed_subtopic_content.SKIP_QUIZZES", True),
        ):
            result = seed.seed_subtopic(MINIMAL_SUBTOPIC, {}, dry_run=True)

    assert not result.failed
    assert result.skipped >= 1
    assert result.inserted == 0


def test_seed_subtopic_when_build_record_raises_then_error_captured_in_result():
    """Exceptions outside call_llm (e.g. in build_record) are captured in SeedResult.errors."""
    fake_video = {
        "video_url": "https://youtube.com/watch?v=xyz",
        "video_provider": "youtube",
        "video_duration_seconds": 300,
        "video_thumbnail_url": "https://img.youtube.com/vi/xyz/maxresdefault.jpg",
    }
    fake_response = {"choices": [{"message": {"content": json.dumps(fake_video)}}]}

    with patch("seed_subtopic_content.litellm.completion", return_value=fake_response):
        with patch("seed_subtopic_content.build_record", side_effect=ValueError("corrupt subtopic")):
            with (
                patch("seed_subtopic_content.SKIP_VIDEOS", False),
                patch("seed_subtopic_content.SKIP_EXPLANATIONS", True),
                patch("seed_subtopic_content.SKIP_QUIZZES", True),
            ):
                result = seed.seed_subtopic(MINIMAL_SUBTOPIC, {}, dry_run=True)

    assert result.failed
    assert any("corrupt subtopic" in e or "ValueError" in e for e in result.errors)
